#!/usr/bin/env python3
"""
Deployment script for Neo4j Asset Manager to Google Compute Engine.
This script automates the deployment process to a GCE VM.
"""
import argparse
import logging
import os
import subprocess
import sys
import tempfile
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


def create_startup_script(env_vars):
    """Create a startup script for the VM."""
    startup_script = """#!/bin/bash
set -e

# Update and install dependencies
apt-get update
apt-get install -y git python3 python3-pip python3-venv

# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Clone the repository
mkdir -p /app
cd /app
git clone https://github.com/neo4j-partners/neo4j-generative-ai-google-cloud.git
cd neo4j-generative-ai-google-cloud/assetmanager

# Create .env file
cat > .env << EOL
"""
    
    # Add environment variables to startup script
    for key, value in env_vars.items():
        startup_script += f"{key}={value}\n"
    
    startup_script += """EOL

# Install dependencies
/root/.cargo/bin/uv add -r pyproject.toml

# Create systemd service
cat > /etc/systemd/system/neo4j-asset-manager.service << EOL
[Unit]
Description=Neo4j Asset Manager
After=network.target

[Service]
ExecStart=/root/.cargo/bin/uv run python -m src.main ui --port 80 --server.address=0.0.0.0
WorkingDirectory=/app/neo4j-generative-ai-google-cloud/assetmanager
Restart=always
User=root
Environment=PATH=/root/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
EOL

# Enable and start the service
systemctl daemon-reload
systemctl enable neo4j-asset-manager
systemctl start neo4j-asset-manager

# Output completion message
echo "Neo4j Asset Manager deployment complete!"
"""
    
    # Create temporary file for startup script
    fd, path = tempfile.mkstemp(suffix=".sh")
    with os.fdopen(fd, 'w') as f:
        f.write(startup_script)
    
    return path


def create_vm(project_id, vm_name, zone, machine_type, startup_script_path, service_account=None):
    """Create a VM instance in Google Compute Engine."""
    logger.info(f"Creating VM instance {vm_name} in {zone}")
    
    cmd = [
        "gcloud", "compute", "instances", "create", vm_name,
        "--project", project_id,
        "--zone", zone,
        "--machine-type", machine_type,
        "--image-project", "debian-cloud",
        "--image-family", "debian-12",
        "--tags", "http-server",
        "--metadata-from-file", f"startup-script={startup_script_path}"
    ]
    
    if service_account:
        cmd.extend(["--service-account", service_account])
    else:
        cmd.extend(["--scopes", "cloud-platform"])
    
    run_command(cmd)
    
    # Get the external IP
    ip = run_command([
        "gcloud", "compute", "instances", "describe", vm_name,
        "--project", project_id,
        "--zone", zone,
        "--format", "value(networkInterfaces[0].accessConfigs[0].natIP)"
    ])
    
    return ip


def create_firewall_rule(project_id, rule_name="allow-http"):
    """Create a firewall rule to allow HTTP traffic."""
    try:
        # Check if rule exists
        run_command([
            "gcloud", "compute", "firewall-rules", "describe", rule_name,
            "--project", project_id
        ])
        logger.info(f"Firewall rule {rule_name} already exists")
    except subprocess.CalledProcessError:
        # Create rule
        logger.info(f"Creating firewall rule {rule_name}")
        run_command([
            "gcloud", "compute", "firewall-rules", "create", rule_name,
            "--project", project_id,
            "--allow", "tcp:80",
            "--target-tags", "http-server",
            "--description", "Allow HTTP traffic to Neo4j Asset Manager"
        ])


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


def check_gcloud_auth():
    """Check if gcloud is authenticated."""
    try:
        run_command(["gcloud", "auth", "list"])
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Deploy Neo4j Asset Manager to Google Compute Engine")
    parser.add_argument("--project-id", type=str, help="Google Cloud Project ID")
    parser.add_argument("--zone", type=str, default="us-central1-a", help="Google Cloud Zone")
    parser.add_argument("--vm-name", type=str, default="neo4j-asset-manager", help="VM Instance Name")
    parser.add_argument("--machine-type", type=str, default="e2-medium", help="VM Machine Type")
    parser.add_argument("--env-file", type=str, default=".env", help="Path to .env file")
    
    args = parser.parse_args()
    
    # Set up paths
    app_dir = Path(__file__).parent
    env_file = app_dir / args.env_file
    
    # Load environment variables
    if env_file.exists():
        env_vars = get_env_vars(env_file)
        project_id = args.project_id or env_vars.get("GCP_PROJECT_ID")
        zone = args.zone or f"{env_vars.get('GCP_LOCATION', 'us-central1')}-a"
    else:
        logger.warning(f"Environment file {env_file} not found")
        project_id = args.project_id
        zone = args.zone
        env_vars = {}
    
    if not project_id:
        logger.error("Project ID not specified. Use --project-id or set GCP_PROJECT_ID in .env file")
        sys.exit(1)
    
    # Check gcloud authentication
    if not check_gcloud_auth():
        logger.error("gcloud not authenticated. Run 'gcloud auth login' first")
        sys.exit(1)
    
    # Get or create service account
    sa_email = get_or_create_service_account(project_id)
    
    # Create startup script
    startup_script_path = create_startup_script(env_vars)
    
    try:
        # Create firewall rule
        create_firewall_rule(project_id)
        
        # Create VM
        ip = create_vm(
            project_id=project_id,
            vm_name=args.vm_name,
            zone=zone,
            machine_type=args.machine_type,
            startup_script_path=startup_script_path,
            service_account=sa_email
        )
        
        logger.info(f"Deployment initiated! Your application will be available at: http://{ip}")
        logger.info("It may take a few minutes for the VM to complete the startup script.")
        logger.info(f"You can check the startup script logs with: gcloud compute ssh {args.vm_name} --zone {zone} --command 'sudo journalctl -u google-startup-scripts.service'")
    
    finally:
        # Clean up temporary file
        if os.path.exists(startup_script_path):
            os.remove(startup_script_path)


if __name__ == "__main__":
    main()
