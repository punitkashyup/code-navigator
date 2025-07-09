"""
Provides a high-level API function for chunking code.
"""
import sys
import os
import logging # Add logging import
import asyncio

# --- Logging Setup ---
# Get logger for this module
logger = logging.getLogger(__name__)
# --- End Logging Setup ---

# Ensure the src directory is in the path for sibling imports
src_dir = os.path.dirname(__file__)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import necessary core components
try:
    from .splitter import process_code_for_rag
    from .chunk_formatting import format_chunk_data
    from .language_config import LANGUAGE_NODE_TYPES
    from .language_mapping import get_language_from_extension
    from .fallback_chunking import chunk_by_lines 
    from .description_generation import generate_descriptions_for_chunks, generate_descriptions_for_chunks_async
except ImportError as e:
    logger.exception(f"Error importing core modules in chunker_api: {e}") # Use logger.exception
    # Depending on usage context, might want to raise or handle differently
    sys.exit(1)

DEFAULT_MAX_CHARS = 1500
DEFAULT_COALESCE = 200

DEFAULT_FALLBACK_CHUNK_SIZE = 40
DEFAULT_FALLBACK_OVERLAP = 15

def split_code(
    code_content: str,
    language_name: str | None = None, # Made optional
    file_path: str = "unknown_file",
    repo_name: str | None = None,
    branch_name: str | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    coalesce: int = DEFAULT_COALESCE,
    include_tokens: bool = False, # Add include_tokens flag
    generate_descriptions: bool = False  # Add flag for AI description generation
) -> tuple[str | None, list[dict] | None, str | None]:
    """
    Chunks the given code content and returns formatted text and structured data.
    If language_name is not provided, it attempts to infer it from file_path.
    If language cannot be determined or is unsupported, falls back to line-based chunking.

    Args:
        code_content: The source code content as a string.
        language_name: The name of the programming language (e.g., 'python'). Optional.
        file_path: The original path of the file (used for metadata and language inference).
        repo_name: Optional name of the repository for metadata.
        branch_name: Optional name of the branch for metadata.
        max_chars: The target maximum number of characters (bytes) per chunk (used for tree-sitter).
        coalesce: The minimum number of non-whitespace characters to keep a
                  chunk separate during coalescing (used for tree-sitter).
        include_tokens: Whether to include token counts in the output metadata.
        generate_descriptions: Whether to generate AI descriptions for the file and its chunks.

    Returns:
        A tuple containing:
        - full_formatted_text: String formatted like chunked.txt, or None on error.
        - structured_data_list: List of dictionaries for JSON output (each dict
                                has 'formatted_chunk_block', 'original_content',
                                'metadata'), or None on error.
        - error_message: A string containing an error message if processing failed,
                         otherwise None.
    """
    determined_language = None
    use_fallback = False
    chunking_method = "tree-sitter" # Default assumption

    # --- Language Determination ---
    if language_name:
        if language_name in LANGUAGE_NODE_TYPES:
            determined_language = language_name
            logger.info(f"Using provided language: {determined_language}")
        else:
            logger.warning(f"Provided language '{language_name}' is invalid or unsupported. Falling back to line-based chunking.")
            use_fallback = True
            chunking_method = "line-based"

    # Try inference if no valid language provided yet and not already falling back
    if not determined_language and not use_fallback:
        if file_path and file_path != "unknown_file":
            inferred_language = get_language_from_extension(file_path)
            if inferred_language:
                if inferred_language in LANGUAGE_NODE_TYPES:
                    determined_language = inferred_language
                    logger.info(f"Inferred language '{determined_language}' from file path '{file_path}'")
                else:
                    logger.warning(f"Inferred language '{inferred_language}' from '{file_path}' is unsupported. Falling back to line-based chunking.")
                    use_fallback = True
                    chunking_method = "line-based"
            else:
                logger.warning(f"Could not infer language for '{file_path}'. Falling back to line-based chunking.")
                use_fallback = True
                chunking_method = "line-based"
        else:
            logger.warning("Language not provided and file path is missing or 'unknown_file'. Falling back to line-based chunking.")
            use_fallback = True
            chunking_method = "line-based"

    # --- Prepare Metadata ---
    # Use determined language if available, otherwise 'plaintext' for fallback
    effective_language_for_metadata = determined_language if determined_language else "plaintext"
    file_metadata = {
        "file_path": file_path,
        "language": effective_language_for_metadata,
        "repo": repo_name or "unknown_repo",
        "branch": branch_name or "unknown_branch",
        "chunking_method": chunking_method
    }

    # --- Step 1: Process code to get chunk components ---
    chunk_components_list = None
    if use_fallback:
        logger.info(f"Using fallback line-based chunking for {file_path}")
        chunk_components_list = chunk_by_lines(
            code_content=code_content,
            file_metadata=file_metadata,
            chunk_size=DEFAULT_FALLBACK_CHUNK_SIZE,
            overlap=DEFAULT_FALLBACK_OVERLAP
        )
    elif determined_language:
        logger.info(f"Using tree-sitter chunking ({determined_language}) for {file_path}")
        chunk_components_list = process_code_for_rag(
            code_content=code_content,
            language_name=determined_language,
            file_metadata=file_metadata,
            MAX_CHARS=max_chars,
            coalesce=coalesce
        )
    else:
        # This case should not be reached if logic above is correct
        error_msg = "Internal error: Could not determine chunking method."
        logger.error(error_msg)
        return None, None, error_msg

    # --- Handle errors/results from chunking ---
    # Check for error structure returned by either chunker
    if isinstance(chunk_components_list, list) and chunk_components_list and isinstance(chunk_components_list[0], dict) and "error" in chunk_components_list[0]:
        error_info = chunk_components_list[0]
        error_msg = error_info.get('error', 'Unknown chunking error')
        trace = error_info.get("traceback", "")
        logger.error(f"Error during {chunking_method} chunking process: {error_msg}\n{trace}")
        return None, None, f"Chunking failed: {error_msg}"
    # Check for unexpected non-list results (primarily from process_code_for_rag)
    if not isinstance(chunk_components_list, list):
        error_msg = f"Unexpected result type from chunking process: {type(chunk_components_list)}"
        logger.error(error_msg)
        return None, None, error_msg
    # Handle empty list case (e.g., empty input file or successful chunking yielded no chunks)
    if not chunk_components_list:
        logger.info(f"Chunking process resulted in 0 chunks for {file_path}.")
        return "", [], None # Return empty string and empty list, no error

    # --- Generate AI Descriptions if requested ---
    if generate_descriptions and chunk_components_list:
        try:
            logger.info(f"Generating AI descriptions for {file_path}")
            chunk_components_list = generate_descriptions_for_chunks(
                chunks=chunk_components_list,
                full_file_content=code_content
            )
        except Exception as e:
            logger.warning(f"Error generating AI descriptions: {e}. Continuing without descriptions.")
            # Don't fail the whole process if description generation fails
    # --- Step 2: Format the chunk components ---
    try:
        # Pass the include_tokens flag to the formatting function
        full_formatted_text, structured_data_list = format_chunk_data(
            chunk_components_list,
            include_tokens=include_tokens
        )
        return full_formatted_text, structured_data_list, None # Success
    except Exception as e:
        error_msg = f"Error during formatting: {e}"
        logger.exception(error_msg) # Use logger.exception
        return None, None, error_msg

async def split_code_async(
    code_content: str,
    language_name: str | None = None, # Made optional
    file_path: str = "unknown_file",
    repo_name: str | None = None,
    branch_name: str | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    coalesce: int = DEFAULT_COALESCE,
    include_tokens: bool = False, # Add include_tokens flag
    generate_descriptions: bool = False  # Add flag for AI description generation
) -> tuple[str | None, list[dict] | None, str | None]:
    """
    Async version of split_code that chunks the given code content and returns formatted text and structured data.
    
    Args:
        Same as split_code
        
    Returns:
        Same as split_code
    """
    determined_language = None
    use_fallback = False
    chunking_method = "tree-sitter" # Default assumption

    # --- Language Determination ---
    if language_name:
        if language_name in LANGUAGE_NODE_TYPES:
            determined_language = language_name
            logger.info(f"Using provided language: {determined_language}")
        else:
            logger.warning(f"Provided language '{language_name}' is invalid or unsupported. Falling back to line-based chunking.")
            use_fallback = True
            chunking_method = "line-based"

    # Try inference if no valid language provided yet and not already falling back
    if not determined_language and not use_fallback:
        if file_path and file_path != "unknown_file":
            inferred_language = get_language_from_extension(file_path)
            if inferred_language:
                if inferred_language in LANGUAGE_NODE_TYPES:
                    determined_language = inferred_language
                    logger.info(f"Inferred language '{determined_language}' from file path '{file_path}'")
                else:
                    logger.warning(f"Inferred language '{inferred_language}' from '{file_path}' is unsupported. Falling back to line-based chunking.")
                    use_fallback = True
                    chunking_method = "line-based"
            else:
                logger.warning(f"Could not infer language for '{file_path}'. Falling back to line-based chunking.")
                use_fallback = True
                chunking_method = "line-based"
        else:
            logger.warning("Language not provided and file path is missing or 'unknown_file'. Falling back to line-based chunking.")
            use_fallback = True
            chunking_method = "line-based"

    # --- Prepare Metadata ---
    # Use determined language if available, otherwise 'plaintext' for fallback
    effective_language_for_metadata = determined_language if determined_language else "plaintext"
    file_metadata = {
        "file_path": file_path,
        "language": effective_language_for_metadata,
        "repo": repo_name or "unknown_repo",
        "branch": branch_name or "unknown_branch",
        "chunking_method": chunking_method
    }

    # --- Step 1: Process code to get chunk components ---
    chunk_components_list = None
    if use_fallback:
        logger.info(f"Using fallback line-based chunking for {file_path}")
        # Run potentially blocking operation in a thread pool
        chunk_components_list = await asyncio.to_thread(
            chunk_by_lines,
            code_content=code_content,
            file_metadata=file_metadata,
            chunk_size=DEFAULT_FALLBACK_CHUNK_SIZE,
            overlap=DEFAULT_FALLBACK_OVERLAP
        )
    elif determined_language:
        logger.info(f"Using tree-sitter chunking ({determined_language}) for {file_path}")
        # Run potentially blocking operation in a thread pool
        chunk_components_list = await asyncio.to_thread(
            process_code_for_rag,
            code_content=code_content,
            language_name=determined_language,
            file_metadata=file_metadata,
            MAX_CHARS=max_chars,
            coalesce=coalesce
        )
    else:
        # This case should not be reached if logic above is correct
        error_msg = "Internal error: Could not determine chunking method."
        logger.error(error_msg)
        return None, None, error_msg

    # --- Handle errors/results from chunking ---
    # Check for error structure returned by either chunker
    if isinstance(chunk_components_list, list) and chunk_components_list and isinstance(chunk_components_list[0], dict) and "error" in chunk_components_list[0]:
        error_info = chunk_components_list[0]
        error_msg = error_info.get('error', 'Unknown chunking error')
        trace = error_info.get("traceback", "")
        logger.error(f"Error during {chunking_method} chunking process: {error_msg}\n{trace}")
        return None, None, f"Chunking failed: {error_msg}"
    # Check for unexpected non-list results (primarily from process_code_for_rag)
    if not isinstance(chunk_components_list, list):
        error_msg = f"Unexpected result type from chunking process: {type(chunk_components_list)}"
        logger.error(error_msg)
        return None, None, error_msg
    # Handle empty list case (e.g., empty input file or successful chunking yielded no chunks)
    if not chunk_components_list:
        logger.info(f"Chunking process resulted in 0 chunks for {file_path}.")
        return "", [], None # Return empty string and empty list, no error

    # --- Generate AI Descriptions if requested ---
    if generate_descriptions and chunk_components_list:
        try:
            logger.info(f"Generating AI descriptions for {file_path}")
            # Use the async version of description generation
            chunk_components_list = await generate_descriptions_for_chunks_async(
                chunks=chunk_components_list,
                full_file_content=code_content
            )
        except Exception as e:
            logger.warning(f"Error generating AI descriptions: {e}. Continuing without descriptions.")
            # Don't fail the whole process if description generation fails
            
    # --- Step 2: Format the chunk components ---
    try:
        # Run potentially blocking operation in a thread pool
        format_result = await asyncio.to_thread(
            format_chunk_data,
            chunk_components_list,
            include_tokens=include_tokens
        )
        full_formatted_text, structured_data_list = format_result
        return full_formatted_text, structured_data_list, None # Success
    except Exception as e:
        error_msg = f"Error during formatting: {e}"
        logger.exception(error_msg) # Use logger.exception
        return None, None, error_msg