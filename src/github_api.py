# src/github_api.py - Functions for interacting with the GitHub API

import os
import requests
import json


class GitHubAPI:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            # Use diff format for getting PR changes
            "Accept": "application/vnd.github.v3.diff",
        }
        self.repo = os.getenv("GITHUB_REPOSITORY") # e.g., "owner/repo"
        self.api_base_url = os.getenv("GITHUB_API_URL", "https://api.github.com") # Default to public GitHub API

    def get_pr_details(self, pr_number):
        """Fetches PR title, description, source branch name, and diff."""
        pr_url = f"{self.api_base_url}/repos/{self.repo}/pulls/{pr_number}"
        diff_url = f"{pr_url}.diff"
        
        pr_details = None
        diff_content = None

        try:
            # Get PR metadata (title, body, head ref)
            # Use standard JSON Accept header
            json_headers = self.headers.copy()
            json_headers["Accept"] = "application/vnd.github.v3+json"
            response_pr = requests.get(pr_url, headers=json_headers)
            response_pr.raise_for_status() # Raise an exception for bad status codes
            pr_data = response_pr.json()
            pr_details = {
                "title": pr_data.get("title", ""),
                "description": pr_data.get("body", ""),
                "branch_name": pr_data.get("head", {}).get("ref", "") # Extract head ref
            }
            
            # Get PR diff (Use diff Accept header)
            diff_headers = self.headers.copy()
            diff_headers["Accept"] = "application/vnd.github.v3.diff"
            response_diff = requests.get(diff_url, headers=diff_headers)
            response_diff.raise_for_status()
            diff_content = response_diff.text

        except requests.exceptions.RequestException as e:
            print(f"Error fetching PR details for #{pr_number}: {e}")
            return None, None

        return pr_details, diff_content

    def post_review_comment(self, pr_number, commit_id, path, line, body):
        """Posts a review comment on a specific line in a file."""
        # Note: Posting comments requires commit_id of the latest commit on the PR branch
        # This needs to be fetched.
        # Line numbers in comments usually refer to the line in the *file* after the change,
        # not the line number in the diff hunk. This needs careful mapping.
        
        comments_url = f"{self.api_base_url}/repos/{self.repo}/pulls/{pr_number}/comments"
        payload = json.dumps({
            "body": body,
            "commit_id": commit_id,
            "path": path,
            "line": line, # The line number in the file
            # "side": "RIGHT", # Usually comment on the changed side
        })
        
        try:
            # Temporarily switch Accept header for JSON response
            json_headers = self.headers.copy()
            json_headers["Accept"] = "application/vnd.github.v3+json"
            response = requests.post(comments_url, headers=json_headers, data=payload)
            response.raise_for_status()
            print(f"Successfully posted comment to {path}:{line}")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error posting review comment: {e}")
            print(f"Response body: {response.text if 'response' in locals() else 'N/A'}")
            return None

    def get_pr_commit_id(self, pr_number):
        """Fetches the HEAD commit SHA of the pull request."""
        pr_url = f"{self.api_base_url}/repos/{self.repo}/pulls/{pr_number}"
        try:
            json_headers = self.headers.copy()
            json_headers["Accept"] = "application/vnd.github.v3+json"
            response = requests.get(pr_url, headers=json_headers)
            response.raise_for_status()
            pr_data = response.json()
            return pr_data.get("head", {}).get("sha")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching PR commit ID for #{pr_number}: {e}")
            return None

    def get_file_content(self, file_path, ref):
        """Fetches the raw content of a file at a specific ref (commit SHA, branch, etc.)."""
        # Use the Get Repository Content endpoint
        # https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#get-repository-content
        content_url = f"{self.api_base_url}/repos/{self.repo}/contents/{file_path}"
        query_params = {"ref": ref}

        # We need raw content, so use the 'application/vnd.github.raw' media type
        raw_headers = self.headers.copy()
        raw_headers["Accept"] = "application/vnd.github.raw"

        try:
            response = requests.get(content_url, headers=raw_headers, params=query_params)
            response.raise_for_status()
            # The response body is the raw file content
            return response.text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"Warning: File not found at path '{file_path}' for ref '{ref}'. It might be a new file in the PR.")
                # Return None or empty string? For new files, the full content doesn't exist at the commit yet.
                # Let's return an empty string to signify this case distinctly from an API error.
                return ""
            else:
                print(f"Error fetching file content for {file_path} at ref {ref}: {e}")
                print(f"Response body: {e.response.text}")
                return None # Indicate a fetch error
        except requests.exceptions.RequestException as e:
            print(f"Error fetching file content for {file_path} at ref {ref}: {e}")
            return None # Indicate a fetch error

    def post_pr_comment(self, pr_number, body):
        """Posts a general comment on the Pull Request (issue comment)."""
        # Uses the issues endpoint, as PRs are issues
        issue_comment_url = f"{self.api_base_url}/repos/{self.repo}/issues/{pr_number}/comments"
        payload = json.dumps({"body": body})

        try:
            json_headers = self.headers.copy()
            json_headers["Accept"] = "application/vnd.github.v3+json"
            response = requests.post(issue_comment_url, headers=json_headers, data=payload)
            response.raise_for_status()
            print(f"Successfully posted summary comment to PR #{pr_number}")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error posting PR comment: {e}")
            print(f"Response body: {response.text if 'response' in locals() else 'N/A'}")
            return None


# Example usage (for testing)
if __name__ == "__main__":
    # Requires GITHUB_TOKEN, GITHUB_REPOSITORY, and PR_NUMBER env vars set for testing
    pr_num_test = os.getenv("PR_NUMBER_TEST")
    if pr_num_test and os.getenv("GITHUB_TOKEN") and os.getenv("GITHUB_REPOSITORY"):
        api = GitHubAPI()
        print(f"Testing with PR #{pr_num_test} in repo {api.repo}")
        
        details, diff = api.get_pr_details(pr_num_test)
        if details and diff:
            print("\n--- PR Details ---")
            print(f"Title: {details['title']}")
            # print(f"Description: {details['description']}")
            print("\n--- PR Diff Snippet ---")
            print(diff[:500] + "...") # Print start of diff
            
            commit_id = api.get_pr_commit_id(pr_num_test)
            if commit_id:
                print(f"\nHEAD commit ID: {commit_id}")
                # Example fetching file content - replace with a real file path
                test_file_path = "README.md" # Replace with a file expected in your test repo
                print(f"\n--- Fetching content for {test_file_path} at {commit_id[:7]} ---")
                file_content = api.get_file_content(test_file_path, commit_id)
                if file_content is not None:
                    print(f"Content (first 200 chars):\n{file_content[:200]}...")
                else:
                    print("Could not fetch file content.")
                # Example posting - replace with actual path/line from diff
                # api.post_review_comment(pr_num_test, commit_id, "src/main.py", 10, "Test comment from script")
                # Example posting PR comment
                # api.post_pr_comment(pr_num_test, "This is a test summary comment.")
            else:
                print("\nCould not get commit ID.")
        else:
            print("\nCould not fetch PR details.")
    else:
        print("Skipping github_api.py example usage.")
        print("Set GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER_TEST env vars to run.") 