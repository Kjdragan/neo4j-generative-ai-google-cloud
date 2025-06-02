#!/usr/bin/env python
"""
Neo4j Generative AI GCP Bootstrap Verification Script

This script verifies that all required GCP resources and configurations
are in place for the Neo4j Generative AI solution.

Key features:
- Verifies GCP project access and enabled APIs
- Checks for required service accounts and their roles
- Validates storage bucket existence and accessibility
- Tests Vertex AI connectivity using the google-genai SDK
- Verifies Neo4j Aura database connectivity
- Produces a detailed JSON report of all verification results

Recent fixes:
- Updated Vertex AI client initialization to use vertexai=True with project and location
- Simplified model generation call to use the latest API format
- Fixed GCP CLI command format issues by removing single quotes around format parameters
- Improved service account verification to use list filtering instead of direct describe
- Enhanced logging functions to handle Unicode encoding errors gracefully
- Added proper environment variable handling for Vertex AI-specific variables
"""

import os
import json
import sys
import socket
from dotenv import load_dotenv, dotenv_values
from pathlib import Path
import subprocess
import platform

# Test results container
results = {
    "success": True,
    "gcp": {"success": False, "message": "", "project_id": ""},
    "storage": {"success": False, "message": "", "bucket": ""},
    "service_account": {"success": False, "message": "", "email": "", "key_found": False},
    "vertex_ai": {"success": False, "message": "", "model": ""},
    "neo4j": {"success": False, "message": "", "uri": "", "vector_indexes": []},
    "errors": []
}

# --- Helper functions ---

def log_info(message):
    """Print info message with clear formatting"""
    print(f"INFO: {message}")

def log_success(message):
    """Print success message with clear formatting"""
    try:
        print(f"✓ {message}")
    except UnicodeEncodeError:
        print(f"[SUCCESS] {message}")

def log_warning(message):
    """Print warning message with clear formatting"""
    try:
        print(f"⚠ {message}")
    except UnicodeEncodeError:
        print(f"[WARNING] {message}")

def log_error(message):
    """Print error message with clear formatting and add to results"""
    try:
        print(f"✗ {message}")
    except UnicodeEncodeError:
        print(f"[ERROR] {message}")
    results["errors"].append(message)
    
def run_command(cmd, capture_output=True):
    """Run a command and return the output"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            check=True,
            capture_output=capture_output,
            text=True
        )
        return result.stdout.strip() if capture_output else ""
    except subprocess.CalledProcessError as e:
        log_error(f"Command failed: {cmd}\nError: {e}")
        if capture_output and e.stdout:
            return e.stdout.strip()
        return None

# --- Environment setup ---

print("=== Neo4j Generative AI Bootstrap Verification ===\n")

# Load environment variables from .env file
env_path = Path(".env")
if not env_path.exists():
    log_error("No .env file found! Please create one with your configuration.")
    print(json.dumps(results))
    sys.exit(1)

# Load directly from file to avoid env var conflicts
env_vars = dotenv_values(".env")
log_info(f"Found variables in .env: {', '.join(env_vars.keys())}")

# Get key environment variables
GCP_PROJECT_ID = env_vars.get("GCP_PROJECT_ID")
GCP_LOCATION = env_vars.get("GCP_LOCATION", "us-central1")  # Default to us-central1 if not specified
VERTEX_PROJECT_ID = env_vars.get("VERTEX_PROJECT_ID", GCP_PROJECT_ID)  # Use GCP_PROJECT_ID if not specified
VERTEX_LOCATION = env_vars.get("VERTEX_LOCATION", GCP_LOCATION)  # Use GCP_LOCATION if not specified
LLM_MODEL = env_vars.get("LLM_MODEL", "gemini-2.5-pro-preview-05-06")  # Use recommended model as default
LLM_THINKING_BUDGET = env_vars.get("LLM_THINKING_BUDGET", "1024")
NEO4J_URI = env_vars.get("NEO4J_URI", "")
NEO4J_USER = env_vars.get("NEO4J_USER", "")
NEO4J_PASSWORD = env_vars.get("NEO4J_PASSWORD", "")

# Validate required variables
if not GCP_PROJECT_ID:
    log_error("GCP_PROJECT_ID not found in .env file!")
    results["gcp"]["message"] = "GCP_PROJECT_ID not set in .env"
    print(json.dumps(results))
    sys.exit(1)

results["gcp"]["project_id"] = GCP_PROJECT_ID
log_info(f"Using GCP_PROJECT_ID: {GCP_PROJECT_ID}")

# --- GCP Project verification ---

print("\n=== 1. Verifying GCP Project Access ===\n")

try:
    project_info = run_command(f"gcloud projects describe {GCP_PROJECT_ID} --format=json")
    if project_info:
        project_data = json.loads(project_info)
        log_success(f"Successfully accessed GCP project: {project_data.get('name')}")
        results["gcp"]["success"] = True
        results["gcp"]["message"] = f"Project '{project_data.get('name')}' accessible"
    else:
        log_error(f"Failed to access GCP project: {GCP_PROJECT_ID}")
        results["gcp"]["message"] = "Project not accessible"
        results["success"] = False
except Exception as e:
    log_error(f"Error verifying GCP project: {str(e)}")
    results["gcp"]["message"] = f"Error: {str(e)}"
    results["success"] = False

# --- API verification ---

print("\n=== 2. Verifying Required APIs ===\n")

required_apis = [
    "aiplatform.googleapis.com", 
    "compute.googleapis.com", 
    "storage.googleapis.com",
    "documentai.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com"
]

# Use a more reliable approach for API verification
enabled_apis = []
try:
    # Get all enabled services in one call - more reliable
    cmd = f"gcloud services list --project={GCP_PROJECT_ID} --format=value(config.name)"
    all_services = run_command(cmd)
    if all_services:
        all_services_list = all_services.splitlines()
        
        for api in required_apis:
            if api in all_services_list:
                log_success(f"{api} is enabled")
                enabled_apis.append(api)
            else:
                log_error(f"{api} is NOT enabled")
                log_info(f"Enable with: gcloud services enable {api} --project={GCP_PROJECT_ID}")
                results["success"] = False
    else:
        log_error("Could not retrieve enabled services")
        results["success"] = False
except Exception as e:
    log_error(f"Error checking APIs: {str(e)}")
    results["success"] = False

# --- Storage bucket verification ---

print("\n=== 3. Verifying Storage Bucket ===\n")

bucket_name = f"{GCP_PROJECT_ID}-data"
results["storage"]["bucket"] = f"gs://{bucket_name}"

try:
    # Verify bucket exists
    bucket_uri = f"gs://{bucket_name}"
    try:
        # Import the storage client
        try:
            from google.cloud import storage
            from google.cloud.exceptions import NotFound, Forbidden, Unauthorized
            log_success("Successfully imported google-cloud-storage package")
        except ImportError:
            log_error("Google Cloud Storage library not found")
            log_info("Install with: uv add google-cloud-storage")
            results["storage"]["message"] = "Missing google-cloud-storage package"
            results["success"] = False
            raise
        
        # Create storage client
        log_info(f"Checking bucket '{bucket_name}' in project '{GCP_PROJECT_ID}'...")
        storage_client = storage.Client(project=GCP_PROJECT_ID)
        
        # Get bucket reference and try to access it
        bucket = storage_client.bucket(bucket_name)
        bucket.reload()  # This will raise NotFound if bucket doesn't exist
        
        # If we get here, bucket exists and is accessible
        log_success(f"Storage bucket {bucket_uri} EXISTS and is accessible")
        
        # Get some basic bucket details
        bucket_details = {
            'name': bucket.name,
            'location': bucket.location,
            'storage_class': bucket.storage_class,
            'created': bucket.time_created.isoformat() if bucket.time_created else 'Unknown'
        }
        log_info(f"Bucket details: {json.dumps(bucket_details, indent=2)}")
        
        results["storage"]["success"] = True
        results["storage"]["message"] = "Bucket exists and is accessible"
        results["storage"]["bucket"] = bucket_uri
        results["storage"]["details"] = bucket_details
        
    except NotFound:
        log_error(f"Storage bucket {bucket_uri} does NOT exist")
        results["storage"]["message"] = "Bucket does not exist"
        results["storage"]["bucket"] = bucket_uri
        results["success"] = False
        
    except (Forbidden, Unauthorized):
        log_warning(f"Storage bucket {bucket_uri} exists but you don't have access permissions")
        results["storage"]["message"] = "Bucket exists but access denied"
        results["storage"]["bucket"] = bucket_uri
        results["success"] = False
        
    except Exception as e:
        log_error(f"Error checking bucket: {str(e)}")
        results["storage"]["message"] = f"Error: {str(e)}"
        results["storage"]["bucket"] = bucket_uri
        results["success"] = False
except Exception as e:
    log_error(f"Error checking storage bucket: {str(e)}")
    results["storage"]["message"] = f"Error: {str(e)}"
    results["success"] = False

# --- Service account verification ---

print("\n=== 4. Verifying Service Account ===\n")

service_account_name = "neo4j-genai-sa"
service_account_email = f"{service_account_name}@{GCP_PROJECT_ID}.iam.gserviceaccount.com"
results["service_account"]["email"] = service_account_email

try:
    # Check if service account exists - use list instead of describe
    sa_list = run_command(
        f"gcloud iam service-accounts list --filter=email:{service_account_email} "
        f"--project={GCP_PROJECT_ID} --format=value(email)"
    )
    sa_exists = sa_list if sa_list else None
    
    if sa_exists and service_account_email in sa_exists:
        log_success(f"Service account {service_account_email} exists")
        
        # Check for service account key file
        sa_key_file = "neo4j-genai-sa-key.json"
        parent_sa_key_file = "../neo4j-genai-sa-key.json"
        
        if os.path.exists(sa_key_file):
            log_success(f"Service account key file {sa_key_file} exists")
            results["service_account"]["key_found"] = True
        elif os.path.exists(parent_sa_key_file):
            log_success(f"Service account key file found in parent directory")
            # Copy key to current directory for tests
            import shutil
            shutil.copy2(parent_sa_key_file, sa_key_file)
            log_info(f"Copied service account key to current directory for tests")
            results["service_account"]["key_found"] = True
        else:
            log_warning(f"Service account key file not found. Create it with:")
            print(f"    gcloud iam service-accounts keys create {sa_key_file} \
    --iam-account={service_account_email} --project={GCP_PROJECT_ID}")
            results["service_account"]["key_found"] = False
        
        # Check IAM roles
        required_roles = [
            "roles/aiplatform.admin",
            "roles/documentai.admin",
            "roles/storage.admin",
            "roles/secretmanager.secretAccessor",
            "roles/run.admin",
            "roles/compute.admin"
        ]
        
        policy_json = run_command(f"gcloud projects get-iam-policy {GCP_PROJECT_ID} --format=json")
        if policy_json:
            policy = json.loads(policy_json)
            all_roles_assigned = True
            
            for role in required_roles:
                role_assigned = False
                for binding in policy.get("bindings", []):
                    if binding.get("role") == role:
                        member = f"serviceAccount:{service_account_email}"
                        if member in binding.get("members", []):
                            log_success(f"Role {role} is assigned to service account")
                            role_assigned = True
                            break
                
                if not role_assigned:
                    log_error(f"Role {role} is NOT assigned to service account")
                    all_roles_assigned = False
            
            if all_roles_assigned:
                results["service_account"]["success"] = True
                results["service_account"]["message"] = "Service account exists with all required roles"
            else:
                results["service_account"]["message"] = "Service account missing some required roles"
                results["success"] = False
    else:
        log_error(f"Service account {service_account_email} does not exist!")
        results["service_account"]["message"] = "Service account does not exist"
        results["success"] = False
except Exception as e:
    log_error(f"Error checking service account: {str(e)}")
    results["service_account"]["message"] = f"Error: {str(e)}"
    results["success"] = False

# --- Vertex AI verification ---

print("\n=== 5. Verifying Vertex AI ===\n")

results["vertex_ai"]["model"] = LLM_MODEL

try:
    # Try importing the right packages
    import google.genai as genai
    log_success("Successfully imported google.genai package")
    
    if LLM_MODEL != "gemini-2.5-pro-preview-05-06":
        log_warning(f"Using model {LLM_MODEL} instead of recommended model gemini-2.5-pro-preview-05-06")
    
    # Initialize client
    try:
        # Initialize Vertex AI client properly based on available credentials
        if os.getenv("GOOGLE_API_KEY"):
            # API key authentication
            client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
            log_success("Successfully initialized Vertex AI client with API key")
        else:
            # Vertex AI project authentication - using the new approach with vertexai=True
            client = genai.Client(
                vertexai=True, 
                project=VERTEX_PROJECT_ID, 
                location=VERTEX_LOCATION
            )
            log_success(f"Successfully initialized Vertex AI client with Vertex AI (project: {VERTEX_PROJECT_ID}, location: {VERTEX_LOCATION})")
        
        # Try to generate content
        prompt = "Write 'Hello from Vertex AI!' in a JSON object with the key 'message'." 
        log_info(f"Testing LLM with model: {LLM_MODEL}")
        
        # Use the exact approach provided by the user
        try:
            # Simple prompt using the exact API pattern from the example
            log_info(f"Testing LLM with model: {LLM_MODEL}")
            
            # Generate content with the model - using the exact API pattern
            response = client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt
            )
            
            # Extract text from response
            if hasattr(response, "text"):
                result_text = response.text
                log_success(f"Successfully generated content: {result_text[:100]}...")
                results["vertex_ai"]["success"] = True
                results["vertex_ai"]["message"] = "Successfully connected to Vertex AI"
                results["vertex_ai"]["model"] = LLM_MODEL
            else:
                result_text = str(response)
                log_warning(f"Response does not have 'text' attribute, using string representation: {result_text[:50]}...")
                results["vertex_ai"]["success"] = True
                results["vertex_ai"]["message"] = "Connected to Vertex AI but response format unexpected"
                results["vertex_ai"]["model"] = LLM_MODEL
        except Exception as e:
            log_error(f"Error generating content: {str(e)}")
            results["vertex_ai"]["message"] = f"Error: {str(e)}"
            results["success"] = False
    except Exception as e:
        log_error(f"Vertex AI client error: {str(e)}")
        results["vertex_ai"]["message"] = f"Error: {str(e)}"
        results["success"] = False
except ImportError as e:
    log_error(f"Failed to import google.genai: {str(e)}")
    log_info("Install with: uv add google-genai>=1.18.0")
    results["vertex_ai"]["message"] = f"Import error: {str(e)}"
    results["success"] = False

# --- Neo4j verification ---

print("\n=== 6. Verifying Neo4j Connection ===\n")

# Make sure Neo4j URI has proper scheme
if NEO4J_URI:
    # Check if URI has prefix
    if not (NEO4J_URI.startswith("neo4j://") or NEO4J_URI.startswith("neo4j+s://")):
        if ".databases.neo4j.io" in NEO4J_URI:
            # Likely an Aura instance, add secure prefix
            NEO4J_URI = f"neo4j+s://{NEO4J_URI}"
            log_info(f"Added 'neo4j+s://' prefix to Neo4j URI")
        else:
            # Add regular prefix
            NEO4J_URI = f"neo4j://{NEO4J_URI}"
            log_info(f"Added 'neo4j://' prefix to Neo4j URI")

    # Mask the full URI for security
    masked_uri = NEO4J_URI
    if len(masked_uri) > 20:
        masked_uri = masked_uri[:20] + "..." 
    results["neo4j"]["uri"] = masked_uri
    
    log_info(f"Testing connection to Neo4j at {masked_uri}")
    log_info(f"With user: {NEO4J_USER}")
    
    # Check DNS resolution first
    try:
        # Extract hostname from URI
        uri_parts = NEO4J_URI.split("://", 1)
        if len(uri_parts) > 1:
            hostname = uri_parts[1]
            # Remove port if present
            if ":" in hostname:
                hostname = hostname.split(":", 1)[0]
            
            log_info(f"Checking DNS resolution for {hostname}...")
            try:
                ip = socket.gethostbyname(hostname)
                log_success(f"DNS resolution successful: {hostname} -> {ip}")
                
                # Try connecting to Neo4j
                try:
                    from neo4j import GraphDatabase
                    driver = GraphDatabase.driver(
                        NEO4J_URI, 
                        auth=(NEO4J_USER, NEO4J_PASSWORD)
                    )
                    
                    # Test connection
                    with driver.session() as session:
                        result = session.run("RETURN 1 as test").single()["test"]
                        log_success(f"Successfully connected to Neo4j! Test query returned: {result}")
                        
                        # Check for vector indexes
                        vector_indexes = []
                        try:
                            indexes = session.run("SHOW INDEXES").data()
                            for idx in indexes:
                                if idx.get("type") == "VECTOR":
                                    vector_indexes.append(idx.get("name"))
                            
                            if vector_indexes:
                                log_success(f"Found vector indexes: {', '.join(vector_indexes)}")
                            else:
                                log_warning("No vector indexes found. You may need to create one for embedding search.")
                            
                            results["neo4j"]["vector_indexes"] = vector_indexes
                        except Exception as e:
                            log_warning(f"Could not check for vector indexes: {str(e)}")
                    
                    # Close driver
                    driver.close()
                    
                    results["neo4j"]["success"] = True
                    results["neo4j"]["message"] = "Neo4j connection successful"
                except Exception as e:
                    error_message = str(e)
                    log_error(f"Neo4j connection error: {error_message}")
                    
                    # Provide helpful diagnostics
                    if "Unauthorized" in error_message:
                        log_info("Authentication failed. Verify NEO4J_USER and NEO4J_PASSWORD in .env file.")
                    elif "AuthenticationRateLimit" in error_message:
                        log_info("Too many failed authentication attempts. Wait a few minutes and try again.")
                    elif "Connection refused" in error_message:
                        log_info("Connection refused. Check if Neo4j is running and the port is correct.")
                    
                    results["neo4j"]["message"] = f"Connection error: {error_message}"
                    results["success"] = False
            except socket.gaierror:
                log_error(f"Cannot resolve hostname '{hostname}'. Check if the Neo4j URI is correct.")
                results["neo4j"]["message"] = f"DNS resolution failed for {hostname}"
                results["success"] = False
    except Exception as e:
        log_error(f"Neo4j verification error: {str(e)}")
        results["neo4j"]["message"] = f"Error: {str(e)}"
        results["success"] = False
else:
    log_error("NEO4J_URI not set in .env file!")
    results["neo4j"]["message"] = "NEO4J_URI not set"
    results["success"] = False

# --- Print summary ---

print("\n=== Verification Summary ===\n")

if results["success"]:
    log_success("All verification checks passed!")
else:
    log_error("Some verification checks failed.")
    print("\nIssues detected:")
    for error in results["errors"]:
        print(f"- {error}")
    
    print("\nFix the issues above and run this verification again.")

# Output machine-readable results for script integration
print("\n=== JSON Results ===\n")
print(json.dumps(results, indent=2))
