#!/usr/bin/env python
"""
Text Chunking Module for Document Processing Pipeline

This module provides intelligent text chunking based on semantic boundaries
with enhanced context preservation across chunks. It integrates with the
existing text_embedding.py module for vector embeddings.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple

class TextChunker:
    """Handles intelligent text chunking with semantic boundary detection."""
    
    def __init__(self, 
                 chunk_size: int = 1000, 
                 chunk_overlap: int = 200,
                 respect_semantic_boundaries: bool = True):
        """
        Initialize the text chunker with configurable parameters.
        
        Args:
            chunk_size: Target size for each text chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            respect_semantic_boundaries: Whether to adjust chunk boundaries to respect
                                         semantic units like paragraphs and sentences
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.respect_semantic_boundaries = respect_semantic_boundaries
        self.logger = logging.getLogger(__name__)
    
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into chunks with semantic boundary awareness.
        
        Args:
            text: The input text to be chunked
            
        Returns:
            List of dictionaries containing:
            - text: The chunk text
            - metadata: Dictionary with chunk information (index, start_char, end_char)
        """
        if not text:
            self.logger.warning("Empty text provided for chunking")
            return []
        
        # First split by paragraphs to preserve semantic units
        paragraphs = self._split_paragraphs(text)
        
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_index = 0
        
        for para in paragraphs:
            # If adding this paragraph would exceed chunk size and we already have content
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                # Add the current chunk to our results
                chunks.append({
                    "text": current_chunk,
                    "metadata": {
                        "chunk_index": chunk_index,
                        "start_char": current_start,
                        "end_char": current_start + len(current_chunk)
                    }
                })
                
                # Start a new chunk with overlap
                if self.respect_semantic_boundaries:
                    # Find a good sentence boundary for the overlap
                    overlap_text = current_chunk[-self.chunk_overlap:] if self.chunk_overlap < len(current_chunk) else current_chunk
                    sentence_boundary = self._find_last_sentence_boundary(overlap_text)
                    overlap_point = len(current_chunk) - (len(overlap_text) - sentence_boundary) if sentence_boundary > 0 else max(0, len(current_chunk) - self.chunk_overlap)
                    current_chunk = current_chunk[overlap_point:]
                else:
                    # Simple character-based overlap
                    overlap_point = max(0, len(current_chunk) - self.chunk_overlap)
                    current_chunk = current_chunk[overlap_point:]
                
                current_start += overlap_point
                chunk_index += 1
            
            # Add the paragraph to the current chunk
            current_chunk += para
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append({
                "text": current_chunk,
                "metadata": {
                    "chunk_index": chunk_index,
                    "start_char": current_start,
                    "end_char": current_start + len(current_chunk)
                }
            })
        
        self.logger.info(f"Split text into {len(chunks)} chunks")
        return chunks
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs, preserving paragraph breaks.
        
        Args:
            text: The input text
            
        Returns:
            List of paragraph strings with their original formatting
        """
        # Split on double newlines (common paragraph separator)
        paragraphs = re.split(r'(\n\s*\n)', text)
        
        # Recombine the paragraphs with their separators
        result = []
        for i in range(0, len(paragraphs), 2):
            para = paragraphs[i]
            separator = paragraphs[i+1] if i+1 < len(paragraphs) else ""
            result.append(para + separator)
        
        return result
    
    def _find_last_sentence_boundary(self, text: str) -> int:
        """
        Find the last sentence boundary in a text.
        
        Args:
            text: The text to analyze
            
        Returns:
            Character position of the last sentence boundary
        """
        # Common sentence-ending punctuation followed by space or newline
        matches = list(re.finditer(r'[.!?](?:\s|$)', text))
        if matches:
            return matches[-1].end()
        return 0
    
    def get_chunk_with_context(self, chunks: List[Dict[str, Any]], chunk_index: int, 
                             context_window: int = 1) -> Dict[str, Any]:
        """
        Get a chunk with surrounding context from adjacent chunks.
        
        Args:
            chunks: List of chunk dictionaries from chunk_text()
            chunk_index: Index of the target chunk
            context_window: Number of chunks to include before and after
            
        Returns:
            Dictionary with:
            - text: The chunk text with context
            - metadata: Updated metadata including context information
        """
        if not chunks or chunk_index < 0 or chunk_index >= len(chunks):
            self.logger.error(f"Invalid chunk index: {chunk_index}")
            return {"text": "", "metadata": {}}
        
        target_chunk = chunks[chunk_index]
        
        # Calculate context range
        start_idx = max(0, chunk_index - context_window)
        end_idx = min(len(chunks) - 1, chunk_index + context_window)
        
        # Collect context chunks
        context_before = [chunks[i]["text"] for i in range(start_idx, chunk_index)]
        context_after = [chunks[i]["text"] for i in range(chunk_index + 1, end_idx + 1)]
        
        # Create combined text with markers
        combined_text = ""
        if context_before:
            combined_text += "[CONTEXT_BEFORE] " + " ".join(context_before) + " [/CONTEXT_BEFORE]\n\n"
        
        combined_text += target_chunk["text"]
        
        if context_after:
            combined_text += "\n\n[CONTEXT_AFTER] " + " ".join(context_after) + " [/CONTEXT_AFTER]"
        
        # Create updated metadata
        metadata = target_chunk["metadata"].copy()
        metadata.update({
            "has_context": bool(context_before or context_after),
            "context_window": context_window,
            "context_chunks_before": list(range(start_idx, chunk_index)) if start_idx < chunk_index else [],
            "context_chunks_after": list(range(chunk_index + 1, end_idx + 1)) if chunk_index < end_idx else []
        })
        
        return {"text": combined_text, "metadata": metadata}
