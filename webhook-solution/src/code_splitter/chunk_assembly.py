"""
Handles the assembly of a single ChunkData object from a byte span.

Coordinates context extraction, import filtering, and final formatting
for a given chunk within a parsed code file.
"""
import logging # Add logging import
import os  # Added for path manipulation
from tree_sitter import Node, Tree

# --- Logging Setup ---
logger = logging.getLogger(__name__)
# --- End Logging Setup ---

from .span import Span # ChunkData no longer returned directly
from .utils import get_line_number, non_whitespace_len, get_node_text # Added get_node_text
from .context_extraction import extract_chunk_context
from .import_filtering import _filter_imports_for_chunk
# format_chunk_with_context is no longer called here

def assemble_chunk_data(
    byte_span: Span,
    root_node: Node,
    tree: Tree, # Pass the whole tree if needed by helpers
    language_config: dict,
    code_bytes: bytes,
    source_str: str,
    original_code_lines: list[str], # Pass original lines if needed by formatters
    base_metadata: dict,
    all_import_nodes: list[Node], # Globally found import nodes
    all_import_lines: list[str],  # Globally found import lines
    last_global_context_end_line: int, # Line where imports ended
    chunk_index: int = 0 # Added chunk_index parameter with default value
) -> dict | None:
    """
    Assembles a dictionary containing chunk components (metadata, context, span)
    for a given byte span.

    Args:
        byte_span: The byte span representing the chunk.
        root_node: The root node of the parsed tree.
        tree: The full parsed tree-sitter tree.
        language_config: Configuration dictionary for the language.
        code_bytes: The source code as bytes.
        source_str: The source code as a string.
        original_code_lines: Original code split into lines.
        base_metadata: Base metadata dictionary for the chunk.
        all_import_nodes: List of all import nodes found in the file.
        all_import_lines: List of all import lines found in the file.
        last_global_context_end_line: The line number where global context (e.g., imports) ended.
        chunk_index: The sequential index of the chunk (for consistency with line-based chunking).

    Returns:
        A dictionary containing chunk components ('metadata', 'import_lines',
        'parent_context_spans', 'chunk_span'), or None if the chunk is
        deemed insignificant.
    """
    original_chunk_text = byte_span.extract_bytes(code_bytes).decode('utf-8', errors='ignore')
    start_line = get_line_number(byte_span.start, source_str) # 0-based line index
    end_line = get_line_number(byte_span.end, source_str)     # 0-based line index

    # Basic check for significance using original text
    if non_whitespace_len(original_chunk_text) < 5: # Configurable threshold?
         return None

    # Normalize file_path to remove anything before repo name
    original_file_path = base_metadata.get('file_path', 'unknown')
    repo_name = base_metadata.get('repo', 'unknown_repo')
    # Find the repo name in the path and keep only from that point forward
    if repo_name in original_file_path:
        repo_index = original_file_path.find(repo_name)
        normalized_file_path = original_file_path[repo_index:]
    else:
        # Fallback if repo name not found in path
        normalized_file_path = os.path.basename(original_file_path)
        normalized_file_path = f"{repo_name}/{normalized_file_path}"
    
    # Update the base_metadata with normalized path
    modified_metadata = base_metadata.copy()
    modified_metadata['file_path'] = normalized_file_path

    # --- Find Start Node for Context ---
    # Try to find the first non-whitespace character's node within the span
    content_start_node = None
    search_start_byte = byte_span.start
    first_char_offset = -1
    for idx, char_byte in enumerate(byte_span.extract_bytes(code_bytes)):
        # Check if the byte corresponds to a non-whitespace character
        try:
            if not chr(char_byte).isspace():
                first_char_offset = byte_span.start + idx
                break
        except UnicodeDecodeError:
             # Handle potential decoding errors if necessary, maybe skip this char
             continue

    if first_char_offset != -1:
        # Find the smallest node containing the first non-whitespace character
        content_start_node = root_node.descendant_for_byte_range(first_char_offset, first_char_offset)

    # Fallback if no non-whitespace char found or node lookup fails
    if content_start_node is None:
        # If we couldn't find a specific start node, use the one covering the span start.
        # This might be less accurate for context but provides a fallback.
        content_start_node = root_node.descendant_for_byte_range(byte_span.start, byte_span.start)
        if content_start_node is None: # Should not happen if root_node is valid
             # Handle error or return None? For now, let's assume it's found.
              logger.warning(f"Could not find any node for chunk at L{start_line+1}") # Use logger.warning
              return None # Cannot proceed without a node

    # --- Find True Chunk Defining Node ---
    # Traverse upwards from content_start_node to find the smallest container
    # node that fully encompasses the original byte_span.
    container_types = set(language_config.get("containers", []))
    true_chunk_defining_node = content_start_node
    current_node = content_start_node
    while current_node.parent:
        parent = current_node.parent
        # Check if parent is a container and encompasses the span
        is_container = parent.type in container_types
        encompasses_span = (parent.start_byte <= byte_span.start and parent.end_byte >= byte_span.end)

        if is_container and encompasses_span:
            true_chunk_defining_node = parent # Found a better fit
            current_node = parent # Continue checking upwards
        else:
            break # Stop if parent is not a container or doesn't encompass the span

    # --- Extract Context ---
    # Pass the correctly identified defining node to context extraction
    ancestor_nodes, parent_context_spans, relational_description = extract_chunk_context(
        chunk_start_node=content_start_node, # Keep passing start node if needed internally
        chunk_defining_node=true_chunk_defining_node, # Pass the identified defining node
        root_node=root_node,
        language_config=language_config,
         code_bytes=code_bytes,
        source_str=source_str,
        last_global_context_end_line=last_global_context_end_line
    )

    # --- Filter Imports ---
    # Filter imports based on identifiers found *within the chunk's byte span*
    filtered_import_lines = _filter_imports_for_chunk(
        all_import_lines=all_import_lines,
        all_import_nodes=all_import_nodes,
        chunk_byte_span=(byte_span.start, byte_span.end), # Pass the span tuple
        root_node=root_node, # Pass the root node for searching
        language_config=language_config,
        code_bytes=code_bytes
    )

    # --- Prepare Components for Return ---
    # Calculate the chunk's line span (1-based for metadata consistency)
    chunk_span_1_based = (start_line + 1, end_line + 1)

    # --- Final Metadata ---
    # Use 1-based lines for metadata
    metadata_start_line = chunk_span_1_based[0]
    metadata_end_line = chunk_span_1_based[1]
    
    metadata = {
        **modified_metadata,  # Use the modified metadata with normalized file_path
        "language": language_config.get("language_name", "unknown"),
        "start_line": metadata_start_line,
        "end_line": metadata_end_line,
        "chunk_id": f"{normalized_file_path}-L{metadata_start_line}-L{metadata_end_line}",
        "relational_description": relational_description, # Use description from context extraction
        "chunk_index": chunk_index # Added for consistency with line-based chunking
        # Optionally add filtered imports/context spans to metadata if needed elsewhere
        # "metadata_imports": filtered_import_lines,
        # "metadata_context_spans": parent_context_spans
    }

    # Refine relational description based on final context (ancestor_nodes now comes from context extraction)
    # Note: ancestor_nodes list now only contains nodes used for context spans (excluding self)
    if not ancestor_nodes: # If no *parent* context was added
        if filtered_import_lines:
             metadata["relational_description"] = "Chunk containing primarily imports"
        else:
             # Check if the chunk itself is a container to refine description
             if content_start_node.type in language_config.get("containers", []):
                 # Try to get name for better description
                 name_node = content_start_node.child_by_field_name('name')
                 if not name_node and len(content_start_node.children) > 1:
                     potential_name_node = content_start_node.children[1]
                     if potential_name_node.type in ['identifier', 'type_identifier']: name_node = potential_name_node
                 chunk_name = get_node_text(name_node, code_bytes) if name_node else None
                 if chunk_name:
                     metadata["relational_description"] = f"Top-level {content_start_node.type} '{chunk_name}'"
                 else:
                     metadata["relational_description"] = f"Top-level {content_start_node.type}"
             else:
                 metadata["relational_description"] = "Top-level code chunk"
    # else: the description derived from ancestors in extract_chunk_context is used

    # --- Extract Parent Context Text ---
    parent_context_text_list = []
    for line_span_tuple in parent_context_spans: # Iterate through (start_line, end_line) tuples
        try:
            # Adjust to use line numbers (0-based index) and slice original_code_lines
            start_idx = line_span_tuple[0] - 1 # Convert 1-based start_line to 0-based index
            end_idx = line_span_tuple[1]       # 1-based end_line is exclusive for slicing, so use directly

            # Basic validation of indices
            if 0 <= start_idx < end_idx <= len(original_code_lines):
                context_lines = original_code_lines[start_idx:end_idx]
                context_text = "\n".join(context_lines)
                parent_context_text_list.append(context_text)
            else:
                 # Log warning if line numbers are out of bounds
                 logger.warning(f"Invalid line numbers for parent context span {line_span_tuple}. Lines available: {len(original_code_lines)}") # Use logger.warning
                 parent_context_text_list.append(f"[Error: Invalid line numbers {line_span_tuple}]")

        except Exception as e:
            # Catch any other unexpected errors during extraction
            logger.warning(f"Could not extract text for parent context line span {line_span_tuple}: {e}") # Use logger.warning
            parent_context_text_list.append(f"[Error extracting context: {e}]")


    # Return the components as a dictionary
    # The caller (e.g., test script formatter) will combine these as needed.
    return {
        "metadata": metadata,
        "import_lines": filtered_import_lines,
        "parent_context_spans": parent_context_spans, # Keep original spans if needed
        "parent_context_text": parent_context_text_list, # Add extracted text
        "parent_context_spans": parent_context_spans,
        "chunk_span_1_based": chunk_span_1_based, # Keep 1-based for metadata
        "byte_span": byte_span, # Add the original byte span object
        "content": original_chunk_text # Add the actual chunk content
    }
