"""
Document AI Processor module for interacting with Google Cloud Document AI.

This module provides functionality to process documents using various Document AI processors
and extract structured data, text, and entities.
"""
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from google.cloud import documentai_v1 as documentai
from google.cloud import storage

logger = logging.getLogger(__name__)

class DocAIProcessor:
    """
    Handles interactions with Google Cloud Document AI.
    """
    
    def __init__(
        self,
        project_id: str,
        location: str = "us-central1", # Default to a common region
        default_processor_id: Optional[str] = None
    ):
        """
        Initialize the DocAIProcessor.
        
        Args:
            project_id: Google Cloud project ID.
            location: Google Cloud region where Document AI processors are located.
            default_processor_id: Optional default Document AI processor ID to use.
        """
        self.project_id = project_id
        self.location = location
        self.default_processor_id = default_processor_id
        
        # Initialize Document AI client
        # The client options can be customized if needed, e.g., for regional endpoints
        client_options = {"api_endpoint": f"{location}-documentai.googleapis.com"}
        self.docai_client = documentai.DocumentProcessorServiceClient(client_options=client_options)
        self.storage_client = storage.Client(project=project_id)

    def process_document_from_gcs(
        self,
        gcs_uri: str,
        processor_id: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> documentai.Document:
        """
        Process a document stored in Google Cloud Storage using Document AI.
        
        Args:
            gcs_uri: The GCS URI of the document (e.g., "gs://bucket_name/file_name.pdf").
            processor_id: The ID of the Document AI processor to use. 
                          If None, uses the default_processor_id.
            mime_type: The MIME type of the document. If None, it will be inferred.
            
        Returns:
            documentai.Document: The processed Document AI document object.
        """
        active_processor_id = processor_id or self.default_processor_id
        if not active_processor_id:
            raise ValueError("Processor ID must be provided either directly or as a default.")

        if not gcs_uri.startswith("gs://"):
            raise ValueError("gcs_uri must be a valid GCS path starting with 'gs://'.")

        gcs_document = documentai.GcsDocument(gcs_uri=gcs_uri, mime_type=mime_type)
        
        # Configure the process request
        request = documentai.ProcessRequest(
            name=self.docai_client.processor_path(
                self.project_id, self.location, active_processor_id
            ),
            gcs_document=gcs_document,
        )
        
        logger.info(f"Processing document {gcs_uri} with processor {active_processor_id}")
        result = self.docai_client.process_document(request=request)
        logger.info(f"Successfully processed document {gcs_uri}")
        return result.document

    def process_document_from_bytes(
        self,
        file_content: bytes,
        processor_id: Optional[str] = None,
        mime_type: str = "application/pdf" # Default to PDF, adjust as needed
    ) -> documentai.Document:
        """
        Process a document from its byte content using Document AI.
        
        Args:
            file_content: The byte content of the document.
            processor_id: The ID of the Document AI processor to use. 
                          If None, uses the default_processor_id.
            mime_type: The MIME type of the document.
            
        Returns:
            documentai.Document: The processed Document AI document object.
        """
        active_processor_id = processor_id or self.default_processor_id
        if not active_processor_id:
            raise ValueError("Processor ID must be provided either directly or as a default.")

        raw_document = documentai.RawDocument(content=file_content, mime_type=mime_type)
        
        # Configure the process request
        request = documentai.ProcessRequest(
            name=self.docai_client.processor_path(
                self.project_id, self.location, active_processor_id
            ),
            raw_document=raw_document,
        )
        
        logger.info(f"Processing document from bytes with processor {active_processor_id}")
        result = self.docai_client.process_document(request=request)
        logger.info(f"Successfully processed document from bytes")
        return result.document

    def extract_text(self, docai_document: documentai.Document) -> str:
        """Extracts the full text from a processed Document AI document."""
        return docai_document.text

    def extract_entities(self, docai_document: documentai.Document) -> List[Dict[str, Any]]:
        """Extracts entities from a processed Document AI document."""
        entities_data = []
        for entity in docai_document.entities:
            entities_data.append({
                "type": entity.type_,
                "mention_text": entity.mention_text,
                "confidence": entity.confidence,
                # Add other relevant entity properties if needed
            })
        return entities_data

    def extract_form_fields(self, docai_document: documentai.Document) -> List[Dict[str, Any]]:
        """Extracts form fields (key-value pairs) from a processed Document AI document."""
        form_fields_data = []
        for page in docai_document.pages:
            for field in page.form_fields:
                field_name = self._get_text_from_layout(field.field_name, docai_document)
                field_value = self._get_text_from_layout(field.field_value, docai_document)
                form_fields_data.append({
                    "field_name": field_name,
                    "field_value": field_value,
                    "name_confidence": field.field_name.confidence if field.field_name else None,
                    "value_confidence": field.field_value.confidence if field.field_value else None,
                })
        return form_fields_data

    def extract_tables(self, docai_document: documentai.Document) -> List[Dict[str, Any]]:
        """Extracts tables from a processed Document AI document."""
        tables_data = []
        for page_num, page in enumerate(docai_document.pages):
            for table_num, table in enumerate(page.tables):
                table_dict = {"page_number": page_num, "table_number": table_num, "rows": []}
                header_row_texts = [
                    self._get_text_from_layout(cell.layout, docai_document) for cell in table.header_rows[0].cells
                ] if table.header_rows else []
                
                for row_num, body_row in enumerate(table.body_rows):
                    row_data = {}
                    for cell_num, cell in enumerate(body_row.cells):
                        cell_text = self._get_text_from_layout(cell.layout, docai_document)
                        header = header_row_texts[cell_num] if cell_num < len(header_row_texts) else f"column_{cell_num}"
                        row_data[header] = cell_text
                    table_dict["rows"].append(row_data)
                tables_data.append(table_dict)
        return tables_data

    def _get_text_from_layout(self, layout: documentai.Document.Page.Layout, docai_document: documentai.Document) -> str:
        """Helper function to extract text based on layout segments."""
        text = ""
        if layout and layout.text_anchor and layout.text_anchor.text_segments:
            for segment in layout.text_anchor.text_segments:
                start_index = int(segment.start_index)
                end_index = int(segment.end_index)
                text += docai_document.text[start_index:end_index]
        return text.strip()

# Example Usage (for testing or demonstration)
if __name__ == '__main__':
    # This example assumes you have a GCP project set up, Document AI API enabled,
    # and a processor created. Replace with your actual values.
    # You would also need to authenticate, e.g., by running `gcloud auth application-default login`
    
    PROJECT_ID = os.getenv("GCP_PROJECT_ID") # Ensure this env var is set
    LOCATION = "us-central1"  # e.g., "us" or "eu"
    # You need to create a processor in the GCP Console first
    PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID") # Ensure this env var is set
    # Example GCS URI of a PDF document
    GCS_FILE_URI = os.getenv("DOCAI_GCS_FILE_URI") # e.g., "gs://your-bucket/your-doc.pdf"

    if not all([PROJECT_ID, PROCESSOR_ID, GCS_FILE_URI]):
        print("Please set GCP_PROJECT_ID, DOCAI_PROCESSOR_ID, and DOCAI_GCS_FILE_URI environment variables.")
    else:
        print(f"Initializing DocAIProcessor for project {PROJECT_ID} in {LOCATION}...")
        doc_ai_handler = DocAIProcessor(PROJECT_ID, LOCATION, PROCESSOR_ID)
        
        print(f"Processing document: {GCS_FILE_URI}")
        try:
            document_object = doc_ai_handler.process_document_from_gcs(GCS_FILE_URI)
            
            print("\n--- Extracted Text (first 500 chars) ---")
            full_text = doc_ai_handler.extract_text(document_object)
            print(full_text[:500] + "...")
            
            print("\n--- Extracted Entities ---")
            entities = doc_ai_handler.extract_entities(document_object)
            for i, entity in enumerate(entities[:5]): # Print first 5 entities
                print(f"  Entity {i+1}: Type='{entity['type']}', Text='{entity['mention_text']}', Confidence={entity['confidence']:.2f}")
            if len(entities) > 5: print("  ...")

            print("\n--- Extracted Form Fields ---")
            form_fields = doc_ai_handler.extract_form_fields(document_object)
            for i, field in enumerate(form_fields[:5]): # Print first 5 form fields
                print(f"  Field {i+1}: Name='{field['field_name']}', Value='{field['field_value']}'")
            if len(form_fields) > 5: print("  ...")

            print("\n--- Extracted Tables ---")
            tables = doc_ai_handler.extract_tables(document_object)
            for i, table in enumerate(tables[:2]): # Print first 2 tables
                print(f"  Table {i+1} (Page {table['page_number']}):")
                for r_idx, row in enumerate(table['rows'][:3]): # Print first 3 rows
                    print(f"    Row {r_idx+1}: {row}")
                if len(table['rows']) > 3: print("      ...")
            if len(tables) > 2: print("  ...")

        except Exception as e:
            print(f"An error occurred: {e}")
            logger.error("DocAI processing example failed", exc_info=True)
