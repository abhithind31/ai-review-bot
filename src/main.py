# src/main.py - Core logic entry point
import os
import sys
import json
from functools import lru_cache # For caching file content

# Import our modules
from github_api import GitHubAPI
from gemini_client import GeminiClient
from config import load_config
from utils import parse_diff, should_exclude_file
from utils import map_hunk_line_to_file_line
from utils import extract_context_around_hunk # Import the new function

# Define the trigger command
TRIGGER_COMMAND = "/gemini-review"

# --- Prompt Template ---
# Updated to include file context and specify focus
PROMPT_TEMPLATE = """
You are an AI assistant reviewing a code change pull request.

**Pull Request Details:**
- **Title:** {pr_title}
- **Description:**
{pr_description}

**File Being Reviewed:** `{file_path}`

**Jira Ticket Context:**
{jira_context}

**Custom Review Instructions:**
{custom_instructions}

**Relevant Code Context:**
{code_context}

**Specific Changes (Diff Hunk):**
```diff
{hunk_content}
```

**Your Task:**
Review the **Specific Changes (Diff Hunk)** within the context of the **Relevant Code Context** provided above.
Focus *exclusively* on identifying potential bugs, security vulnerabilities, performance issues, or violations of the **Custom Review Instructions** based *only* on the provided information.
If you find specific lines within the **Diff Hunk** that require changes, provide your feedback.
If the hunk looks good according to the instructions and context, respond with an empty list.

**Output Format:**
Respond *only* with a JSON object containing a list called "reviews". Each item in the list should be an object with "lineNumber" (integer, relative to the *start of the diff hunk*, starting at 1) and "reviewComment" (string).

Example valid JSON response:
{{"reviews": [{{"lineNumber": 5, "reviewComment": "This loop could lead to an infinite loop if the condition is never met."}}]}}

Example response for no issues:
{{"reviews": []}}

Do NOT suggest adding code comments or making purely stylistic changes unless specifically requested by the custom instructions.
Do NOT comment on code outside the provided **Diff Hunk**.
"""

def build_prompt(pr_details, file_path, code_context, hunk_content, custom_instructions, jira_context):
    """Builds the prompt string using the template and provided context."""
    return PROMPT_TEMPLATE.format(
        pr_title=pr_details['title'],
        pr_description=pr_details.get('description', '') or "N/A", # Handle empty description
        file_path=file_path,
        jira_context=jira_context,
        custom_instructions=custom_instructions or "N/A", # Handle empty instructions
        code_context=code_context, # Add the extracted context
        hunk_content=hunk_content # Keep the original hunk
    )

# LRU Cache decorator to avoid fetching the same file content multiple times
@lru_cache(maxsize=16) # Cache up to 16 files
def get_cached_file_content(github_api, file_path, commit_id):
    print(f"  Fetching content for: {file_path} @ {commit_id[:7]}")
    return github_api.get_file_content(file_path, commit_id)

def main():
    print("Starting AI Review Bot...")

    # 1. Get event payload path from environment variable
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print(f"Error: GITHUB_EVENT_PATH '{event_path}' is invalid or file does not exist.", file=sys.stderr)
        sys.exit(1)

    # 2. Parse event payload
    try:
        with open(event_path, 'r') as f:
            event_payload = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing event payload JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading event payload file: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract relevant details
    try:
        comment_body = event_payload["comment"]["body"]
        if "pull_request" not in event_payload["issue"]:
             print("Comment is not on a Pull Request. Skipping.")
             sys.exit(0)
        pr_number = event_payload["issue"]["number"]
    except KeyError as e:
        print(f"Error: Missing expected key in event payload: {e}", file=sys.stderr)
        print("Payload dump:", json.dumps(event_payload, indent=2))
        sys.exit(1)

    print(f"Processing comment on PR #{pr_number}...")

    # 3. Check if comment is the trigger command
    if not comment_body.strip().startswith(TRIGGER_COMMAND):
        print(f"Comment does not start with trigger command '{TRIGGER_COMMAND}'. Skipping.")
        sys.exit(0)

    print("Trigger command detected.")

    # 4. Instantiate GitHubAPI early for reuse
    try:
        github_api = GitHubAPI()
    except Exception as e: # Catch potential init errors if any added later
        print(f"Error initializing GitHub API: {e}", file=sys.stderr)
        sys.exit(1)

    # 5. Fetch PR details (diff and commit ID)
    commit_id = None
    try:
        pr_details, diff_content = github_api.get_pr_details(pr_number)
        if pr_details is None or diff_content is None:
            print(f"Error: Could not fetch PR details or diff for PR #{pr_number}.", file=sys.stderr)
            sys.exit(1)

        # Fetch commit_id needed for fetching file content and posting comments
        commit_id = github_api.get_pr_commit_id(pr_number)
        if not commit_id:
            print("Error: Could not fetch commit ID for PR. Cannot fetch content or post comments.", file=sys.stderr)
            sys.exit(1)

        print(f"\n--- Fetched PR Details for #{pr_number} ---")
        print(f"Title: {pr_details['title']}")
        description = pr_details.get('description')
        description_snippet = (description[:100] + '...') if description else 'N/A'
        print(f"Description: {description_snippet}")
        print(f"Using commit ID: {commit_id}")

    except Exception as e:
        print(f"An error occurred during GitHub API interaction: {e}", file=sys.stderr)
        sys.exit(1)

    # 6. Load config
    config = load_config()
    print(f"\n--- Loaded Configuration ---")
    print(f"Exclude patterns: {config.get('exclude')}")
    print(f"Custom instructions: {config.get('custom_instructions', '')[:100]}...")
    print("--------------------------")

    # 7. Parse Diff and Filter files
    print("\n--- Parsing Diff and Filtering Files ---")
    parsed_diff_data = parse_diff(diff_content)
    filtered_files = {}
    excluded_files_count = 0
    for file_path, data in parsed_diff_data.items():
        if should_exclude_file(file_path, config['exclude']):
            excluded_files_count += 1
        else:
            if data.get('hunks'):
                 filtered_files[file_path] = data
            else:
                print(f"Skipping file with no hunks: {file_path}")

    print(f"Total files in diff: {len(parsed_diff_data)}")
    print(f"Files excluded: {excluded_files_count}")
    print(f"Files to review: {len(filtered_files)}")
    print("-------------------------------------")

    if not filtered_files:
        print("No files left to review after filtering. Exiting.")
        sys.exit(0)

    # 8. Initialize Gemini Client
    try:
        gemini = GeminiClient()
    except ValueError as e:
        print(f"Error initializing Gemini Client: {e}", file=sys.stderr)
        sys.exit(1)

    # 9. Process Hunks with Context
    all_comments = []
    print("\n--- Starting Review Process --- ")
    total_hunks = sum(len(data['hunks']) for data in filtered_files.values())
    hunk_counter = 0
    # Process file by file
    for file_path, data in filtered_files.items():
        print(f"\nReviewing file: {file_path} ({len(data['hunks'])} hunks)")

        # Get full file content (using cache)
        full_file_content = get_cached_file_content(github_api, file_path, commit_id)

        if full_file_content is None:
             print(f"  Error fetching content for {file_path}, skipping reviews for this file.", file=sys.stderr)
             hunk_counter += len(data['hunks']) # Increment counter for skipped hunks
             continue # Skip to next file

        # Process hunks within the file
        for hunk_index, hunk in enumerate(data['hunks']):
            hunk_counter += 1
            print(f"  Processing hunk {hunk_index + 1}/{len(data['hunks'])} (Overall: {hunk_counter}/{total_hunks})")

            # a. Extract Context (Function/Class + Imports or Fallback)
            code_context_snippet = extract_context_around_hunk(full_file_content, hunk['header'])

            # b. Fetch Jira context (Phase 3) - Placeholder
            jira_context = "N/A" # TODO: Implement Jira fetching if enabled in config

            # c. Build prompt with context
            prompt = build_prompt(
                pr_details=pr_details,
                file_path=file_path,
                code_context=code_context_snippet, # Pass the new context
                hunk_content=hunk['content'],
                custom_instructions=config['custom_instructions'],
                jira_context=jira_context
            )
            # print(f"    Code Context Snippet:\n{code_context_snippet[:300]}...") # Debug context
            # print(f"    Prompt for Hunk {hunk_index + 1}:\n{prompt[:200]}...\n") # Debug prompt start

            # d. Call Gemini API
            try:
                review_result = gemini.get_review(prompt)
            except Exception as e:
                print(f"  Error calling Gemini API for hunk {hunk_index + 1} in {file_path}: {e}", file=sys.stderr)
                continue # Skip this hunk on error

            # e. Collect responses for posting
            if review_result and 'reviews' in review_result:
                for review in review_result['reviews']:
                    hunk_line_num = review.get('lineNumber')
                    review_comment = review.get('reviewComment')

                    if hunk_line_num is None or review_comment is None:
                        print(f"  Warning: Skipping review item with missing 'lineNumber' or 'reviewComment' in {file_path}")
                        continue

                    file_line_number = map_hunk_line_to_file_line(hunk['header'], hunk['content'], hunk_line_num)

                    if file_line_number:
                        print(f"  -> Comment found for hunk line {hunk_line_num} (maps to file line {file_line_number})")
                        all_comments.append({
                            "commit_id": commit_id,
                            "path": file_path,
                            "line": file_line_number,
                            "body": review_comment
                        })
                    else:
                         print(f"  -> Warning: Could not map hunk line {hunk_line_num} in {file_path} to file line number. Comment may be on a deleted line or mapping failed.")
            else:
                 print(f"  Warning: Invalid or empty response structure from Gemini for hunk {hunk_index + 1} in {file_path}")

    # 10. Post review comments via GitHub API
    print(f"\n--- Posting {len(all_comments)} comments --- ")
    if not all_comments:
        print("No review comments to post.")
    else:
        comments_posted_count = 0
        comments_failed_count = 0
        for comment_data in all_comments:
            try:
                github_api.post_review_comment(
                    pr_number=pr_number,
                    commit_id=comment_data["commit_id"],
                    path=comment_data["path"],
                    line=comment_data["line"],
                    body=comment_data["body"]
                )
                comments_posted_count += 1
            except Exception as e:
                 comments_failed_count += 1
                 print(f"  Error posting comment to {comment_data['path']}:{comment_data['line']}: {e}", file=sys.stderr)

        print(f"Finished posting comments. Posted: {comments_posted_count}, Failed: {comments_failed_count}")

    print("\nAI Review Bot finished processing.")

if __name__ == "__main__":
    print("Executing main function...")
    main()