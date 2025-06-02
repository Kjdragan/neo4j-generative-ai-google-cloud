import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get required environment variables
NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USER = os.getenv('NEO4J_USER')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

print("=== Debug Environment Variables ===")
print(f"NEO4J_URI: {NEO4J_URI}")
print(f"NEO4J_USER: {NEO4J_USER}")
print(f"NEO4J_PASSWORD length: {len(NEO4J_PASSWORD) if NEO4J_PASSWORD else 0} chars")

# Print all environment variables for debugging
print("\n=== All Environment Variables ===")
for key, value in os.environ.items():
    if key.startswith('NEO4J'):
        if 'PASSWORD' in key:
            print(f"{key}: [MASKED]")
        else:
            print(f"{key}: {value}")
