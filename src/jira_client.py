# src/jira_client.py
import os
import re
from jira import JIRA, JIRAError

# Default regex to find Jira keys like PROJ-123, CORE-45 etc.
# Looks for 2-10 uppercase letters, a hyphen, and 1 or more digits.
DEFAULT_JIRA_TICKET_PATTERN = r'([A-Z]{2,10}-\d+)'

class JiraClient:
    """Handles interaction with the Jira API."""

    def __init__(self, server_url=None, user_email=None, api_token=None):
        """Initializes the Jira client.

        Args:
            server_url (str, optional): The base URL of the Jira instance.
            user_email (str, optional): The email address of the Jira user.
            api_token (str, optional): The API token for Jira authentication.
        """
        self.client = None
        self.error = None # Store initialization error

        if not all([server_url, user_email, api_token]):
            self.error = "Jira server URL, user email, or API token is missing. Cannot initialize client."
            print(f"Warning: {self.error}")
            return # Do not proceed if credentials are missing

        try:
            print(f"Connecting to Jira at {server_url}...")
            # Basic Authentication with email and API token
            self.client = JIRA(
                server=server_url,
                basic_auth=(user_email, api_token),
                options={'verify': True} # Ensure SSL verification is enabled
            )
            # Verify connection by fetching server info (optional but good practice)
            # server_info = self.client.server_info()
            # print(f"Connected to Jira: {server_info['baseUrl']} - Version: {server_info['version']}")
            print("Jira client initialized successfully.")

        except JIRAError as e:
            self.error = f"Jira connection failed: Status {e.status_code} - {e.text}"
            print(f"Error: {self.error}", file=os.sys.stderr)
            self.client = None # Ensure client is None on failure
        except Exception as e:
            self.error = f"An unexpected error occurred during Jira client initialization: {e}"
            print(f"Error: {self.error}", file=os.sys.stderr)
            self.client = None

    def is_available(self):
        """Check if the Jira client was initialized successfully."""
        return self.client is not None and self.error is None

    def extract_ticket_keys(self, text, pattern=DEFAULT_JIRA_TICKET_PATTERN):
        """Extracts potential Jira ticket keys from a string using regex.

        Args:
            text (str): The text to search within (e.g., PR title, description).
            pattern (str, optional): The regex pattern to use for finding keys.
                                     Defaults to DEFAULT_JIRA_TICKET_PATTERN.

        Returns:
            list[str]: A list of unique potential Jira ticket keys found.
                       Returns an empty list if no keys are found or text is None.
        """
        if not text:
            return []
        
        try:
            # Find all matches and return unique keys
            matches = re.findall(pattern, text)
            # Convert to uppercase for consistency? Optional.
            # unique_keys = list(set(match.upper() for match in matches))
            unique_keys = list(set(matches)) 
            if unique_keys:
                print(f"  Found potential Jira keys: {unique_keys}")
            return unique_keys
        except re.error as e:
            print(f"Error compiling or using regex pattern '{pattern}': {e}", file=os.sys.stderr)
            return [] # Return empty on regex error

    def get_ticket_details(self, ticket_key):
        """Fetches details for a specific Jira ticket.

        Args:
            ticket_key (str): The Jira ticket key (e.g., 'PROJ-123').

        Returns:
            dict: A dictionary containing relevant ticket details (summary, description, status, etc.)
                  Returns None if the client is unavailable or the ticket is not found/accessible.
        """
        if not self.is_available():
            print("Jira client not available, cannot fetch ticket details.")
            return None

        try:
            print(f"  Fetching details for Jira ticket: {ticket_key}")
            issue = self.client.issue(ticket_key, fields="summary,description,status,issuetype,priority,labels,fixVersions,components,assignee,reporter")
            
            # Construct a dictionary with desired fields
            details = {
                "key": issue.key,
                "summary": issue.fields.summary,
                "description": issue.fields.description or "No description provided.", # Handle None description
                "status": issue.fields.status.name if issue.fields.status else "N/A",
                "type": issue.fields.issuetype.name if issue.fields.issuetype else "N/A",
                "priority": issue.fields.priority.name if issue.fields.priority else "N/A",
                "labels": issue.fields.labels or [],
                # Add more fields as needed
            }
            print(f"    Successfully fetched details for {ticket_key}")
            return details
        except JIRAError as e:
            if e.status_code == 404:
                print(f"  Jira ticket {ticket_key} not found.")
            else:
                print(f"  Error fetching Jira ticket {ticket_key}: Status {e.status_code} - {e.text}", file=os.sys.stderr)
            return None
        except Exception as e:
            print(f"  An unexpected error occurred fetching ticket {ticket_key}: {e}", file=os.sys.stderr)
            return None

    def format_context_for_prompt(self, ticket_details_list):
        """Formats fetched ticket details into a string suitable for the AI prompt.

        Args:
            ticket_details_list (list[dict]): A list of dictionaries, where each dict
                                              contains details for one Jira ticket.

        Returns:
            str: A formatted string containing the context from all tickets,
                 or "N/A" if the list is empty or None.
        """
        if not ticket_details_list:
            return "N/A"

        context_parts = []
        for details in ticket_details_list:
            if not details: continue # Skip if None was added to list due to errors

            # Truncate long descriptions
            description = details.get("description", "N/A")
            max_desc_len = 500 # Limit description length in prompt
            if len(description) > max_desc_len:
                description = description[:max_desc_len] + "... (truncated)"
                
            context = f"- Ticket: {details.get('key', 'N/A')}\n" \
                      f"  Summary: {details.get('summary', 'N/A')}\n" \
                      f"  Status: {details.get('status', 'N/A')}\n" \
                      f"  Type: {details.get('type', 'N/A')}\n" \
                      f"  Description: {description}\n"
            context_parts.append(context)

        return "\n".join(context_parts) if context_parts else "N/A"


# Example Usage (for standalone testing)
if __name__ == "__main__":
    # Requires environment variables: JIRA_SERVER_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN
    print("--- Testing Jira Client --- ")
    server = os.getenv("JIRA_SERVER_URL")
    email = os.getenv("JIRA_USER_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    test_ticket_key = os.getenv("JIRA_TEST_TICKET_KEY", "PROJ-1") # Example key

    if not all([server, email, token]):
        print("Missing Jira environment variables for testing (JIRA_SERVER_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN)")
    else:
        jira_client = JiraClient(server_url=server, user_email=email, api_token=token)

        if jira_client.is_available():
            print("\n--- Testing Key Extraction ---")
            test_text = "Fixes bug reported in PROJ-123 and addresses feature CORE-456. Ref also XYZ-789."
            keys = jira_client.extract_ticket_keys(test_text)
            print(f"Extracted keys: {keys}")

            print("\n--- Testing Ticket Detail Fetching --- ")
            details_list = []
            # Fetch details for extracted keys (or a known test key)
            keys_to_fetch = keys or [test_ticket_key] 
            for key in keys_to_fetch:
                 details = jira_client.get_ticket_details(key)
                 if details:
                     details_list.append(details)
            
            if details_list:
                # print("\nFetched Details:")
                # import json
                # print(json.dumps(details_list, indent=2))

                print("\n--- Testing Prompt Formatting ---")
                prompt_context = jira_client.format_context_for_prompt(details_list)
                print(prompt_context)
            else:
                print(f"Could not fetch details for keys: {keys_to_fetch}")
        else:
             print(f"Jira client initialization failed. Error: {jira_client.error}")

    print("\n--- Test with missing credentials ---")
    bad_client = JiraClient() # No credentials
    print(f"Is bad client available? {bad_client.is_available()}")
    print(f"Error: {bad_client.error}")
    print(f"Fetching with bad client: {bad_client.get_ticket_details('ANY-1')}")
    print(f"Extracting with bad client: {bad_client.extract_ticket_keys('Key TEST-1')}") # Should still work 