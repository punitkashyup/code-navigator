# src/core/fallback_chunking.py
"""
Provides a fallback chunking mechanism based on line counts.
"""
import logging
import os  # Added for path manipulation

logger = logging.getLogger(__name__)

def chunk_by_lines(
    code_content: str,
    file_metadata: dict,
    chunk_size: int = 40,
    overlap: int = 15
) -> list[dict]:
    """
    Chunks the given content by lines with a specified overlap.

    Args:
        code_content: The string content to chunk.
        file_metadata: Base metadata dictionary for the file.
        chunk_size: The target number of lines per chunk.
        overlap: The number of lines to overlap between consecutive chunks.

    Returns:
        A list of chunk component dictionaries. Each dictionary contains:
        - 'content': The text content of the chunk.
        - 'metadata': An updated metadata dictionary including start_line,
                      end_line, and original file metadata.
        Returns an empty list if content is empty or chunk_size is invalid.
        Returns a list containing an error dict if overlap is invalid.
    """
    if not code_content:
        return []

    lines = code_content.splitlines(keepends=True) # Keep line endings for accurate reconstruction
    total_lines = len(lines)
    chunk_components = []
    start_line_idx = 0
    chunk_index = 0

    if chunk_size <= 0:
        logger.error("Chunk size must be positive. Returning empty list.")
        return [] # Return empty list for invalid chunk size

    if overlap < 0 or overlap >= chunk_size:
        logger.error("Overlap must be non-negative and less than chunk size.")
        # Return error structure consistent with process_code_for_rag
        return [{"error": "Invalid overlap value.", "traceback": ""}]
    
    # Normalize file_path to remove anything before repo name
    original_file_path = file_metadata.get('file_path', 'unknown')
    repo_name = file_metadata.get('repo', 'unknown_repo')
    # Find the repo name in the path and keep only from that point forward
    if repo_name in original_file_path:
        repo_index = original_file_path.find(repo_name)
        normalized_file_path = original_file_path[repo_index:]
    else:
        # Fallback if repo name not found in path
        normalized_file_path = os.path.basename(original_file_path)
        normalized_file_path = f"{repo_name}/{normalized_file_path}"
    
    # Update the file_metadata with normalized path
    modified_metadata = file_metadata.copy()
    modified_metadata['file_path'] = normalized_file_path

    while start_line_idx < total_lines:
        end_line_idx = min(start_line_idx + chunk_size, total_lines)
        chunk_lines = lines[start_line_idx:end_line_idx]
        # Ensure content is not empty (can happen if last lines are empty)
        if not chunk_lines:
             break
        chunk_content = "".join(chunk_lines)

        # Create metadata for this chunk
        metadata_start_line = start_line_idx + 1  # 1-based indexing for lines
        metadata_end_line = end_line_idx
        
        chunk_metadata = modified_metadata.copy() # Start with modified base file metadata
        chunk_metadata.update({
            "chunk_index": chunk_index,
            "start_line": metadata_start_line,
            "end_line": metadata_end_line,
            "chunking_method": "line-based",
            # Use normalized path for chunk_id
            "chunk_id": f"{normalized_file_path}-L{metadata_start_line}-L{metadata_end_line}",
            "relational_description": "Line-based code chunk"
        })

        chunk_components.append({
            "content": chunk_content,
            "metadata": chunk_metadata
        })

        # Move to the next chunk start position
        step = chunk_size - overlap
        # step should always be > 0 due to overlap validation above
        start_line_idx += step
        chunk_index += 1

    if not chunk_components and total_lines > 0:
         # This case might indicate an issue, but basic handling is to return empty.
         logger.warning("Fallback chunking produced no chunks despite having content.")

    logger.info(f"Fallback chunking created {len(chunk_components)} chunks for {modified_metadata.get('file_path', 'unknown file')}")
    return chunk_components

# Example usage (optional)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    test_content = "\n".join([f"Line {i+1}" for i in range(100)])
    test_metadata = {"file_path": "test.txt", "language": "plaintext"}
    print("--- Standard Test ---")
    components = chunk_by_lines(test_content, test_metadata, chunk_size=10, overlap=3)
    print(f"Generated {len(components)} chunks.")
    if components and isinstance(components[0], dict) and "content" in components[0]:
        print(f"First chunk metadata: {components[0]['metadata']}")
        print(f"Last chunk metadata: {components[-1]['metadata']}")

    # Test edge case: short content
    short_content = "Line 1\nLine 2\nLine 3"
    print("\n--- Short Content Test ---")
    components_short = chunk_by_lines(short_content, test_metadata, chunk_size=5, overlap=1)
    print(f"Generated {len(components_short)} chunks.")
    if components_short:
        print(f"First chunk metadata: {components_short[0]['metadata']}")

    # Test empty content
    print("\n--- Empty Content Test ---")
    components_empty = chunk_by_lines("", test_metadata)
    print(f"Generated {len(components_empty)} chunks.")

    # Test invalid overlap
    print("\n--- Invalid Overlap Test ---")
    components_invalid_overlap = chunk_by_lines(test_content, test_metadata, chunk_size=10, overlap=10)
    print(f"Result: {components_invalid_overlap}")

    # Test invalid chunk size
    print("\n--- Invalid Chunk Size Test ---")
    components_invalid_size = chunk_by_lines(test_content, test_metadata, chunk_size=0, overlap=3)
    print(f"Result: {components_invalid_size}")
