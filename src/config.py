# src/config.py - Configuration loading and management

import os
import yaml # Requires PyYAML package
import sys

# Get default config path from environment variable set by action.yml, 
# defaulting to the standard path if not set (e.g., during local testing)
DEFAULT_CONFIG_PATH_IN_REPO = os.getenv("CONFIG_PATH", ".github/gemini-reviewer.yml") 
DEFAULT_INSTRUCTIONS = "Focus on bugs, security, and performance. Do not suggest code comments."

# Jira credentials from environment variables (set by the workflow)
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER_EMAIL = os.getenv("JIRA_USER_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

def load_config(config_path_override=None):
    """Loads configuration from the YAML file or returns defaults.
    Uses config_path_override if provided, otherwise uses DEFAULT_CONFIG_PATH_IN_REPO.
    Also injects Jira credentials if Jira is enabled.
    """
    target_config_path = config_path_override if config_path_override else DEFAULT_CONFIG_PATH_IN_REPO
    
    config = {
        "exclude": [],
        "custom_instructions": DEFAULT_INSTRUCTIONS,
        "jira": { # Default Jira config structure
            "enabled": False,
            "url": None,
            "user_email": None,
            "api_token": None,
            "project_keys": [],
            "ticket_id_pattern": None # Will default in JiraClient if None
        }
    }

    # Important: When running as an action, the config file path is relative
    # to the root of the *consuming* repository, not the action repository.
    # The GITHUB_WORKSPACE variable points to the root of the consuming repo checkout.
    workspace_path = os.getenv("GITHUB_WORKSPACE", ".") # Default to current dir if not in GHA
    absolute_config_path = os.path.join(workspace_path, target_config_path)

    print(f"Attempting to load config from: {absolute_config_path} (relative: {target_config_path})")

    if os.path.exists(absolute_config_path):
        try:
            with open(absolute_config_path, 'r') as f:
                user_config = yaml.safe_load(f)
            
            if user_config:
                config["exclude"] = user_config.get("exclude", [])
                # Ensure instructions are treated as a single string block
                config["custom_instructions"] = user_config.get("custom_instructions", DEFAULT_INSTRUCTIONS).strip()
                
                # Load Jira config block if present
                jira_config = user_config.get("jira")
                if isinstance(jira_config, dict):
                    config["jira"]["enabled"] = jira_config.get("enabled", False)
                    # Only attempt to load credentials if Jira is explicitly enabled
                    if config["jira"]["enabled"]:
                        config["jira"]["url"] = JIRA_URL
                        config["jira"]["user_email"] = JIRA_USER_EMAIL
                        config["jira"]["api_token"] = JIRA_API_TOKEN
                        config["jira"]["project_keys"] = jira_config.get("project_keys", [])
                        config["jira"]["ticket_id_pattern"] = jira_config.get("ticket_id_pattern")
                        
                        # Validation for credentials when enabled
                        if not all([JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN]):
                            print("Warning: Jira is enabled in config, but one or more required secrets (JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN) are missing from environment variables.", file=sys.stderr)
                            config["jira"]["enabled"] = False # Disable if secrets are missing
                else:
                     config["jira"]["enabled"] = False # Ensure disabled if not a dict

                print(f"Loaded configuration from {absolute_config_path}")
                if config["jira"]["enabled"]:
                    print("Jira integration is ENABLED.")
            else:
                 print(f"Configuration file {absolute_config_path} is empty, using defaults.")

        except yaml.YAMLError as e:
            print(f"Error parsing YAML configuration file {absolute_config_path}: {e}")
            print("Using default configuration.")
        except Exception as e:
            print(f"Error reading configuration file {absolute_config_path}: {e}")
            print("Using default configuration.")
    else:
        print(f"Configuration file {absolute_config_path} not found, using defaults.")

    # Basic validation
    if not isinstance(config["exclude"], list):
        print(f"Warning: 'exclude' key in config is not a list. Ignoring.")
        config["exclude"] = []
    if not isinstance(config["custom_instructions"], str):
         print(f"Warning: 'custom_instructions' key in config is not a string. Using default.")
         config["custom_instructions"] = DEFAULT_INSTRUCTIONS

    return config

# Example usage (for testing)
if __name__ == "__main__":
    # Create a dummy config file for testing
    dummy_path = "./temp_test_config.yml"
    dummy_content = """
exclude:
  - "*.log"
  - "/dist/"
custom_instructions: |
  Line 1 of instructions.
  Line 2, check for XYZ.
jira:
  project_keys: ["TEST"]
"""
    with open(dummy_path, 'w') as f:
        f.write(dummy_content)
        
    # Set dummy env vars for testing Jira credential loading
    os.environ["JIRA_URL"] = "https://test.atlassian.net"
    os.environ["JIRA_USER_EMAIL"] = "test@example.com"
    os.environ["JIRA_API_TOKEN"] = "dummytoken"
    # Simulate enabling Jira in the dummy file
    dummy_content_jira_enabled = dummy_content.replace("project_keys: [\"TEST\"]", "enabled: true\n  project_keys: [\"TEST\"]")
    with open(dummy_path, 'w') as f:
        f.write(dummy_content_jira_enabled)
        
    print("--- Testing config loading (with Jira enabled) --- ")
    loaded_cfg = load_config(dummy_path)
    print("\nLoaded Config:")
    import json
    print(json.dumps(loaded_cfg, indent=2))
    
    # Test default loading
    print("\n--- Testing default config loading --- ")
    default_cfg = load_config("non_existent_file.yml")
    print("\nDefault Config:")
    print(json.dumps(default_cfg, indent=2))

    # Clean up dummy file and env vars
    os.remove(dummy_path)
    del os.environ["JIRA_URL"]
    del os.environ["JIRA_USER_EMAIL"]
    del os.environ["JIRA_API_TOKEN"] 