import os
import json
from dotenv import load_dotenv, dotenv_values

# First, clear any existing environment variables that might conflict
for key in list(os.environ.keys()):
    if key.startswith('NEO4J'):
        print(f"Warning: Found existing environment variable {key}={os.environ[key]}")

# Load directly from .env file instead of using environment variables
print("Loading variables directly from .env file...")
env_vars = dotenv_values(".env")

# Get required environment variables
NEO4J_URI = env_vars.get('NEO4J_URI')
NEO4J_USER = env_vars.get('NEO4J_USER')
NEO4J_PASSWORD = env_vars.get('NEO4J_PASSWORD')
NEO4J_DATABASE = env_vars.get('NEO4J_DATABASE', 'neo4j')

# Create a dictionary to store test results
neo4j_test_result = {
    "success": False,
    "message": "",
    "error": "",
    "vector_indexes": []
}

print("--- Neo4j Connection Test ---")
print(f"Using values directly from .env file:")
print(f"NEO4J_URI: {NEO4J_URI}")
print(f"NEO4J_USER: {NEO4J_USER}")
print(f"NEO4J_PASSWORD length: {len(NEO4J_PASSWORD) if NEO4J_PASSWORD else 0} chars")

try:
    # Validate NEO4J_URI
    if not NEO4J_URI:
        raise ValueError("NEO4J_URI is empty in .env file")
    
    # For Aura connections, the URI format is neo4j+s://hash.databases.neo4j.io
    valid_schemes = ['bolt://', 'bolt+ssc://', 'bolt+s://', 'neo4j://', 'neo4j+ssc://', 'neo4j+s://']
    is_valid_uri = any(NEO4J_URI.startswith(scheme) for scheme in valid_schemes)
    
    # Add prefix if needed
    if not is_valid_uri and 'databases.neo4j.io' in NEO4J_URI:
        print(f"Adding 'neo4j+s://' prefix to URI: {NEO4J_URI}")
        NEO4J_URI = f"neo4j+s://{NEO4J_URI}"
        is_valid_uri = True
    
    if not is_valid_uri:
        raise ValueError(f"Invalid URI scheme. URI should start with one of: {', '.join(valid_schemes)}")
    
    # Check if hostname is resolvable
    import socket
    from urllib.parse import urlparse
    parsed_uri = urlparse(NEO4J_URI)
    hostname = parsed_uri.hostname
    print(f"Checking if hostname '{hostname}' is resolvable...")
    
    try:
        socket.gethostbyname(hostname)
        print(f"Hostname resolution successful for {hostname}")
    except socket.gaierror:
        print(f"WARNING: Cannot resolve hostname '{hostname}'. Check if the Neo4j URI is correct.")
        neo4j_test_result["error"] = f"Cannot resolve hostname '{hostname}'. Check if the Neo4j URI is correct."
        neo4j_test_result["resolution"] = "Verify that the Neo4j URI in .env file is correct and the database exists."
        print(json.dumps(neo4j_test_result))
        raise ValueError(f"Cannot resolve hostname '{hostname}'")
    
    # Try to connect to Neo4j
    print(f"Attempting to connect to Neo4j at {NEO4J_URI}")
    import neo4j
    
    # Create driver with explicit auth
    driver = neo4j.GraphDatabase.driver(
        NEO4J_URI,
        auth=neo4j.basic_auth(NEO4J_USER, NEO4J_PASSWORD)
    )
    
    # Test connection with simple query
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run("RETURN 'Connected to Neo4j!' as message")
        message = result.single()["message"]
        print(f"Neo4j Test Success: {message}")
        neo4j_test_result["success"] = True
        neo4j_test_result["message"] = message
        
        # Check for Vertex AI Vector Index
        try:
            vector_result = session.run("SHOW INDEXES YIELD name, type WHERE type='VECTOR' RETURN name")
            vector_indexes = [record["name"] for record in vector_result]
            
            if vector_indexes:
                print(f"Found {len(vector_indexes)} vector indexes: {', '.join(vector_indexes)}")
                neo4j_test_result["vector_indexes"] = vector_indexes
            else:
                print("No vector indexes found. You may need to create one for embedding search.")
        except Exception as vector_err:
            print(f"Could not check for vector indexes: {vector_err}")
            neo4j_test_result["vector_index_error"] = str(vector_err)
    
    driver.close()

except Exception as e:
    error_message = str(e)
    print(f"Neo4j Connection ERROR: {error_message}")
    neo4j_test_result["error"] = error_message
    
    # Check for common errors and provide helpful messages
    if "AuthenticationRateLimit" in error_message:
        print("NOTE: You've hit the authentication rate limit. Wait a few minutes before trying again.")
        neo4j_test_result["resolution"] = "Wait a few minutes before trying again due to authentication rate limit."
    elif "Unauthorized" in error_message:
        print("NOTE: Check that your Neo4j username and password are correct in the .env file.")
        neo4j_test_result["resolution"] = "Verify Neo4j credentials in .env file."
    elif "Unable to retrieve routing information" in error_message:
        print("NOTE: Unable to reach Neo4j server. Check if the URI is correct and the database is online.")
        neo4j_test_result["resolution"] = "Verify Neo4j URI and check if database is online."

# Output the structured result as JSON
print(json.dumps(neo4j_test_result))
