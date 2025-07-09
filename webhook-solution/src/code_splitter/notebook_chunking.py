"""
Handles the specific logic for chunking Jupyter Notebook files (.ipynb)
by processing their cell structure.
"""
import json
import logging # Add logging import

# --- Logging Setup ---
logger = logging.getLogger(__name__)
# --- End Logging Setup ---

# Assuming ChunkData is defined in span.py relative to this file
from .span import ChunkData

def chunk_notebook_cells(
    notebook_content: str,
    file_metadata: dict,
    max_chars: int = 2000 # Default max characters for splitting large cells
) -> list[ChunkData]:
    """
    Chunks a Jupyter Notebook by processing its cells.

    Args:
        notebook_content: The raw string content of the .ipynb file.
        file_metadata: Base metadata for the file (e.g., path).
        max_chars: Maximum characters per chunk (applied when splitting large cells).

    Returns:
        A list of ChunkData objects, each representing a chunk from a cell
        or a part of a large cell. Returns an empty list if parsing fails or
        the notebook has no cells.
    """
    chunks = []
    try:
        notebook_json = json.loads(notebook_content)
        cells = notebook_json.get("cells", [])
    except json.JSONDecodeError:
        # Handle invalid JSON gracefully
        logger.warning(f"Could not parse JSON for notebook: {file_metadata.get('file_path', 'unknown')}") # Use logger.warning
        return [] # Return empty list if notebook is not valid JSON

    for idx, cell in enumerate(cells):
        cell_type = cell.get("cell_type")
        source = cell.get("source")

        # Ensure source is treated as a single string
        if isinstance(source, list):
            cell_content = "".join(source)
        elif isinstance(source, str):
            cell_content = source
        else:
            cell_content = "" # Handle unexpected source types

        cell_len = len(cell_content)
        # Base metadata for all chunks derived from this cell
        cell_metadata_base = {
            **file_metadata,
            "language": "Jupyter Notebook", # Specific language marker
            "cell_type": cell_type,
            "original_cell_index": idx,
        }

        # Skip empty cells
        if not cell_content.strip():
            continue

        # If cell is small enough, treat it as one chunk
        if cell_len <= max_chars:
            chunk_id = f"{file_metadata.get('file_path', 'unknown')}-cell{idx}-0"
            # Calculate line numbers within the cell content
            start_line = 1
            end_line = cell_content.count('\n') + 1
            metadata = {
                **cell_metadata_base,
                "chunk_id": chunk_id,
                "start_line": start_line, # Line numbers relative to the cell start
                "end_line": end_line
            }
            chunks.append(ChunkData(content=cell_content, metadata=metadata))
        else:
            # Split large cells based on max_chars (simple text split)
            start = 0
            sub_chunk_index = 0
            while start < cell_len:
                end = min(start + max_chars, cell_len)
                # Try to find a newline near the end boundary for cleaner breaks
                # Look backwards from 'end' within the current slice [start:end]
                newline_pos = cell_content.rfind('\n', start, end)

                # Break at newline if it's found within the latter half of the slice
                # to avoid very small chunks after the newline.
                if newline_pos != -1 and newline_pos > start + (max_chars // 4):
                    end = newline_pos + 1 # Include the newline character in the chunk

                sub_content = cell_content[start:end]
                chunk_id = f"{file_metadata.get('file_path', 'unknown')}-cell{idx}-{sub_chunk_index}"

                # Calculate line numbers relative to the *start of the cell*
                start_line_in_cell = cell_content[:start].count('\n') + 1
                end_line_in_cell = cell_content[:end].count('\n') + 1

                metadata = {
                    **cell_metadata_base,
                    "chunk_id": chunk_id,
                    "start_line": start_line_in_cell, # Relative to cell
                    "end_line": end_line_in_cell      # Relative to cell
                }
                # Only add non-empty sub-chunks
                if sub_content.strip():
                    chunks.append(ChunkData(content=sub_content, metadata=metadata))

                start = end
                sub_chunk_index += 1

    return chunks
