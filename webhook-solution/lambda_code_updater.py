# Standard library imports
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from typing import List, Any, Optional
from urllib.parse import urlparse, urlunparse

# Third-party library imports
import urllib3
import warnings
from dotenv import load_dotenv
from langchain_aws import BedrockEmbeddings
# from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch
from langchain_core.documents import Document
from pydantic import BaseModel, field_validator
from opensearchpy import OpenSearch, exceptions as opensearch_exceptions

# Local application imports
# Import these conditionally in the code to avoid circular imports
# from opensearch_ops import delete_chunks_by_metadata, get_opensearch_client
# from code_splitter.processor import split_code_async

# Suppress insecure request warnings for OpenSearch
warnings.filterwarnings("ignore", category=UserWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger()

# --- Models for event data ---
class Repository(BaseModel):
    url: str
    name: str
    branch: str
    
    @field_validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Repository URL must start with http:// or https://')
        return v

class LambdaEvent(BaseModel):
    repository: Repository
    added_files: List[str] = []
    modified_files: List[str] = []
    deleted_files: List[str] = []
    commit_id: str
    
    @field_validator('commit_id')
    def validate_commit_id(cls, v):
        if not v or len(v) < 4:
            raise ValueError('Commit ID is required and must be valid')
        return v

# --- Main Lambda Handler ---
async def process_code_changes(event, context):
    """
    Handler function for incremental code ingestion.
    
    This function receives information about GitHub repository changes
    and updates the OpenSearch index accordingly.
    
    Args:
        event: The event containing repository and file change information
        context: The Lambda context
        
    Returns:
        A dictionary with status code and response body
    """
    logger.info(f"Received event: {json.dumps(event, indent=2)}")
    
    try:
        # Parse and validate the input event
        try:
            lambda_event = LambdaEvent(**event)
            logger.info(f"Processing changes for repository {lambda_event.repository.name}")
        except Exception as e:
            logger.error(f"Invalid event format: {str(e)}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid event format: {str(e)}"})
            }
        
        # Extract repository info
        repo_info = lambda_event.repository
        repo_url = repo_info.url
        repo_name = repo_info.name
        branch = repo_info.branch
        
        # Process deleted files first (no need to clone for deletions)
        if lambda_event.deleted_files:
            logger.info(f"Processing {len(lambda_event.deleted_files)} deleted files")
            await process_deleted_files(repo_name, branch, lambda_event.deleted_files)
        
        # Process added and modified files if any
        files_to_process = lambda_event.added_files + lambda_event.modified_files
        if files_to_process:
            logger.info(f"Processing {len(files_to_process)} added/modified files")
            await process_updated_files(repo_url, repo_name, branch, files_to_process)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Successfully processed changes",
                "repository": repo_name,
                "commit_id": lambda_event.commit_id,
                "added": len(lambda_event.added_files),
                "modified": len(lambda_event.modified_files),
                "deleted": len(lambda_event.deleted_files)
            })
        }
    
    except Exception as e:
        logger.error(f"Error processing code changes: {str(e)}")
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }

# --- Process Deleted Files ---
async def process_deleted_files(repo_name: str, branch: str, deleted_files: List[str]):
    """
    Delete chunks for files that have been removed from the repository.
    
    Args:
        repo_name: Name of the repository
        branch: Name of the branch
        deleted_files: List of file paths that were deleted
    
    Raises:
        Exception: If there is an error initializing the OpenSearch client
    """
    # Import here to avoid circular imports and allow for module mocking in tests
    from opensearch_ops import delete_chunks_by_metadata, get_opensearch_client
    
    # Get OpenSearch client
    try:
        client = get_opensearch_client()
        logger.info(f"Successfully connected to OpenSearch for processing deleted files")
    except Exception as e:
        logger.error(f"Failed to initialize OpenSearch client: {str(e)}")
        raise
    
    # Process each deleted file
    failure_count = 0
    for file_path_in_list in deleted_files:
        try:
            # Construct the full file_path as stored in metadata
            full_file_path = f"{repo_name}/{file_path_in_list}"
            
            # Delete chunks for this file based on metadata
            # Using "repo" and "branch" as per discovered metadata structure
            metadata_filters = {
                "repo": repo_name,
                "branch": branch,
                "file_path": full_file_path
            }
            
            result = delete_chunks_by_metadata(
                metadata_filters=metadata_filters,
                opensearch_client=client
            )
            
            logger.info(f"Deleted {result.get('deleted', 0)} chunks for {full_file_path}")
        
        except Exception as e:
            failure_count += 1
            logger.error(f"Error deleting chunks for {full_file_path}: {str(e)}")
            # Continue with other files even if one fails
    
    if failure_count > 0:
        logger.warning(f"Failed to process {failure_count} out of {len(deleted_files)} deleted files")

# --- Process Added/Modified Files ---
async def process_updated_files(repo_url: str, repo_name: str, branch: str, files_to_process: List[str]):
    """
    Process added or modified files by cloning the repo and processing each file.
    
    Args:
        repo_url: URL of the repository
        repo_name: Name of the repository
        branch: Branch to clone
        files_to_process: List of file paths to process
        
    Raises:
        Exception: If there is an error cloning the repository or initializing clients
    """
    
    # Set up temporary directory for cloning
    temp_dir = os.path.join('/tmp/repos', repo_name.replace('/', '_'))
    os.makedirs(os.path.dirname(temp_dir), exist_ok=True)

    try:
        logger.info(f"Using directory for cloning: {temp_dir}")
        
        # Clone repository with minimal depth
        clone_success = clone_repo(
            repo_url=repo_url,
            target_dir=temp_dir,
            token=os.getenv("GITHUB_TOKEN"),  # Optional token for private repos
            branch=branch,
            shallow=True,
            timeout=300  # 5 minutes timeout
        )
        
        if not clone_success:
            error_msg = f"Failed to clone repository {repo_url}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        logger.info(f"Successfully cloned repository {repo_url}")
        
        # Initialize embeddings and OpenSearch
        from opensearch_ops import delete_chunks_by_metadata, get_opensearch_client
        
        # Load environment variables (if any)
        load_dotenv()
        
        # Get OpenSearch configuration from environment
        opensearch_url = os.getenv("OPENSEARCH_URL", "https://opensearch:9200")
        index_name = os.getenv("OPENSEARCH_INDEX", "ingested_code_index")
        admin_user = os.getenv("OPENSEARCH_USER", "admin")
        admin_pw = os.getenv("OPENSEARCH_ADMIN_PW")
        text_field = os.getenv("OPENSEARCH_TEXT_FIELD", "text")
        vector_field = os.getenv("OPENSEARCH_VECTOR_FIELD", "vector_field")
        
        if not admin_pw:
            error_msg = "Missing OPENSEARCH_ADMIN_PW environment variable"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Initialize OpenSearch client
        os_client = get_opensearch_client(
            opensearch_url=opensearch_url,
            username=admin_user,
            password=admin_pw
        )
        
        # Check for disk space issues and try to resolve
        if not check_and_handle_disk_space_issue(os_client, index_name):
            logger.warning("OpenSearch disk space issues detected and could not be resolved. " +
                          "Some write operations may fail. Delete operations should still work.")
        
        # Initialize embeddings
        try:
            embeddings = BedrockEmbeddings(
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                model_id=os.getenv("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v2:0"),
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
            
            )
            # embeddings = OpenAIEmbeddings(
            #     model="text-embedding-3-large"
            # )
            logger.info("Initialized Bedrock embeddings")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock embeddings: {str(e)}")
            raise
        
        # Initialize vector store
        vector_store = OpenSearchVectorSearch(
            opensearch_url=opensearch_url,
            index_name=index_name,
            embedding_function=embeddings,
            text_field=text_field,
            vector_field=vector_field,
            http_auth=(admin_user, admin_pw),
            verify_certs=False,
            use_ssl="https" in opensearch_url
        )
        
        logger.info(f"Initialized OpenSearch vector store with index {index_name}")
        
        # Set concurrent processing limit based on environment or default
        concurrent_limit = int(os.getenv("CONCURRENT_FILE_LIMIT", "5"))
        semaphore = asyncio.Semaphore(concurrent_limit)
        logger.info(f"Processing files with concurrency limit of {concurrent_limit}")
        
        # Process each file concurrently
        tasks = []
        for file_path in files_to_process:
            task = process_single_file(
                file_path=file_path,
                temp_dir=temp_dir,
                repo_url=repo_url,
                repo_name=repo_name,
                branch=branch,
                vector_store=vector_store,
                os_client=os_client,
                semaphore=semaphore
            )
            tasks.append(task)
        
        # Wait for all file processing tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful and failed files
        failures = sum(1 for r in results if isinstance(r, Exception))
        success = len(results) - failures
        
        logger.info(f"Completed processing {success} files successfully with {failures} failures")
    
    finally:
        # Cleanup is optional in Docker since we reuse the directory
        # If cleanup is desired, uncomment the following
        # if os.getenv("CLEANUP_AFTER_RUN", "False").lower() == "true":
        #     if os.path.exists(temp_dir):
        #         try:
        #             shutil.rmtree(temp_dir)
        #             logger.info(f"Cleaned up clone directory: {temp_dir}")
        #         except OSError as e:
        #             logger.error(f"Error removing directory {temp_dir}: {e}")
        pass

async def process_single_file(
    file_path: str,
    temp_dir: str,
    repo_url: str,
    repo_name: str,
    branch: str,
    vector_store: Any,
    os_client: Any,
    semaphore: asyncio.Semaphore
) -> Optional[Exception]:
    """
    Process a single file with semaphore for concurrency control.
    
    Args:
        file_path: Path to the file relative to the repo root
        temp_dir: Directory where the repo was cloned
        repo_url: URL of the repository
        repo_name: Name of the repository
        branch: Name of the branch
        vector_store: The initialized vector store
        os_client: The initialized OpenSearch client
        semaphore: Semaphore for concurrency control
        
    Returns:
        None if successful or Exception if failed
    """
    async with semaphore:
        full_path = os.path.join(temp_dir, file_path)
        
        if not os.path.exists(full_path):
            logger.warning(f"File not found in cloned repo: {file_path}")
            return Exception(f"File not found: {file_path}")
        
        # First delete existing chunks for this file (if it's a modification)
        from opensearch_ops import delete_chunks_by_metadata, get_chunks_by_metadata
        
        # Check if any chunks exist first to debug the field names
        try:
            # First check what chunks exist with a broader query
            broader_metadata = {
                "repo": repo_name,
                "branch": branch,
            }
            existing_chunks = get_chunks_by_metadata(
                metadata_filters=broader_metadata,
                opensearch_client=os_client,
                size=5  # Just get a few for debugging
            )
            
            # Log the metadata of found chunks
            if existing_chunks:
                logger.info(f"Found {len(existing_chunks)} existing chunks for repo {repo_name}")
                # Log the first chunk's metadata to see field names
                logger.info(f"Sample chunk metadata: {existing_chunks[0]['metadata']}")
                
                # Extract the correct file path from the sample
                sample_file_path = None
                for field in existing_chunks[0]['metadata']:
                    if field.lower() == 'file_path':
                        sample_file_path = existing_chunks[0]['metadata'][field]
                        logger.info(f"Found file path field with value: {sample_file_path}")
                        break
        except Exception as e:
            logger.warning(f"Error checking existing chunks: {str(e)}")
        
        # Now try to delete with the corrected field names
        # We specify just the repo and file_path which should be sufficient to identify the file
        metadata_filters = {
            "repo": repo_name,
            "file_path": f"{repo_name}/{file_path}"
        }
        
        try:
            # Always delete existing chunks first (for both new and modified files)
            # This ensures we don't have duplicates
            delete_result = delete_chunks_by_metadata(
                metadata_filters=metadata_filters,
                opensearch_client=os_client
            )
            logger.info(f"Deleted {delete_result.get('deleted', 0)} existing chunks for {file_path}")
            
            # If we didn't delete anything, try with just the file name
            if delete_result.get('deleted', 0) == 0:
                # Try with just the file name part
                file_name = os.path.basename(file_path)
                metadata_filters_by_name = {
                    "repo": repo_name,
                    "branch": branch
                }
                
                chunks_to_check = get_chunks_by_metadata(
                    metadata_filters=metadata_filters_by_name,
                    opensearch_client=os_client,
                    size=100  # Get more to check
                )
                
                # Find chunks that match the file name
                matching_chunks = []
                for chunk in chunks_to_check:
                    chunk_file_path = chunk['metadata'].get('file_path', '')
                    if file_name in chunk_file_path:
                        matching_chunks.append(chunk)
                        
                if matching_chunks:
                    # Use the exact file path from the first matching chunk
                    exact_file_path = matching_chunks[0]['metadata'].get('file_path', '')
                    logger.info(f"Found matching chunk with file path: {exact_file_path}")
                    
                    # Delete using this exact path
                    exact_path_filters = {
                        "repo": repo_name,
                        "file_path": exact_file_path
                    }
                    
                    delete_result_exact = delete_chunks_by_metadata(
                        metadata_filters=exact_path_filters,
                        opensearch_client=os_client
                    )
                    logger.info(f"Deleted {delete_result_exact.get('deleted', 0)} existing chunks using exact file path match")
        except Exception as e:
            logger.warning(f"Error deleting existing chunks for {file_path}: {str(e)}")
        
        # Process the file and create new chunks
        try:
            # Add the src directory to Python path if needed
            ensure_src_in_path()
            
            # Process the file to get documents
            documents = await process_file_and_get_documents(
                file_path=full_path,
                repo_name=repo_name,
                branch_name=branch,
                repo_url=repo_url
            )
            
            if documents:
                # Log the metadata of the first document to confirm structure
                logger.info(f"Sample metadata of new document: {documents[0].metadata}")
                
                # Add documents to vector store with configurable bulk size
                bulk_size = int(os.getenv("OPENSEARCH_BULK_SIZE", "500"))
                await vector_store.aadd_documents(
                    documents,
                    text_field=os.getenv("OPENSEARCH_TEXT_FIELD", "text"),
                    vector_field=os.getenv("OPENSEARCH_VECTOR_FIELD", "vector_field"),
                    bulk_size=bulk_size,
                    refresh=True
                )
                logger.info(f"Added {len(documents)} chunks for {file_path} with bulk size {bulk_size}")
                return None
            else:
                logger.warning(f"No chunks generated for {file_path}")
                return None
        
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            logger.error(traceback.format_exc())
            return e

def ensure_src_in_path():
    """Ensure that the src directory is in the Python path."""
    # Add the src directory to Python path if needed
    src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    return src_dir

# --- Repository Operations ---
def clone_repo(
    repo_url: str, 
    target_dir: str, 
    token: Optional[str] = None, 
    branch: Optional[str] = None, 
    shallow: bool = True, 
    timeout: int = 600
) -> bool:
    """
    Clone a git repository to the specified directory.
    
    Args:
        repo_url: URL of the repository to clone
        target_dir: Directory to clone into
        token: GitHub token for private repositories
        branch: Branch to checkout
        shallow: Whether to do a shallow clone
        timeout: Timeout in seconds
        
    Returns:
        True if cloning was successful, False otherwise
    """
    if os.path.exists(target_dir):
        logger.info(f"Removing existing directory: {target_dir}")
        try:
            shutil.rmtree(target_dir)
        except OSError as e:
            logger.error(f"Error removing directory {target_dir}: {e}")
            return False
    
    os.makedirs(os.path.dirname(target_dir), exist_ok=True)

    # Add token to URL if provided (for private repos)
    clone_url = repo_url
    if token and repo_url.startswith("https://"):
        parsed_url = urlparse(repo_url)
        clone_url = urlunparse(parsed_url._replace(netloc=f"{token}@{parsed_url.netloc}"))
        logger.info(f"Cloning with token from: {repo_url.split('://')[0]}://{repo_url.split('://')[-1].split('@')[-1]}")
    else:
        logger.info(f"Cloning: {repo_url}")

    # Build git clone command
    cmd = ["git", "clone"]
    if shallow:
        cmd.extend(["--depth", "1"])
    if branch:
        cmd.extend(["-b", branch])
    cmd.extend([clone_url, target_dir])

    try:
        # Execute git clone command
        process = subprocess.run(
            cmd, 
            check=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        
        logger.info(f"Successfully cloned {repo_url}" + 
                   (f" (branch: {branch})" if branch else "") + 
                   (f" (shallow)" if shallow else "") + 
                   f" to {target_dir}")
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"Failed to clone {repo_url} within timeout of {timeout} seconds.")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone {repo_url}. Error: {e.stderr}")
        return False

# --- File Processing for Chunking ---
async def process_file_and_get_documents(
    file_path: str,
    repo_name: str,
    branch_name: str,
    repo_url: str
) -> List[Any]:
    """
    Process a file and generate document chunks.
    
    Args:
        file_path: Path to the file to process
        repo_name: Name of the repository
        branch_name: Name of the branch
        repo_url: URL of the repository
        
    Returns:
        List of Document objects ready for ingestion into OpenSearch
    """
    # Dynamically import to avoid circular dependencies
    try:
        ensure_src_in_path()
            
        from src.code_splitter.processor import split_code_async
    except ImportError as e:
        logger.error(f"Import error: {str(e)}")
        raise
    
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"Could not read file {file_path}: {e}")
        return []

    if not content.strip():
        logger.info(f"Skipping empty file: {file_path}")
        return []

    # Calculate relative path more robustly
    repo_path_components = get_relative_file_path(file_path, repo_name)
    logger.debug(f"Processing file: {repo_path_components} for repo {repo_name}")
    
    # Process the file to generate chunks
    try:
        chunker_max_chars = int(os.getenv('CHUNKER_MAX_CHARS', '1500'))
        chunker_coalesce = int(os.getenv('CHUNKER_COALESCE', '200'))
        generate_descriptions = os.getenv('GENERATE_AI_DESCRIPTIONS', 'True').lower() == 'true'
        
        full_formatted_text, structured_data_list, error_message = await split_code_async(
            code_content=content,
            language_name=None,  # Let processor infer
            file_path=repo_path_components,
            repo_name=repo_name,
            branch_name=branch_name,
            max_chars=chunker_max_chars,
            coalesce=chunker_coalesce,
            generate_descriptions=generate_descriptions
        )
    except Exception as e:
        logger.error(f"Error in split_code_async for {file_path}: {str(e)}")
        logger.error(traceback.format_exc())
        return []

    if error_message:
        logger.error(f"Error chunking {file_path}: {error_message}")
        return []

    documents = []
    if structured_data_list:
        for chunk_data in structured_data_list:
            # Combine original content with metadata using a separator token
            metadata = chunk_data['metadata']
            metadata_str = "\n".join([f"{key}: {value}" for key, value in metadata.items()])
            combined_content = f"<CHUNK_START>\n```\n{chunk_data['original_content']}\n```\n<CHUNK_END>\n\n[METADATA_START]\n{metadata_str}\n[METADATA_END]"
            
            doc = Document(
                page_content=combined_content,
                metadata=metadata  # Keep metadata for filtering/retrieval
            )
            documents.append(doc)
    
    logger.info(f"Processed {file_path}, created {len(documents)} documents.")
    return documents

def get_relative_file_path(file_path: str, repo_name: str) -> str:
    """
    Get the relative path of a file within the repository.
    
    Args:
        file_path: Full path to the file
        repo_name: Name of the repository
        
    Returns:
        The relative path within the repository
    """
    # Try to extract the relative path more robustly
    try:
        # Method 1: Using the repo name in path
        if repo_name.replace('/', '_') in file_path:
            parts = file_path.split(repo_name.replace('/', '_'))
            if len(parts) > 1 and parts[1].startswith('/'):
                return parts[1].lstrip('/')
        
        # Method 2: Using the base directory name
        repo_dir = os.path.basename(os.path.dirname(file_path))
        if repo_dir and repo_dir in file_path:
            parts = file_path.split(repo_dir + '/')
            if len(parts) > 1:
                return parts[1]
    except Exception as e:
        logger.warning(f"Error extracting relative path: {str(e)}")
    
    # Fallback: Just use the basename
    return os.path.basename(file_path)

# Add this function before process_single_file
def check_and_handle_disk_space_issue(client: OpenSearch, index_name: str = None) -> bool:
    """
    Check if OpenSearch index has read-only block due to disk space issues and attempt to resolve.
    
    Args:
        client: OpenSearch client
        index_name: Name of the index to check (defaults to env var)
        
    Returns:
        True if the index is now writable, False otherwise
    """
    if not index_name:
        index_name = os.getenv('OPENSEARCH_INDEX', 'ingested_code_index')
    
    try:
        # Check for index blocks
        index_settings = client.indices.get_settings(index=index_name)
        blocks = index_settings.get(index_name, {}).get('settings', {}).get('index', {}).get('blocks', {})
        
        if 'read_only_allow_delete' in blocks and blocks.get('read_only_allow_delete') == 'true':
            logger.warning(f"Index {index_name} is in read-only mode due to disk space issues")
            
            # 1. Try to free up space by deleting old data (uncommenting as needed)
            # delete_result = delete_chunks_by_metadata({"some_field": "old_value"}, opensearch_client=client)
            # logger.info(f"Deleted {delete_result.get('deleted', 0)} old chunks to free up space")
            
            # 2. Try to clear the block
            try:
                client.indices.put_settings(
                    index=index_name,
                    body={"index.blocks.read_only_allow_delete": None}
                )
                logger.info(f"Attempted to clear read-only block on index {index_name}")
                
                # Verify the block is cleared
                updated_settings = client.indices.get_settings(index=index_name)
                updated_blocks = updated_settings.get(index_name, {}).get('settings', {}).get('index', {}).get('blocks', {})
                if 'read_only_allow_delete' not in updated_blocks:
                    logger.info(f"Successfully cleared read-only block on index {index_name}")
                    return True
                else:
                    logger.warning(f"Could not clear read-only block on index {index_name}, disk space issue likely persists")
                    return False
            except Exception as e:
                logger.error(f"Error clearing read-only block: {str(e)}")
                return False
        else:
            # No read-only block detected
            return True
            
    except opensearch_exceptions.NotFoundError:
        logger.warning(f"Index {index_name} not found")
        return True  # Not found means no disk space issue with this index
    except Exception as e:
        logger.error(f"Error checking index blocks: {str(e)}")
        return False

# Main entry point for direct testing
if __name__ == "__main__":
    # Simple test code to run the core processing directly
    test_event = {
        "repository": {
            "url": "https://github.com/yourusername/your-repo.git",
            "name": "yourusername/your-repo",
            "branch": "main"
        },
        "added_files": ["README.md"],
        "modified_files": [],
        "deleted_files": [],
        "commit_id": "sample-commit-id"
    }
    
    # Run the core processing function directly
    import asyncio
    result = asyncio.run(process_code_changes(test_event, None))
    print(json.dumps(result, indent=2)) 