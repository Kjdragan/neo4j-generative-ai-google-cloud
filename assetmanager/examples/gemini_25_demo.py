"""
Demo script to showcase the Gemini 2.5 Pro Preview capabilities using the Google GenAI SDK.
Run this script with: uv run python examples/gemini_25_demo.py
"""
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

from src.utils.config import get_gcp_settings
from src.utils.genai_utils import (
    init_genai,
    generate_text,
    get_text_embedding,
    extract_structured_data
)

# Load environment variables
load_dotenv()

def text_generation_demo(prompt: str = None):
    """Demo text generation with Gemini 2.5 Pro Preview."""
    print("\n===== TEXT GENERATION DEMO =====")
    
    if not prompt:
        prompt = """
        Explain the relationship between Neo4j graph databases and 
        large language models like Gemini. What are the key benefits 
        of combining these technologies?
        """
    
    print(f"Prompt: {prompt}\n")
    
    # Get GCP settings
    gcp_settings = get_gcp_settings()
    init_genai(gcp_settings['project'], gcp_settings['location'])
    
    # Generate text with system instruction (new feature in Gemini 2.5)
    response = generate_text(
        prompt=prompt,
        temperature=0.2,
        system_instruction="You are a helpful expert in graph databases and AI. Provide clear, concise explanations with examples.",
        project_id=gcp_settings['project'],
        location=gcp_settings['location']
    )
    
    print(f"Response:\n{response}\n")


def structured_output_demo():
    """Demo structured output extraction with Gemini 2.5 Pro Preview."""
    print("\n===== STRUCTURED OUTPUT DEMO =====")
    
    text = """
    Asset Management Report - Q2 2024
    
    Company: Neo4j, Inc.
    CEO: Emil Eifrem
    Founded: 2007
    Headquarters: San Mateo, CA
    
    Key Products:
    - Neo4j Graph Database
    - Neo4j AuraDB (Cloud offering)
    - Neo4j Graph Data Science
    
    Recent Partnerships:
    1. Google Cloud Platform (April 2024)
    2. Microsoft Azure (March 2024)
    
    Financial Performance:
    Revenue: $142M (up 27% YoY)
    Employees: 850
    Valuation: $3.5B
    """
    
    print(f"Input Text:\n{text}\n")
    
    # Define schema for structured extraction
    schema = {
        "type": "object",
        "properties": {
            "company": {"type": "string"},
            "ceo": {"type": "string"},
            "founded": {"type": "integer"},
            "revenue": {"type": "string"},
            "valuation": {"type": "string"},
            "products": {"type": "array", "items": {"type": "string"}},
            "partnerships": {"type": "array", "items": {"type": "object", "properties": {
                "partner": {"type": "string"},
                "date": {"type": "string"}
            }}}
        }
    }
    
    # Get GCP settings
    gcp_settings = get_gcp_settings()
    
    # Extract structured data (new feature in Gemini 2.5)
    data = extract_structured_data(
        text=text,
        schema=schema,
        project_id=gcp_settings['project'],
        location=gcp_settings['location']
    )
    
    print("Extracted Structured Data:")
    for key, value in data.items():
        print(f"  {key}: {value}")


def embedding_demo():
    """Demo text embedding with Gemini embedding model."""
    print("\n===== EMBEDDING DEMO =====")
    
    texts = [
        "Neo4j is a graph database management system.",
        "Gemini is a large language model developed by Google.",
        "Graph databases store data in nodes and relationships."
    ]
    
    # Get GCP settings
    gcp_settings = get_gcp_settings()
    
    print("Generating embeddings for multiple texts...\n")
    
    for i, text in enumerate(texts):
        embedding = get_text_embedding(
            text=text,
            project_id=gcp_settings['project'],
            location=gcp_settings['location']
        )
        
        print(f"Text {i+1}: \"{text}\"")
        print(f"  Embedding dimension: {len(embedding)}")
        print(f"  First 5 values: {embedding[:5]}\n")


def main():
    """Run the Gemini 2.5 Pro Preview demo."""
    parser = argparse.ArgumentParser(description="Demo for Gemini 2.5 Pro Preview capabilities")
    parser.add_argument("--demo", choices=["text", "structured", "embedding", "all"], default="all",
                       help="Which demo to run")
    parser.add_argument("--prompt", type=str, default=None,
                       help="Custom prompt for text generation demo")
    
    args = parser.parse_args()
    
    print("\n🔥 GEMINI 2.5 PRO PREVIEW DEMO 🔥")
    print("Using the new Google GenAI SDK")
    print("----------------------------------\n")
    
    if args.demo in ["text", "all"]:
        text_generation_demo(args.prompt)
        
    if args.demo in ["structured", "all"]:
        structured_output_demo()
        
    if args.demo in ["embedding", "all"]:
        embedding_demo()
    
    print("\nDemo completed successfully!")


if __name__ == "__main__":
    main()
