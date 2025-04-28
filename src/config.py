# src/config.py - Configuration loading and management

import os
import yaml # Requires PyYAML package
import sys

# Get default config path from environment variable set by action.yml, 
# defaulting to the standard path if not set (e.g., during local testing)
# Renamed default config file
DEFAULT_CONFIG_PATH_IN_REPO = os.getenv("CONFIG_PATH", ".github/ai-reviewer.yml") 
DEFAULT_INSTRUCTIONS = "Focus on bugs, security, and performance. Do not suggest code comments."

# Jira credentials from environment variables (set by the workflow)
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER_EMAIL = os.getenv("JIRA_USER_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Note: AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) and 
# config (AWS_REGION, BEDROCK_MODEL_ID) are read directly from env vars 
# by bedrock_client.py and action.yml. We don't need to load them here.

def load_config(config_path_override=None):
    """Loads configuration from the YAML file or returns defaults.
    Uses config_path_override if provided, otherwise uses DEFAULT_CONFIG_PATH_IN_REPO.
    Also injects Jira credentials from environment variables if Jira is enabled in the config file.
    """
    target_config_path = config_path_override if config_path_override else DEFAULT_CONFIG_PATH_IN_REPO
    
    # Base default config structure
    config = {
        "exclude": [],
        "custom_instructions": DEFAULT_INSTRUCTIONS,
        "jira": { 
            "enabled": False,
            "url": None,
            "user_email": None,
            "api_token": None,
            "project_keys": [],
            "ticket_id_pattern": None # Will default in JiraClient if None
        }
    }

    # Determine absolute path to config file within the checked-out repository
    workspace_path = os.getenv("GITHUB_WORKSPACE", ".") # Default to current dir if not in GHA
    absolute_config_path = os.path.join(workspace_path, target_config_path)

    print(f"Attempting to load config from: {absolute_config_path} (relative: {target_config_path})")
    if os.path.exists(absolute_config_path):
        try:
            with open(absolute_config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # Merge user config into defaults, overwriting where specified
                    config["exclude"] = user_config.get("exclude", config["exclude"])
                    config["custom_instructions"] = user_config.get("custom_instructions", config["custom_instructions"])
                    
                    # Merge Jira config section carefully
                    if "jira" in user_config:
                        user_jira_config = user_config["jira"] or {}
                        config["jira"]["enabled"] = user_jira_config.get("enabled", config["jira"]["enabled"])
                        # Only update url, project_keys, pattern from file. Credentials come from env vars.
                        config["jira"]["url"] = user_jira_config.get("url", config["jira"]["url"])
                        config["jira"]["project_keys"] = user_jira_config.get("project_keys", config["jira"]["project_keys"])
                        config["jira"]["ticket_id_pattern"] = user_jira_config.get("ticket_id_pattern", config["jira"]["ticket_id_pattern"])
                        
            print("Successfully loaded and merged user configuration.")
        except yaml.YAMLError as e:
            print(f"Warning: Error parsing config file {target_config_path}: {e}. Using defaults.", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Error reading config file {target_config_path}: {e}. Using defaults.", file=sys.stderr)
    else:
        print(f"Config file not found at {absolute_config_path}. Using default configuration.")

    # Inject Jira credentials from environment variables if Jira is enabled
    if config["jira"]["enabled"]:
        print("Jira is enabled. Injecting credentials from environment variables.")
        # Use credentials from env vars if available, otherwise keep potentially file-loaded URL (though secrets are preferred)
        config["jira"]["url"] = JIRA_URL or config["jira"].get("url") 
        config["jira"]["user_email"] = JIRA_USER_EMAIL
        config["jira"]["api_token"] = JIRA_API_TOKEN

        # Validate that necessary Jira env vars are present if enabled
        if not config["jira"].get("url") or not config["jira"].get("user_email") or not config["jira"].get("api_token"):
            print("Warning: Jira is enabled in config, but one or more required Jira environment variables (JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN) are missing. Jira integration might fail.", file=sys.stderr)
            # Optionally disable Jira if secrets are missing
            # config["jira"]["enabled"] = False 
            # print("Disabling Jira integration due to missing secrets.", file=sys.stderr)

    return config

# Example usage (for testing)
if __name__ == "__main__":
    print("\n--- Testing config loading (Defaults) ---")
    default_config = load_config("non_existent_file.yml")
    print(json.dumps(default_config, indent=2))

    # Simulate finding a config file
    print("\n--- Testing config loading (Simulated File) ---")
    # Create a dummy config file in the workspace
    workspace = os.getenv("GITHUB_WORKSPACE", ".")
    dummy_path_rel = ".github/ai-reviewer.yml"
    dummy_path_abs = os.path.join(workspace, dummy_path_rel)
    os.makedirs(os.path.dirname(dummy_path_abs), exist_ok=True)
    dummy_content = """
exclude:
  - "*.test.py"
custom_instructions: "Specific test instructions."
jira:
  enabled: true
  url: https://test-jira.atlassian.net # From file
  project_keys: [TEST]
"""
    with open(dummy_path_abs, 'w') as f:
        f.write(dummy_content)
    
    # Simulate Jira env vars being set
    os.environ["JIRA_URL"] = "https://secret-jira.atlassian.net"
    os.environ["JIRA_USER_EMAIL"] = "test@example.com"
    os.environ["JIRA_API_TOKEN"] = "dummytoken"
    os.environ["CONFIG_PATH"] = dummy_path_rel # Ensure load_config finds it
    
    file_config = load_config() # Load using the default path now set in env
    print(json.dumps(file_config, indent=2))
    
    # Clean up dummy file and env vars
    # os.remove(dummy_path_abs)
    # del os.environ["JIRA_URL"]
    # del os.environ["JIRA_USER_EMAIL"]
    # del os.environ["JIRA_API_TOKEN"]
    # if os.getenv("CONFIG_PATH") == dummy_path_rel:
    #      del os.environ["CONFIG_PATH"]
    print("\n--- Test finished ---") 