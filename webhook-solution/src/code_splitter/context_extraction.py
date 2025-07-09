"""
Handles the extraction of contextual information for code chunks,
including finding all import statements and determining ancestor context
(parent signatures and relational descriptions).
"""
from tree_sitter import Node, Tree

# Assuming these utilities are in core/utils.py
from .utils import get_node_text, get_line_number

def find_all_import_nodes(
    root_node: Node,
    language_config: dict,
    code_bytes: bytes
) -> tuple[list[Node], list[str]]:
    """
    Finds all import-related nodes and their corresponding text lines in the tree.

    Args:
        root_node: The root node of the parsed tree-sitter tree.
        language_config: Configuration dictionary for the language.
        code_bytes: The source code as bytes.

    Returns:
        A tuple containing:
        - list[Node]: Sorted list of unique import nodes.
        - list[str]: List of unique import statement text lines, corresponding
                     to the nodes, sorted by appearance.
    """
    all_import_nodes: list[Node] = []
    import_types = set(language_config.get("imports", []))

    if not import_types or not root_node:
        return [], []

    # Traverse the tree to find all nodes matching the configured import types
    queue = [root_node]
    visited_children = {root_node.id} # Keep track of visited nodes
    head = 0
    while head < len(queue):
        node = queue[head]; head += 1
        if not node: continue

        # Check if the node itself is an import type
        if node.type in import_types:
            # Ensure we don't add duplicates if traversal visits a node multiple times
            is_new = True
            for existing_node in all_import_nodes:
                if existing_node.id == node.id:
                    is_new = False
                    break
            if is_new:
                 all_import_nodes.append(node)

        # Decide whether to traverse children based on container types
        # Avoid traversing into deep containers unless they are also import types
        # (e.g., some languages might allow imports inside classes/functions)
        should_traverse_children = True
        # If the node is a container but NOT the root and NOT an import type itself, stop traversal down this path for imports.
        if node.type in language_config.get("containers", []) and \
           node != root_node and \
           node.type not in import_types:
             should_traverse_children = False

        if should_traverse_children:
            for child in node.children:
                if child.id not in visited_children:
                    queue.append(child)
                    visited_children.add(child.id)

    # Sort imports by their start byte position
    all_import_nodes.sort(key=lambda n: n.start_byte)

    # Get unique import text lines corresponding to the sorted nodes
    processed_import_texts = set()
    unique_import_texts = []
    final_import_nodes = [] # Keep nodes corresponding to unique texts
    for node in all_import_nodes:
        node_text = get_node_text(node, code_bytes).strip()
        if node_text and node_text not in processed_import_texts:
            unique_import_texts.append(node_text)
            processed_import_texts.add(node_text)
            final_import_nodes.append(node) # Add the node associated with this unique text

    # Split the combined unique texts into lines for the final list
    import_lines = "\n".join(unique_import_texts).splitlines()

    return final_import_nodes, import_lines


# Need to import Node for type hinting
from .utils import get_node_text, get_line_number, get_indentation_level

def extract_chunk_context(
    chunk_start_node: Node | None, # Node where chunk content starts
    chunk_defining_node: Node, # Node that defines the chunk (e.g., function_definition for a function chunk)
    root_node: Node,
    language_config: dict,
    code_bytes: bytes,
    source_str: str,
    last_global_context_end_line: int # e.g., end line of last import
) -> tuple[list[Node], list[tuple[int, int]], str]:
    """
    Extracts ancestor context (signatures) and relational description for a chunk.

    Args:
        chunk_start_node: The tree-sitter node representing the start of the chunk's content.
        chunk_defining_node: The tree-sitter node that best represents the chunk itself (e.g., the function_definition node if the chunk is a whole function).
        root_node: The root node of the parsed tree.
        language_config: Configuration dictionary for the language.
        code_bytes: The source code as bytes.
        source_str: The source code as a string (for line number calculations).
        last_global_context_end_line: The line number where global context (like imports) ended.

    Returns:
        A tuple containing:
        - list[Node]: List of ancestor container nodes (excluding the chunk defining node itself).
        - list[tuple[int, int]]: List of (start_line, end_line) tuples (1-based) for parent context signatures.
        - str: The relational description string.
    """
    parent_context_spans: list[tuple[int, int]] = []
    ancestor_nodes_for_context: list[Node] = [] # Store actual ancestors used for context spans
    relational_description = "Code chunk" # Default description

    container_types = set(language_config.get("containers", []))
    stop_types = set(language_config.get("stop_at", []) + ['comment']) # Stop traversal at these types

    if not chunk_start_node or not container_types:
        return [], parent_context_spans, relational_description # Return empty list for nodes too

    # --- Find Ancestor Containers ---
    # We traverse from the chunk_defining_node upwards to find parents
    current = chunk_defining_node.parent # Start from the parent
    found_ancestors: list[Node] = []
    while current:
        # Add if it's a container type
        if current.type in container_types:
            found_ancestors.append(current)
        # Stop conditions
        if current.type in stop_types or current.parent is None:
            break
        current = current.parent

    found_ancestors.reverse() # Order from outermost to innermost

    # --- Determine Context Spans and Description ---
    container_names_for_desc = []
    processed_context_node_ids = set() # Avoid processing the same ancestor twice

    for ancestor_node in found_ancestors:
        # Skip if this ancestor is the same as the node defining the chunk itself
        # or if we've somehow processed it already.
        if ancestor_node.id == chunk_defining_node.id or \
           ancestor_node.id in processed_context_node_ids:
            continue

        # Determine the end byte of the signature (usually up to the body start)
        body_node = ancestor_node.child_by_field_name('body')
        signature_end_byte = body_node.start_byte if body_node else ancestor_node.end_byte

        # Refinement: For languages with explicit block delimiters (like {}),
        # try to end the signature just after the opening delimiter if no body node found.
        if not body_node:
            block_delimiters = language_config.get("block_delimiters", {})
            start_delim = block_delimiters.get("start")
            if start_delim:
                # Get text up to a reasonable limit to find the delimiter
                header_text_full = code_bytes[ancestor_node.start_byte:min(ancestor_node.end_byte, ancestor_node.start_byte + 500)].decode('utf-8', errors='ignore')
                delim_pos = header_text_full.find(start_delim)
                if delim_pos != -1:
                    # Calculate byte offset of delimiter end
                    signature_end_byte = ancestor_node.start_byte + len(header_text_full[:delim_pos+len(start_delim)].encode('utf-8'))

        # Calculate 1-based line numbers for the signature span
        signature_start_line = get_line_number(ancestor_node.start_byte, source_str) + 1
        signature_end_line = get_line_number(signature_end_byte, source_str) + 1

        # Add the span to our list
        parent_context_spans.append((signature_start_line, signature_end_line))
        ancestor_nodes_for_context.append(ancestor_node) # Keep track of nodes used for context
        processed_context_node_ids.add(ancestor_node.id)

        # --- Build Relational Description (using the same logic as before) ---
        name_node = ancestor_node.child_by_field_name('name')
        if not name_node and len(ancestor_node.children) > 1:
             potential_name_node = ancestor_node.children[1]
             if potential_name_node.type in ['identifier', 'type_identifier']:
                 name_node = potential_name_node
        ancestor_name = get_node_text(name_node, code_bytes) if name_node else None
        if ancestor_name:
            container_names_for_desc.append(f"{ancestor_node.type} '{ancestor_name}'")
        else:
            container_names_for_desc.append(f"{ancestor_node.type}")


    # --- Finalize Relational Description ---
    if container_names_for_desc:
        relational_description = f"Chunk within {' -> '.join(container_names_for_desc)}"
    elif not found_ancestors: # If no ancestors were found traversing up
         relational_description = "Top-level code chunk"
    # If ancestors were found but filtered out (e.g., chunk was a top-level function),
    # the default "Code chunk" might be okay, or we could refine based on chunk_defining_node.type


    # Return the nodes that actually contributed to the context spans
    return ancestor_nodes_for_context, parent_context_spans, relational_description
