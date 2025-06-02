#!/usr/bin/env python3
"""
Deployment script for Neo4j Asset Manager to Google Cloud Run.
This script automates the deployment process to Google Cloud Run.
"""
import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_command(cmd, cwd=None):
    """Run a shell command and return the output."""
    logger.info(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd,
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        if result.stdout:
            logger.info(result.stdout)
        return result.stdout.strip() if result.stdout else ""
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with error: {e}")
        if e.stderr:
            logger.error(e.stderr)
        raise


def create_dockerfile(app_dir, port=8080):
    """Create a Dockerfile for the application."""
    dockerfile_path = app_dir / "Dockerfile"
    
    # Check if Dockerfile already exists
    if dockerfile_path.exists():
        logger.info(f"Dockerfile already exists at {dockerfile_path}")
        return dockerfile_path
    
    logger.info(f"Creating Dockerfile at {dockerfile_path}")
    
    dockerfile_content = f"""FROM python:3.10-slim

WORKDIR /app

# Copy application code
COPY . .

# Install uv package manager and dependencies
RUN pip install --no-cache-dir uv && \\
    uv add -r pyproject.toml

# Set environment variables
ENV PORT={port}

# Run the application
CMD ["python", "-m", "src.main", "ui", "--port", "$PORT", "--server.address=0.0.0.0"]
"""
    
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)
        
    logger.info("Dockerfile created successfully")
    return dockerfile_path


def check_gcloud_auth():
    """Check if gcloud is authenticated."""
    try:
        run_command(["gcloud", "auth", "list"])
        return True
    except subprocess.CalledProcessError:
        return False


def get_or_create_service_account(project_id, service_account_name="neo4j-asset-manager-sa"):
    """Get or create a service account for the application."""
    sa_email = f"{service_account_name}@{project_id}.iam.gserviceservices.com"
    
    try:
        # Check if service account exists
        run_command(["gcloud", "iam", "service-accounts", "describe", sa_email, "--project", project_id])
        logger.info(f"Service account {sa_email} already exists")
    except subprocess.CalledProcessError:
        # Create service account
        logger.info(f"Creating service account {sa_email}")
        run_command([
            "gcloud", "iam", "service-accounts", "create", 
            service_account_name,
            "--display-name", "Neo4j Asset Manager Service Account",
            "--project", project_id
        ])
        
        # Add roles to service account
        roles = [
            "roles/aiplatform.user",
            "roles/storage.objectUser",
            "roles/secretmanager.secretAccessor"
        ]
        
        for role in roles:
            run_command([
                "gcloud", "projects", "add-iam-policy-binding",
                project_id,
                "--member", f"serviceAccount:{sa_email}",
                "--role", role
            ])
            
    return sa_email


def build_and_push_image(project_id, app_dir, service_name):
    """Build and push the Docker image to Google Container Registry."""
    image_name = f"gcr.io/{project_id}/{service_name}"
    
    logger.info(f"Building Docker image: {image_name}")
    run_command(["gcloud", "builds", "submit", "--tag", image_name], cwd=app_dir)
    
    return image_name


def deploy_to_cloud_run(project_id, service_name, image_name, region, sa_email, env_vars=None):
    """Deploy the application to Cloud Run."""
    logger.info(f"Deploying {service_name} to Cloud Run in {region}")
    
    cmd = [
        "gcloud", "run", "deploy", service_name,
        "--image", image_name,
        "--platform", "managed",
        "--region", region,
        "--allow-unauthenticated",
        "--service-account", sa_email,
        "--project", project_id
    ]
    
    # Add environment variables
    if env_vars:
        for key, value in env_vars.items():
            cmd.extend(["--set-env-vars", f"{key}={value}"])
    
    run_command(cmd)
    
    # Get the deployed URL
    url = run_command([
        "gcloud", "run", "services", "describe", service_name,
        "--platform", "managed",
        "--region", region,
        "--format", "value(status.url)",
        "--project", project_id
    ])
    
    return url


def get_env_vars(env_file):
    """Get environment variables from .env file."""
    load_dotenv(env_file)
    
    # Required environment variables
    required_vars = [
        "GCP_PROJECT_ID",
        "GCP_LOCATION",
        "GCP_BUCKET_NAME",
        "LLM_MODEL",
        "EMBEDDING_MODEL",
        "NEO4J_URI",
        "NEO4J_USER",
        "NEO4J_PASSWORD",
        "NEO4J_DATABASE"
    ]
    
    env_vars = {}
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            logger.warning(f"Environment variable {var} not set in {env_file}")
        else:
            env_vars[var] = value
    
    return env_vars


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Deploy Neo4j Asset Manager to Google Cloud Run")
    parser.add_argument("--project-id", type=str, help="Google Cloud Project ID")
    parser.add_argument("--region", type=str, default="us-central1", help="Google Cloud Region")
    parser.add_argument("--service-name", type=str, default="neo4j-asset-manager", help="Cloud Run Service Name")
    parser.add_argument("--env-file", type=str, default=".env", help="Path to .env file")
    
    args = parser.parse_args()
    
    # Set up paths
    app_dir = Path(__file__).parent
    env_file = app_dir / args.env_file
    
    # Load environment variables
    if env_file.exists():
        env_vars = get_env_vars(env_file)
        project_id = args.project_id or env_vars.get("GCP_PROJECT_ID")
        region = args.region or env_vars.get("GCP_LOCATION", "us-central1")
    else:
        logger.warning(f"Environment file {env_file} not found")
        project_id = args.project_id
        region = args.region
        env_vars = {}
    
    if not project_id:
        logger.error("Project ID not specified. Use --project-id or set GCP_PROJECT_ID in .env file")
        sys.exit(1)
    
    # Check gcloud authentication
    if not check_gcloud_auth():
        logger.error("gcloud not authenticated. Run 'gcloud auth login' first")
        sys.exit(1)
    
    # Create Dockerfile
    create_dockerfile(app_dir)
    
    # Get or create service account
    sa_email = get_or_create_service_account(project_id)
    
    # Build and push Docker image
    image_name = build_and_push_image(project_id, app_dir, args.service_name)
    
    # Deploy to Cloud Run
    url = deploy_to_cloud_run(
        project_id=project_id,
        service_name=args.service_name,
        image_name=image_name,
        region=region,
        sa_email=sa_email,
        env_vars=env_vars
    )
    
    logger.info(f"Deployment complete! Your application is available at: {url}")


if __name__ == "__main__":
    main()
