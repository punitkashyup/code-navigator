"""
Handles the creation of initial byte spans from a tree-sitter parse tree.
Includes recursive chunking based on MAX_CHARS, gap filling, and coalescing small chunks.
"""
from tree_sitter import Tree, Node

from .span import Span
from .utils import non_whitespace_len # Assuming non_whitespace_len is in utils.py

def _chunk_tree_recursive(node: Node, source_code_bytes: bytes, MAX_CHARS: int) -> list[Span]:
    """
    Recursively chunk a tree node based on MAX_CHARS limit.

    This function traverses the node's children. If a child exceeds MAX_CHARS,
    it's recursively chunked. If adding a child to the current chunk exceeds
    MAX_CHARS, the current chunk is finalized, and the child starts a new chunk.

    Args:
        node: The tree-sitter node to chunk.
        source_code_bytes: The source code as bytes (needed for length calculations).
        MAX_CHARS: The maximum number of characters (bytes) per chunk.

    Returns:
        A list of Span objects representing the initial chunks based on size limits.
    """
    chunks: list[Span] = []
    current_chunk_start = node.start_byte
    current_chunk_end = node.start_byte # Use end_byte to track the end of the current chunk

    for child in node.children:
        child_len = child.end_byte - child.start_byte
        if child_len == 0:
            continue # Skip empty nodes

        # If the child itself is too large, chunk it recursively
        if child_len > MAX_CHARS:
            # Finalize the chunk before this large child, if it exists
            if current_chunk_end > current_chunk_start:
                chunks.append(Span(current_chunk_start, current_chunk_end))
            # Add chunks from the large child
            chunks.extend(_chunk_tree_recursive(child, source_code_bytes, MAX_CHARS))
            # Reset the current chunk to start after this large child
            current_chunk_start = child.end_byte
            current_chunk_end = child.end_byte
        # If adding this child exceeds the limit, finalize the current chunk
        elif child.end_byte - current_chunk_start > MAX_CHARS:
            # Finalize the current chunk if it has content
            if current_chunk_end > current_chunk_start:
                chunks.append(Span(current_chunk_start, current_chunk_end))
            # Start a new chunk with this child
            current_chunk_start = child.start_byte
            current_chunk_end = child.end_byte
        # Otherwise, extend the current chunk to include this child
        else:
            # If the chunk is currently empty, set its start point
            if current_chunk_end == current_chunk_start:
                current_chunk_start = child.start_byte
            # Extend the end point
            # Extend the end point, ensuring it covers the child
            current_chunk_end = max(current_chunk_end, child.end_byte)

    # Add the final chunk, ensuring it goes up to the node's end byte
    # This captures any trailing content within the node not covered by the last child
    if node.end_byte > current_chunk_start:
        # Ensure the final chunk doesn't overlap excessively with previously added recursive chunks
        # If the last action was adding recursive chunks, current_chunk_start was reset.
        # If the last action was finalizing a chunk before a large child, current_chunk_start was reset.
        # If the last action was extending, current_chunk_start is the start of the last chunk.
        
        # Check if the last added chunk (if any) ends where this one starts.
        # Avoid adding an empty or fully overlapping chunk.
        if not chunks or chunks[-1].end <= current_chunk_start:
             chunks.append(Span(current_chunk_start, node.end_byte))
        else:
             # Handle potential overlap: Adjust the start of this final chunk
             # if it significantly overlaps the end of the last chunk from recursion.
             # This logic might need refinement based on observed overlaps.
             # For now, let's assume the gap filling handles minor overlaps.
             adjusted_start = max(current_chunk_start, chunks[-1].end if chunks else current_chunk_start)
             if node.end_byte > adjusted_start:
                 chunks.append(Span(adjusted_start, node.end_byte))


    return chunks


def create_byte_spans(tree: Tree, source_code_bytes: bytes, MAX_CHARS: int, coalesce: int) -> list[Span]:
    """
    Create byte spans from a tree, filling gaps and coalescing small chunks.

    Args:
        tree: The tree-sitter parse tree.
        source_code_bytes: The source code as bytes.
        MAX_CHARS: The maximum number of characters (bytes) per chunk.
        coalesce: The minimum number of non-whitespace characters to keep a chunk separate.

    Returns:
        A list of finalized Span objects representing the code chunks.
    """
    if not tree or not tree.root_node:
        return []

    # 1. Initial recursive chunking based on MAX_CHARS
    byte_chunks = _chunk_tree_recursive(tree.root_node, source_code_bytes, MAX_CHARS)

    if not byte_chunks:
        # Handle case where recursive chunking returns nothing (e.g., empty file parsed)
        # If the root node has size, create a single chunk for the whole file
        if tree.root_node.end_byte > tree.root_node.start_byte:
             return [Span(tree.root_node.start_byte, tree.root_node.end_byte)]
        else:
            return []

    # 2. Fill in gaps between chunks
    filled_chunks = []
    current_pos = tree.root_node.start_byte # Start from the beginning of the root node

    for chunk in byte_chunks:
        # If there's a gap before the current chunk
        if chunk.start > current_pos:
            gap_chunk = Span(current_pos, chunk.start)
            # Only add non-empty gap chunks
            if len(gap_chunk) > 0:
                filled_chunks.append(gap_chunk)

        # Add the current chunk itself, ensuring start is not before current_pos
        safe_start = max(current_pos, chunk.start)
        if chunk.end > safe_start: # Ensure the chunk has a positive length
            filled_chunks.append(Span(safe_start, chunk.end))
            current_pos = chunk.end # Update position to the end of the added chunk
        elif chunk.end == safe_start and chunk.start == chunk.end:
            # Handle zero-length chunks that might occur; just update position
            current_pos = chunk.end

    # Add any remaining gap at the end of the file
    if tree.root_node.end_byte > current_pos:
        filled_chunks.append(Span(current_pos, tree.root_node.end_byte))

    # Ensure filled_chunks is not empty if the file has content
    if not filled_chunks and tree.root_node.end_byte > tree.root_node.start_byte:
         # This case might happen if initial_byte_chunks was empty but root node wasn't.
         # Should have been handled earlier, but as a safeguard:
         filled_chunks = [Span(tree.root_node.start_byte, tree.root_node.end_byte)]
    elif not filled_chunks:
        return [] # Truly empty file or error

    # 3. Coalesce small chunks (using filled_chunks)
    coalesced_chunks = []
    if not filled_chunks: # Redundant check, safe
        return []

    current_chunk = filled_chunks[0] # Start with the first filled chunk

    for next_chunk in filled_chunks[1:]: # Iterate over the rest of the filled chunks
        current_text = current_chunk.extract_bytes(source_code_bytes).decode('utf-8', errors='ignore')
        current_non_ws = non_whitespace_len(current_text)
        should_combine = False

        # Condition 1: Current chunk is very small (less than coalesce)
        if current_non_ws < coalesce:
            # Condition 2: Combining doesn't exceed MAX_CHARS significantly
            # Using 1.5 * MAX_CHARS as a heuristic threshold for combining
            combined_byte_len = len(current_chunk) + len(next_chunk)
            if combined_byte_len < MAX_CHARS * 1.5:
                # Condition 3: Combining doesn't add too many newlines OR current chunk is tiny
                # This tries to avoid merging large blocks separated by a small comment/whitespace chunk
                combined_text = (current_chunk + next_chunk).extract_bytes(source_code_bytes).decode('utf-8', errors='ignore')
                current_newlines = current_text.count('\n')
                combined_newlines = combined_text.count('\n')
                # Combine if few newlines are added OR if the current chunk is really small (e.g., just whitespace/comment)
                if (combined_newlines - current_newlines < 3) or current_non_ws < coalesce / 2:
                    should_combine = True

        if should_combine:
            # Combine the next chunk into the current one
            current_chunk += next_chunk
        else:
            # Finalize the current chunk and start a new one
            coalesced_chunks.append(current_chunk)
            current_chunk = next_chunk

    # Add the last chunk (which might be a result of coalescing)
    coalesced_chunks.append(current_chunk)

    # Final filter: Remove potentially empty chunks resulting from coalescing or gaps
    final_chunks = [chunk for chunk in coalesced_chunks if len(chunk) > 0 and non_whitespace_len(chunk.extract_bytes(source_code_bytes).decode('utf-8', errors='ignore')) > 0]


    return final_chunks
