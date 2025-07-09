"""
Handles the formatting of chunk data into specified text formats
and structured data representations.
"""

PLACEHOLDER_TEXT = "#... some code ..."

def format_chunk_data(
    chunk_data_list: list[dict],
    include_tokens: bool = True # Add flag with default True
) -> tuple[str, list[dict]]:
    """
    Formats the list of chunk dictionaries into a full text representation
    (like chunked.txt or with placeholders) and a structured list suitable for JSON output.

    Args:
        chunk_data_list: A list of dictionaries, where each dictionary
                         contains the components of a chunk as returned by
                         process_code_for_rag (including metadata, import_lines,
                         parent_context_text, content, byte_span, etc.).
        include_tokens: If True, includes <<...>> tags and content. If False,
                        replaces content between first and last tag with a placeholder.

    Returns:
        A tuple containing:
        - full_formatted_text: A single string with all chunks formatted and
                               joined by separators. Format depends on include_tokens.
        - structured_data_list: A list of dictionaries, each representing a
                                chunk with its formatted block (reflecting include_tokens),
                                original content, and original metadata.
    """
    individual_formatted_blocks_for_output = [] # For the final text string AND JSON field
    structured_data_list = [] # For the JSON structure

    for chunk_dict in chunk_data_list:
        # --- Extract components from the input dictionary ---
        imports_list = chunk_dict.get("import_lines", [])
        parent_context_list = chunk_dict.get("parent_context_text", [])
        original_content = chunk_dict.get("content", "")
        metadata = chunk_dict.get("metadata", {}) # Keep original metadata

        # --- Prepare components ---
        imports = "\n".join(imports_list)
        content_for_comparison = original_content.lstrip('\n') # For comparison logic

        # --- New Logic: Check if first line of last parent block matches first line of content ---
        # --- and remove only that last parent block if it matches ---
        processed_parent_list = list(parent_context_list) # Create a mutable copy
        if processed_parent_list and content_for_comparison: # Check if list is not empty
            # Get the last block/string from the parent context list
            last_parent_block = processed_parent_list[-1]
            # Get the first line of this last parent block
            parent_block_lines = last_parent_block.splitlines()
            first_line_of_last_parent = parent_block_lines[0].strip() if parent_block_lines else ""

            # Get the first line of the original content
            content_lines = content_for_comparison.splitlines()
            first_content_line = content_lines[0].strip() if content_lines else ""

            # Check if stripped first lines match and are not empty
            if first_line_of_last_parent and first_line_of_last_parent == first_content_line:
                # Remove only the last parent block from the list
                processed_parent_list.pop()

        # --- Construct parent_context string from the (potentially modified) list ---
        if processed_parent_list:
            parent_context = ("\n#... some code ...\n").join(processed_parent_list)
        else:
            parent_context = "" # Set to empty if list becomes empty after removal

        # --- Build the fully tagged block first (always needed for reference or direct use) ---
        fully_tagged_parts = []
        if imports:
            fully_tagged_parts.append(f"<<IMPORTS_START>>\n{imports}\n<<IMPORTS_END>>")
        if parent_context: # Use potentially truncated context
            fully_tagged_parts.append(f"<<PARENT_CONTEXT_START>>\n{parent_context}\n<<PARENT_CONTEXT_END>>")
        content_to_format = original_content.lstrip('\n')
        if original_content.strip(): # Only add original content block if it's not just whitespace
            fully_tagged_parts.append(f"<<ORIGINAL_CHUNK_START>>\n{content_to_format}\n<<ORIGINAL_CHUNK_END>>")
        fully_tagged_formatted_block = "\n\n".join(fully_tagged_parts)

        # --- Determine the final formatted block based on include_tokens ---
        formatted_block_for_output: str
        if include_tokens:
            formatted_block_for_output = fully_tagged_formatted_block
        else:
            # Build intermediate list with placeholders and content
            intermediate_parts = []
            if imports:
                intermediate_parts.extend([PLACEHOLDER_TEXT, imports, PLACEHOLDER_TEXT])
            if parent_context:
                intermediate_parts.extend([PLACEHOLDER_TEXT, parent_context, PLACEHOLDER_TEXT])
            content_to_format = original_content.lstrip('\n')
            if original_content.strip(): # Use the same condition as for fully_tagged_parts
                intermediate_parts.extend([PLACEHOLDER_TEXT, content_to_format, PLACEHOLDER_TEXT])

            # Remove first and last tokens if list is not empty
            if intermediate_parts:
                intermediate_parts[0] = ""
                if len(intermediate_parts) > 1:
                    intermediate_parts[-1] = ""

            # Consolidate placeholders and filter empty strings
            final_parts = []
            for i, part in enumerate(intermediate_parts):
                if part == "":
                    continue # Skip empty strings
                # Skip consecutive placeholders
                if part == PLACEHOLDER_TEXT and final_parts and final_parts[-1] == PLACEHOLDER_TEXT:
                    continue
                final_parts.append(part)

            # Join the final parts with a single newline
            formatted_block_for_output = "\n".join(final_parts)

        individual_formatted_blocks_for_output.append(formatted_block_for_output)

        # --- Prepare the dictionary for the structured output list ---
        output_metadata = metadata.copy()
        # Ensure byte_span is removed from the final metadata output
        if "byte_span" in output_metadata:
            del output_metadata["byte_span"]

        structured_chunk_info = {
            "formatted_chunk_block": formatted_block_for_output, # Reflects include_tokens flag
            "original_content": original_content,
            "metadata": output_metadata
        }
        structured_data_list.append(structured_chunk_info)

    # Join the individual formatted blocks with the appropriate separator
    separator = "\n\n========== CHUNK SEPARATOR ==========\n\n" # Always use the full separator
    full_formatted_text = separator.join(individual_formatted_blocks_for_output)

    return full_formatted_text, structured_data_list
