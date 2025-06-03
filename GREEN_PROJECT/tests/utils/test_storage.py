#!/usr/bin/env python
"""
Tests for the Google Cloud Storage utility module.

This module contains unit tests for the StorageClient class.
"""

import os
import unittest
from unittest import mock
from pathlib import Path
import tempfile

from google.cloud import storage
from google.cloud.exceptions import NotFound

from src.utils.storage import StorageClient
from src.utils import config


class TestStorageClient(unittest.TestCase):
    """Test cases for the StorageClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the storage client
        self.mock_client_patcher = mock.patch('google.cloud.storage.Client')
        self.mock_client = self.mock_client_patcher.start()
        
        # Create a mock storage client instance
        self.mock_client_instance = mock.Mock()
        self.mock_client.return_value = self.mock_client_instance
        
        # Create a storage client with mocked GCP client
        self.storage_client = StorageClient(
            project_id="test-project",
            bucket_name="test-bucket",
        )
        
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(b"Test file content")
        self.temp_file.close()
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.mock_client_patcher.stop()
        
        # Remove temporary file
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_init(self):
        """Test initialization of StorageClient."""
        client = StorageClient(
            project_id="test-project",
            bucket_name="test-bucket",
        )
        
        self.assertEqual(client.project_id, "test-project")
        self.assertEqual(client.bucket_name, "test-bucket")
        
        # Test with default values
        with mock.patch.object(config, 'GCP_PROJECT_ID', "default-project"):
            with mock.patch.object(config, 'STORAGE_BUCKET', "default-bucket"):
                client = StorageClient()
                
                self.assertEqual(client.project_id, "default-project")
                self.assertEqual(client.bucket_name, "default-bucket")
    
    def test_get_bucket(self):
        """Test getting a bucket."""
        # Mock the bucket
        mock_bucket = mock.Mock()
        self.mock_client_instance.bucket.return_value = mock_bucket
        
        # Get bucket
        bucket = self.storage_client.get_bucket("test-bucket")
        
        # Verify the bucket was returned
        self.assertEqual(bucket, mock_bucket)
        
        # Verify the client.bucket method was called with correct arguments
        self.mock_client_instance.bucket.assert_called_once_with("test-bucket")
        
        # Verify bucket.reload was called to check if bucket exists
        mock_bucket.reload.assert_called_once()
    
    def test_get_bucket_not_found(self):
        """Test getting a non-existent bucket."""
        # Mock the bucket
        mock_bucket = mock.Mock()
        self.mock_client_instance.bucket.return_value = mock_bucket
        
        # Make bucket.reload raise NotFound
        mock_bucket.reload.side_effect = NotFound("Bucket not found")
        
        # Get bucket should raise NotFound
        with self.assertRaises(NotFound):
            self.storage_client.get_bucket("non-existent-bucket")
    
    def test_create_bucket(self):
        """Test creating a bucket."""
        # Mock the bucket
        mock_bucket = mock.Mock()
        self.mock_client_instance.bucket.return_value = mock_bucket
        
        # Create bucket
        bucket = self.storage_client.create_bucket(
            bucket_name="new-bucket",
            location="us-central1",
            storage_class="STANDARD",
        )
        
        # Verify the bucket was returned
        self.assertEqual(bucket, mock_bucket)
        
        # Verify the client.bucket method was called with correct arguments
        self.mock_client_instance.bucket.assert_called_once_with("new-bucket")
        
        # Verify bucket.create was called with correct arguments
        mock_bucket.create.assert_called_once_with(
            location="us-central1",
            storage_class="STANDARD",
        )
    
    def test_list_buckets(self):
        """Test listing buckets."""
        # Mock the client.list_buckets method
        mock_bucket1 = mock.Mock()
        mock_bucket2 = mock.Mock()
        self.mock_client_instance.list_buckets.return_value = [mock_bucket1, mock_bucket2]
        
        # List buckets
        buckets = self.storage_client.list_buckets()
        
        # Verify the buckets were returned
        self.assertEqual(buckets, [mock_bucket1, mock_bucket2])
        
        # Verify the client.list_buckets method was called
        self.mock_client_instance.list_buckets.assert_called_once()
    
    def test_upload_file_from_path(self):
        """Test uploading a file from a path."""
        # Mock the bucket
        mock_bucket = mock.Mock()
        self.mock_client_instance.bucket.return_value = mock_bucket
        
        # Mock the blob
        mock_blob = mock.Mock()
        mock_bucket.blob.return_value = mock_blob
        
        # Upload file
        blob = self.storage_client.upload_file(
            source_file=self.temp_file.name,
            destination_blob_name="test-blob",
            content_type="text/plain",
            make_public=True,
        )
        
        # Verify the blob was returned
        self.assertEqual(blob, mock_blob)
        
        # Verify the bucket.blob method was called with correct arguments
        mock_bucket.blob.assert_called_once_with("test-blob")
        
        # Verify blob.upload_from_filename was called with correct arguments
        mock_blob.upload_from_filename.assert_called_once_with(
            self.temp_file.name,
            content_type="text/plain",
        )
        
        # Verify blob.make_public was called
        mock_blob.make_public.assert_called_once()
    
    def test_download_file_to_path(self):
        """Test downloading a file to a path."""
        # Mock the bucket
        mock_bucket = mock.Mock()
        self.mock_client_instance.bucket.return_value = mock_bucket
        
        # Mock the blob
        mock_blob = mock.Mock()
        mock_bucket.blob.return_value = mock_blob
        
        # Download file
        self.storage_client.download_file(
            source_blob_name="test-blob",
            destination_file=self.temp_file.name,
        )
        
        # Verify the bucket.blob method was called with correct arguments
        mock_bucket.blob.assert_called_once_with("test-blob")
        
        # Verify blob.download_to_filename was called with correct arguments
        mock_blob.download_to_filename.assert_called_once_with(self.temp_file.name)
    
    def test_download_as_bytes(self):
        """Test downloading a file as bytes."""
        # Mock the bucket
        mock_bucket = mock.Mock()
        self.mock_client_instance.bucket.return_value = mock_bucket
        
        # Mock the blob
        mock_blob = mock.Mock()
        mock_bucket.blob.return_value = mock_blob
        
        # Mock blob.download_as_bytes
        mock_blob.download_as_bytes.return_value = b"Test content"
        
        # Download as bytes
        content = self.storage_client.download_as_bytes(
            source_blob_name="test-blob",
        )
        
        # Verify the content was returned
        self.assertEqual(content, b"Test content")
        
        # Verify the bucket.blob method was called with correct arguments
        mock_bucket.blob.assert_called_once_with("test-blob")
        
        # Verify blob.download_as_bytes was called
        mock_blob.download_as_bytes.assert_called_once()
    
    def test_list_blobs(self):
        """Test listing blobs."""
        # Mock the bucket
        mock_bucket = mock.Mock()
        self.mock_client_instance.bucket.return_value = mock_bucket
        
        # Mock bucket.list_blobs
        mock_blob1 = mock.Mock()
        mock_blob2 = mock.Mock()
        mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2]
        
        # List blobs
        blobs = self.storage_client.list_blobs(
            prefix="test-prefix",
            delimiter="/",
        )
        
        # Verify the blobs were returned
        self.assertEqual(blobs, [mock_blob1, mock_blob2])
        
        # Verify the bucket.list_blobs method was called with correct arguments
        mock_bucket.list_blobs.assert_called_once_with(
            prefix="test-prefix",
            delimiter="/",
        )
    
    def test_delete_blob(self):
        """Test deleting a blob."""
        # Mock the bucket
        mock_bucket = mock.Mock()
        self.mock_client_instance.bucket.return_value = mock_bucket
        
        # Mock the blob
        mock_blob = mock.Mock()
        mock_bucket.blob.return_value = mock_blob
        
        # Delete blob
        self.storage_client.delete_blob(
            blob_name="test-blob",
        )
        
        # Verify the bucket.blob method was called with correct arguments
        mock_bucket.blob.assert_called_once_with("test-blob")
        
        # Verify blob.delete was called
        mock_blob.delete.assert_called_once()
    
    def test_get_blob_metadata(self):
        """Test getting blob metadata."""
        # Mock the bucket
        mock_bucket = mock.Mock()
        self.mock_client_instance.bucket.return_value = mock_bucket
        
        # Mock the blob
        mock_blob = mock.Mock()
        mock_bucket.blob.return_value = mock_blob
        
        # Set blob attributes
        mock_blob.name = "test-blob"
        mock_blob.bucket = mock.Mock()
        mock_blob.bucket.name = "test-bucket"
        mock_blob.content_type = "text/plain"
        mock_blob.size = 100
        mock_blob.updated = "2023-01-01T00:00:00Z"
        mock_blob.time_created = "2023-01-01T00:00:00Z"
        mock_blob.md5_hash = "hash"
        mock_blob.storage_class = "STANDARD"
        mock_blob.public = True
        mock_blob.public_url = "https://example.com/test-blob"
        
        # Get metadata
        metadata = self.storage_client.get_blob_metadata(
            blob_name="test-blob",
        )
        
        # Verify the metadata was returned
        self.assertEqual(metadata["name"], "test-blob")
        self.assertEqual(metadata["bucket"], "test-bucket")
        self.assertEqual(metadata["content_type"], "text/plain")
        self.assertEqual(metadata["size"], 100)
        self.assertEqual(metadata["updated"], "2023-01-01T00:00:00Z")
        self.assertEqual(metadata["created"], "2023-01-01T00:00:00Z")
        self.assertEqual(metadata["md5_hash"], "hash")
        self.assertEqual(metadata["storage_class"], "STANDARD")
        self.assertEqual(metadata["public_url"], "https://example.com/test-blob")
        
        # Verify the bucket.blob method was called with correct arguments
        mock_bucket.blob.assert_called_once_with("test-blob")
        
        # Verify blob.reload was called
        mock_blob.reload.assert_called_once()
    
    def test_blob_exists(self):
        """Test checking if a blob exists."""
        # Mock the bucket
        mock_bucket = mock.Mock()
        self.mock_client_instance.bucket.return_value = mock_bucket
        
        # Mock the blob
        mock_blob = mock.Mock()
        mock_bucket.blob.return_value = mock_blob
        
        # Mock blob.exists
        mock_blob.exists.return_value = True
        
        # Check if blob exists
        exists = self.storage_client.blob_exists(
            blob_name="test-blob",
        )
        
        # Verify the result was returned
        self.assertTrue(exists)
        
        # Verify the bucket.blob method was called with correct arguments
        mock_bucket.blob.assert_called_once_with("test-blob")
        
        # Verify blob.exists was called
        mock_blob.exists.assert_called_once()


if __name__ == "__main__":
    unittest.main()
