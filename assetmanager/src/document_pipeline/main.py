# assetmanager/src/document_pipeline/main.py
import os
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

from .processor import DocumentProcessor, DocumentType # Assuming processor.py is in the same directory
from .neo4j_uploader import Neo4jError # To catch specific Neo4j errors

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """
    Main function to run the document processing pipeline.
    """
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env') # Load .env from assetmanager/

    parser = argparse.ArgumentParser(description="Process a document using the Document Processing Pipeline.")
    parser.add_argument("file_path", type=str, help="Path to the document file to process.")
    parser.add_argument("--gcs-bucket", type=str, default=os.getenv("GCS_BUCKET_NAME"),
                        help="GCS bucket for document staging (overrides .env).")
    parser.add_argument("--docai-processor-id", type=str, default=os.getenv("DOCAI_PROCESSOR_ID"),
                        help="Document AI processor ID to use (overrides .env).")
    parser.add_argument("--gcp-project-id", type=str, default=os.getenv("GCP_PROJECT_ID"),
                        help="GCP Project ID (overrides .env).")
    parser.add_argument("--gcp-region", type=str, default=os.getenv("GCP_REGION", "us-central1"),
                        help="GCP Region for services (overrides .env).")
    parser.add_argument("--neo4j-uri", type=str, default=os.getenv("NEO4J_URI"),
                        help="Neo4j connection URI (overrides .env).")
    parser.add_argument("--neo4j-user", type=str, default=os.getenv("NEO4J_USERNAME"),
                        help="Neo4j username (overrides .env).")
    parser.add_argument("--neo4j-password", type=str, default=os.getenv("NEO4J_PASSWORD"),
                        help="Neo4j password (overrides .env).")
    parser.add_argument("--vertex-embedding-model", type=str, default=os.getenv("VERTEX_EMBEDDING_MODEL", "text-embedding-004"),
                        help="Vertex AI embedding model (overrides .env).")
    parser.add_argument("--vertex-llm-model", type=str, default=os.getenv("VERTEX_LLM_MODEL", "gemini-2.5-pro-preview-05-06"),
                        help="Vertex AI LLM model (overrides .env).")
    parser.add_argument("--neo4j-embedding-dim", type=int, default=int(os.getenv("NEO4J_EMBEDDING_DIMENSION", 768)),
                        help="Neo4j embedding dimension (overrides .env).")

    args = parser.parse_args()

    # Validate required arguments that don't have defaults in getenv or are critical
    required_env_vars = {
        "GCP_PROJECT_ID": args.gcp_project_id,
        "NEO4J_URI": args.neo4j_uri,
        "NEO4J_USERNAME": args.neo4j_user,
        "NEO4J_PASSWORD": args.neo4j_password
    }

    missing_vars = [key for key, value in required_env_vars.items() if not value]
    if missing_vars:
        logger.error(f"Missing required configuration: {', '.join(missing_vars)}. "
                     "Please set them in .env or pass as arguments.")
        return

    try:
        logger.info(f"Initializing DocumentProcessor for project: {args.gcp_project_id}, region: {args.gcp_region}")
        processor = DocumentProcessor(
            project_id=args.gcp_project_id,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
            location=args.gcp_region,
            bucket_name=args.gcs_bucket,
            docai_default_processor_id=args.docai_processor_id,
            vertex_embedding_model=args.vertex_embedding_model,
            vertex_llm_model=args.vertex_llm_model,
            neo4j_embedding_dimension=args.neo4j_embedding_dim
        )

        file_to_process = Path(args.file_path)
        if not file_to_process.exists():
            logger.error(f"File not found: {file_to_process}")
            return

        logger.info(f"Processing document: {file_to_process}")
        
        # If a specific DocAI processor ID is provided via CLI, pass it to process_document
        # Otherwise, process_document will use the default one set during DocumentProcessor init
        docai_processor_override = args.docai_processor_id if args.docai_processor_id != os.getenv("DOCAI_PROCESSOR_ID") else None

        result = processor.process_document(
            document_path=file_to_process,
            docai_processor_id_override=docai_processor_override # Pass override if specified
        )
        
        if result:
            logger.info(f"Successfully processed document. Result: {result.get('document_id', 'N/A')}")
            if result.get("gcs_uri"):
                logger.info(f"Document uploaded to: {result['gcs_uri']}")
            if result.get("neo4j_nodes_created"):
                logger.info(f"Neo4j nodes created: {result['neo4j_nodes_created']}")
            if result.get("neo4j_relationships_created"):
                logger.info(f"Neo4j relationships created: {result['neo4j_relationships_created']}")
        else:
            logger.warning("Document processing completed, but no detailed result returned.")

    except ConnectionError as ce: # Catch connection errors from DocumentProcessor init
        logger.error(f"Connection error during setup: {ce}")
    except Neo4jError as ne:
        logger.error(f"A Neo4j operation failed: {ne}")
    except ValueError as ve:
        logger.error(f"Configuration or input error: {ve}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()
