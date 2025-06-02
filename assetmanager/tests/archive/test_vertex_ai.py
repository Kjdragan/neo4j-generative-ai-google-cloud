import os
import json
import sys
from dotenv import dotenv_values

try:
    import google.genai as genai
    print("Successfully imported google.genai")
except ImportError as e:
    print(f"Failed to import google.genai: {e}")
    sys.exit(1)

# Load environment variables directly from .env file
env_vars = dotenv_values(".env")
print(f"Found variables in .env: {list(env_vars.keys())}")

# Get required environment variables
GCP_PROJECT_ID = env_vars.get('GCP_PROJECT_ID')
LLM_MODEL = env_vars.get('LLM_MODEL', 'gemini-2.5-pro-preview-05-06')  # Default if not set
LLM_THINKING_BUDGET = env_vars.get('LLM_THINKING_BUDGET', '1024')

print(f"--- Vertex AI Test ---")
print(f"Using GCP_PROJECT_ID: {GCP_PROJECT_ID}")
print(f"Attempting to use LLM Model: {LLM_MODEL}")
print(f"With Thinking Budget: {LLM_THINKING_BUDGET}")

try:
    # Initialize Vertex AI client
    print(f"Initializing Vertex AI client")
    genai.configure(api_key=None, transport="rest", vertexai=True, 
                    project=GCP_PROJECT_ID, location="us-central1")
    
    # Try Method 1: GenerativeModel
    try:
        print("Trying method 1: GenerativeModel...")
        model = genai.GenerativeModel(model_name=LLM_MODEL)
        response = model.generate_content(
            "Write 'Hello from Vertex AI!' in a JSON object with the key 'message'.",
            generation_config=genai.GenerationConfig(
                max_output_tokens=int(LLM_THINKING_BUDGET)
            )
        )
        
        # Process response
        if hasattr(response, 'text'):
            result_text = response.text
        else:
            result_text = str(response)
            
        print(f"Response received: {result_text[:100]}...")
        
        try:
            result = json.loads(result_text)
            output = {"success": True, "message": result.get("message", "Success but unexpected format")}
        except json.JSONDecodeError:
            output = {"success": True, "message": "Received non-JSON response: " + result_text[:50]}
        
        print(json.dumps(output))
        sys.exit(0)
        
    except (AttributeError, TypeError) as e:
        print(f"Method 1 failed: {e}")
        
        # Try Method 2: Client.generate_content
        try:
            print("Trying method 2: Client.generate_content...")
            client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location="us-central1")
            response = client.generate_content(
                model=f"models/{LLM_MODEL}",
                contents="Write 'Hello from Vertex AI!' in a JSON object with the key 'message'.",
                generation_config={
                    "max_output_tokens": int(LLM_THINKING_BUDGET)
                }
            )
            
            # Process response
            if hasattr(response, 'text'):
                result_text = response.text
            else:
                result_text = str(response)
                
            print(f"Response received: {result_text[:100]}...")
            
            try:
                result = json.loads(result_text)
                output = {"success": True, "message": result.get("message", "Success but unexpected format")}
            except json.JSONDecodeError:
                output = {"success": True, "message": "Received non-JSON response: " + result_text[:50]}
            
            print(json.dumps(output))
            sys.exit(0)
            
        except Exception as e2:
            print(f"Method 2 failed: {e2}")
            
            # Try Method 3: Client.generate_text
            try:
                print("Trying method 3: Client.generate_text...")
                response = client.generate_text(
                    model=f"models/{LLM_MODEL}",
                    prompt="Write 'Hello from Vertex AI!' in a JSON object with the key 'message'.",
                    max_output_tokens=int(LLM_THINKING_BUDGET)
                )
                
                # Process response
                if hasattr(response, 'text'):
                    result_text = response.text
                else:
                    result_text = str(response)
                    
                print(f"Response received: {result_text[:100]}...")
                
                try:
                    result = json.loads(result_text)
                    output = {"success": True, "message": result.get("message", "Success but unexpected format")}
                except json.JSONDecodeError:
                    output = {"success": True, "message": "Received non-JSON response: " + result_text[:50]}
                
                print(json.dumps(output))
                sys.exit(0)
                
            except Exception as e3:
                print(f"All methods failed. Final error: {e3}")
                output = {"success": False, "message": str(e3)}
                print(json.dumps(output))
                sys.exit(1)

except Exception as e:
    print(f"Vertex AI initialization error: {str(e)}")
    output = {"success": False, "message": str(e)}
    print(json.dumps(output))
    sys.exit(1)
