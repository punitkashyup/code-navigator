"""
Handles the logic for filtering import statements based on identifier usage
within a code chunk and its context.
"""
import logging # Add logging import
from collections import defaultdict
from tree_sitter import Node

# --- Logging Setup ---
logger = logging.getLogger(__name__)
# --- End Logging Setup ---

# Assuming these are correctly imported relative to this new file's location
# If utils.py remains in core, this is correct.
from .utils import get_node_text

# --- Identifier Finding ---

def _find_identifiers_in_span(
    root_node: Node,
    start_byte: int,
    end_byte: int,
    language_config: dict
) -> set[str]:
    """
    Find all identifier texts within a given byte span, using language-specific config.

    Args:
        root_node: The root node of the tree to search within.
        start_byte: The starting byte of the span.
        end_byte: The ending byte of the span.
        language_config: The configuration dictionary for the language.

    Returns:
        A set of identifier strings found within the span.
    """
    # Removed duplicated docstring start """
    identifiers = set()
    if start_byte >= end_byte:
        return identifiers

    # Get identifier types from config, default to empty list if not found
    config_identifier_types = set(language_config.get("identifier_types", []))
    # Also include common member access types which might not be in simple identifier lists
    # but are relevant for finding used names (e.g., obj.member)
    member_access_types = {'member_expression', 'attribute'}

    # Find the smallest node encompassing the span to start the search
    start_node = root_node.descendant_for_byte_range(start_byte, start_byte)
    end_node = root_node.descendant_for_byte_range(end_byte -1, end_byte -1) # -1 because end is exclusive for range

    if not start_node:
        return identifiers # Cannot find identifiers if start node is invalid

    # Use a queue for BFS/DFS-like traversal within the span
    queue = [start_node]
    visited_node_ids = {start_node.id}
    processed_identifiers = set() # Track identifiers already added

    while queue:
        current_node = queue.pop(0)

        # --- Check if node is within the target span ---
        # Optimization: If node starts after span end, skip its children
        if current_node.start_byte >= end_byte:
            continue
        # Optimization: If node ends before span start, skip (shouldn't happen with initial queue setup)
        if current_node.end_byte <= start_byte:
             continue

        # --- Process the node if it overlaps the span ---
        node_start_in_span = max(current_node.start_byte, start_byte)
        node_end_in_span = min(current_node.end_byte, end_byte)

        if node_start_in_span < node_end_in_span: # Ensure there's actual overlap

            # Check if the node itself is a configured identifier type
            if current_node.type in config_identifier_types:
                node_text = current_node.text.decode('utf-8', errors='ignore')
                # Skip empty identifiers and common keywords
                if node_text and not node_text.isspace() and node_text not in processed_identifiers:
                    identifiers.add(node_text)
                    processed_identifiers.add(node_text)

            # Special handling for member access (e.g., obj.prop) - capture object and property
            # If the member access node itself overlaps the span, try to add both parts if they are identifiers.
            if current_node.type in member_access_types:
                 # Add the object part if it's an identifier
                 object_node = current_node.child_by_field_name('object')
                 if object_node and object_node.type in config_identifier_types:
                     object_text = object_node.text.decode('utf-8', errors='ignore')
                     if object_text and not object_text.isspace() and object_text not in processed_identifiers:
                         identifiers.add(object_text)
                         processed_identifiers.add(object_text)

                 # Add the property/attribute part if it's an identifier
                 property_node = current_node.child_by_field_name('property') or \
                                 current_node.child_by_field_name('attribute') or \
                                 current_node.child_by_field_name('field')
                 if property_node and property_node.type in config_identifier_types:
                     property_text = property_node.text.decode('utf-8', errors='ignore')
                     if property_text and not property_text.isspace() and property_text not in processed_identifiers:
                         identifiers.add(property_text)
                         processed_identifiers.add(property_text)
                 # Fallback for property if not in config_identifier_types but is 'identifier'
                 elif property_node and property_node.type == 'identifier':
                      property_text = property_node.text.decode('utf-8', errors='ignore')
                      if property_text and not property_text.isspace() and property_text not in processed_identifiers:
                          identifiers.add(property_text)
                          processed_identifiers.add(property_text)

            # Traverse children only if they might overlap the span
            for child in current_node.children:
                # Check if child overlaps the span and hasn't been visited
                if child.id not in visited_node_ids and child.end_byte > start_byte and child.start_byte < end_byte:
                    queue.append(child)
                    visited_node_ids.add(child.id)

    return identifiers


# --- Import Filtering Logic ---

def _filter_imports_for_chunk(
    all_import_lines: list[str],
    all_import_nodes: list[Node],
    # chunk_node: Node | None, # No longer used directly
    chunk_byte_span: tuple[int, int], # Use the byte span instead
    root_node: Node, # Need root node for searching
    # ancestor_nodes: list[Node], # Not used for filtering anymore
    language_config: dict,
    code_bytes: bytes
) -> list[str]:
    """
    Filters the list of all import lines to include only those relevant to the
    identifiers found *within* the chunk's specific byte span.

    Args:
        all_import_lines: List of all import lines found in the file.
        all_import_nodes: List of tree-sitter nodes corresponding to the import lines.
        chunk_byte_span: Tuple (start_byte, end_byte) for the chunk.
        root_node: The root node of the parsed tree.
        language_config: Configuration dictionary for the language.
        code_bytes: The raw byte content of the source code file.

    Returns:
        A list of import line strings relevant to the chunk and its context.
    """
    # 1. Parse import nodes to map imported names to the original import line index
    # Map: imported_name -> set(index_in_all_import_lines)
    imported_names_to_line_indices: dict[str, set[int]] = defaultdict(set)
    # Map: index_in_all_import_lines -> set(imported_names)
    # line_index_to_imported_names: dict[int, set[str]] = defaultdict(set) # Not strictly needed for filtering logic

    # Get the valid import node types from the config
    valid_import_types = set(language_config.get("imports", []))
    # language = language_config.get("language_name", "unknown") # Get language name for internal logic if needed

    # Create a mapping from node ID to line index for easier lookup
    node_id_to_line_index: dict[int, int] = {node.id: i for i, node in enumerate(all_import_nodes)}

    for import_node in all_import_nodes:
        # Skip nodes that aren't considered imports by the config for this language
        if import_node.type not in valid_import_types:
            continue

        line_idx = node_id_to_line_index.get(import_node.id)
        if line_idx is None: continue # Should not happen

        imported_names_in_node = set()

        # --- Language-specific import parsing (now only runs for valid import types) ---
        # Note: The outer if/elif language == ... is removed, but the inner logic
        # still needs to differentiate based on node.type for languages with multiple import styles.

        # Python specific parsing
        if import_node.type == "import_statement": # Python 'import ...'
            try:
                for name_node in import_node.named_children:
                    if name_node.type == 'dotted_name':
                        first_identifier = name_node.child(0)
                        if first_identifier and first_identifier.type == 'identifier':
                            imported_names_in_node.add(get_node_text(first_identifier, code_bytes))
                    elif name_node.type == 'aliased_import':
                        alias_node = name_node.child_by_field_name('alias')
                        if alias_node:
                            imported_names_in_node.add(get_node_text(alias_node, code_bytes))
                    elif name_node.type == 'identifier':
                         imported_names_in_node.add(get_node_text(name_node, code_bytes))
            except Exception as e:
                print(f"Warning: Error parsing Python import_statement: {e}")

        elif import_node.type == "import_from_statement": # Python 'from ... import ...'
            try:
                # Find the node containing the imported names (could be import_list or wildcard_import)
                names_container = None
                for child in import_node.children:
                    if child.type in ['import_list', 'wildcard_import']:
                        names_container = child
                        break

                if names_container:
                    if names_container.type == 'wildcard_import':
                        imported_names_in_node.add("*") # Mark wildcard imports
                    elif names_container.type == 'import_list':
                        # Iterate through ALL children of the import_list to find identifiers
                        for item_node in names_container.children: # Use children instead of named_children
                             # Check for aliased imports first
                             if item_node.type == 'aliased_import':
                                 # Find the name node (could be identifier or dotted_name)
                                 name_part = item_node.child_by_field_name('name')
                                 alias_part = item_node.child_by_field_name('alias')
                                 if alias_part: # If there's an alias, that's the name in scope
                                     imported_names_in_node.add(get_node_text(alias_part, code_bytes))
                                 # If no alias, add the original name (less common in from imports but possible)
                                 elif name_part:
                                     imported_names_in_node.add(get_node_text(name_part, code_bytes))
                             # Handle direct identifiers or dotted names within the list
                             elif item_node.type in ['identifier', 'dotted_name']:
                                 name_text = get_node_text(item_node, code_bytes) # Get text
                                 imported_names_in_node.add(name_text)
            except Exception as e:
                logger.warning(f"Error parsing Python import_from_statement: {e}") # Use logger.warning

        # Javascript/Typescript specific parsing
        elif import_node.type in ["import_statement", "import_declaration"]: # JS/TS
            try:
                for child in import_node.named_children:
                    if child.type == "import_clause":
                        default_import = child.child_by_field_name("default")
                        if default_import:
                            imported_names_in_node.add(get_node_text(default_import, code_bytes))
                        named_imports = child.child_by_field_name("named_imports")
                        if named_imports:
                            for import_specifier in named_imports.named_children:
                                if import_specifier.type == "import_specifier":
                                    alias = import_specifier.child_by_field_name("alias")
                                    if alias:
                                        imported_names_in_node.add(get_node_text(alias, code_bytes))
                                    else:
                                        name = import_specifier.child_by_field_name("name")
                                        if name:
                                            imported_names_in_node.add(get_node_text(name, code_bytes))
                        namespace_import = child.child_by_field_name("namespace_import")
                        if namespace_import:
                            name = namespace_import.child_by_field_name("name")
                            if name:
                                imported_names_in_node.add(get_node_text(name, code_bytes))
            except Exception as e:
                logger.warning(f"Error parsing JS/TS import: {e}") # Use logger.warning

        elif import_node.type == "lexical_declaration": # JS/TS require()
            try:
                for declaration in import_node.named_children:
                    if declaration.type == "variable_declarator":
                        name = declaration.child_by_field_name("name")
                        value = declaration.child_by_field_name("value")
                        if name and value and value.type == "call_expression":
                            function_name = value.child_by_field_name("function")
                            if function_name and get_node_text(function_name, code_bytes) == "require":
                                imported_names_in_node.add(get_node_text(name, code_bytes))
            except Exception as e:
                logger.warning(f"Error parsing JS/TS require statement: {e}") # Use logger.warning

        # Java specific parsing
        elif import_node.type == "import_declaration": # Java
            try:
                name = import_node.child_by_field_name("name")
                if name:
                    qualified_name = get_node_text(name, code_bytes)
                    last_dot = qualified_name.rfind('.')
                    if last_dot != -1:
                        imported_names_in_node.add(qualified_name[last_dot + 1:])
                    else:
                        imported_names_in_node.add(qualified_name)
            except Exception as e:
                logger.warning(f"Error parsing Java import declaration: {e}") # Use logger.warning

        # C / C++ specific parsing
        elif import_node.type == "preproc_include": # C/C++
            try:
                path = import_node.child_by_field_name("path")
                if path:
                    header_path = get_node_text(path, code_bytes)
                    # Extract just the filename without extension (simple heuristic)
                    header_name = header_path.split('/')[-1].split('.')[0].strip('<>"')
                    if header_name: # Avoid adding empty strings if parsing fails
                        imported_names_in_node.add(header_name)
            except Exception as e:
                logger.warning(f"Error parsing C/C++ include directive: {e}") # Use logger.warning

        elif import_node.type == "preproc_def": # C/C++
            try:
                name = import_node.child_by_field_name("name")
                if name:
                    imported_names_in_node.add(get_node_text(name, code_bytes))
            except Exception as e:
                logger.warning(f"Error parsing C/C++ preprocessor definition: {e}") # Use logger.warning

        # Go specific parsing
        elif import_node.type == "import_declaration": # Go
            # This block already has try...except from previous step
            try:
                for spec in import_node.named_children:
                    if spec.type == "import_spec":
                        name = spec.child_by_field_name("name")
                        if name:
                            imported_names_in_node.add(get_node_text(name, code_bytes))
                        else:
                            path = spec.child_by_field_name("path")
                            if path:
                                package_path = get_node_text(path, code_bytes).strip('"')
                                package_name = package_path.split('/')[-1]
                                imported_names_in_node.add(package_name)
            except Exception as e:
                logger.warning(f"Error parsing Go import declaration: {e}") # Use logger.warning

        # Ruby specific parsing
        elif import_node.type in ["require_statement", "load_statement"]: # Ruby
            # This block already has try...except from previous step
            try:
                argument = import_node.child(1)
                if argument:
                    module_path = get_node_text(argument, code_bytes).strip('"\'')
                    module_name = module_path.split('/')[-1].split('.')[0]
                    imported_names_in_node.add(module_name)
            except Exception as e:
                logger.warning(f"Error parsing Ruby require/load statement: {e}") # Use logger.warning

        # Rust specific parsing
        elif import_node.type == "use_declaration": # Rust
            # This block already has try...except from previous step
            try:
                tree_path = import_node.child_by_field_name("path")
                if tree_path:
                    path_text = get_node_text(tree_path, code_bytes)
                    segments = path_text.split('::')
                    if segments:
                        imported_names_in_node.add(segments[-1])

                use_tree_list = None
                for child in import_node.named_children:
                    if child.type == "use_tree_list":
                        use_tree_list = child
                        break

                if use_tree_list:
                    for use_tree in use_tree_list.named_children:
                        if use_tree.type == "use_tree":
                            path = use_tree.child_by_field_name("path")
                            if path:
                                imported_names_in_node.add(get_node_text(path, code_bytes))
            except Exception as e:
                logger.warning(f"Error parsing Rust use declaration: {e}") # Use logger.warning

        # PHP specific parsing
        elif import_node.type == "use_declaration": # PHP
            # This block already has try...except from previous step
            try:
                for clause in import_node.named_children:
                    if clause.type == "use_clause":
                        name = clause.child_by_field_name("name")
                        alias = clause.child_by_field_name("alias")
                        if alias:
                            imported_names_in_node.add(get_node_text(alias, code_bytes))
                        elif name:
                            qualified_name = get_node_text(name, code_bytes)
                            last_backslash = qualified_name.rfind('\\')
                            if last_backslash != -1:
                                imported_names_in_node.add(qualified_name[last_backslash + 1:])
                            else:
                                imported_names_in_node.add(qualified_name)
            except Exception as e:
                logger.warning(f"Error parsing PHP use declaration: {e}") # Use logger.warning

        elif import_node.type in ["include_expression", "require_expression"]: # PHP
            # These are hard to analyze statically, often using variables.
            # Mark as wildcard to indicate potential dependencies.
            imported_names_in_node.add("*")

        # --- End Language-specific parsing ---

        # Map the found names to the line index
        for name in imported_names_in_node:
            imported_names_to_line_indices[name].add(line_idx)
            # line_index_to_imported_names[line_idx].add(name) # Not needed here


    # 2. Find identifiers used ONLY within the current chunk's byte span
    start_byte, end_byte = chunk_byte_span
    used_identifiers = _find_identifiers_in_span(
        root_node=root_node,
        start_byte=start_byte,
        end_byte=end_byte,
        language_config=language_config
    )
    # print(f"Chunk Span ({start_byte}-{end_byte}): Found identifiers: {used_identifiers}") # Optional debug

    # 3. Match used identifiers against imported names
    relevant_line_indices = set()
    has_wildcard_import = False
    if "*" in imported_names_to_line_indices:
        has_wildcard_import = True
        # Always include the line that caused the wildcard import
        relevant_line_indices.update(imported_names_to_line_indices["*"])
        
        # CURRENT LIMITATION: We include ALL imports when a wildcard is present
        # When we encounter a wildcard import (e.g., "from module import *" or PHP's "include"),
        # we currently include ALL import lines as a safety measure since we cannot statically
        # determine exactly which names are brought into scope.
        #
        # Future improvements could include:
        # 1. More selective inclusion based on module analysis
        # 2. Heuristic-based filtering using common module patterns
        # 3. Integration with language-specific module introspection
        relevant_line_indices.update(range(len(all_import_lines)))


    # If no wildcard, filter based on specific identifiers
    if not has_wildcard_import:
        for identifier in used_identifiers:
            if identifier in imported_names_to_line_indices:
                relevant_line_indices.update(imported_names_to_line_indices[identifier])

    # 4. Return only the relevant import lines, sorted by original order
    filtered_lines = [all_import_lines[i] for i in sorted(list(relevant_line_indices))]

    return filtered_lines
