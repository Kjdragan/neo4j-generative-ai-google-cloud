import os
import json
from dotenv import dotenv_values

# Load directly from .env file instead of using environment variables
print("Loading variables directly from .env file...")
env_vars = dotenv_values(".env")

# Get Neo4j connection details
NEO4J_URI = env_vars.get('NEO4J_URI')
NEO4J_USER = env_vars.get('NEO4J_USER')
NEO4J_PASSWORD = env_vars.get('NEO4J_PASSWORD')
NEO4J_DATABASE = env_vars.get('NEO4J_DATABASE', 'neo4j')

print(f"NEO4J_URI from .env: {NEO4J_URI}")

# Validate and fix Neo4j URI if needed
if NEO4J_URI and 'databases.neo4j.io' in NEO4J_URI and not NEO4J_URI.startswith('neo4j+s://'):
    print(f"Adding 'neo4j+s://' prefix to URI: {NEO4J_URI}")
    NEO4J_URI = f"neo4j+s://{NEO4J_URI}"

try:
    # Check DNS resolution
    import socket
    from urllib.parse import urlparse
    parsed_uri = urlparse(NEO4J_URI)
    hostname = parsed_uri.hostname
    print(f"Checking DNS resolution for {hostname}...")
    ip = socket.gethostbyname(hostname)
    print(f"✅ DNS resolution successful: {hostname} -> {ip}")
    
    # Connect to Neo4j
    import neo4j
    print(f"Connecting to Neo4j at {NEO4J_URI}...")
    driver = neo4j.GraphDatabase.driver(
        NEO4J_URI,
        auth=neo4j.basic_auth(NEO4J_USER, NEO4J_PASSWORD)
    )
    
    with driver.session(database=NEO4J_DATABASE) as session:
        # Simple connection test
        result = session.run("RETURN 'Connected to Neo4j!' as message")
        message = result.single()["message"]
        print(f"✅ {message}")
        
        # Check for vector indexes
        try:
            vector_result = session.run("SHOW INDEXES YIELD name, type WHERE type='VECTOR' RETURN name")
            vector_indexes = [record["name"] for record in vector_result]
            
            if vector_indexes:
                print(f"✅ Found {len(vector_indexes)} vector indexes: {', '.join(vector_indexes)}")
            else:
                print("⚠️ No vector indexes found. You may need to create one for embedding search.")
        except Exception as vector_err:
            print(f"⚠️ Could not check for vector indexes: {vector_err}")
    
    driver.close()
    print("✅ Neo4j connection test successful!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    
    if "AuthenticationRateLimit" in str(e):
        print("⚠️ You've hit the authentication rate limit. Wait a few minutes before trying again.")
    elif "Unauthorized" in str(e):
        print("⚠️ Check that your Neo4j username and password are correct in the .env file.")
