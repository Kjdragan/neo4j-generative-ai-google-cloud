import os
import json
from dotenv import load_dotenv
import google.genai as genai

# Load environment variables from .env in the current directory (assetmanager)
load_dotenv()

# Get environment variables with fallbacks
PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'neo4j-deployment-new1')
NEO4J_URI = os.getenv('NEO4J_URI', '')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'gemini-2.5-pro-preview-05-06')  # Using preferred model
LLM_THINKING_BUDGET = int(os.getenv('LLM_THINKING_BUDGET', 1024))

print(f"Python: Using GCP_PROJECT_ID: {PROJECT_ID}")

# Vertex AI Test
print("  --- Vertex AI Test --- ")
print(f"    Attempting to use LLM Model: {LLM_MODEL}")
print(f"    With Thinking Budget: {LLM_THINKING_BUDGET}")

try:
    # Initialize Vertex AI client according to google-genai SDK
    client = genai.Client(project=PROJECT_ID, location='us-central1', vertexai=True)
    
    # Set up generation parameters as a simple dictionary
    generation_params = {
        'temperature': 0.1,
        'max_output_tokens': 1024
    }
    
    # Quick test of LLM with proper API format
    prompt = "Hello, are you operational?"
    response = client.generate_content(
        model=LLM_MODEL,
        contents=prompt,
        **generation_params  # Pass parameters directly
    )
    
    # Print response
    print("    Vertex AI Test Success: Model responded with:")
    print(f"    {response.text[:100]}...")
    
except Exception as e:
    print(f"    Vertex AI Test ERROR: {str(e)}")

# Neo4j Connection Test
print("  --- Neo4j Connection Test --- ")

# Validate NEO4J_URI - ensure it's not empty and has a valid scheme
if not NEO4J_URI or '://' not in NEO4J_URI:
    print(f"    Neo4j Connection ERROR: Invalid URI format. URI should include a scheme like 'neo4j://', 'bolt://' or 'neo4j+s://'")
    raise ValueError("Invalid Neo4j URI")

# Only show first 20 chars of URI for security
uri_display = NEO4J_URI[:20] + '...' if len(NEO4J_URI) > 20 else NEO4J_URI
print(f"    Attempting to connect to Neo4j at {uri_display} (credentials hidden)")

try:
    # Try to connect to Neo4j
    import neo4j
    driver = neo4j.GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
        
    # Test connection with simple query
    with driver.session() as session:
        # Simple query to test connection
        result = session.run("RETURN 'Connected to Neo4j!' as message")
        message = result.single()["message"]
        print(f"    Neo4j Test Success: {message}")
            
            # Check for Vertex AI Vector Index
            try:
                vector_result = session.run("SHOW INDEXES YIELD name, type WHERE type='VECTOR' RETURN name")
                vector_indexes = [record["name"] for record in vector_result]
                
                if vector_indexes:
                    print(f"    Found {len(vector_indexes)} vector indexes: {', '.join(vector_indexes)}")
                else:
                    print("    No vector indexes found. You may need to create one for embedding search.")
            except Exception as vector_err:
                print(f"    Could not check for vector indexes: {vector_err}")
        
        driver.close()
    except Exception as e:
        print(f"   Neo4j Connection ERROR: {e}")

