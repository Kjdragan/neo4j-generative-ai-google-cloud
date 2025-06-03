#!/usr/bin/env python
"""
Document AI processor module for the Neo4j Generative AI Google Cloud project.

This module provides functionality for processing documents using Google Cloud's
Document AI service. It supports various document types and sources.
"""

import os
import base64
import json
from enum import Enum
from typing import Dict, List, Optional, Union, BinaryIO, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import urlparse
import tempfile
import logging
import time

from google.cloud import documentai_v1 as documentai
from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError, RetryError, ResourceExhausted

from ..utils import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DocumentSource(Enum):
    """Enum for document source types."""
    LOCAL_FILE = "local_file"
    GCS_BUCKET = "gcs_bucket"
    URL = "url"
    BASE64 = "base64"


class DocumentType(Enum):
    """Enum for document types."""
    FORM = "form"
    GENERAL = "general"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    SEC_FILING = "sec_filing"
    LEGAL = "legal"
    UNKNOWN = "unknown"


@dataclass
class DocumentMetadata:
    """Metadata for a document."""
    source_type: DocumentSource
    source_path: str
    mime_type: Optional[str] = None
    document_type: Optional[DocumentType] = None
    size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    created_at: Optional[str] = None
    filename: Optional[str] = None


class DocumentAIProcessor:
    """Class for processing documents using Document AI."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        timeout: int = 300,
    ):
        """
        Initialize the Document AI processor.
        
        Args:
            project_id: GCP project ID (defaults to config.GCP_PROJECT_ID)
            location: GCP location (defaults to config.GCP_LOCATION)
            timeout: Timeout for Document AI operations in seconds
        """
        self.project_id = project_id or config.GCP_PROJECT_ID
        self.location = location or config.GCP_LOCATION
        self.timeout = timeout
        
        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID must be set in environment or provided")
        
        # Initialize Document AI client
        self.client = documentai.DocumentProcessorServiceClient()
        
        # Initialize storage client for GCS operations
        self.storage_client = storage.Client(project=self.project_id)
        
        # Cache for processor instances
        self._processor_cache = {}
        
        logger.info(f"Initialized DocumentAIProcessor with project_id={self.project_id}, location={self.location}")

    def get_processor_path(self, processor_id: str) -> str:
        """
        Get the full resource path for a Document AI processor.
        
        Args:
            processor_id: The processor ID
            
        Returns:
            The full resource path for the processor
        """
        return self.client.processor_path(
            project=self.project_id,
            location=self.location,
            processor=processor_id
        )
    
    def detect_document_type(self, content: bytes, mime_type: str) -> DocumentType:
        """
        Detect the document type based on content analysis.
        
        Args:
            content: The document content as bytes
            mime_type: The MIME type of the document
            
        Returns:
            The detected document type
        """
        # TODO: Implement intelligent document type detection
        # This could use a combination of:
        # 1. MIME type analysis
        # 2. Content structure analysis
        # 3. ML-based classification
        # 4. Keyword/pattern matching
        
        # For now, use a simple heuristic based on content
        content_sample = content[:5000].decode('utf-8', errors='ignore').lower()
        
        # Check for SEC filing indicators
        if 'form 13d' in content_sample or 'schedule 13d' in content_sample:
            return DocumentType.SEC_FILING
        
        # Check for invoice indicators
        if 'invoice' in content_sample and ('total' in content_sample or 'amount due' in content_sample):
            return DocumentType.INVOICE
        
        # Check for receipt indicators
        if 'receipt' in content_sample and ('total' in content_sample or 'amount' in content_sample):
            return DocumentType.RECEIPT
        
        # Check for legal document indicators
        if 'agreement' in content_sample or 'contract' in content_sample or 'terms and conditions' in content_sample:
            return DocumentType.LEGAL
        
        # Default to general type
        return DocumentType.GENERAL
    
    def get_processor_for_document_type(self, document_type: DocumentType) -> str:
        """
        Get the appropriate processor ID for a document type.
        
        Args:
            document_type: The document type
            
        Returns:
            The processor ID for the document type
        """
        processor_map = {
            DocumentType.FORM: config.get_docai_processor_id("form"),
            DocumentType.INVOICE: config.get_docai_processor_id("form"),  # Use form processor for invoices
            DocumentType.RECEIPT: config.get_docai_processor_id("form"),  # Use form processor for receipts
            DocumentType.SEC_FILING: config.get_docai_processor_id("form"),  # Use form processor for SEC filings
            DocumentType.LEGAL: config.get_docai_processor_id("ocr"),  # Use OCR processor for legal docs
            DocumentType.GENERAL: config.get_docai_processor_id("ocr"),  # Use OCR processor for general docs
            DocumentType.UNKNOWN: config.get_docai_processor_id("ocr"),  # Default to OCR processor
        }
        
        processor_id = processor_map.get(document_type)
        if not processor_id:
            # Fall back to OCR processor if specific processor not configured
            processor_id = config.get_docai_processor_id("ocr")
            
        if not processor_id:
            raise ValueError(f"No processor configured for document type {document_type}")
            
        return processor_id
    
    def process_document(
        self,
        source: str,
        source_type: Union[DocumentSource, str],
        mime_type: Optional[str] = None,
        document_type: Optional[Union[DocumentType, str]] = None,
        processor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a document using Document AI.
        
        Args:
            source: The document source (file path, URL, GCS URI, or base64 string)
            source_type: The type of source (DocumentSource enum or string)
            mime_type: The MIME type of the document (optional, will be detected if not provided)
            document_type: The document type (DocumentType enum or string, optional)
            processor_id: Specific processor ID to use (optional, will be selected based on document_type if not provided)
            
        Returns:
            The processed document data
        """
        # Convert string source_type to enum if needed
        if isinstance(source_type, str):
            source_type = DocumentSource(source_type)
            
        # Convert string document_type to enum if needed
        if isinstance(document_type, str) and document_type:
            document_type = DocumentType(document_type)
        
        # Get document content and metadata
        content, metadata = self._get_document_content(source, source_type, mime_type)
        
        # Detect document type if not provided
        if not document_type:
            document_type = self.detect_document_type(content, metadata.mime_type)
            metadata.document_type = document_type
            
        # Get processor ID if not provided
        if not processor_id:
            processor_id = self.get_processor_for_document_type(document_type)
            
        # Process the document
        processor_path = self.get_processor_path(processor_id)
        
        # Create document object
        document = documentai.Document(
            content=content,
            mime_type=metadata.mime_type,
        )
        
        # Create process request
        request = documentai.ProcessRequest(
            name=processor_path,
            document=document,
        )
        
        # Process document with exponential backoff retry
        max_retries = 5
        base_delay = 2  # seconds
        for attempt in range(max_retries):
            try:
                logger.info(f"Processing document with processor {processor_id} (attempt {attempt+1}/{max_retries})")
                response = self.client.process_document(request=request, timeout=self.timeout)
                break
            except (GoogleAPIError, RetryError, ResourceExhausted) as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to process document after {max_retries} attempts: {e}")
                    raise
                
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Error processing document: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
        
        # Extract document data
        document = response.document
        
        # Convert Document AI response to dictionary
        result = self._document_to_dict(document, metadata)
        
        return result
    
    def _get_document_content(
        self,
        source: str,
        source_type: DocumentSource,
        mime_type: Optional[str] = None,
    ) -> Tuple[bytes, DocumentMetadata]:
        """
        Get document content and metadata from various sources.
        
        Args:
            source: The document source (file path, URL, GCS URI, or base64 string)
            source_type: The type of source
            mime_type: The MIME type of the document (optional)
            
        Returns:
            Tuple of (document content as bytes, document metadata)
        """
        content = None
        metadata = DocumentMetadata(
            source_type=source_type,
            source_path=source,
            mime_type=mime_type,
        )
        
        if source_type == DocumentSource.LOCAL_FILE:
            # Load from local file
            file_path = Path(source)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {source}")
                
            with open(file_path, "rb") as f:
                content = f.read()
                
            # Set metadata
            metadata.size_bytes = file_path.stat().st_size
            metadata.filename = file_path.name
            
            # Detect MIME type if not provided
            if not mime_type:
                import mimetypes
                metadata.mime_type = mimetypes.guess_type(source)[0] or "application/octet-stream"
                
        elif source_type == DocumentSource.GCS_BUCKET:
            # Load from GCS bucket
            if not source.startswith("gs://"):
                raise ValueError(f"Invalid GCS URI: {source}. Must start with 'gs://'")
                
            # Parse GCS URI
            bucket_name = source.split("/")[2]
            blob_name = "/".join(source.split("/")[3:])
            
            # Get blob
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # Download content
            content = blob.download_as_bytes()
            
            # Set metadata
            metadata.size_bytes = blob.size
            metadata.filename = Path(blob_name).name
            metadata.created_at = blob.time_created.isoformat() if blob.time_created else None
            
            # Detect MIME type if not provided
            if not mime_type:
                metadata.mime_type = blob.content_type or "application/octet-stream"
                
        elif source_type == DocumentSource.URL:
            # Load from URL
            import requests
            response = requests.get(source, stream=True)
            response.raise_for_status()
            
            content = response.content
            
            # Set metadata
            metadata.size_bytes = len(content)
            metadata.filename = Path(urlparse(source).path).name
            
            # Get MIME type from response headers or use provided value
            if not mime_type:
                metadata.mime_type = response.headers.get("content-type", "application/octet-stream")
                
        elif source_type == DocumentSource.BASE64:
            # Decode base64 content
            try:
                content = base64.b64decode(source)
                metadata.size_bytes = len(content)
                
                # Use provided MIME type or default
                if not mime_type:
                    metadata.mime_type = "application/octet-stream"
                    
            except Exception as e:
                raise ValueError(f"Invalid base64 content: {e}")
                
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
            
        # Ensure we have content
        if not content:
            raise ValueError(f"Failed to get content from {source}")
            
        # Ensure we have a MIME type
        if not metadata.mime_type:
            metadata.mime_type = "application/octet-stream"
            
        return content, metadata
    
    def _document_to_dict(self, document: documentai.Document, metadata: DocumentMetadata) -> Dict[str, Any]:
        """
        Convert a Document AI document to a dictionary.
        
        Args:
            document: The Document AI document
            metadata: Document metadata
            
        Returns:
            Dictionary representation of the document
        """
        # Extract text from document
        text = document.text
        
        # Extract entities
        entities = []
        for entity in document.entities:
            entity_dict = {
                "type": entity.type_,
                "mention_text": text[entity.mention_text.begin_index:entity.mention_text.end_index],
                "confidence": entity.confidence,
                "properties": [],
            }
            
            # Extract entity properties
            for prop in entity.properties:
                prop_dict = {
                    "type": prop.type_,
                    "mention_text": text[prop.mention_text.begin_index:prop.mention_text.end_index],
                    "confidence": prop.confidence,
                }
                entity_dict["properties"].append(prop_dict)
                
            entities.append(entity_dict)
        
        # Extract pages
        pages = []
        for page in document.pages:
            page_dict = {
                "page_number": page.page_number,
                "width": page.dimension.width,
                "height": page.dimension.height,
                "blocks": [],
                "tables": [],
                "form_fields": [],
            }
            
            # Extract blocks
            for block in page.blocks:
                block_dict = {
                    "layout": self._layout_to_dict(block.layout, text),
                    "confidence": block.confidence,
                }
                page_dict["blocks"].append(block_dict)
            
            # Extract tables
            for table in page.tables:
                table_dict = {
                    "layout": self._layout_to_dict(table.layout, text),
                    "confidence": table.confidence,
                    "header_rows": table.header_rows,
                    "body_rows": [],
                }
                
                # Extract rows
                for row in table.body_rows:
                    row_dict = {
                        "cells": [],
                    }
                    
                    # Extract cells
                    for cell in row.cells:
                        cell_dict = {
                            "layout": self._layout_to_dict(cell.layout, text),
                            "row_span": cell.row_span,
                            "col_span": cell.col_span,
                            "text": text[cell.layout.text_anchor.text_segments[0].start_index:cell.layout.text_anchor.text_segments[0].end_index] if cell.layout.text_anchor.text_segments else "",
                        }
                        row_dict["cells"].append(cell_dict)
                        
                    table_dict["body_rows"].append(row_dict)
                    
                page_dict["tables"].append(table_dict)
            
            # Extract form fields
            for form_field in page.form_fields:
                field_dict = {
                    "name": {
                        "text": text[form_field.field_name.text_anchor.text_segments[0].start_index:form_field.field_name.text_anchor.text_segments[0].end_index] if form_field.field_name.text_anchor.text_segments else "",
                        "confidence": form_field.field_name.confidence,
                    },
                    "value": {
                        "text": text[form_field.field_value.text_anchor.text_segments[0].start_index:form_field.field_value.text_anchor.text_segments[0].end_index] if form_field.field_value.text_anchor.text_segments else "",
                        "confidence": form_field.field_value.confidence,
                    },
                    "confidence": form_field.confidence,
                }
                page_dict["form_fields"].append(field_dict)
                
            pages.append(page_dict)
        
        # Create result dictionary
        result = {
            "text": text,
            "entities": entities,
            "pages": pages,
            "metadata": {
                "source_type": metadata.source_type.value,
                "source_path": metadata.source_path,
                "mime_type": metadata.mime_type,
                "document_type": metadata.document_type.value if metadata.document_type else None,
                "size_bytes": metadata.size_bytes,
                "page_count": len(document.pages),
                "created_at": metadata.created_at,
                "filename": metadata.filename,
            }
        }
        
        return result
    
    def _layout_to_dict(self, layout: documentai.Document.Page.Layout, text: str) -> Dict[str, Any]:
        """
        Convert a Document AI layout to a dictionary.
        
        Args:
            layout: The Document AI layout
            text: The document text
            
        Returns:
            Dictionary representation of the layout
        """
        # Extract text segments
        text_segments = []
        for segment in layout.text_anchor.text_segments:
            text_segments.append({
                "start_index": segment.start_index,
                "end_index": segment.end_index,
                "text": text[segment.start_index:segment.end_index],
            })
        
        # Extract bounding poly
        bounding_poly = {
            "vertices": [
                {"x": vertex.x, "y": vertex.y}
                for vertex in layout.bounding_poly.vertices
            ]
        }
        
        # Create layout dictionary
        layout_dict = {
            "text_anchor": {
                "text_segments": text_segments,
            },
            "bounding_poly": bounding_poly,
            "confidence": layout.confidence,
        }
        
        return layout_dict


class ProcessorFactory:
    """Factory for creating Document AI processors based on document type."""
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
    ):
        """
        Initialize the processor factory.
        
        Args:
            project_id: GCP project ID (defaults to config.GCP_PROJECT_ID)
            location: GCP location (defaults to config.GCP_LOCATION)
        """
        self.project_id = project_id or config.GCP_PROJECT_ID
        self.location = location or config.GCP_LOCATION
        
        # Initialize the base DocumentAIProcessor
        self.base_processor = DocumentAIProcessor(
            project_id=self.project_id,
            location=self.location,
        )
        
        # Cache for specialized processors
        self._processor_cache = {}
    
    def get_processor(self, document_type: Union[DocumentType, str]) -> DocumentAIProcessor:
        """
        Get a Document AI processor for a specific document type.
        
        Args:
            document_type: The document type
            
        Returns:
            A Document AI processor configured for the document type
        """
        # Convert string to enum if needed
        if isinstance(document_type, str):
            document_type = DocumentType(document_type)
            
        # Return cached processor if available
        if document_type in self._processor_cache:
            return self._processor_cache[document_type]
            
        # Use the base processor for now
        # In the future, we could create specialized processor subclasses for different document types
        processor = self.base_processor
        
        # Cache the processor
        self._processor_cache[document_type] = processor
        
        return processor
    
    def process_document(
        self,
        source: str,
        source_type: Union[DocumentSource, str],
        mime_type: Optional[str] = None,
        document_type: Optional[Union[DocumentType, str]] = None,
        processor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a document using the appropriate processor.
        
        Args:
            source: The document source (file path, URL, GCS URI, or base64 string)
            source_type: The type of source (DocumentSource enum or string)
            mime_type: The MIME type of the document (optional, will be detected if not provided)
            document_type: The document type (DocumentType enum or string, optional)
            processor_id: Specific processor ID to use (optional, will be selected based on document_type if not provided)
            
        Returns:
            The processed document data
        """
        # Convert string source_type to enum if needed
        if isinstance(source_type, str):
            source_type = DocumentSource(source_type)
            
        # Get document content to detect type if not provided
        if not document_type:
            # Get document content and detect type
            content, metadata = self.base_processor._get_document_content(source, source_type, mime_type)
            document_type = self.base_processor.detect_document_type(content, metadata.mime_type)
        elif isinstance(document_type, str):
            # Convert string to enum
            document_type = DocumentType(document_type)
            
        # Get the appropriate processor
        processor = self.get_processor(document_type)
        
        # Process the document
        return processor.process_document(
            source=source,
            source_type=source_type,
            mime_type=mime_type,
            document_type=document_type,
            processor_id=processor_id,
        )
