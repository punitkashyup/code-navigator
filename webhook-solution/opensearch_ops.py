import os
import logging
from typing import Dict, List, Any, Optional, Union
from opensearchpy import OpenSearch, exceptions as opensearch_exceptions
from dotenv import load_dotenv

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def get_opensearch_client(
    opensearch_url: str = None,
    username_env_var: str = "OPENSEARCH_USER",
    password_env_var: str = "OPENSEARCH_ADMIN_PW",
    username: Optional[str] = None,
    password: Optional[str] = None,
    verify_certs: bool = False
) -> OpenSearch:
    """
    Create and return an OpenSearch client.
    
    Args:
        opensearch_url: URL for OpenSearch cluster (defaults to env var)
        username_env_var: Environment variable name for username
        password_env_var: Environment variable name for password
        username: Direct username (falls back to env var if not provided)
        password: Direct password (falls back to env var if not provided)
        verify_certs: Whether to verify SSL certificates
    
    Returns:
        OpenSearch client instance
    """
    load_dotenv()
    
    # If URL is not provided, get from environment
    if not opensearch_url:
        opensearch_url = os.getenv('OPENSEARCH_URL', 'http://localhost:9200')
    
    # Get credentials from environment if not provided directly
    admin_user = username or os.getenv(username_env_var, "admin")
    admin_pw = password or os.getenv(password_env_var)
    
    if not admin_pw:
        logger.warning(f"OpenSearch password not found in environment variable '{password_env_var}'")
        # In Docker environment, we might be using non-secure OpenSearch
        if "DISABLE_SECURITY_PLUGIN" in os.environ and os.environ.get("DISABLE_SECURITY_PLUGIN").lower() == "true":
            logger.info("Security is disabled for OpenSearch, attempting connection without credentials")
            try:
                client = OpenSearch(
                    hosts=[opensearch_url],
                    verify_certs=False,
                    use_ssl="https" in opensearch_url,
                    timeout=60
                )
                if client.ping():
                    return client
            except Exception as e:
                logger.error(f"Failed to connect without credentials: {e}")
        
        raise ValueError(f"Missing OpenSearch password. Set {password_env_var} or provide directly.")
    
    try:
        client = OpenSearch(
            hosts=[opensearch_url],
            http_auth=(admin_user, admin_pw),
            verify_certs=False,
            use_ssl="https" in opensearch_url,
            timeout=60
        )
        
        if not client.ping():
            logger.error(f"OpenSearch ping failed at {opensearch_url}")
            raise ConnectionError("OpenSearch ping failed")
        
        logger.info(f"Successfully connected to OpenSearch at {opensearch_url}")
        return client
    except opensearch_exceptions.ConnectionError as e:
        logger.error(f"Failed to connect to OpenSearch at {opensearch_url}: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during OpenSearch connection: {e}")
        raise

def delete_chunks_by_metadata(
    metadata_filters: Dict[str, str],
    index_name: str = None,
    opensearch_client: Optional[OpenSearch] = None,
    **client_kwargs
) -> Dict[str, Any]:
    """
    Delete chunks from OpenSearch based on metadata filters.
    
    Args:
        metadata_filters: Dictionary of metadata fields and values to match
            (e.g. {"repo_name": "my_repo", "branch_name": "main", "file_path": "src/app.py"})
        index_name: Name of the OpenSearch index (defaults to env var)
        opensearch_client: Existing OpenSearch client (optional)
        **client_kwargs: Additional arguments to pass to get_opensearch_client if client not provided
    
    Returns:
        Dictionary with deletion results
    """
    if not metadata_filters:
        raise ValueError("metadata_filters cannot be empty")
    
    # Use provided index name or get from environment
    if not index_name:
        index_name = os.getenv('OPENSEARCH_INDEX', 'ingested_code_index')
    
    client = opensearch_client or get_opensearch_client(**client_kwargs)
    
    # Build the query to match documents with the specified metadata
    metadata_conditions = []
    for field, value in metadata_filters.items():
        # Use term query for exact matches on keyword subfields for specific fields
        if field in ["repo", "branch", "file_path", "repo_name", "branch_name", "chunk_id"]: # Add other known exact match fields as necessary
            metadata_conditions.append({"term": {f"metadata.{field}.keyword": value}})
        else:
            # Fallback to match for other fields (e.g., descriptive text fields)
            metadata_conditions.append({"match": {f"metadata.{field}": value}})
    
    query = {
        "query": {
            "bool": {
                "must": metadata_conditions
            }
        }
    }
    
    try:
        # Delete by query
        result = client.delete_by_query(
            index=index_name,
            body=query,
            refresh=True  # Refresh the index to make changes available immediately
        )
        
        logger.info(f"Deleted {result.get('deleted', 0)} chunks matching metadata filters: {metadata_filters}")
        return result
    
    except Exception as e:
        logger.error(f"Error deleting chunks with metadata {metadata_filters}: {e}")
        raise

def get_chunks_by_metadata(
    metadata_filters: Dict[str, str],
    index_name: str = None,
    text_field: str = None,
    size: int = 1000,
    opensearch_client: Optional[OpenSearch] = None,
    **client_kwargs
) -> List[Dict[str, Any]]:
    """
    Retrieve chunks from OpenSearch based on metadata filters.
    
    Args:
        metadata_filters: Dictionary of metadata fields and values to match
        index_name: Name of the OpenSearch index (defaults to env var)
        text_field: Name of field containing the document text (defaults to env var)
        size: Maximum number of results to return
        opensearch_client: Existing OpenSearch client (optional)
        **client_kwargs: Additional arguments to pass to get_opensearch_client
    
    Returns:
        List of documents matching the query
    """
    if not metadata_filters:
        raise ValueError("metadata_filters cannot be empty")
    
    # Use provided values or get from environment
    if not index_name:
        index_name = os.getenv('OPENSEARCH_INDEX', 'ingested_code_index')
    
    if not text_field:
        text_field = os.getenv('OPENSEARCH_TEXT_FIELD', 'text')
    
    client = opensearch_client or get_opensearch_client(**client_kwargs)
    
    # Build the query
    metadata_conditions = []
    for field, value in metadata_filters.items():
        metadata_conditions.append({"match": {f"metadata.{field}": value}})
    
    query = {
        "size": size,
        "query": {
            "bool": {
                "must": metadata_conditions
            }
        }
    }
    
    try:
        response = client.search(index=index_name, body=query)
        hits = response.get("hits", {}).get("hits", [])
        
        result = []
        for hit in hits:
            document = {
                "content": hit["_source"].get(text_field),
                "id": hit["_id"],
                "score": hit["_score"],
                "metadata": hit["_source"].get("metadata", {})
            }
            result.append(document)
        
        logger.info(f"Found {len(result)} chunks matching metadata filters: {metadata_filters}")
        return result
    
    except Exception as e:
        logger.error(f"Error retrieving chunks with metadata {metadata_filters}: {e}")
        raise

def count_chunks_by_metadata(
    metadata_filters: Dict[str, str],
    index_name: str = None,
    opensearch_client: Optional[OpenSearch] = None,
    **client_kwargs
) -> int:
    """
    Count chunks matching the given metadata filters.
    
    Args:
        metadata_filters: Dictionary of metadata fields and values to match
        index_name: Name of the OpenSearch index (defaults to env var)
        opensearch_client: Existing OpenSearch client (optional)
        **client_kwargs: Additional arguments to pass to get_opensearch_client
    
    Returns:
        Count of matching documents
    """
    if not metadata_filters:
        raise ValueError("metadata_filters cannot be empty")
    
    # Use provided index name or get from environment
    if not index_name:
        index_name = os.getenv('OPENSEARCH_INDEX', 'ingested_code_index')
    
    client = opensearch_client or get_opensearch_client(**client_kwargs)
    
    # Build the query
    metadata_conditions = []
    for field, value in metadata_filters.items():
        metadata_conditions.append({"match": {f"metadata.{field}": value}})
    
    query = {
        "query": {
            "bool": {
                "must": metadata_conditions
            }
        }
    }
    
    try:
        response = client.count(index=index_name, body=query)
        count = response.get("count", 0)
        logger.info(f"Found {count} chunks matching metadata filters: {metadata_filters}")
        return count
    
    except Exception as e:
        logger.error(f"Error counting chunks with metadata {metadata_filters}: {e}")
        raise

def get_metadata_by_filters(
    metadata_filters: Dict[str, str],
    index_name: str = None,
    size: int = 1000,
    opensearch_client: Optional[OpenSearch] = None,
    **client_kwargs
) -> List[Dict[str, Any]]:
    """
    Retrieve only the metadata of chunks matching the given filters.
    
    Args:
        metadata_filters: Dictionary of metadata fields and values to match
        index_name: Name of the OpenSearch index (defaults to env var)
        size: Maximum number of results to return
        opensearch_client: Existing OpenSearch client (optional)
        **client_kwargs: Additional arguments to pass to get_opensearch_client
    
    Returns:
        List of metadata objects from matching documents
    """
    if not metadata_filters:
        raise ValueError("metadata_filters cannot be empty")
    
    # Use provided index name or get from environment
    if not index_name:
        index_name = os.getenv('OPENSEARCH_INDEX', 'ingested_code_index')
    
    client = opensearch_client or get_opensearch_client(**client_kwargs)
    
    # Build the query
    metadata_conditions = []
    for field, value in metadata_filters.items():
        metadata_conditions.append({"match": {f"metadata.{field}": value}})
    
    query = {
        "size": size,
        "_source": ["metadata"],  # Only retrieve metadata fields
        "query": {
            "bool": {
                "must": metadata_conditions
            }
        }
    }
    
    try:
        response = client.search(index=index_name, body=query)
        hits = response.get("hits", {}).get("hits", [])
        
        result = []
        for hit in hits:
            metadata = hit["_source"].get("metadata", {})
            metadata["_id"] = hit["_id"]  # Include document ID
            result.append(metadata)
        
        logger.info(f"Found metadata for {len(result)} chunks matching filters: {metadata_filters}")
        return result
    
    except Exception as e:
        logger.error(f"Error retrieving metadata with filters {metadata_filters}: {e}")
        raise

# Utility for creating the OpenSearch index if it doesn't exist
def ensure_index_exists(
    index_name: str = None,
    text_field: str = None,
    vector_field: str = None,
    vector_dimension: int = 1024,
    opensearch_client: Optional[OpenSearch] = None,
    **client_kwargs
) -> bool:
    """
    Create the OpenSearch index if it doesn't exist.
    
    Args:
        index_name: Name of the index to create (defaults to env var)
        text_field: Name of the text field (defaults to env var)
        vector_field: Name of the vector field (defaults to env var)
        vector_dimension: Dimension of the embedding vector
        opensearch_client: Existing OpenSearch client (optional)
        **client_kwargs: Additional arguments to pass to get_opensearch_client
        
    Returns:
        True if index was created or already exists
    """
    # Use provided values or get from environment
    if not index_name:
        index_name = os.getenv('OPENSEARCH_INDEX', 'ingested_code_index')
    
    if not text_field:
        text_field = os.getenv('OPENSEARCH_TEXT_FIELD', 'text')
    
    if not vector_field:
        vector_field = os.getenv('OPENSEARCH_VECTOR_FIELD', 'vector_field')
    
    client = opensearch_client or get_opensearch_client(**client_kwargs)
    
    # Check if index exists
    if client.indices.exists(index=index_name):
        logger.info(f"Index '{index_name}' already exists.")
        return True
    
    # Create the index with KNN support
    mapping = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                text_field: {"type": "text"},
                vector_field: {"type": "knn_vector", "dimension": vector_dimension}
            }
        }
    }
    
    try:
        client.indices.create(index=index_name, body=mapping)
        logger.info(f"Created index '{index_name}' with KNN support.")
        return True
    except opensearch_exceptions.RequestError as e:
        # Check for race condition (index already exists)
        if "resource_already_exists_exception" in str(e).lower():
            logger.warning(f"Index '{index_name}' already exists (race condition).")
            return True
        
        logger.error(f"Error creating index '{index_name}': {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating index '{index_name}': {e}")
        return False

# Example usage (commented out - for reference only)
# if __name__ == "__main__":
#     # Initialize OpenSearch client
#     client = get_opensearch_client()
    
#     # Create the index if it doesn't exist
#     ensure_index_exists(opensearch_client=client)
    
#     # Delete all chunks from a specific repository and branch
#     delete_chunks_by_metadata({
#         "repo": "test-code-repo",
#         "branch": "main"
#     }, opensearch_client=client)
    
#     # Get metadata only for chunks in a specific repository
#     metadata_list = get_metadata_by_filters({
#         "repo": "test-code-repo",
#         "branch": "main"
#     }, opensearch_client=client)
#     print(metadata_list)
    
    # Example: Delete chunks for a specific file
    # delete_chunks_by_metadata({
    #     "repo_name": "example/repo",
    #     "branch_name": "main",
    #     "file_path": "src/main.py"
    # }, opensearch_client=client)
    
    # Example: Count chunks in a repository
    # count = count_chunks_by_metadata({
    #     "repo_name": "example/repo"
    # }, opensearch_client=client)
    # print(f"Found {count} chunks in repository") 