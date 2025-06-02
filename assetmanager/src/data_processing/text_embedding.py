"""
Text embedding module for processing SEC 10-K filings.
This replaces the functionality from the '2-text-embedding' notebook.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from google.cloud import storage
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tqdm import tqdm

from src.utils.config import BUCKET_NAME, DATA_DIR, get_gcp_settings
from src.utils.genai_utils import get_text_embedding, GEMINI_EMBEDDING_MODEL

logger = logging.getLogger(__name__)


def download_10k_filings(bucket_name: str = "neo4j-datasets", 
                         blob_name: str = "sec-demo/form10k.zip",
                         target_dir: Optional[Path] = None) -> Path:
    """
    Download 10-K filings from Google Cloud Storage.
    
    Args:
        bucket_name: The name of the bucket containing the filings
        blob_name: The name of the blob containing the filings
        target_dir: Optional target directory to save the filings to
        
    Returns:
        Path: The path to the extracted filings
    """
    if target_dir is None:
        target_dir = DATA_DIR
        
    # Create target directory if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)
    
    zip_path = target_dir / "form10k.zip"
    extract_path = target_dir / "form10k"
    
    # Download file if it doesn't exist
    if not zip_path.exists():
        logger.info(f"Downloading 10-K filings from gs://{bucket_name}/{blob_name}")
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(str(zip_path))
        logger.info(f"Downloaded 10-K filings to {zip_path}")
    else:
        logger.info(f"10-K filings already downloaded to {zip_path}")
    
    # Extract file if directory doesn't exist
    if not extract_path.exists():
        logger.info(f"Extracting 10-K filings to {extract_path}")
        os.makedirs(extract_path, exist_ok=True)
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        logger.info(f"Extracted 10-K filings to {extract_path}")
    else:
        logger.info(f"10-K filings already extracted to {extract_path}")
    
    return extract_path


def chunk_text(text: str, 
               chunk_size: int = 2000, 
               chunk_overlap: int = 15) -> List[str]:
    """
    Split text into smaller chunks for embedding.
    
    Args:
        text: The text to chunk
        chunk_size: The size of each chunk
        chunk_overlap: The overlap between chunks
        
    Returns:
        List[str]: The chunked text
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )
    
    return text_splitter.split_text(text)


def create_text_embedding_entries(input_text: str, 
                                 company_name: str, 
                                 cusip: str,
                                 model_name: str = GEMINI_EMBEDDING_MODEL) -> List[Dict[str, Any]]:
    """
    Create text embedding entries for a company's 10-K filing.
    
    Args:
        input_text: The text to embed
        company_name: The name of the company
        cusip: The CUSIP identifier for the company
        model_name: The embedding model to use
        
    Returns:
        List[Dict[str, Any]]: The embedding entries
    """
    # Chunk the text
    docs = chunk_text(input_text)
    
    result = []
    for seq_id, doc in enumerate(docs):
        # Skip empty chunks
        if not doc.strip():
            continue
            
        # Get embedding
        try:
            # Get GCP settings for the GenAI SDK
            gcp_settings = get_gcp_settings()
            
            embedding = get_text_embedding(
                text=doc, 
                model_name=model_name,
                project_id=gcp_settings.get('project'),
                location=gcp_settings.get('location')
            )
            
            result.append({
                "cusip": cusip,
                "company_name": company_name,
                "sequence_id": seq_id,
                "text": doc,
                "embedding": embedding,
            })
        except Exception as e:
            logger.error(f"Error creating embedding for {company_name} chunk {seq_id}: {e}")
    
    return result


def process_10k_filings(filings_dir: Path, 
                        output_file: Optional[Path] = None,
                        batch_size: int = 3) -> pd.DataFrame:
    """
    Process 10-K filings to create embeddings.
    
    Args:
        filings_dir: Directory containing 10-K filings
        output_file: Optional file to save the embeddings to
        batch_size: Number of chunks to process in each batch
        
    Returns:
        pd.DataFrame: DataFrame containing the embeddings
    """
    if output_file is None:
        output_file = DATA_DIR / "10k_embeddings.csv"
        
    all_embeddings = []
    
    # Get list of files
    files = list(filings_dir.glob("*.txt"))
    logger.info(f"Found {len(files)} 10-K filings")
    
    # Process each file
    for file_path in tqdm(files, desc="Processing 10-K filings"):
        try:
            # Load file
            with open(file_path, 'r', encoding='utf-8') as f:
                filing = json.load(f)
                
            # Extract file name without extension
            file_id = file_path.stem
            
            # Get company name and CUSIP
            company_name = filing.get("companyName", "Unknown")
            cusip = filing.get("cusip", file_id)
            
            # Process item 1 (business description)
            if "item1" in filing and filing["item1"]:
                logger.info(f"Processing {company_name} ({cusip})")
                
                # Create embeddings
                embeddings = create_text_embedding_entries(
                    input_text=filing["item1"],
                    company_name=company_name,
                    cusip=cusip,
                )
                
                all_embeddings.extend(embeddings)
                
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
    
    # Create DataFrame
    df = pd.DataFrame(all_embeddings)
    
    # Save to file if specified
    if output_file:
        # Create directory if it doesn't exist
        os.makedirs(output_file.parent, exist_ok=True)
        
        # Save to CSV (excluding embedding column which is too large)
        df_save = df.drop(columns=["embedding"])
        df_save.to_csv(output_file, index=False)
        
        # Save embeddings separately as numpy arrays or in a format suitable for Neo4j
        embedding_file = output_file.with_suffix(".npy")
        import numpy as np
        np.save(embedding_file, np.array(df["embedding"].tolist()))
        
        logger.info(f"Saved embeddings to {output_file} and {embedding_file}")
    
    return df


def upload_embeddings_to_gcs(embeddings_file: Path, 
                            bucket_name: str = BUCKET_NAME,
                            destination_blob_name: Optional[str] = None) -> str:
    """
    Upload embeddings to Google Cloud Storage.
    
    Args:
        embeddings_file: Path to the embeddings file
        bucket_name: Name of the bucket to upload to
        destination_blob_name: Optional name for the destination blob
        
    Returns:
        str: The URI of the uploaded blob
    """
    if destination_blob_name is None:
        destination_blob_name = f"embeddings/{embeddings_file.name}"
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    
    blob.upload_from_filename(str(embeddings_file))
    
    uri = f"gs://{bucket_name}/{destination_blob_name}"
    logger.info(f"Uploaded embeddings to {uri}")
    
    return uri


def import_embeddings_to_neo4j(embeddings_df: pd.DataFrame) -> None:
    """
    Import embeddings to Neo4j.
    This function will need to be implemented based on your Neo4j schema.
    
    Args:
        embeddings_df: DataFrame containing the embeddings
    """
    from src.utils.neo4j_utils import Neo4jConnection
    
    with Neo4jConnection() as neo4j:
        # First, create companies
        companies = embeddings_df[["cusip", "company_name"]].drop_duplicates().to_dict("records")
        for company in tqdm(companies, desc="Creating companies"):
            neo4j.merge_node(
                label="Company",
                unique_properties={"cusip": company["cusip"]},
                other_properties={"name": company["company_name"]}
            )
        
        # Then, create text chunks and link to companies
        for _, row in tqdm(embeddings_df.iterrows(), desc="Creating text chunks", total=len(embeddings_df)):
            # Create text chunk node
            chunk_id = neo4j.create_node(
                label="TextChunk",
                properties={
                    "text": row["text"],
                    "sequence_id": row["sequence_id"],
                    "embedding": row["embedding"],  # This depends on Neo4j's ability to store vectors
                }
            )
            
            # Link text chunk to company
            neo4j.run_query(
                """
                MATCH (c:Company {cusip: $cusip}), (t:TextChunk)
                WHERE id(t) = $chunk_id
                CREATE (c)-[:HAS_DESCRIPTION]->(t)
                """,
                params={"cusip": row["cusip"], "chunk_id": chunk_id}
            )
    
    logger.info(f"Imported {len(embeddings_df)} embeddings to Neo4j")
