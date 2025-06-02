"""
Core document processor for handling document ingestion, processing, and extraction.
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from enum import Enum

import json
import csv
from bs4 import BeautifulSoup # For parsing HTML/XML content if needed

from google.cloud import storage
# documentai and genai will be used by sub-processors

from .docai_processor import DocAIProcessor
from .vertex_ai_processor import VertexAIProcessor
from .neo4j_uploader import Neo4jUploader, Neo4jError

logger = logging.getLogger(__name__)

class DocumentType(Enum):
    """Supported document types for processing."""
    PDF = "pdf"
    TEXT = "txt"
    CSV = "csv"
    EXCEL = "xlsx"
    WORD = "docx"
    JSON = "json"
    XML = "xml"
    HTML = "html"
    SEC_13D = "13d"
    SEC_10K = "10k"
    UNKNOWN = "unknown"

class DocumentProcessor:
    """
    Core document processor that handles document intake, processing, and extraction.
    
    This class uses Document AI for parsing and Vertex AI for entity extraction
    and text embedding to create a complete document processing pipeline.
    """
    
    def __init__(
        self, 
        project_id: str,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        location: str = "us-central1", # GCP region for DocAI and VertexAI
        bucket_name: Optional[str] = None, # GCS bucket for document staging
        # DocAI specific params
        docai_default_processor_id: Optional[str] = None, 
        # VertexAI specific params
        vertex_embedding_model: str = "text-embedding-004",
        vertex_llm_model: str = "gemini-2.5-pro-preview-05-06", # Updated as per user preference
        # Neo4j specific params
        neo4j_embedding_dimension: int = 768 # Default for text-embedding-004, adjust as needed
    ):
        """
        Initialize the document processor.
        
        Args:
            project_id: GCP project ID.
            neo4j_uri: URI for the Neo4j database.
            neo4j_user: Username for Neo4j authentication.
            neo4j_password: Password for Neo4j authentication.
            location: GCP region for Document AI and Vertex AI services.
            bucket_name: GCS bucket for document staging and intermediate storage.
            docai_default_processor_id: Default Document AI processor ID.
            vertex_embedding_model: Default Vertex AI model for text embeddings.
            vertex_llm_model: Default Vertex AI model for LLM tasks.
            neo4j_embedding_dimension: Dimension of embeddings for Neo4j vector index.
        """
        self.project_id = project_id
        self.location = location
        self.bucket_name = bucket_name
        self.neo4j_embedding_dimension = neo4j_embedding_dimension
        
        # Initialize GCS client (still useful for uploads if bucket_name is provided)
        self.storage_client = storage.Client(project=project_id)
        
        # Initialize sub-processors
        self.docai_handler = DocAIProcessor(
            project_id=project_id,
            location=location,
            default_processor_id=docai_default_processor_id
        )
        self.vertex_handler = VertexAIProcessor(
            project_id=project_id,
            location=location,
            default_embedding_model=vertex_embedding_model,
            default_llm_model=vertex_llm_model
        )
        try:
            self.neo4j_uploader = Neo4jUploader(
                uri=neo4j_uri,
                user=neo4j_user,
                password=neo4j_password
            )
            # Optionally, create a default vector index on initialization if desired
            # self.neo4j_uploader.create_vector_index(
            #     index_name="default_document_embeddings", 
            #     node_label="Chunk", 
            #     embedding_property="embedding", 
            #     dimensions=self.neo4j_embedding_dimension
            # )
        except Neo4jError as e:
            logger.error(f"Failed to initialize Neo4jUploader or create index: {e}")
            # Decide if this is a fatal error for DocumentProcessor initialization
            raise ConnectionError(f"Could not connect to Neo4j or setup index: {e}") from e
        
        # Create bucket if it doesn't exist
        if bucket_name and not self._bucket_exists(bucket_name):
            self._create_bucket(bucket_name)
    
    def _bucket_exists(self, bucket_name: str) -> bool:
        """Check if a bucket exists."""
        try:
            self.storage_client.get_bucket(bucket_name)
            return True
        except Exception:
            return False
    
    def _create_bucket(self, bucket_name: str) -> None:
        """Create a new bucket."""
        bucket = self.storage_client.bucket(bucket_name)
        bucket.create(location=self.location)
        logger.info(f"Created bucket {bucket_name}")
    
    def upload_document(
        self, 
        file_path: Union[str, Path],
        destination_folder: Optional[str] = None
    ) -> str:
        """
        Upload a document to Cloud Storage.
        
        Args:
            file_path: Path to the document
            destination_folder: Optional folder within the bucket
            
        Returns:
            str: GCS URI of the uploaded document
        """
        if not self.bucket_name:
            raise ValueError("Bucket name must be provided to upload documents")
        
        file_path = Path(file_path)
        blob_name = f"{destination_folder}/{file_path.name}" if destination_folder else file_path.name
        
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(blob_name)
        
        blob.upload_from_filename(str(file_path))
        gcs_uri = f"gs://{self.bucket_name}/{blob_name}"
        
        logger.info(f"Uploaded {file_path} to {gcs_uri}")
        return gcs_uri
    
    def detect_document_type(self, file_path: Union[str, Path]) -> DocumentType:
        """
        Detect document type based on file extension and content.
        
        Args:
            file_path: Path to the document
            
        Returns:
            DocumentType: The detected document type
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower().lstrip('.')
        
        # Check extension first
        if extension == 'pdf':
            return DocumentType.PDF
        elif extension in ('txt', 'text'):
            return DocumentType.TEXT
        elif extension == 'csv':
            return DocumentType.CSV
        elif extension in ('xls', 'xlsx'):
            return DocumentType.EXCEL
        elif extension in ('doc', 'docx'):
            return DocumentType.WORD
        elif extension == 'json':
            return DocumentType.JSON
        elif extension == 'xml':
            # Check for SEC filings in XML format
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(2000)  # Read the first 2000 chars
                if "<edgarSubmission" in content or "<sec:form13" in content:
                    if "13D" in content or "13d" in content:
                        return DocumentType.SEC_13D
                    elif "10-K" in content or "10K" in content or "10k" in content:
                        return DocumentType.SEC_10K
            return DocumentType.XML
        elif extension == 'html':
            return DocumentType.HTML
        
        return DocumentType.UNKNOWN
    
    def process_document(
        self, 
        document_path: Union[str, Path],
        upload_to_gcs: bool = True,
        extract_entities: bool = True,
        generate_embeddings: bool = True
    ) -> Dict[str, Any]:
        """
        Process a document using Document AI and Vertex AI.
        
        Args:
            document_path: Path to the document
            upload_to_gcs: Whether to upload the document to GCS
            extract_entities: Whether to extract entities
            generate_embeddings: Whether to generate embeddings
            
        Returns:
            Dict[str, Any]: The processed document data
        """
        document_path = Path(document_path)
        
        # Detect document type
        doc_type = self.detect_document_type(document_path)
        logger.info(f"Detected document type: {doc_type.value}")
        
        # Upload to GCS if requested
        gcs_uri = None
        if upload_to_gcs and self.bucket_name:
            gcs_uri = self.upload_document(document_path)
        
        # Process based on document type
        if doc_type == DocumentType.PDF:
            return self._process_pdf(document_path, gcs_uri, extract_entities, generate_embeddings)
        elif doc_type in (DocumentType.SEC_13D, DocumentType.SEC_10K):
            return self._process_sec_filing(document_path, doc_type, gcs_uri, extract_entities, generate_embeddings)
        elif doc_type == DocumentType.TEXT:
            return self._process_text(document_path, gcs_uri, extract_entities, generate_embeddings)
        else:
            # Generic processing for other document types
            return self._process_generic(document_path, doc_type, gcs_uri, extract_entities, generate_embeddings)
    
    def _process_pdf(
        self, 
        file_path: Path,
        gcs_uri: Optional[str],
        extract_entities: bool,
        generate_embeddings: bool,
        docai_processor_id_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a PDF document using Document AI, Vertex AI, and load to Neo4j."""
        logger.info(f"Processing PDF: {file_path}")
        results = {"source_file": str(file_path), "gcs_uri": gcs_uri, "status": "started"}
        doc_id = file_path.stem # Use filename stem as document ID, or generate a UUID

        try:
            # 1. Process with Document AI
            if not gcs_uri and self.bucket_name: # Upload if not already uploaded
                gcs_uri = self.upload_document(file_path, destination_folder="pdf_inputs")
                results["gcs_uri"] = gcs_uri
            
            if not gcs_uri:
                # Option: process from bytes if no GCS path and no bucket for upload
                # For simplicity, current example prioritizes GCS path for DocAI
                logger.warning("No GCS URI for PDF and no bucket to upload to. Skipping DocAI processing.")
                # Fallback: try to extract text with a simpler tool or return error
                # For now, we assume DocAI needs GCS or bytes processing is implemented in DocAIProcessor
                with open(file_path, "rb") as f_bytes:
                    docai_document = self.docai_handler.process_document_from_bytes(
                        file_content=f_bytes.read(),
                        processor_id=docai_processor_id_override, # or self.docai_handler.default_processor_id
                        mime_type="application/pdf"
                    )
            else:
                docai_document = self.docai_handler.process_document_from_gcs(
                    gcs_uri=gcs_uri,
                    processor_id=docai_processor_id_override # or self.docai_handler.default_processor_id
                )

            full_text = self.docai_handler.extract_text(docai_document)
            results["extracted_text_length"] = len(full_text)
            # results["docai_entities"] = self.docai_handler.extract_entities(docai_document)
            # results["docai_form_fields"] = self.docai_handler.extract_form_fields(docai_document)
            # results["docai_tables"] = self.docai_handler.extract_tables(docai_document)

            # 2. Entity Extraction with Vertex AI (example: extract from full text)
            if extract_entities and full_text:
                # Define a schema for what you want to extract
                # This is a generic example; tailor it to your PDF content
                entity_schema = {
                    "type": "object",
                    "properties": {
                        "document_title": {"type": "string"},
                        "key_people": {"type": "array", "items": {"type": "string"}},
                        "organizations": {"type": "array", "items": {"type": "string"}},
                        "summary": {"type": "string"}
                    }
                }
                extracted_vertex_entities = self.vertex_handler.extract_structured_data_from_text(
                    text_content=full_text[:20000], # Limit context for LLM if text is too long
                    json_schema=entity_schema
                )
                results["vertex_entities"] = extracted_vertex_entities
                # Persist these entities to Neo4j
                if extracted_vertex_entities:
                    # Example: Create a Document node and link entities
                    self.neo4j_uploader.add_node("Document", {"id": doc_id, "title": extracted_vertex_entities.get("document_title", file_path.name), "source_uri": gcs_uri or str(file_path)})
                    for person_name in extracted_vertex_entities.get("key_people", []):
                        p_node = self.neo4j_uploader.add_node("Person", {"name": person_name})
                        self.neo4j_uploader.add_relationship("Document", {"id": doc_id}, "Person", {"name": person_name}, "MENTIONS_PERSON")
                    # Add more entity types as needed

            # 3. Embedding Generation with Vertex AI (example: chunk full text)
            if generate_embeddings and full_text:
                # Simple chunking strategy (replace with more sophisticated chunking)
                chunks = [full_text[i:i+1000] for i in range(0, len(full_text), 1000)]
                embeddings = self.vertex_handler.get_text_embeddings(texts=chunks)
                results["num_chunks_embedded"] = len(chunks)
                # Persist chunks and embeddings to Neo4j
                for i, (chunk_text, embedding_vector) in enumerate(zip(chunks, embeddings)):
                    if embedding_vector: # Ensure embedding was successful
                        chunk_id = f"{doc_id}_chunk_{i}"
                        self.neo4j_uploader.add_chunk_with_embedding(
                            document_id=doc_id,
                            chunk_id=chunk_id,
                            text_chunk=chunk_text,
                            embedding=embedding_vector,
                            metadata={"source_document_type": "PDF"}
                        )
            results["status"] = "completed"
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {e}", exc_info=True)
            results["status"] = "failed"
            results["error"] = str(e)
        
        return results
    
    def _process_sec_filing(
        self, 
        file_path: Path, 
        doc_type: DocumentType,
        gcs_uri: Optional[str],
        extract_entities: bool,
        generate_embeddings: bool
    ) -> Dict[str, Any]:
        """Process an SEC filing (13D or 10K)."""
        logger.info(f"Processing SEC filing {doc_type.value}: {file_path}")
        results = {"source_file": str(file_path), "gcs_uri": gcs_uri, "status": "started", "doc_type": doc_type.value}
        doc_id = file_path.stem

        # For SEC filings, they are often XML/HTML like. We'll extract text first.
        # A more robust solution might use a specific DocAI processor for SEC forms if available
        # or advanced XML/HTML parsing libraries.
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic text extraction (placeholder - improve with proper parsing e.g. BeautifulSoup for HTML parts)
            # For now, let's assume `content` is the primary text to work with.
            # A better approach would be to use a library to strip XML/HTML tags or parse specific sections.
            soup = BeautifulSoup(content, 'html.parser')
            full_text = soup.get_text(separator='\n', strip=True)
            if not full_text:
                full_text = content # Fallback if BS4 yields nothing (e.g. pure XML not HTML-like)

            results["extracted_text_length"] = len(full_text)

            if extract_entities and full_text:
                # Tailor schema for SEC filings (e.g., filer, subject company, key events for 13D)
                # This is a generic example
                schema_13d = {
                    "type": "object",
                    "properties": {
                        "filer_name": {"type": "string"},
                        "subject_company_name": {"type": "string"},
                        "date_of_event": {"type": "string", "format": "date"},
                        "purpose_of_transaction": {"type": "string"}
                    }
                }
                # Schema for 10K would be different (e.g., business overview, risk factors, financial data)
                # For simplicity, using a generic schema here
                current_schema = schema_13d # Choose schema based on doc_type

                extracted_data = self.vertex_handler.extract_structured_data_from_text(
                    text_content=full_text[:30000], # Limit context
                    json_schema=current_schema
                )
                results["vertex_entities"] = extracted_data
                # Persist to Neo4j
                if extracted_data:
                    doc_node_props = {"id": doc_id, "type": doc_type.value, "source_uri": gcs_uri or str(file_path)}
                    doc_node_props.update(extracted_data) # Add extracted fields to document node
                    self.neo4j_uploader.add_node("SECForm", doc_node_props)
            
            if generate_embeddings and full_text:
                chunks = [full_text[i:i+1000] for i in range(0, len(full_text), 1000)]
                embeddings = self.vertex_handler.get_text_embeddings(texts=chunks, task_type="RETRIEVAL_DOCUMENT")
                results["num_chunks_embedded"] = len(chunks)
                for i, (chunk_text, embedding_vector) in enumerate(zip(chunks, embeddings)):
                    if embedding_vector:
                        chunk_id = f"{doc_id}_chunk_{i}"
                        self.neo4j_uploader.add_chunk_with_embedding(
                            document_id=doc_id, # Link to the SECForm node via its id
                            chunk_id=chunk_id,
                            text_chunk=chunk_text,
                            embedding=embedding_vector,
                            metadata={"source_document_type": doc_type.value}
                        )
            results["status"] = "completed"
        except Exception as e:
            logger.error(f"Error processing SEC filing {file_path}: {e}", exc_info=True)
            results["status"] = "failed"
            results["error"] = str(e)
        return results
    
    def _process_text(
        self, 
        file_path: Path,
        gcs_uri: Optional[str],
        extract_entities: bool,
        generate_embeddings: bool
    ) -> Dict[str, Any]:
        """Process a plain text document."""
        logger.info(f"Processing text document: {file_path}")
        results = {"source_file": str(file_path), "gcs_uri": gcs_uri, "status": "started"}
        doc_id = file_path.stem

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                full_text = f.read()
            results["extracted_text_length"] = len(full_text)

            if extract_entities and full_text:
                # Generic schema for text, or could be context-dependent
                entity_schema = {
                    "type": "object",
                    "properties": {
                        "main_topics": {"type": "array", "items": {"type": "string"}},
                        "summary": {"type": "string"}
                    }
                }
                extracted_data = self.vertex_handler.extract_structured_data_from_text(
                    text_content=full_text[:30000],
                    json_schema=entity_schema
                )
                results["vertex_entities"] = extracted_data
                if extracted_data:
                    doc_node_props = {"id": doc_id, "type": "TextDocument", "source_uri": gcs_uri or str(file_path)}
                    doc_node_props.update(extracted_data)
                    self.neo4j_uploader.add_node("Document", doc_node_props) # Generic Document label

            if generate_embeddings and full_text:
                chunks = [full_text[i:i+1000] for i in range(0, len(full_text), 1000)]
                embeddings = self.vertex_handler.get_text_embeddings(texts=chunks)
                results["num_chunks_embedded"] = len(chunks)
                for i, (chunk_text, embedding_vector) in enumerate(zip(chunks, embeddings)):
                    if embedding_vector:
                        chunk_id = f"{doc_id}_chunk_{i}"
                        self.neo4j_uploader.add_chunk_with_embedding(
                            document_id=doc_id,
                            chunk_id=chunk_id,
                            text_chunk=chunk_text,
                            embedding=embedding_vector,
                            metadata={"source_document_type": "TXT"}
                        )
            results["status"] = "completed"
        except Exception as e:
            logger.error(f"Error processing text document {file_path}: {e}", exc_info=True)
            results["status"] = "failed"
            results["error"] = str(e)
        return results
    
    def _process_generic(
        self, 
        file_path: Path,
        doc_type: DocumentType,
        gcs_uri: Optional[str],
        extract_entities: bool,
        generate_embeddings: bool
    ) -> Dict[str, Any]:
        """Generic processing for other document types (Word, Excel, JSON, CSV, HTML, XML)."""
        logger.info(f"Processing generic document type {doc_type.value}: {file_path}")        
        # For Word, Excel: Could use a DocAI processor if configured for these types, 
        # or convert to PDF/text first. This is a simplified version.
        # For JSON, CSV, XML, HTML: Parse content directly.
        
        # Placeholder: This simplified generic handler will try to extract text if possible
        # and then proceed like a text document. A robust solution would involve
        # specific parsers or DocAI processors for each type.
        full_text = ""
        try:
            if doc_type in [DocumentType.WORD, DocumentType.EXCEL, DocumentType.HTML, DocumentType.XML]:
                # Attempt to use a general Document AI processor if available and configured
                # This assumes a general processor can OCR or extract text from these.
                # Or, use libraries like python-docx, openpyxl, BeautifulSoup, xml.etree.ElementTree
                logger.warning(f"Generic processing for {doc_type.value} may be limited. Attempting text extraction.")
                if gcs_uri or (self.bucket_name and self.docai_handler.default_processor_id):
                    if not gcs_uri:
                        gcs_uri = self.upload_document(file_path, destination_folder="generic_inputs")
                    
                    # Determine mime_type for DocAI if possible
                    mime_map = {
                        DocumentType.WORD: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        DocumentType.EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        DocumentType.HTML: "text/html",
                        DocumentType.XML: "application/xml"
                    }
                    mime = mime_map.get(doc_type)
                    
                    if self.docai_handler.default_processor_id and mime:
                        docai_document = self.docai_handler.process_document_from_gcs(gcs_uri, mime_type=mime)
                        full_text = self.docai_handler.extract_text(docai_document)
                    else:
                        logger.warning(f"No default DocAI processor or suitable mime type for {doc_type.value}, falling back to basic text read.")
                        # Fallback for types not easily processed by default DocAI or if no default proc.
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f: full_text = f.read()
                        except: 
                            logger.error(f"Could not read {file_path} as text.")
                            pass # full_text remains empty
                else:
                    # Fallback for local files if no GCS/DocAI configured for them
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f: full_text = f.read()
                    except: 
                        logger.error(f"Could not read {file_path} as text.")
                        pass # full_text remains empty
            
            elif doc_type == DocumentType.JSON:
                with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
                full_text = json.dumps(data, indent=2) # Convert JSON to string for processing
            elif doc_type == DocumentType.CSV:
                with open(file_path, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.reader(f)
                    full_text = "\n".join([",".join(row) for row in reader])
            else: # UNKNOWN or other types not explicitly handled
                logger.warning(f"No specific generic processing logic for {doc_type.value}. Treating as simple text if possible.")
                try: 
                    with open(file_path, 'r', encoding='utf-8') as f: full_text = f.read()
                except: pass

            if not full_text:
                return {"status": f"Could not extract text from {doc_type.value} document {file_path}", "error": "No text extracted"}

            # Proceed with Vertex AI and Neo4j as if it's a text document
            # This is a simplification; real generic processing would be more nuanced.
            temp_text_path = file_path.with_suffix(f".{doc_type.value}.extracted.txt")
            with open(temp_text_path, "w", encoding="utf-8") as f_out:
                f_out.write(full_text)
            
            results = self._process_text(temp_text_path, gcs_uri, extract_entities, generate_embeddings)
            temp_text_path.unlink() # Clean up temporary file
            results["original_doc_type"] = doc_type.value
            return results

        except Exception as e:
            logger.error(f"Error in generic processing for {file_path} ({doc_type.value}): {e}", exc_info=True)
            return {"status": "failed", "error": str(e), "doc_type": doc_type.value}

