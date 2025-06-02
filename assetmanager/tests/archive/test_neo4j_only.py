import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get required environment variables
NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USER = os.getenv('NEO4J_USER')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

# Create a dictionary to store test results - will be converted to JSON later
neo4j_test_result = {
    "success": False,
    "message": "",
    "error": "",
    "vector_indexes": []
}

print("--- Neo4j Connection Test ---")

try:
    # Validate NEO4J_URI - ensure it's not empty and has a valid scheme
    if not NEO4J_URI:
        raise ValueError("NEO4J_URI is empty. Please set it in your .env file.")
    
    # For Aura connections, the URI format is neo4j+s://hash.databases.neo4j.io
    # Check if URI has a valid scheme
    valid_schemes = ['bolt://', 'bolt+ssc://', 'bolt+s://', 'neo4j://', 'neo4j+ssc://', 'neo4j+s://']
    
    # Check if any of the valid schemes match the beginning of our URI
    is_valid_uri = any(NEO4J_URI.startswith(scheme) for scheme in valid_schemes)
    
    # Special case for Neo4j Aura - since some environment variables might not include the ://
    if not is_valid_uri and 'databases.neo4j.io' in NEO4J_URI:
        print(f"    NEO4J_URI appears to be an Aura instance but is missing proper scheme prefix.")
        print(f"    Adding 'neo4j+s://' prefix to URI: {NEO4J_URI}")
        NEO4J_URI = f"neo4j+s://{NEO4J_URI}"
        is_valid_uri = True
            
    if not is_valid_uri:
        raise ValueError(f"Invalid URI scheme. URI should start with one of: {', '.join(valid_schemes)}")
    
    # Only show first 20 chars of URI for security
    uri_display = NEO4J_URI[:20] + '...' if len(NEO4J_URI) > 20 else NEO4J_URI
    print(f"    Attempting to connect to Neo4j at {uri_display} (credentials hidden)")
    
    # Debug output for connection parameters (masking password)
    print(f"    Debug - URI: {NEO4J_URI}")
    print(f"    Debug - Username: {NEO4J_USER}")
    print(f"    Debug - Password length: {len(NEO4J_PASSWORD) if NEO4J_PASSWORD else 0} chars")
    
    # Check if hostname in URI is resolvable
    import socket
    try:
        # Extract hostname from URI
        from urllib.parse import urlparse
        parsed_uri = urlparse(NEO4J_URI)
        hostname = parsed_uri.hostname
        print(f"    Checking if hostname '{hostname}' is resolvable...")
        
        # Try to resolve the hostname
        socket.gethostbyname(hostname)
        print(f"    Hostname resolution successful for {hostname}")
    except socket.gaierror:
        print(f"    WARNING: Cannot resolve hostname '{hostname}'. Check if the Neo4j URI is correct.")
        neo4j_test_result["error"] = f"Cannot resolve hostname '{hostname}'. Check if the Neo4j URI is correct."
        neo4j_test_result["resolution"] = "Verify that the Neo4j URI in .env file is correct and the database exists."
        print(json.dumps(neo4j_test_result))
        raise ValueError(f"Cannot resolve hostname '{hostname}'")
    
    # Try to connect to Neo4j
    import neo4j
    
    # Create driver with explicit auth - make sure to use neo4j+s:// for Aura
    driver = neo4j.GraphDatabase.driver(
        NEO4J_URI,
        auth=neo4j.basic_auth(NEO4J_USER, NEO4J_PASSWORD)
    )
    
    # Test connection with simple query
    with driver.session() as session:
        # Simple query to test connection
        result = session.run("RETURN 'Connected to Neo4j!' as message")
        message = result.single()["message"]
        print(f"    Neo4j Test Success: {message}")
        neo4j_test_result["success"] = True
        neo4j_test_result["message"] = message
        
        # Check for Vertex AI Vector Index
        try:
            vector_result = session.run("SHOW INDEXES YIELD name, type WHERE type='VECTOR' RETURN name")
            vector_indexes = [record["name"] for record in vector_result]
            
            if vector_indexes:
                print(f"    Found {len(vector_indexes)} vector indexes: {', '.join(vector_indexes)}")
                neo4j_test_result["vector_indexes"] = vector_indexes
            else:
                print("    No vector indexes found. You may need to create one for embedding search.")
        except Exception as vector_err:
            print(f"    Could not check for vector indexes: {vector_err}")
            neo4j_test_result["vector_index_error"] = str(vector_err)
    
    driver.close()

except Exception as e:
    error_message = str(e)
    print(f"    Neo4j Connection ERROR: {error_message}")
    neo4j_test_result["error"] = error_message
    
    # Check for common errors and provide helpful messages
    if "AuthenticationRateLimit" in error_message:
        print("    NOTE: You've hit the authentication rate limit. Wait a few minutes before trying again.")
        neo4j_test_result["resolution"] = "Wait a few minutes before trying again due to authentication rate limit."
    elif "Unauthorized" in error_message:
        print("    NOTE: Check that your Neo4j username and password are correct in the .env file.")
        neo4j_test_result["resolution"] = "Verify Neo4j credentials in .env file."
    elif "Unable to retrieve routing information" in error_message:
        print("    NOTE: Unable to reach Neo4j server. Check if the URI is correct and the database is online.")
        neo4j_test_result["resolution"] = "Verify Neo4j URI and check if database is online."

# Output the structured result as JSON for PowerShell to parse
print(json.dumps(neo4j_test_result))
