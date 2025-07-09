"""
Span and ChunkData classes for Code Navigator.

This module contains the core data structures for representing code chunks.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Span:
    """
    Represents a span of code with start and end positions.
    
    Spans track start and end positions in the source code and can be
    combined, measured, and manipulated easily.
    """
    start: int = 0
    end: int = 0

    def __post_init__(self):
        if self.end is None:
            self.end = self.start
        self.end = max(self.start, self.end)

    def extract_bytes(self, code_bytes: bytes) -> bytes:
        """Extract bytes from the span."""
        start_byte = max(0, min(self.start, len(code_bytes)))
        end_byte = max(start_byte, min(self.end, len(code_bytes)))
        return code_bytes[start_byte:end_byte]

    def extract_lines(self, s: str) -> str:
        """Extract lines from the span."""
        lines = s.splitlines()
        end = min(self.end, len(lines))
        start = min(self.start, end)
        if start == end:
            return ""
        extracted = "\n".join(lines[start:end])
        if s.endswith('\n') and end == len(lines):
            extracted += '\n'
        return extracted

    def __add__(self, other: Span) -> Span:
        """Combine two spans."""
        if isinstance(other, Span):
            new_start = min(self.start, other.start)
            new_end = max(self.end, other.end)
            return Span(new_start, new_end)
        else:
            raise NotImplementedError("Can only add Span to Span")

    def __len__(self) -> int:
        """Get the length of the span."""
        return self.end - self.start


@dataclass
class ChunkData:
    """
    Represents a chunk of code with content and metadata.
    
    ChunkData objects are the final output of the chunking process and
    contain both the code content and associated metadata.
    """
    content: str
    metadata: dict = field(default_factory=dict)
