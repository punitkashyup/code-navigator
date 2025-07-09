"""
RAG (Retrieval-Augmented Generation) pipeline implementation.

This module contains functions for:
1. Query transformation (creating variations of the original query)
2. Multi-query retrieval (using both BM25 and vector search)
3. Deduplication of retrieved chunks
4. Reranking of chunks based on relevance to the original query
5. Orchestration of the entire pipeline
"""

import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
import hashlib

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_aws import BedrockEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch
from opensearchpy import OpenSearch

import config
import prompts
import opensearch_ops

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize embedding model based on provider
def get_embedding_model():
    """Initialize and return the appropriate embedding model."""
    if config.EMBEDDING_PROVIDER == "bedrock":
        try:
            import boto3
            from botocore.config import Config
            
            # Configure boto3 session with proper settings
            boto_config = Config(
                max_pool_connections=config.BEDROCK_MAX_POOL_CONNECTIONS,
                retries={"max_attempts": 2},
                read_timeout=60,
                connect_timeout=10
            )
            
            # Create session with AWS credentials
            session = boto3.Session(
                aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
                aws_session_token=config.AWS_SESSION_TOKEN,
                region_name=config.AWS_REGION
            )
            
            embeddings = BedrockEmbeddings(
                model_id=config.BEDROCK_EMBEDDING_MODEL,
                client=session.client("bedrock-runtime", config=boto_config)
            )
            
            logger.info(f"Initialized Bedrock embeddings with model: {config.BEDROCK_EMBEDDING_MODEL}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock embeddings: {e}")
            logger.info("Falling back to OpenAI embeddings")
            
    # Fallback to OpenAI or if explicitly configured
    if not config.OPENAI_API_KEY:
        raise ValueError("No valid embedding provider configured. Please set either Bedrock AWS credentials or OpenAI API key.")
        
    embeddings = OpenAIEmbeddings(
        model=config.OPENAI_EMBEDDING_MODEL,
        openai_api_key=config.OPENAI_API_KEY
    )
    
    logger.info(f"Initialized OpenAI embeddings with model: {config.OPENAI_EMBEDDING_MODEL}")
    return embeddings

# Initialize embedding model
embedding_model = get_embedding_model()

# Initialize vector store wrapper
def get_vector_store() -> OpenSearchVectorSearch:
    """Initialize and return the OpenSearch vector store."""
    return OpenSearchVectorSearch(
        opensearch_url=config.OPENSEARCH_URL,
        index_name=config.OPENSEARCH_INDEX,
        embedding_function=embedding_model,
        text_field=config.OPENSEARCH_TEXT_FIELD,
        vector_field=config.OPENSEARCH_VECTOR_FIELD,
        http_auth=(config.OPENSEARCH_USER, config.OPENSEARCH_ADMIN_PW),
        verify_certs=False,
        use_ssl=False if "http://" in config.OPENSEARCH_URL else True,
    )

# Initialize OpenSearch client
def get_opensearch_client() -> OpenSearch:
    """Initialize and return the OpenSearch client."""
    return opensearch_ops.get_opensearch_client(
        opensearch_url=config.OPENSEARCH_URL,
        username=config.OPENSEARCH_USER,
        password=config.OPENSEARCH_ADMIN_PW,
        verify_certs=True
    )

async def transform_query(query: str, n: int = None) -> List[str]:
    """
    Transform original query into n semantically similar queries.
    
    Args:
        query: Original user query
        n: Number of queries to generate (default: from config)
        
    Returns:
        List of generated queries including the original
    """
    if n is None:
        n = config.QUERY_EXPANSION_N
    
    # Always include the original query
    queries = [query]
    
    try:
        # Initialize the LLM for query expansion
        llm = ChatOpenAI(
            model=config.QUERY_EXPANSION_MODEL,
            temperature=0.7,  # Some creativity is good for query variations
            openai_api_key=config.OPENAI_API_KEY
        )
        
        # Format the prompt
        prompt = prompts.QUERY_TRANSFORMATION_PROMPT.format(query=query, n=n)
        
        # Get LLM response
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        content = response.content
        
        # Parse the JSON response
        try:
            # Extract JSON if embedded in text
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
                
            generated_queries = json.loads(content)
            
            if isinstance(generated_queries, list):
                # Add all unique generated queries
                for q in generated_queries:
                    if isinstance(q, str) and q not in queries:
                        queries.append(q)
                        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse query expansion JSON: {e}")
            logger.error(f"Raw content: {content}")
            # Fall back to simple text parsing if JSON parsing fails
            for line in content.split('\n'):
                cleaned = line.strip().strip('"').strip("'")
                if cleaned and cleaned not in queries:
                    queries.append(cleaned)
    
    except Exception as e:
        logger.error(f"Query transformation failed: {e}")
    
    # Return the original query if transformation failed or no valid queries were generated
    if len(queries) == 1:
        logger.warning("Query transformation returned no results, using original query only")
    else:
        logger.info(f"Generated {len(queries) - 1} additional queries")
    
    return queries

async def retrieve_bm25_chunks(
    query: str, 
    client: OpenSearch,
    k: int = None
) -> List[Document]:
    """
    Retrieve chunks using BM25 search.
    
    Args:
        query: Search query
        client: OpenSearch client
        k: Number of results to retrieve (default: from config)
        
    Returns:
        List of Document objects with chunks and metadata
    """
    if k is None:
        k = config.BM25_K
        
    try:
        search_body = {
            "size": k,
            "query": {
                "match": {
                    config.OPENSEARCH_TEXT_FIELD: query
                }
            }
        }
        
        # Use asyncio.to_thread to run the sync OpenSearch client in a separate thread
        response = await asyncio.to_thread(
            client.search,
            index=config.OPENSEARCH_INDEX,
            body=search_body
        )
        
        hits = response.get("hits", {}).get("hits", [])
        
        # Convert hits to Document objects
        docs = []
        for hit in hits:
            source = hit["_source"]
            content = source.get(config.OPENSEARCH_TEXT_FIELD, "")
            metadata = source.get("metadata", {})
            # Add OpenSearch score and retrieval method to metadata
            metadata["_score"] = hit["_score"]
            metadata["_retrieval_method"] = "bm25"
            metadata["_id"] = hit["_id"]
            
            doc = Document(page_content=content, metadata=metadata)
            docs.append(doc)
            
        logger.info(f"BM25 search for '{query}' returned {len(docs)} chunks")
        return docs
        
    except Exception as e:
        logger.error(f"BM25 search failed for query '{query}': {e}")
        return []

async def retrieve_vector_chunks(
    query: str,
    vector_store: OpenSearchVectorSearch,
    k: int = None
) -> List[Document]:
    """
    Retrieve chunks using vector search.
    
    Args:
        query: Search query
        vector_store: OpenSearchVectorSearch instance
        k: Number of results to retrieve (default: from config)
        
    Returns:
        List of Document objects with chunks and metadata
    """
    if k is None:
        k = config.VECTOR_SEARCH_K
        
    try:
        retriever = vector_store.as_retriever(
            search_kwargs={
                "k": k,
                "search_type": "approximate_search",  # k-NN search
                "vector_field": config.OPENSEARCH_VECTOR_FIELD,
                "text_field": config.OPENSEARCH_TEXT_FIELD,
            }
        )
        
        # Use the retriever to get documents
        docs = await retriever.ainvoke(query)
        
        # Add retrieval method to metadata
        for doc in docs:
            doc.metadata["_retrieval_method"] = "vector"
            
        logger.info(f"Vector search for '{query}' returned {len(docs)} chunks")
        return docs
        
    except Exception as e:
        logger.error(f"Vector search failed for query '{query}': {e}")
        return []

async def retrieve_chunks(
    queries: List[str],
    bm25_k: int = None,
    vector_k: int = None
) -> List[Document]:
    """
    Retrieve code chunks using both BM25 and vector search for multiple queries.
    
    Args:
        queries: List of queries (original + transformed)
        bm25_k: Number of BM25 results per query (default: from config)
        vector_k: Number of vector search results per query (default: from config)
        
    Returns:
        Combined list of retrieved Documents
    """
    if not queries:
        logger.error("No queries provided for retrieval")
        return []
        
    # Initialize clients
    os_client = get_opensearch_client()
    vector_store = get_vector_store()
    
    all_chunks = []
    
    # Process each query
    for query in queries:
        # Perform BM25 search
        bm25_chunks = await retrieve_bm25_chunks(query, os_client, bm25_k)
        all_chunks.extend(bm25_chunks)
        
        # Perform vector search
        vector_chunks = await retrieve_vector_chunks(query, vector_store, vector_k)
        all_chunks.extend(vector_chunks)
    
    logger.info(f"Total chunks retrieved across {len(queries)} queries: {len(all_chunks)}")
    return all_chunks

def deduplicate_chunks(chunks: List[Document]) -> List[Document]:
    """
    Remove duplicate chunks based on chunk_id or content.
    
    Args:
        chunks: List of retrieved chunks
        
    Returns:
        Deduplicated list of chunks
    """
    if not chunks:
        return []
        
    unique_chunks = []
    seen_ids = set()
    seen_contents = set()
    
    for chunk in chunks:
        # Try to get a unique identifier
        chunk_id = None
        
        # First check if there's a chunk_id in metadata
        if chunk.metadata and "chunk_id" in chunk.metadata:
            chunk_id = chunk.metadata["chunk_id"]
        elif chunk.metadata and "_id" in chunk.metadata:
            # Use OpenSearch document ID as fallback
            chunk_id = chunk.metadata["_id"]
        
        # If we have a chunk_id and haven't seen it before
        if chunk_id and chunk_id not in seen_ids:
            seen_ids.add(chunk_id)
            unique_chunks.append(chunk)
        # Otherwise fall back to content-based deduplication
        elif not chunk_id:
            # Hash the content to create a unique identifier
            content_hash = hashlib.md5(chunk.page_content.encode()).hexdigest()
            
            if content_hash not in seen_contents:
                seen_contents.add(content_hash)
                unique_chunks.append(chunk)
    
    logger.info(f"Deduplicated {len(chunks)} chunks to {len(unique_chunks)} unique chunks")
    return unique_chunks

async def rerank_chunks(
    chunks: List[Document], 
    original_query: str, 
    top_m: int = None
) -> List[Document]:
    """
    Rerank chunks based on relevance to original query using LLM.
    
    Args:
        chunks: List of deduplicated chunks
        original_query: Original user query
        top_m: Number of top chunks to return (default: from config)
        
    Returns:
        Top M chunks sorted by relevance
    """
    if not chunks:
        return []
        
    if top_m is None:
        top_m = config.RERANK_TOP_M
        
    try:
        # Initialize the LLM for reranking
        llm = ChatOpenAI(
            model=config.RERANKER_MODEL,
            temperature=0.2,  # Low temperature for consistent evaluations
            openai_api_key=config.OPENAI_API_KEY
        )
        
        # Format chunks for the prompt
        formatted_chunks = ""
        for i, chunk in enumerate(chunks):
            # Extract metadata fields we want to show (exclude internal ones starting with _)
            metadata_str = "\n".join([
                f"{k}: {v}" for k, v in chunk.metadata.items() 
                if not k.startswith("_") and k != "vector"
            ])
            
            # Format the chunk using the template
            chunk_id = chunk.metadata.get("chunk_id", chunk.metadata.get("_id", str(i)))
            formatted_chunk = prompts.RERANKING_CHUNK_FORMAT.format(
                index=i,
                chunk_id=chunk_id,
                content=chunk.page_content,
                metadata=metadata_str
            )
            formatted_chunks += formatted_chunk
        
        # Format the prompt
        prompt = prompts.RERANKING_PROMPT.format(
            query=original_query,
            chunks=formatted_chunks
        )
        
        # Get LLM response
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        content = response.content
        
        # Parse the JSON response
        try:
            # Extract JSON if embedded in text
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
                
            rankings = json.loads(content)
            
            if not isinstance(rankings, list):
                logger.error(f"Expected list, got {type(rankings)}: {rankings}")
                # Fall back to original order if not a list
                return chunks[:top_m] if top_m < len(chunks) else chunks
                
            # Sort chunks by rank and limit to top_m
            ranked_chunks = []
            for rank_info in rankings:
                if isinstance(rank_info, dict) and "id" in rank_info:
                    chunk_id = int(rank_info["id"])
                    if 0 <= chunk_id < len(chunks):
                        # Add score to metadata
                        chunks[chunk_id].metadata["_rerank_score"] = rank_info.get("score", 0.0)
                        ranked_chunks.append(chunks[chunk_id])
            
            # If we have fewer ranked chunks than requested, add the remaining in original order
            if len(ranked_chunks) < top_m:
                remaining_ids = [i for i in range(len(chunks)) if i not in [int(r.get("id", -1)) for r in rankings]]
                for i in remaining_ids:
                    if len(ranked_chunks) >= top_m:
                        break
                    chunks[i].metadata["_rerank_score"] = 0.0  # Mark as unranked
                    ranked_chunks.append(chunks[i])
            
            # Limit to top_m
            top_chunks = ranked_chunks[:top_m]
            
            logger.info(f"Reranked {len(chunks)} chunks, returning top {len(top_chunks)}")
            return top_chunks
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse reranking JSON: {e}")
            logger.error(f"Raw content: {content}")
            # Fall back to original order
            return chunks[:top_m] if top_m < len(chunks) else chunks
            
    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        # Fall back to original order
        return chunks[:top_m] if top_m < len(chunks) else chunks

async def execute_rag_pipeline(
    query: str,
    query_expansion_n: int = None,
    bm25_k: int = None,
    vector_k: int = None,
    rerank_top_m: int = None
) -> Dict[str, Any]:
    """
    Execute full RAG pipeline from query to ranked results.
    
    Args:
        query: Original user query
        query_expansion_n: Number of additional queries to generate
        bm25_k: Number of BM25 results per query
        vector_k: Number of vector search results per query
        rerank_top_m: Number of top chunks to return after reranking
        
    Returns:
        Dictionary with status and results
    """
    try:
        # 1. Transform query to multiple queries
        logger.info(f"Starting RAG pipeline for query: '{query}'")
        queries = await transform_query(query, query_expansion_n)
        
        # 2. Retrieve chunks for all queries
        all_chunks = await retrieve_chunks(queries, bm25_k, vector_k)
        
        if not all_chunks:
            return {
                "status": "success",
                "message": "No relevant code chunks found",
                "data": {
                    "chunks": [],
                    "metadata": {
                        "original_query": query,
                        "expanded_queries": queries,
                        "total_chunks_retrieved": 0
                    }
                }
            }
        
        # 3. Deduplicate chunks
        unique_chunks = deduplicate_chunks(all_chunks)
        
        # 4. Rerank chunks based on original query
        ranked_chunks = await rerank_chunks(unique_chunks, query, rerank_top_m)
        
        # 5. Format results
        result_chunks = []
        for chunk in ranked_chunks:
            # Format metadata to exclude internal fields
            metadata = {k: v for k, v in chunk.metadata.items() if not k.startswith("_") and k != "vector"}
            
            # Add relevant internal fields with cleaned names
            if "_rerank_score" in chunk.metadata:
                metadata["relevance_score"] = chunk.metadata["_rerank_score"]
            if "_retrieval_method" in chunk.metadata:
                metadata["retrieval_method"] = chunk.metadata["_retrieval_method"]
                
            result_chunks.append({
                "content": chunk.page_content,
                "metadata": metadata
            })
        
        # Return the formatted results
        return {
            "status": "success",
            "data": {
                "chunks": result_chunks,
                "metadata": {
                    "original_query": query,
                    "expanded_queries": queries,
                    "total_chunks_retrieved": len(all_chunks),
                    "unique_chunks": len(unique_chunks),
                    "chunks_returned": len(result_chunks)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"RAG pipeline failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"RAG pipeline failed: {str(e)}",
            "data": None
        }