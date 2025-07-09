"""
RAG MCP Server - Provides code search and metadata operations through MCP tools.

This server exposes four primary tools:
1. RAG Tool - Advanced code search using query transformation and reranking
2. Get Chunks by Metadata - Retrieve code chunks matching specific metadata criteria
3. Count Chunks by Metadata - Count code chunks matching specific metadata criteria
4. Get Metadata by Filters - Retrieve only metadata for chunks matching specific criteria

Features:
- Supports both AWS Bedrock (recommended) and OpenAI embeddings
- Hybrid search combining BM25 and vector search
- Query expansion and reranking for better results
- Comprehensive metadata filtering capabilities
"""

import os
import asyncio
import logging
import uvicorn
import argparse
from typing import Dict, List, Any
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
import config
import rag_pipeline
import opensearch_ops

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name="code-search-mcp",
    stateless_http=True,
    streamable_http_path="/mcp",
)

@mcp.tool()
async def rag_tool(query: str) -> Dict[str, Any]:
    """
    Find the most relevant code snippets that match your query.
    
    This tool searches across code repositories to find snippets that best 
    answer your question or match your search criteria.
    
    Args:
        query: Your search query about code or concepts
        
    Returns:
        JSON object with status and retrieved code chunks (with content and metadata)
    """
    try:
        result = await rag_pipeline.execute_rag_pipeline(query)
        return result
    except Exception as e:
        logger.error(f"RAG tool error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def get_chunks_by_metadata_tool(
    metadata_filters: Dict[str, str]
) -> Dict[str, Any]:
    """
    Retrieve code chunks matching specific metadata criteria.
    
    The metadata_filters can include any combination of these fields 
    (partial matching is supported - you don't need to provide all fields, but minimum one is required):
    - repo: Repository name (e.g., 'organization/repo-name')
    - branch: Branch name (e.g., 'main', 'develop')
    - file_path: File path within repository (e.g., 'src/app.py')
    - chunk_id: Unique identifier for the code chunk (it is index of the chunk in original file, starts from 1)
    - language: Programming language (e.g., 'python', 'javascript')
    - start_line: Starting line number in original file
    - end_line: Ending line number in original file
    
    Args:
        metadata_filters: Dictionary of metadata fields and values to match
        
    Returns:
        JSON object with status and matching code chunks
    """
    try:
        # Validate input
        if not metadata_filters:
            return {
                "status": "error", 
                "message": "metadata_filters cannot be empty"
            }
        
        # Get chunks using opensearch_ops - run in thread to avoid blocking
        chunks = await asyncio.to_thread(
            opensearch_ops.get_chunks_by_metadata,
            metadata_filters=metadata_filters,
            size=config.MAX_CHUNKS,
            index_name=config.OPENSEARCH_INDEX,
            opensearch_url=config.OPENSEARCH_URL,
            username=config.OPENSEARCH_USER,
            password=config.OPENSEARCH_ADMIN_PW
        )
        
        # Format the response
        return {
            "status": "success",
            "data": {
                "chunks": chunks,
                "metadata": {
                    "total_chunks": len(chunks),
                    "filters_applied": metadata_filters
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Get chunks by metadata error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def count_chunks_by_metadata_tool(
    metadata_filters: Dict[str, str]
) -> Dict[str, Any]:
    """
    Count code chunks matching specific metadata criteria.
    
    The metadata_filters can include any combination of these fields 
    (partial matching is supported - you don't need to provide all fields, but minimum one is required):
    - repo: Repository name (e.g., 'organization/repo-name')
    - branch: Branch name (e.g., 'main', 'develop')
    - file_path: File path within repository (e.g., 'src/app.py')
    - chunk_id: Unique identifier for the code chunk (it is index of the chunk in original file, starts from 1)
    - language: Programming language (e.g., 'python', 'javascript')
    - start_line: Starting line number in original file
    - end_line: Ending line number in original file
    
    Args:
        metadata_filters: Dictionary of metadata fields and values to match
        
    Returns:
        JSON object with status and count of matching chunks
    """
    try:
        # Validate input
        if not metadata_filters:
            return {
                "status": "error", 
                "message": "metadata_filters cannot be empty"
            }
        
        # Count chunks using opensearch_ops - run in thread to avoid blocking
        count = await asyncio.to_thread(
            opensearch_ops.count_chunks_by_metadata,
            metadata_filters=metadata_filters,
            index_name=config.OPENSEARCH_INDEX,
            opensearch_url=config.OPENSEARCH_URL,
            username=config.OPENSEARCH_USER,
            password=config.OPENSEARCH_ADMIN_PW
        )
        
        # Format the response
        return {
            "status": "success",
            "data": {
                "count": count,
                "filters_applied": metadata_filters
            }
        }
        
    except Exception as e:
        logger.error(f"Count chunks by metadata error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def get_metadata_by_filters_tool(
    metadata_filters: Dict[str, str]
) -> Dict[str, Any]:
    """
    Retrieve only metadata for chunks matching specific criteria.
    
    The metadata_filters can include any combination of these fields 
    (partial matching is supported - you don't need to provide all fields, but minimum one is required):
    - repo: Repository name (e.g., 'organization/repo-name')
    - branch: Branch name (e.g., 'main', 'develop')
    - file_path: File path within repository (e.g., 'src/app.py')
    - chunk_id: Unique identifier for the code chunk (it is index of the chunk in original file, starts from 1)
    - language: Programming language (e.g., 'python', 'javascript')
    - start_line: Starting line number in original file
    - end_line: Ending line number in original file
    
    Args:
        metadata_filters: Dictionary of metadata fields and values to match
        
    Returns:
        JSON object with status and matching metadata objects
    """
    try:
        # Validate input
        if not metadata_filters:
            return {
                "status": "error", 
                "message": "metadata_filters cannot be empty"
            }
        
        # Get metadata using opensearch_ops - run in thread to avoid blocking
        metadata_list = await asyncio.to_thread(
            opensearch_ops.get_metadata_by_filters,
            metadata_filters=metadata_filters,
            size=config.MAX_CHUNKS,
            index_name=config.OPENSEARCH_INDEX,
            opensearch_url=config.OPENSEARCH_URL,
            username=config.OPENSEARCH_USER,
            password=config.OPENSEARCH_ADMIN_PW
        )
        
        # Format the response
        return {
            "status": "success",
            "data": {
                "metadata_items": metadata_list,
                "total_items": len(metadata_list),
                "filters_applied": metadata_filters
            }
        }
        
    except Exception as e:
        logger.error(f"Get metadata by filters error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

def run_server(host=None, port=None):
    """Run the MCP server with the given host and port."""
    # Use provided values or config defaults
    host = host or config.HOST
    port = port or config.PORT
    
    logger.info(f"Starting RAG MCP server at {host}:{port}")
    logger.info(f"Using OpenSearch at {config.OPENSEARCH_URL}")
    
    # Run using Uvicorn
    uvicorn.run(
        mcp.streamable_http_app(),
        host=host,
        port=port,
        log_level=config.LOG_LEVEL_UVICORN,
    )

if __name__ == "__main__":
    # Log configuration
    logger.info("Starting MCP server with configuration:")
    logger.info(f"OpenSearch URL: {config.OPENSEARCH_URL}")
    logger.info(f"OpenSearch Index: {config.OPENSEARCH_INDEX}")
    logger.info(f"Max Chunks: {config.MAX_CHUNKS}")
    
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description='Run RAG MCP server')
    parser.add_argument('--host', default=None, help='Host to bind to')
    parser.add_argument('--port', type=int, default=None, help='Port to listen on')
    args = parser.parse_args()
    
    # Run the server
    run_server(args.host, args.port) 