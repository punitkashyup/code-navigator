"""
Core functionality for Code Navigator.

This package contains the core components for code chunking and processing.
"""

from .span import Span, ChunkData
from .splitter import create_byte_spans, process_code_for_rag
from .language_config import LANGUAGE_NODE_TYPES
from .utils import (
    non_whitespace_len,
    get_line_number,
    get_node_text,
    get_node_start_column,
    get_byte_offset
)
from .processor import split_code, split_code_async

__all__ = [
    'Span',
    'ChunkData',
    'create_byte_spans',
    'process_code_for_rag',
    'LANGUAGE_NODE_TYPES',
    'non_whitespace_len',
    'get_line_number',
    'get_node_text',
    'get_node_start_column',
    'get_byte_offset',
    'split_code',
    'split_code_async'
]
