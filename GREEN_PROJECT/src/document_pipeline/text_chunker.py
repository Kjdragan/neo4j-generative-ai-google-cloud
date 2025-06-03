#!/usr/bin/env python
"""
Text chunking module for the Neo4j Generative AI Google Cloud project.

This module provides functionality for splitting document text into chunks
for embedding and storage in Neo4j.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Union, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TextChunker:
    """Class for chunking document text into smaller pieces for embedding."""
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        chunk_strategy: str = "paragraph",
    ):
        """
        Initialize the TextChunker.
        
        Args:
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Overlap between chunks in characters
            chunk_strategy: Chunking strategy (paragraph, sentence, fixed, or token)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_strategy = chunk_strategy
        
        # Validate chunk_strategy
        valid_strategies = ["paragraph", "sentence", "fixed", "token"]
        if chunk_strategy not in valid_strategies:
            raise ValueError(f"Invalid chunk strategy: {chunk_strategy}. Must be one of {valid_strategies}")
        
        # Validate chunk_size and chunk_overlap
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        
        logger.info(f"Initialized TextChunker with chunk_size={chunk_size}, "
                   f"chunk_overlap={chunk_overlap}, chunk_strategy={chunk_strategy}")
    
    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks based on the configured strategy.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk
            
        Returns:
            List of dictionaries containing chunk text and metadata
        """
        if not text:
            logger.warning("Empty text provided for chunking")
            return []
        
        # Select chunking strategy
        if self.chunk_strategy == "paragraph":
            chunks = self._chunk_by_paragraph(text)
        elif self.chunk_strategy == "sentence":
            chunks = self._chunk_by_sentence(text)
        elif self.chunk_strategy == "token":
            chunks = self._chunk_by_token(text)
        else:  # fixed
            chunks = self._chunk_by_fixed_size(text)
        
        # Add metadata to chunks
        result = []
        for i, chunk_text in enumerate(chunks):
            chunk_dict = {
                "text": chunk_text,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            
            # Add metadata if provided
            if metadata:
                # Create a copy of metadata to avoid modifying the original
                chunk_dict["metadata"] = {**metadata}
            
            result.append(chunk_dict)
        
        logger.info(f"Split text into {len(result)} chunks using {self.chunk_strategy} strategy")
        return result
    
    def _chunk_by_paragraph(self, text: str) -> List[str]:
        """
        Split text into chunks by paragraph boundaries.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        # Split text into paragraphs
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # If adding this paragraph would exceed chunk_size, save current chunk and start a new one
            if len(current_chunk) + len(paragraph) > self.chunk_size and current_chunk:
                chunks.append(current_chunk)
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk:
                    # Get the last part of the previous chunk for overlap
                    words = current_chunk.split()
                    overlap_word_count = min(len(words), self.chunk_overlap // 5)  # Approximate words in overlap
                    overlap_text = " ".join(words[-overlap_word_count:])
                    current_chunk = overlap_text
                else:
                    current_chunk = ""
            
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _chunk_by_sentence(self, text: str) -> List[str]:
        """
        Split text into chunks by sentence boundaries.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        # Split text into sentences
        # This is a simple sentence splitter; consider using nltk or spacy for better results
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence would exceed chunk_size, save current chunk and start a new one
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                chunks.append(current_chunk)
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk:
                    # Get the last part of the previous chunk for overlap
                    words = current_chunk.split()
                    overlap_word_count = min(len(words), self.chunk_overlap // 5)  # Approximate words in overlap
                    overlap_text = " ".join(words[-overlap_word_count:])
                    current_chunk = overlap_text
                else:
                    current_chunk = ""
            
            # Add sentence to current chunk
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _chunk_by_fixed_size(self, text: str) -> List[str]:
        """
        Split text into chunks of fixed size.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            # Calculate end position
            end = min(start + self.chunk_size, text_length)
            
            # If not at the end of text and not at a whitespace, move back to the last whitespace
            if end < text_length and not text[end].isspace():
                # Find the last whitespace within the chunk
                last_space = text.rfind(" ", start, end)
                if last_space > start:
                    end = last_space
            
            # Extract chunk
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position for next chunk, accounting for overlap
            start = end - self.chunk_overlap if self.chunk_overlap > 0 else end
            
            # Ensure we make progress even if overlap is large
            if start <= 0 or start >= end:
                start = end
        
        return chunks
    
    def _chunk_by_token(self, text: str) -> List[str]:
        """
        Split text into chunks based on approximate token count.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        # Split text into words as a simple approximation of tokens
        words = text.split()
        
        # Estimate average word length including space
        avg_word_length = len(text) / max(len(words), 1)
        
        # Estimate words per chunk based on chunk_size
        words_per_chunk = max(1, int(self.chunk_size / avg_word_length))
        
        # Estimate words in overlap
        overlap_words = max(0, int(self.chunk_overlap / avg_word_length))
        
        chunks = []
        i = 0
        
        while i < len(words):
            # Calculate end index for this chunk
            end = min(i + words_per_chunk, len(words))
            
            # Extract chunk
            chunk = " ".join(words[i:end])
            chunks.append(chunk)
            
            # Move to next chunk, accounting for overlap
            i = end - overlap_words if overlap_words > 0 else end
            
            # Ensure we make progress even if overlap is large
            if i <= 0 or i >= end:
                i = end
        
        return chunks
    
    def merge_small_chunks(
        self,
        chunks: List[Dict[str, Any]],
        min_chunk_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Merge small chunks to ensure minimum chunk size.
        
        Args:
            chunks: List of chunk dictionaries
            min_chunk_size: Minimum size of each chunk in characters
            
        Returns:
            List of merged chunk dictionaries
        """
        if not chunks:
            return []
        
        # Validate min_chunk_size
        if min_chunk_size <= 0:
            raise ValueError("min_chunk_size must be positive")
        if min_chunk_size > self.chunk_size:
            raise ValueError("min_chunk_size must not exceed chunk_size")
        
        merged_chunks = []
        current_chunk = None
        
        for chunk in chunks:
            if current_chunk is None:
                current_chunk = chunk.copy()
                continue
            
            # If current chunk is smaller than min_chunk_size, merge with next chunk
            if len(current_chunk["text"]) < min_chunk_size:
                # Merge text
                current_chunk["text"] += "\n" + chunk["text"]
                
                # Update metadata if present
                if "metadata" in current_chunk and "metadata" in chunk:
                    # For merged chunks, we keep the metadata from the first chunk
                    # but note that it's a merged chunk
                    current_chunk["metadata"]["merged"] = True
                    current_chunk["metadata"]["merged_with"] = chunk["chunk_index"]
            else:
                # Add current chunk to results and start a new one
                merged_chunks.append(current_chunk)
                current_chunk = chunk.copy()
        
        # Add the last chunk if it exists
        if current_chunk is not None:
            merged_chunks.append(current_chunk)
        
        # Update chunk indices
        for i, chunk in enumerate(merged_chunks):
            chunk["chunk_index"] = i
            chunk["total_chunks"] = len(merged_chunks)
        
        logger.info(f"Merged chunks: {len(chunks)} original chunks -> {len(merged_chunks)} merged chunks")
        return merged_chunks
    
    def extract_metadata_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Extract and consolidate metadata from chunks.
        
        Args:
            chunks: List of chunk dictionaries
            
        Returns:
            Consolidated metadata dictionary
        """
        if not chunks:
            return {}
        
        # Initialize with metadata from first chunk
        consolidated = {}
        for chunk in chunks:
            if "metadata" in chunk:
                for key, value in chunk["metadata"].items():
                    # Skip chunk-specific metadata
                    if key in ["chunk_index", "total_chunks", "merged", "merged_with"]:
                        continue
                    
                    # If key already exists in consolidated, append new value if different
                    if key in consolidated:
                        if isinstance(consolidated[key], list):
                            if value not in consolidated[key]:
                                consolidated[key].append(value)
                        elif consolidated[key] != value:
                            consolidated[key] = [consolidated[key], value]
                    else:
                        consolidated[key] = value
        
        return consolidated
