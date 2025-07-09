"""
Main entry point for the Code Navigator chunking algorithm.

Orchestrates the process of parsing code, creating byte spans,
extracting context, filtering imports, formatting, and handling fallbacks.
"""
import traceback
import json
from tree_sitter import Parser, Tree, Node # Keep Parser for type checking
import logging # Add logging import

# --- Logging Setup ---
logger = logging.getLogger(__name__)
# --- End Logging Setup ---

# --- Core Data Structures ---
from .span import Span, ChunkData

# --- Configuration ---
from .language_config import LANGUAGE_NODE_TYPES

# --- Utility Functions ---
from .utils import get_line_number # Keep specific utils needed here

# --- Refactored Chunking Stages ---
from .byte_span_creation import create_byte_spans
from .context_extraction import find_all_import_nodes
from .chunk_assembly import assemble_chunk_data
from .fallback_chunking import chunk_by_lines # Corrected import
from .notebook_chunking import chunk_notebook_cells


def process_code_for_rag(
    code_content: str,
    language_name: str,
    file_metadata: dict,
    MAX_CHARS: int = 1500,
    coalesce: int = 100
) -> list[dict] | dict:
    """
    Main entry point for chunking code or notebooks for RAG processing.

    Handles language detection, parsing, chunking, context addition, and fallbacks.

    Args:
        code_content: The source code content as a string.
        language_name: The name of the programming language.
        file_metadata: Base metadata dictionary for the file (e.g., path).
        MAX_CHARS: The target maximum number of characters (bytes) per chunk.
        coalesce: The minimum number of non-whitespace characters to keep a chunk separate during coalescing.

    Returns:
        A list of dictionaries, where each dictionary represents a chunk
        (with "content" and "metadata" keys), or a dictionary containing
        "error" and "traceback" keys if a critical error occurred.
    """
    try:
        if not code_content.strip():
            return [] # Return empty list for empty files

        # --- Handle Jupyter Notebooks Separately ---
        if language_name == "Jupyter Notebook":
            try:
                # Use the dedicated notebook chunking function
                chunk_data_list = chunk_notebook_cells(code_content, file_metadata, MAX_CHARS)
                # Convert ChunkData to dict for final output
                return [{"content": cd.content, "metadata": cd.metadata} for cd in chunk_data_list]
            except json.JSONDecodeError as e:
                 logger.error(f"Error decoding JSON for Jupyter Notebook ({file_metadata.get('file_path', 'unknown')}): {e}") # Use logger.error
                 return {"error": f"Invalid JSON for Jupyter Notebook: {e}", "traceback": traceback.format_exc()}
            except Exception as e:
                 logger.exception(f"Error processing Jupyter Notebook ({file_metadata.get('file_path', 'unknown')}): {e}") # Use logger.exception
                 return {"error": f"Failed to process notebook cells: {e}", "traceback": traceback.format_exc()}

        # --- Handle Standard Code Files ---
        language_config = LANGUAGE_NODE_TYPES.get(language_name)

        # Check if language is supported and has a valid parser
        if not language_config or not isinstance(language_config.get('parser'), Parser):
            logger.warning(f"Language '{language_name}' not configured or parser unavailable. Using fallback line chunker.") # Use logger.warning
            # Fallback chunker now returns list[dict] including 'byte_span'
            chunk_data_list = chunk_by_lines(code_content, file_metadata) # Corrected function call
            return chunk_data_list # Return the list of dicts directly

        # Ensure the language name is stored in the config dict for assemble_chunk_data
        if language_config:
            language_config['language_name'] = language_name

        # --- Proceed with tree-sitter parsing ---
        parser = language_config['parser']
        logger.info(f"Using pre-loaded parser for language '{language_name}'.") # Use logger.info
        encoded_code = code_content.encode("utf-8", errors='ignore')
        tree = parser.parse(encoded_code)

        # Check for parsing errors or invalid tree
        if tree is None or tree.root_node is None or tree.root_node.has_error:
            logger.warning(f"Parsing issues for {file_metadata.get('file_path', language_name)}. Using fallback line chunker.") # Use logger.warning
            # Fallback chunker now returns list[dict] including 'byte_span'
            chunk_data_list = chunk_by_lines(code_content, file_metadata) # Corrected function call
            return chunk_data_list # Return the list of dicts directly

        root_node = tree.root_node
        source_str = encoded_code.decode("utf-8", errors='ignore') # Decode once for reuse
        original_code_lines = source_str.splitlines()

        # --- Stage 1: Create Byte Spans ---
        byte_spans = create_byte_spans(tree, encoded_code, MAX_CHARS=MAX_CHARS, coalesce=coalesce)

        # Handle case where no spans are created for non-empty file (should be rare after fixes)
        if not byte_spans and code_content.strip():
            logger.warning(f"No byte spans created for {file_metadata.get('file_path', language_name)}. Treating as single chunk.") # Use logger.warning
            byte_spans = [Span(0, len(encoded_code))] # Create a single span for the whole file

        if not byte_spans:
             return [] # Return empty if no spans could be generated

        # --- Stage 2: Extract Global Context (Imports) ---
        all_import_nodes, all_import_lines = find_all_import_nodes(
            root_node=root_node,
            language_config=language_config,
            code_bytes=encoded_code
        )
        last_global_context_end_line = -1
        if all_import_nodes:
            # Calculate the end line of the last import statement found
            last_import_end_byte = all_import_nodes[-1].end_byte
            last_global_context_end_line = get_line_number(last_import_end_byte, source_str)

        # --- Stage 3: Assemble ChunkData for each span ---
        final_chunk_data_list: list[ChunkData] = []
        # Track signatures to avoid adding highly similar chunks consecutively
        # (e.g., chunks differing only by a comment or minor whitespace)
        processed_chunk_signatures = set()
        chunk_index = 0  # Track chunk_index for consistent metadata across chunking methods

        for byte_span in byte_spans:
            chunk_data = assemble_chunk_data(
                byte_span=byte_span,
                root_node=root_node,
                tree=tree,
                language_config=language_config,
                code_bytes=encoded_code,
                source_str=source_str,
                original_code_lines=original_code_lines,
                base_metadata=file_metadata.copy(), # Pass a copy to avoid modification issues
                all_import_nodes=all_import_nodes,
                all_import_lines=all_import_lines,
                last_global_context_end_line=last_global_context_end_line,
                chunk_index=chunk_index  # Pass the current chunk index
            )

            if chunk_data: # chunk_data is now a dictionary
                final_chunk_data_list.append(chunk_data) # Append the dictionary unconditionally
                chunk_index += 1  # Increment index only for valid chunks

        # --- Adjust trailing/leading whitespace between chunks ---
        for i in range(len(final_chunk_data_list) - 1):
            current_chunk_dict = final_chunk_data_list[i]
            next_chunk_dict = final_chunk_data_list[i+1]

            # Ensure 'content' key exists in both dictionaries
            if 'content' in current_chunk_dict and 'content' in next_chunk_dict:
                current_content = current_chunk_dict['content']
                len_original = len(current_content)
                stripped_content = current_content.rstrip(' \t') # Only remove trailing spaces/tabs
                len_stripped = len(stripped_content)

                if len_original > len_stripped:
                    # Trailing whitespace found
                    trailing_ws = current_content[len_stripped:]
                    # Update current chunk's content
                    current_chunk_dict['content'] = stripped_content
                    # Prepend whitespace to next chunk's content
                    next_chunk_dict['content'] = trailing_ws + next_chunk_dict['content']
            else:
                # Handle cases where 'content' might be missing (shouldn't happen with current logic)
                logger.warning(f"'content' key missing in chunk index {i} or {i+1}. Skipping whitespace adjustment.") # Use logger.warning


        # --- Return the list of structured chunk dictionaries ---
        # The final_chunk_data_list now contains dictionaries with keys:
        # 'metadata', 'import_lines', 'parent_context_spans', 'byte_span', 'content', etc.
        # The 'content' has been adjusted for inter-chunk whitespace.
        return final_chunk_data_list

    except Exception as e:
        logger.exception(f"Critical Error processing code for RAG ({file_metadata.get('file_path', language_name)}): {e}") # Use logger.exception
        # Log the full traceback for debugging
        # traceback.print_exc() # logger.exception includes traceback
        return {"error": f"Failed to process code: {e}", "traceback": traceback.format_exc()}
