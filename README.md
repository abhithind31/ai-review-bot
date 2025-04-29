# AI Code Review Bot - GitHub Action

This repository contains a GitHub Action that uses AI (AWS Bedrock - Claude) to review Pull Requests based on comments.

## Features

*   Trigger review via PR comment (e.g., `/ai-review`).
*   Hunk-based analysis for focused feedback.
*   Configurable review instructions and file exclusion patterns via a `.github/ai-reviewer.yml` file **in the consuming repository**.
*   Posts review comments directly to the relevant lines in the PR.
*   Configurable Bedrock model (defaults to `anthropic.claude-3-sonnet-20240229-v1:0`).
*   Jira integration for context-aware reviews (enabled by default).

## Usage in Your Workflow

To use this action in your own repository:

1.  **Ensure Action Permissions:** Your organization/repository settings might need to allow actions created within the organization to run (`Settings` -> `Actions` -> `General`).
2.  **Set Secrets:** Add your AWS Credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) and the target `AWS_REGION` as **Repository Secrets** or **Organization Secrets**. If using temporary credentials (e.g., from assuming an IAM role or AWS SSO), you **must** also provide the `AWS_SESSION_TOKEN`.
    *   `AWS_ACCESS_KEY_ID`: Your AWS Access Key ID.
    *   `AWS_SECRET_ACCESS_KEY`: Your AWS Secret Access Key.
    *   `AWS_SESSION_TOKEN`: (Optional, but required for temporary credentials) Your AWS Session Token.
    *   `AWS_REGION`: The AWS region where your Bedrock model is available (e.g., `us-east-1`).
    *(Alternatively, configure AWS credentials for your GitHub Actions runner using OIDC or other secure methods if preferred. If using methods that automatically configure environment variables like OIDC, you might not need to pass these secrets explicitly.)*
3.  **(Optional) Configuration File:** Create a `.github/ai-reviewer.yml` file in your repository to customize file exclusions, AI review instructions, or disable Jira integration (`jira.enabled: false`). See the example `ai-reviewer.yml` (Jira enabled by default).
4.  **(Required for Jira) Set Jira Secrets:** Since Jira integration is enabled by default, you **must** provide your Jira instance URL, a user email associated with an API token, and the API token itself as secrets (`JIRA_URL`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`) in your repository/organization settings, unless you disable Jira in the config file.
    *   Pass these secrets to the action using the `jira-url`, `jira-user-email`, and `jira-api-token` inputs (see workflow example below).
    *   The action fetches context for the review by identifying a Jira key using the following order:
        1.  **Explicit Key in Command:** Looks for a valid Jira key provided directly after the trigger command (e.g., `/ai-review PROJ-123`).
        2.  **PR Source Branch Name:** If no key is found in the command, it searches the Pull Request's source branch name for the first occurrence of a pattern matching the Jira key format (e.g., extracting `PROJ-123` from `feature/PROJ-123-new-login`).
    *   You can customize the regex pattern used for extraction (`ticket_id_pattern`) in the `ai-reviewer.yml` config file.
5.  **Create Workflow File:** Add a workflow file (e.g., `.github/workflows/ai-code-review.yml`) to your repository:

```yaml
# .github/workflows/ai-code-review.yml
name: AI Code Review

on:
  issue_comment:
    types: [created]

jobs:
  review:
    # Run only if comment is on a PR and starts with the trigger command
    if: startsWith(github.event.comment.body, '/ai-review') && github.event.issue.pull_request
    runs-on: ubuntu-latest
    # Permissions needed by the action to read code and write comments
    permissions:
      contents: read
      pull-requests: write
      issues: read

    steps:
      # IMPORTANT: Checkout the code so the action can access config files (e.g., ai-reviewer.yml)
      - name: Checkout code
        uses: actions/checkout@v4
        # Optional: Fetch the specific PR head commit if needed for pristine state
        # ref: ${{ github.event.issue.pull_request.head.sha }}
        # fetch-depth: 0 # Fetch full history if needed by other steps

      - name: Run AI Review Bot Action
        # Replace your-org/ai-review-bot with your actual org/repo name
        # Replace @vX with the specific tag/branch/commit SHA you want to use
        uses: your-org/ai-review-bot@v1 
        with:
          # Pass AWS secrets to the action
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-session-token: ${{ secrets.AWS_SESSION_TOKEN }} # Required if using temporary credentials
          aws-region: ${{ secrets.AWS_REGION }} # e.g., 'us-east-1' or set as secret
          # --- JIRA Integration (Enabled by Default) --- 
          # Provide these secrets unless Jira is disabled in the config file.
          jira-url: ${{ secrets.JIRA_URL }}
          jira-user-email: ${{ secrets.JIRA_USER_EMAIL }}
          jira-api-token: ${{ secrets.JIRA_API_TOKEN }}
          
          # Optional: Override the default Bedrock model ID
          # bedrock-model-id: 'anthropic.claude-v2:1'
          # Optional: Override the default config file path
          # config-path: '.github/my-custom-review-config.yml'
          # Optional: Pass a specific GitHub token if needed (defaults to github.token)
          # github-token: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
```

6.  **Trigger:** Comment `/ai-review` on a Pull Request in your repository.

## Action Inputs

*   `github-token`: (Optional) GitHub token. Defaults to `${{ github.token }}`.
*   `aws-access-key-id`: (Required) AWS Access Key ID.
*   `aws-secret-access-key`: (Required) AWS Secret Access Key.
*   `aws-session-token`: (Optional) AWS Session Token. Required if using temporary AWS credentials.
*   `aws-region`: (Required) AWS Region for Bedrock.
*   `bedrock-model-id`: (Optional) Bedrock model ID. Defaults to `anthropic.claude-3-sonnet-20240229-v1:0`.
*   `config-path`: (Optional) Path to the `.yml` config file in the consuming repo. Defaults to `.github/ai-reviewer.yml`.
*   `jira-url`: (Optional) URL of your Jira instance. Required if Jira integration is enabled (default).
*   `jira-user-email`: (Optional) Email of the Jira user for authentication. Required if Jira integration is enabled (default).
*   `jira-api-token`: (Optional) Jira API token for authentication. Required if Jira integration is enabled (default).

## Development

This repository contains the source code (`src/`), dependencies (`requirements.txt`), and the action definition (`action.yml`).

To contribute:
1. Clone the repository.
2. Make changes to the Python code in `src/`.
3. Test locally if possible (requires setting environment variables like `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `GITHUB_EVENT_PATH`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_API_URL`, `PR_NUMBER`, `JIRA_URL`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN` manually. Include `AWS_SESSION_TOKEN` if testing with temporary credentials).
4. Update `action.yml` if inputs/outputs change.
5. Commit, push, and create a Pull Request.
6. Remember to create new version tags (e.g., `v1.1`) for releases. 