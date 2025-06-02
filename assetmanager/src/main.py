"""
Main entry point for the Neo4j Asset Manager application.
This script can be used to run different components of the application.
"""
import argparse
import logging
import os
import sys
from pathlib import Path

from src.data_processing.entity_extraction import process_form13_filings
from src.data_processing.text_embedding import (download_10k_filings,
                                              process_10k_filings,
                                              upload_embeddings_to_gcs)
from src.utils.config import init_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def setup_parser():
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(description="Neo4j Asset Manager")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Process 13F filings
    form13_parser = subparsers.add_parser("process-form13", help="Process Form 13F filings")
    form13_parser.add_argument("--input-dir", type=str, help="Input directory containing Form 13F filings")
    form13_parser.add_argument("--output-dir", type=str, help="Output directory for processed filings")
    form13_parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing")
    
    # Process 10K filings
    form10k_parser = subparsers.add_parser("process-form10k", help="Process Form 10K filings")
    form10k_parser.add_argument("--input-dir", type=str, help="Input directory containing Form 10K filings")
    form10k_parser.add_argument("--output-file", type=str, help="Output file for embeddings")
    form10k_parser.add_argument("--batch-size", type=int, default=3, help="Batch size for processing")
    
    # Download 10K filings
    download_parser = subparsers.add_parser("download-form10k", help="Download Form 10K filings")
    download_parser.add_argument("--bucket", type=str, default="neo4j-datasets", help="GCS bucket containing filings")
    download_parser.add_argument("--blob", type=str, default="sec-demo/form10k.zip", help="GCS blob name")
    download_parser.add_argument("--target-dir", type=str, help="Target directory to save filings")
    
    # Upload embeddings to GCS
    upload_parser = subparsers.add_parser("upload-embeddings", help="Upload embeddings to GCS")
    upload_parser.add_argument("--file", type=str, required=True, help="Embeddings file to upload")
    upload_parser.add_argument("--bucket", type=str, help="GCS bucket to upload to")
    upload_parser.add_argument("--blob", type=str, help="GCS blob name")
    
    # Run API server
    api_parser = subparsers.add_parser("api", help="Run API server")
    api_parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run API on")
    api_parser.add_argument("--port", type=int, default=8000, help="Port to run API on")
    
    # Run Streamlit UI
    ui_parser = subparsers.add_parser("ui", help="Run Streamlit UI")
    ui_parser.add_argument("--port", type=int, default=8501, help="Port to run UI on")
    
    return parser


def run_api_server(host, port):
    """Run the API server."""
    import uvicorn
    from src.api.endpoints import app
    
    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


def run_streamlit_ui(port):
    """Run the Streamlit UI."""
    import subprocess
    
    logger.info(f"Starting Streamlit UI on port {port}")
    
    # Get the path to the Streamlit app
    app_path = Path(__file__).parent / "ui" / "app.py"
    
    # Run Streamlit
    cmd = ["streamlit", "run", str(app_path), "--server.port", str(port)]
    subprocess.run(cmd)


def main():
    """Main entry point."""
    # Initialize configuration
    init_config()
    
    # Set up argument parser
    parser = setup_parser()
    args = parser.parse_args()
    
    # Execute command
    if args.command == "process-form13":
        input_dir = args.input_dir or os.environ.get("INPUT_DIR")
        output_dir = args.output_dir or os.environ.get("OUTPUT_DIR")
        
        if not input_dir or not output_dir:
            logger.error("Input and output directories must be specified")
            sys.exit(1)
            
        process_form13_filings(
            input_dir=Path(input_dir),
            output_dir=Path(output_dir),
            batch_size=args.batch_size,
        )
        
    elif args.command == "process-form10k":
        input_dir = args.input_dir
        output_file = args.output_file
        
        if not input_dir:
            logger.error("Input directory must be specified")
            sys.exit(1)
            
        process_10k_filings(
            filings_dir=Path(input_dir),
            output_file=Path(output_file) if output_file else None,
            batch_size=args.batch_size,
        )
        
    elif args.command == "download-form10k":
        target_dir = args.target_dir
        
        download_10k_filings(
            bucket_name=args.bucket,
            blob_name=args.blob,
            target_dir=Path(target_dir) if target_dir else None,
        )
        
    elif args.command == "upload-embeddings":
        file_path = args.file
        bucket = args.bucket
        blob = args.blob
        
        if not file_path:
            logger.error("Embeddings file must be specified")
            sys.exit(1)
            
        upload_embeddings_to_gcs(
            embeddings_file=Path(file_path),
            bucket_name=bucket,
            destination_blob_name=blob,
        )
        
    elif args.command == "api":
        run_api_server(args.host, args.port)
        
    elif args.command == "ui":
        run_streamlit_ui(args.port)
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
