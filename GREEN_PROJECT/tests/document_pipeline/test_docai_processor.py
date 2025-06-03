#!/usr/bin/env python
"""
Tests for the Document AI processor module.

This module contains unit tests for the DocumentAIProcessor and ProcessorFactory classes.
"""

import os
import unittest
from unittest import mock
from pathlib import Path
import tempfile
import base64

from google.cloud import documentai_v1 as documentai

from src.document_pipeline.docai_processor import (
    DocumentAIProcessor,
    ProcessorFactory,
    DocumentSource,
    DocumentType,
    DocumentMetadata,
)
from src.utils import config


class TestDocumentAIProcessor(unittest.TestCase):
    """Test cases for the DocumentAIProcessor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the Document AI client
        self.mock_client_patcher = mock.patch(
            'google.cloud.documentai_v1.DocumentProcessorServiceClient'
        )
        self.mock_client = self.mock_client_patcher.start()
        
        # Mock the storage client
        self.mock_storage_patcher = mock.patch('google.cloud.storage.Client')
        self.mock_storage = self.mock_storage_patcher.start()
        
        # Create a processor with mocked clients
        self.processor = DocumentAIProcessor(
            project_id="test-project",
            location="us-central1",
        )
        
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(b"Test document content")
        self.temp_file.close()
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.mock_client_patcher.stop()
        self.mock_storage_patcher.stop()
        
        # Remove temporary file
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_init(self):
        """Test initialization of DocumentAIProcessor."""
        processor = DocumentAIProcessor(
            project_id="test-project",
            location="us-central1",
        )
        
        self.assertEqual(processor.project_id, "test-project")
        self.assertEqual(processor.location, "us-central1")
        self.assertEqual(processor.timeout, 300)  # Default timeout
        
        # Test with default values
        with mock.patch.object(config, 'GCP_PROJECT_ID', "default-project"):
            with mock.patch.object(config, 'GCP_LOCATION', "default-location"):
                processor = DocumentAIProcessor()
                
                self.assertEqual(processor.project_id, "default-project")
                self.assertEqual(processor.location, "default-location")
    
    def test_get_processor_path(self):
        """Test getting processor path."""
        processor_id = "test-processor-id"
        
        # Mock the client.processor_path method
        self.processor.client.processor_path.return_value = (
            "projects/test-project/locations/us-central1/processors/test-processor-id"
        )
        
        path = self.processor.get_processor_path(processor_id)
        
        self.assertEqual(
            path,
            "projects/test-project/locations/us-central1/processors/test-processor-id"
        )
        
        # Verify the client method was called with correct arguments
        self.processor.client.processor_path.assert_called_once_with(
            project="test-project",
            location="us-central1",
            processor=processor_id
        )
    
    def test_detect_document_type(self):
        """Test document type detection."""
        # Test SEC filing detection
        content = b"This is a Form 13D filing for the SEC."
        mime_type = "application/pdf"
        
        doc_type = self.processor.detect_document_type(content, mime_type)
        self.assertEqual(doc_type, DocumentType.SEC_FILING)
        
        # Test invoice detection
        content = b"INVOICE\nTotal: $100.00\nAmount due: $100.00"
        doc_type = self.processor.detect_document_type(content, mime_type)
        self.assertEqual(doc_type, DocumentType.INVOICE)
        
        # Test receipt detection
        content = b"RECEIPT\nTotal amount: $25.50"
        doc_type = self.processor.detect_document_type(content, mime_type)
        self.assertEqual(doc_type, DocumentType.RECEIPT)
        
        # Test legal document detection
        content = b"AGREEMENT\nTerms and Conditions\nThis contract..."
        doc_type = self.processor.detect_document_type(content, mime_type)
        self.assertEqual(doc_type, DocumentType.LEGAL)
        
        # Test default detection
        content = b"Some generic content that doesn't match any specific type."
        doc_type = self.processor.detect_document_type(content, mime_type)
        self.assertEqual(doc_type, DocumentType.GENERAL)
    
    def test_get_processor_for_document_type(self):
        """Test getting processor ID for document type."""
        # Mock the config.get_docai_processor_id method
        with mock.patch.object(config, 'get_docai_processor_id') as mock_get_id:
            # Set up mock return values
            mock_get_id.side_effect = lambda x: {
                "form": "form-processor-id",
                "ocr": "ocr-processor-id",
                "splitter": "splitter-processor-id",
                "quality": "quality-processor-id",
            }.get(x)
            
            # Test form processor
            processor_id = self.processor.get_processor_for_document_type(DocumentType.FORM)
            self.assertEqual(processor_id, "form-processor-id")
            
            # Test invoice processor (should use form processor)
            processor_id = self.processor.get_processor_for_document_type(DocumentType.INVOICE)
            self.assertEqual(processor_id, "form-processor-id")
            
            # Test general document processor (should use OCR processor)
            processor_id = self.processor.get_processor_for_document_type(DocumentType.GENERAL)
            self.assertEqual(processor_id, "ocr-processor-id")
    
    def test_get_document_content_local_file(self):
        """Test getting document content from local file."""
        source = self.temp_file.name
        source_type = DocumentSource.LOCAL_FILE
        
        content, metadata = self.processor._get_document_content(source, source_type)
        
        self.assertEqual(content, b"Test document content")
        self.assertEqual(metadata.source_type, DocumentSource.LOCAL_FILE)
        self.assertEqual(metadata.source_path, source)
        self.assertEqual(metadata.size_bytes, len(b"Test document content"))
        self.assertEqual(metadata.filename, Path(source).name)
    
    @mock.patch('requests.get')
    def test_get_document_content_url(self, mock_requests_get):
        """Test getting document content from URL."""
        # Mock the requests.get response
        mock_response = mock.Mock()
        mock_response.content = b"URL document content"
        mock_response.headers = {"content-type": "text/plain"}
        mock_requests_get.return_value = mock_response
        
        source = "https://example.com/document.txt"
        source_type = DocumentSource.URL
        
        content, metadata = self.processor._get_document_content(source, source_type)
        
        self.assertEqual(content, b"URL document content")
        self.assertEqual(metadata.source_type, DocumentSource.URL)
        self.assertEqual(metadata.source_path, source)
        self.assertEqual(metadata.size_bytes, len(b"URL document content"))
        self.assertEqual(metadata.filename, "document.txt")
        self.assertEqual(metadata.mime_type, "text/plain")
    
    def test_get_document_content_base64(self):
        """Test getting document content from base64 string."""
        original_content = b"Base64 document content"
        base64_content = base64.b64encode(original_content).decode('utf-8')
        
        source = base64_content
        source_type = DocumentSource.BASE64
        mime_type = "text/plain"
        
        content, metadata = self.processor._get_document_content(source, source_type, mime_type)
        
        self.assertEqual(content, original_content)
        self.assertEqual(metadata.source_type, DocumentSource.BASE64)
        self.assertEqual(metadata.source_path, source)
        self.assertEqual(metadata.size_bytes, len(original_content))
        self.assertEqual(metadata.mime_type, mime_type)
    
    @mock.patch('google.cloud.documentai_v1.DocumentProcessorServiceClient.process_document')
    def test_process_document(self, mock_process_document):
        """Test processing a document."""
        # Create a mock Document AI response
        mock_document = mock.Mock()
        mock_document.text = "Processed document text"
        mock_document.entities = []
        mock_document.pages = []
        
        mock_response = mock.Mock()
        mock_response.document = mock_document
        mock_process_document.return_value = mock_response
        
        # Mock the processor path
        self.processor.client.processor_path.return_value = (
            "projects/test-project/locations/us-central1/processors/test-processor-id"
        )
        
        # Process a document
        result = self.processor.process_document(
            source=self.temp_file.name,
            source_type=DocumentSource.LOCAL_FILE,
            mime_type="text/plain",
            document_type=DocumentType.GENERAL,
            processor_id="test-processor-id",
        )
        
        # Verify the result
        self.assertEqual(result["text"], "Processed document text")
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["pages"], [])
        self.assertEqual(result["metadata"]["document_type"], DocumentType.GENERAL.value)
        self.assertEqual(result["metadata"]["source_type"], DocumentSource.LOCAL_FILE.value)
        self.assertEqual(result["metadata"]["source_path"], self.temp_file.name)


class TestProcessorFactory(unittest.TestCase):
    """Test cases for the ProcessorFactory class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the DocumentAIProcessor
        self.mock_processor_patcher = mock.patch(
            'src.document_pipeline.docai_processor.DocumentAIProcessor'
        )
        self.mock_processor_class = self.mock_processor_patcher.start()
        
        # Create a mock processor instance
        self.mock_processor = mock.Mock()
        self.mock_processor_class.return_value = self.mock_processor
        
        # Create a factory
        self.factory = ProcessorFactory(
            project_id="test-project",
            location="us-central1",
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.mock_processor_patcher.stop()
    
    def test_init(self):
        """Test initialization of ProcessorFactory."""
        factory = ProcessorFactory(
            project_id="test-project",
            location="us-central1",
        )
        
        self.assertEqual(factory.project_id, "test-project")
        self.assertEqual(factory.location, "us-central1")
        
        # Verify DocumentAIProcessor was initialized with correct arguments
        self.mock_processor_class.assert_called_once_with(
            project_id="test-project",
            location="us-central1",
        )
    
    def test_get_processor(self):
        """Test getting a processor for a document type."""
        # Get a processor for a document type
        processor = self.factory.get_processor(DocumentType.FORM)
        
        # Verify we got the mock processor
        self.assertEqual(processor, self.mock_processor)
        
        # Get the same processor again (should be cached)
        processor2 = self.factory.get_processor(DocumentType.FORM)
        
        # Verify we got the same processor and no new one was created
        self.assertEqual(processor2, self.mock_processor)
        self.mock_processor_class.assert_called_once()  # Only called once during initialization
    
    def test_process_document(self):
        """Test processing a document using the factory."""
        # Mock the processor's process_document method
        self.mock_processor.process_document.return_value = {"result": "success"}
        
        # Process a document using the factory
        result = self.factory.process_document(
            source="test-source",
            source_type=DocumentSource.LOCAL_FILE,
            mime_type="text/plain",
            document_type=DocumentType.FORM,
        )
        
        # Verify the result
        self.assertEqual(result, {"result": "success"})
        
        # Verify the processor's process_document method was called with correct arguments
        self.mock_processor.process_document.assert_called_once_with(
            source="test-source",
            source_type=DocumentSource.LOCAL_FILE,
            mime_type="text/plain",
            document_type=DocumentType.FORM,
            processor_id=None,
        )


if __name__ == "__main__":
    unittest.main()
