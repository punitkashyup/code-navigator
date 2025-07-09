"""
Utility functions for Code Navigator.

This module contains utility functions for working with code and ASTs.
"""

import re
from tree_sitter import Node


def non_whitespace_len(s: str) -> int:
    """
    Calculate the length of a string excluding whitespace.
    
    Args:
        s: The string to measure.
        
    Returns:
        The number of non-whitespace characters.
    """
    return len(re.sub(r"\s", "", s))


def get_line_number(index: int, source_code: str) -> int:
    """
    Convert a byte index to a line number.
    
    Args:
        index: The byte index.
        source_code: The source code string.
        
    Returns:
        The line number (0-based).
    """
    lines = source_code.splitlines(keepends=True)
    total_bytes = 0
    encoded_lines = [line.encode('utf-8', errors='ignore') for line in lines]
    for line_number, line_bytes in enumerate(encoded_lines):
        total_bytes += len(line_bytes)
        if total_bytes > index:
            return line_number
    if index == total_bytes and lines:
        return len(lines) - 1
    return max(0, len(lines) - 1)


def get_node_text(node: Node, code_bytes: bytes) -> str:
    """
    Get the text of a node from the code bytes.
    
    Args:
        node: The tree-sitter node.
        code_bytes: The source code as bytes.
        
    Returns:
        The text of the node.
    """
    return code_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')


def get_node_start_column(node: Node) -> int:
    """
    Get the starting column of a node.
    
    Args:
        node: The tree-sitter node.
        
    Returns:
        The column number (0-based).
    """
    return node.start_point[1]


def get_byte_offset(line_num: int, source_lines: list[str]) -> int:
    """
    Calculate the byte offset for a line number.
    
    Args:
        line_num: The line number (0-based).
        source_lines: The source code lines.
        
    Returns:
        The byte offset.
    """
    if line_num < 0:
        return 0
    offset = 0
    for i in range(min(line_num, len(source_lines))):
        offset += len(source_lines[i].encode('utf-8', errors='ignore'))
        if i < len(source_lines) - 1:
            offset += len('\n'.encode('utf-8'))
    return offset


def get_indentation_level(line: str) -> str:
    """
    Get the leading whitespace (indentation) of a line.

    Args:
        line: The line of code.

    Returns:
        A string containing the leading whitespace characters.
    """
    return "".join(c for c in line if c.isspace())[:len(line) - len(line.lstrip(' '))]
