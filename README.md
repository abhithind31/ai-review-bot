# AI Code Review Bot - GitHub Action

This repository contains a GitHub Action that uses AI (AWS Bedrock - Claude) to review Pull Requests based on comments.

## Features

*   Trigger review via PR comment (e.g., `/ai-review`).
*   Hunk-based analysis for focused feedback.
*   Configurable review instructions and file exclusion patterns via a `.github/ai-reviewer.yml` file **in the consuming repository**.
*   Posts review comments directly to the relevant lines in the PR.
*   Configurable Bedrock model (defaults to `anthropic.claude-3-sonnet-20240229-v1:0`).
*   (Planned) Jira integration for context-aware reviews.

## Usage in Your Workflow

To use this action in your own repository:

1.  **Ensure Action Permissions:** Your organization/repository settings might need to allow actions created within the organization to run (`Settings` -> `Actions` -> `General`).
2.  **Set Secrets:** Add your AWS Credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) and the target `AWS_REGION` as **Repository Secrets** or **Organization Secrets**. The action requires these to authenticate with AWS Bedrock.
    *   `AWS_ACCESS_KEY_ID`: Your AWS Access Key ID.
    *   `AWS_SECRET_ACCESS_KEY`: Your AWS Secret Access Key.
    *   `AWS_REGION`: The AWS region where your Bedrock model is available (e.g., `us-east-1`).
    *(Alternatively, configure AWS credentials for your GitHub Actions runner using OIDC or other secure methods if preferred.)*
3.  **(Optional) Configuration File:** Create a `.github/ai-reviewer.yml` file in your repository to customize file exclusions and AI review instructions. See the example `ai-reviewer.yml` in this repository's root for the format.
4.  **Create Workflow File:** Add a workflow file (e.g., `.github/workflows/ai-code-review.yml`) to your repository:

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
      - name: Run AI Review Bot Action
        # Replace your-org/ai-review-bot with your actual org/repo name
        # Replace @vX with the specific tag/branch/commit SHA you want to use
        uses: your-org/ai-review-bot@v1 
        with:
          # Pass AWS secrets to the action
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }} # e.g., 'us-east-1' or set as secret
          # Optional: Override the default Bedrock model ID
          # bedrock-model-id: 'anthropic.claude-v2:1'
          # Optional: Override the default config file path
          # config-path: '.github/my-custom-review-config.yml'
          # Optional: Pass a specific GitHub token if needed (defaults to github.token)
          # github-token: ${{ secrets.CUSTOM_GITHUB_TOKEN }}
```

5.  **Trigger:** Comment `/ai-review` on a Pull Request in your repository.

## Action Inputs

*   `github-token`: (Optional) GitHub token. Defaults to `${{ github.token }}`.
*   `aws-access-key-id`: (Required) AWS Access Key ID.
*   `aws-secret-access-key`: (Required) AWS Secret Access Key.
*   `aws-region`: (Required) AWS Region for Bedrock.
*   `bedrock-model-id`: (Optional) Bedrock model ID. Defaults to `anthropic.claude-3-sonnet-20240229-v1:0`.
*   `config-path`: (Optional) Path to the `.yml` config file in the consuming repo. Defaults to `.github/ai-reviewer.yml`.

## Development

This repository contains the source code (`src/`), dependencies (`requirements.txt`), and the action definition (`action.yml`).

To contribute:
1. Clone the repository.
2. Make changes to the Python code in `src/`.
3. Test locally if possible (requires setting environment variables like `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `GITHUB_EVENT_PATH`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_API_URL`, `PR_NUMBER` manually).
4. Update `action.yml` if inputs/outputs change.
5. Commit, push, and create a Pull Request.
6. Remember to create new version tags (e.g., `v1.1`) for releases. 