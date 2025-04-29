# src/bedrock_client.py - Wrapper for AWS Bedrock API calls (Claude)

import os
import json
import sys
import boto3
from botocore.exceptions import ClientError

# Get Bedrock config from environment variables set by action.yml
DEFAULT_BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0" # Default model
AWS_REGION = os.getenv("AWS_REGION")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID)
# AWS Credentials will be picked up by boto3 automatically from env vars:
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN (optional)

class BedrockClient:
    def __init__(self):
        if not AWS_REGION:
            print("Error: AWS_REGION environment variable not set.", file=sys.stderr)
            sys.exit("Missing AWS_REGION environment variable.")

        try:
            # Boto3 will automatically use credentials from env vars or IAM role
            self.client = boto3.client(
                service_name='bedrock-runtime',
                region_name=AWS_REGION
            )
            self.model_id = BEDROCK_MODEL_ID
            print(f"BedrockClient initialized with region: {AWS_REGION}, model: {self.model_id}")
        except Exception as e:
            print(f"Error initializing Boto3 Bedrock client: {e}", file=sys.stderr)
            sys.exit(f"Failed to initialize Boto3 client in region '{AWS_REGION}': {e}")

    def _construct_claude_payload(self, prompt):
        """Constructs the payload for Claude models on Bedrock."""
        # Claude 3 models use the Messages API format
        # Older Claude models (e.g., v2.1) might use a different text completion format.
        # Adjust this based on the specific model_id if needed.
        # Assuming Claude 3 Messages API structure:
        system_prompt = "You are an AI code review assistant. Analyze the provided code diff and context, then respond ONLY in the specified JSON format: {\"reviews\": [{\"lineNumber\": int, \"reviewComment\": str}]}. If no issues are found, return {\"reviews\": []}."
        
        # Wrap the user's prompt within the 'user' role message
        messages = [{"role": "user", "content": prompt}]

        # Maximum tokens to generate. Adjust as needed for expected review complexity.
        max_tokens = 2048 

        # Construct the body
        # Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31", # Required for Claude 3
            "max_tokens": max_tokens,
            "system": system_prompt, # System prompt for overall instruction
            "messages": messages,
            # Add other parameters like temperature, top_p if needed
            # "temperature": 0.7,
            # "top_p": 0.9,
        })
        return body

    def get_review(self, prompt):
        """Sends the prompt to the Bedrock model and expects a JSON response."""
        if not self.client:
            print("Error: Bedrock client not initialized.", file=sys.stderr)
            return {"reviews": []}

        request_body = self._construct_claude_payload(prompt)
        response_body_text = None

        try:
            print(f"\n--- Sending Prompt to Bedrock ({self.model_id}) ---")
            # print(prompt) # Keep prompt logging minimal
            print("Prompt length:", len(prompt), "chars")
            print("Request Body (partial):", request_body[:200] + "..." if len(request_body) > 200 else request_body)
            print("-------------------------------------------------")

            # Invoke the model
            response = self.client.invoke_model(
                body=request_body,
                modelId=self.model_id,
                accept='application/json',
                contentType='application/json'
            )

            # --- Process Response ---
            response_body = json.loads(response.get('body').read())
            
            # Claude 3 Messages API response structure:
            # response_body will contain keys like 'id', 'type', 'role', 'content', 'stop_reason', etc.
            # We need the text content from the 'content' list.
            # Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html#model-parameters-anthropic-claude-messages-response
            
            if response_body.get("type") == "message" and response_body.get("content"):
                # Content is a list of blocks, typically one text block
                if response_body["content"][0].get("type") == "text":
                    response_body_text = response_body["content"][0]["text"]
                else:
                    print(f"Warning: Unexpected content block type in Bedrock response: {response_body['content'][0].get('type')}", file=sys.stderr)
                    return {"reviews": []}
            else:
                # Handle potential errors or unexpected structure indicated in the response
                stop_reason = response_body.get('stop_reason', 'N/A')
                print(f"Warning: Unexpected response structure or stop reason from Bedrock: {stop_reason}. Full response body: {response_body}", file=sys.stderr)
                # Example check for blocked prompts (content filtering)
                if stop_reason == 'content_filtered':
                     print("Error: The prompt was blocked by Bedrock's content filter.", file=sys.stderr)
                return {"reviews": []} # Return empty on error or unexpected structure


            # Clean the response: Remove potential ```json ... ``` markers if any
            response_body_text = response_body_text.strip().removeprefix("```json").removesuffix("```").strip()

            print(f"\n--- Raw Bedrock Response (cleaned) ---\n{response_body_text}\n------------------------------------")

            # Parse the JSON response string
            review_data = json.loads(response_body_text)

            # Basic validation of the response structure
            if "reviews" not in review_data or not isinstance(review_data["reviews"], list):
                print(f"Warning: Invalid JSON response format from Bedrock: 'reviews' key missing or not a list. Response: {response_body_text}", file=sys.stderr)
                return {"reviews": []} # Return empty on format error

            # Validate individual review items
            valid_reviews = []
            for item in review_data["reviews"]:
                if not isinstance(item, dict) or not all(k in item for k in ("lineNumber", "reviewComment")):
                    print(f"Warning: Invalid review item format: {item}. Missing keys.", file=sys.stderr)
                    continue
                if not isinstance(item["lineNumber"], int):
                    print(f"Warning: Invalid review item format: {item}. 'lineNumber' not an integer.", file=sys.stderr)
                    continue
                if not isinstance(item["reviewComment"], str) or not item["reviewComment"].strip():
                    print(f"Warning: Invalid review item format: {item}. 'reviewComment' not a non-empty string.", file=sys.stderr)
                    continue
                valid_reviews.append(item)

            return {"reviews": valid_reviews}

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from Bedrock: {e}", file=sys.stderr)
            print(f"Raw response text was: {response_body_text}", file=sys.stderr)
            return {"reviews": []}
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message")
            print(f"AWS Bedrock API Error: {error_code} - {error_message}", file=sys.stderr)
            # Specific handling for common errors if needed
            if error_code == 'AccessDeniedException':
                print("  -> Check AWS credentials and permissions for Bedrock.", file=sys.stderr)
            elif error_code == 'ValidationException':
                 print(f"  -> Check the request payload structure and parameters. Request body: {request_body}", file=sys.stderr)
            elif error_code == 'ResourceNotFoundException':
                 print(f"  -> Ensure the model ID '{self.model_id}' is correct and available in region '{AWS_REGION}'.", file=sys.stderr)
            return {"reviews": []}
        except Exception as e:
            # Catch other potential errors
            print(f"Error during Bedrock API call or processing: {e}", file=sys.stderr)
            print(f"Exception Type: {type(e).__name__}", file=sys.stderr)
            if response_body_text:
                print(f"Response text before error: {response_body_text}", file=sys.stderr)
            return {"reviews": []}

# Example usage (for local testing - requires AWS credentials configured)
if __name__ == "__main__":
    # Set AWS_REGION for testing if not already set
    if not os.getenv("AWS_REGION"):
        # os.environ["AWS_REGION"] = "us-east-1" # Example: uncomment and set your region
        print("Warning: AWS_REGION environment variable not set for local testing.", file=sys.stderr)
        
    # Requires AWS credentials (e.g., via env vars AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    # or an IAM role/profile configured for boto3 to find.
    print("Attempting local test for BedrockClient...")
    print("Ensure AWS credentials and region are configured.")
    
    # Basic check if region seems configured
    if os.getenv("AWS_REGION"):
        try:
            client = BedrockClient()
            test_prompt = (
                "You are reviewing code.\n" 
                "File: test.py\n"
                "Diff:\n" 
                "```diff\n" 
                "+ def hello():\n" 
                "+   print(\"Hello\")\n"
                "```\n" 
                "Respond in JSON only: {\"reviews\": [{\"lineNumber\": 2, \"reviewComment\": \"Consider adding type hints.\"}]}"
            )
            review = client.get_review(test_prompt)
            print("\n--- Parsed Review Data ---")
            print(json.dumps(review, indent=2))
        except SystemExit as e:
             print(f"Local test failed during initialization: {e}")
        except Exception as e:
            print(f"Local test failed: {e}")
            print(f"Exception Type: {type(e).__name__}")
    else:
        print("Skipping bedrock_client.py example usage due to missing AWS_REGION.") 