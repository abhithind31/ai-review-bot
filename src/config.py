# src/config.py - Configuration loading and management

import os
import yaml # Requires PyYAML package

DEFAULT_CONFIG_PATH = ".github/gemini-reviewer.yml"
DEFAULT_INSTRUCTIONS = "Focus on bugs, security, and performance. Do not suggest code comments."

def load_config(config_path=DEFAULT_CONFIG_PATH):
    """Loads configuration from the YAML file or returns defaults."""
    config = {
        "exclude": [],
        "custom_instructions": DEFAULT_INSTRUCTIONS,
        "jira": None # Placeholder for Jira config
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
            
            if user_config:
                config["exclude"] = user_config.get("exclude", [])
                # Ensure instructions are treated as a single string block
                config["custom_instructions"] = user_config.get("custom_instructions", DEFAULT_INSTRUCTIONS).strip()
                config["jira"] = user_config.get("jira") # Load entire Jira block if present
                print(f"Loaded configuration from {config_path}")
            else:
                 print(f"Configuration file {config_path} is empty, using defaults.")

        except yaml.YAMLError as e:
            print(f"Error parsing YAML configuration file {config_path}: {e}")
            print("Using default configuration.")
        except Exception as e:
            print(f"Error reading configuration file {config_path}: {e}")
            print("Using default configuration.")
    else:
        print(f"Configuration file {config_path} not found, using defaults.")

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
        
    print("--- Testing config loading --- ")
    loaded_cfg = load_config(dummy_path)
    print("\nLoaded Config:")
    import json
    print(json.dumps(loaded_cfg, indent=2))
    
    # Test default loading
    print("\n--- Testing default config loading --- ")
    default_cfg = load_config("non_existent_file.yml")
    print("\nDefault Config:")
    print(json.dumps(default_cfg, indent=2))

    # Clean up dummy file
    os.remove(dummy_path) 