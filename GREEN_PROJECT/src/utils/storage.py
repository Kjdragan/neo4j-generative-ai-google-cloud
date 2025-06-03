#!/usr/bin/env python
"""
Google Cloud Storage utilities for the Neo4j Generative AI Google Cloud project.

This module provides functionality for interacting with Google Cloud Storage,
including uploading, downloading, and managing files in buckets.
"""

import os
import logging
from typing import Optional, List, BinaryIO, Union
from pathlib import Path

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError, NotFound

from . import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class StorageClient:
    """Client for interacting with Google Cloud Storage."""
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ):
        """
        Initialize the Storage client.
        
        Args:
            project_id: GCP project ID (defaults to config.GCP_PROJECT_ID)
            bucket_name: Default bucket name (defaults to config.STORAGE_BUCKET)
        """
        self.project_id = project_id or config.GCP_PROJECT_ID
        self.bucket_name = bucket_name or config.STORAGE_BUCKET
        
        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID must be set in environment or provided")
        
        # Initialize storage client
        self.client = storage.Client(project=self.project_id)
        
        logger.info(f"Initialized StorageClient with project_id={self.project_id}, bucket_name={self.bucket_name}")
    
    def get_bucket(self, bucket_name: Optional[str] = None) -> storage.Bucket:
        """
        Get a bucket by name.
        
        Args:
            bucket_name: The name of the bucket (defaults to self.bucket_name)
            
        Returns:
            The bucket object
            
        Raises:
            NotFound: If the bucket does not exist
        """
        bucket_name = bucket_name or self.bucket_name
        
        if not bucket_name:
            raise ValueError("Bucket name must be provided")
        
        try:
            bucket = self.client.bucket(bucket_name)
            # Check if bucket exists by getting its metadata
            bucket.reload()
            return bucket
        except NotFound:
            logger.error(f"Bucket {bucket_name} not found")
            raise
    
    def create_bucket(
        self,
        bucket_name: Optional[str] = None,
        location: str = "us-central1",
        storage_class: str = "STANDARD",
    ) -> storage.Bucket:
        """
        Create a new bucket.
        
        Args:
            bucket_name: The name of the bucket (defaults to self.bucket_name)
            location: The location of the bucket
            storage_class: The storage class of the bucket
            
        Returns:
            The created bucket object
        """
        bucket_name = bucket_name or self.bucket_name
        
        if not bucket_name:
            raise ValueError("Bucket name must be provided")
        
        try:
            bucket = self.client.bucket(bucket_name)
            bucket.create(
                location=location,
                storage_class=storage_class,
            )
            logger.info(f"Created bucket {bucket_name} in {location} with storage class {storage_class}")
            return bucket
        except GoogleCloudError as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            raise
    
    def list_buckets(self) -> List[storage.Bucket]:
        """
        List all buckets in the project.
        
        Returns:
            A list of bucket objects
        """
        try:
            buckets = list(self.client.list_buckets())
            logger.info(f"Listed {len(buckets)} buckets in project {self.project_id}")
            return buckets
        except GoogleCloudError as e:
            logger.error(f"Failed to list buckets: {e}")
            raise
    
    def upload_file(
        self,
        source_file: Union[str, Path, BinaryIO],
        destination_blob_name: Optional[str] = None,
        bucket_name: Optional[str] = None,
        content_type: Optional[str] = None,
        make_public: bool = False,
    ) -> storage.Blob:
        """
        Upload a file to a bucket.
        
        Args:
            source_file: The source file path or file-like object
            destination_blob_name: The name of the destination blob (defaults to source file name)
            bucket_name: The name of the bucket (defaults to self.bucket_name)
            content_type: The content type of the file
            make_public: Whether to make the file publicly accessible
            
        Returns:
            The uploaded blob object
        """
        bucket_name = bucket_name or self.bucket_name
        
        if not bucket_name:
            raise ValueError("Bucket name must be provided")
        
        # Get bucket
        bucket = self.get_bucket(bucket_name)
        
        # Determine destination blob name if not provided
        if not destination_blob_name:
            if isinstance(source_file, (str, Path)):
                destination_blob_name = os.path.basename(str(source_file))
            else:
                raise ValueError("destination_blob_name must be provided for file-like objects")
        
        # Create blob
        blob = bucket.blob(destination_blob_name)
        
        try:
            # Upload file
            if isinstance(source_file, (str, Path)):
                blob.upload_from_filename(
                    str(source_file),
                    content_type=content_type,
                )
            else:
                blob.upload_from_file(
                    source_file,
                    content_type=content_type,
                )
            
            # Make public if requested
            if make_public:
                blob.make_public()
            
            logger.info(f"Uploaded {destination_blob_name} to {bucket_name}")
            return blob
        except GoogleCloudError as e:
            logger.error(f"Failed to upload {destination_blob_name} to {bucket_name}: {e}")
            raise
    
    def download_file(
        self,
        source_blob_name: str,
        destination_file: Union[str, Path, BinaryIO],
        bucket_name: Optional[str] = None,
    ) -> None:
        """
        Download a file from a bucket.
        
        Args:
            source_blob_name: The name of the source blob
            destination_file: The destination file path or file-like object
            bucket_name: The name of the bucket (defaults to self.bucket_name)
        """
        bucket_name = bucket_name or self.bucket_name
        
        if not bucket_name:
            raise ValueError("Bucket name must be provided")
        
        # Get bucket
        bucket = self.get_bucket(bucket_name)
        
        # Get blob
        blob = bucket.blob(source_blob_name)
        
        try:
            # Download file
            if isinstance(destination_file, (str, Path)):
                blob.download_to_filename(str(destination_file))
            else:
                blob.download_to_file(destination_file)
            
            logger.info(f"Downloaded {source_blob_name} from {bucket_name}")
        except GoogleCloudError as e:
            logger.error(f"Failed to download {source_blob_name} from {bucket_name}: {e}")
            raise
    
    def download_as_bytes(
        self,
        source_blob_name: str,
        bucket_name: Optional[str] = None,
    ) -> bytes:
        """
        Download a file from a bucket as bytes.
        
        Args:
            source_blob_name: The name of the source blob
            bucket_name: The name of the bucket (defaults to self.bucket_name)
            
        Returns:
            The file content as bytes
        """
        bucket_name = bucket_name or self.bucket_name
        
        if not bucket_name:
            raise ValueError("Bucket name must be provided")
        
        # Get bucket
        bucket = self.get_bucket(bucket_name)
        
        # Get blob
        blob = bucket.blob(source_blob_name)
        
        try:
            # Download as bytes
            content = blob.download_as_bytes()
            
            logger.info(f"Downloaded {source_blob_name} from {bucket_name} as bytes")
            return content
        except GoogleCloudError as e:
            logger.error(f"Failed to download {source_blob_name} from {bucket_name} as bytes: {e}")
            raise
    
    def list_blobs(
        self,
        prefix: Optional[str] = None,
        delimiter: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ) -> List[storage.Blob]:
        """
        List blobs in a bucket.
        
        Args:
            prefix: Filter results to objects whose names begin with this prefix
            delimiter: Filter results to objects whose names do not contain the delimiter
                       after the prefix
            bucket_name: The name of the bucket (defaults to self.bucket_name)
            
        Returns:
            A list of blob objects
        """
        bucket_name = bucket_name or self.bucket_name
        
        if not bucket_name:
            raise ValueError("Bucket name must be provided")
        
        # Get bucket
        bucket = self.get_bucket(bucket_name)
        
        try:
            # List blobs
            blobs = list(bucket.list_blobs(prefix=prefix, delimiter=delimiter))
            
            logger.info(f"Listed {len(blobs)} blobs in {bucket_name}")
            return blobs
        except GoogleCloudError as e:
            logger.error(f"Failed to list blobs in {bucket_name}: {e}")
            raise
    
    def delete_blob(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None,
    ) -> None:
        """
        Delete a blob from a bucket.
        
        Args:
            blob_name: The name of the blob to delete
            bucket_name: The name of the bucket (defaults to self.bucket_name)
        """
        bucket_name = bucket_name or self.bucket_name
        
        if not bucket_name:
            raise ValueError("Bucket name must be provided")
        
        # Get bucket
        bucket = self.get_bucket(bucket_name)
        
        # Get blob
        blob = bucket.blob(blob_name)
        
        try:
            # Delete blob
            blob.delete()
            
            logger.info(f"Deleted {blob_name} from {bucket_name}")
        except GoogleCloudError as e:
            logger.error(f"Failed to delete {blob_name} from {bucket_name}: {e}")
            raise
    
    def get_blob_metadata(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None,
    ) -> dict:
        """
        Get metadata for a blob.
        
        Args:
            blob_name: The name of the blob
            bucket_name: The name of the bucket (defaults to self.bucket_name)
            
        Returns:
            A dictionary of blob metadata
        """
        bucket_name = bucket_name or self.bucket_name
        
        if not bucket_name:
            raise ValueError("Bucket name must be provided")
        
        # Get bucket
        bucket = self.get_bucket(bucket_name)
        
        # Get blob
        blob = bucket.blob(blob_name)
        
        try:
            # Get metadata
            blob.reload()
            
            metadata = {
                "name": blob.name,
                "bucket": blob.bucket.name,
                "content_type": blob.content_type,
                "size": blob.size,
                "updated": blob.updated,
                "created": blob.time_created,
                "md5_hash": blob.md5_hash,
                "storage_class": blob.storage_class,
                "public_url": blob.public_url if blob.public else None,
            }
            
            logger.info(f"Got metadata for {blob_name} in {bucket_name}")
            return metadata
        except GoogleCloudError as e:
            logger.error(f"Failed to get metadata for {blob_name} in {bucket_name}: {e}")
            raise
    
    def blob_exists(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """
        Check if a blob exists in a bucket.
        
        Args:
            blob_name: The name of the blob
            bucket_name: The name of the bucket (defaults to self.bucket_name)
            
        Returns:
            True if the blob exists, False otherwise
        """
        bucket_name = bucket_name or self.bucket_name
        
        if not bucket_name:
            raise ValueError("Bucket name must be provided")
        
        # Get bucket
        bucket = self.get_bucket(bucket_name)
        
        # Get blob
        blob = bucket.blob(blob_name)
        
        try:
            # Check if blob exists
            return blob.exists()
        except GoogleCloudError as e:
            logger.error(f"Failed to check if {blob_name} exists in {bucket_name}: {e}")
            raise
