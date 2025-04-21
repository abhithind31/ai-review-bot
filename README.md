# AI Code Review Bot

This GitHub Action uses AI (Gemini) to review Pull Requests based on comments.

## Features

- Trigger review via PR comment (`/gemini-review`).
- Hunk-based analysis for focused feedback.
- Customizable review instructions via `.github/gemini-reviewer.yml`.
- File exclusion patterns.
- (Planned) Jira integration for context-aware reviews.

## Setup

1.  Add the workflow file (`.github/workflows/code-review.yml` - or `.github/code-review-action.yml` if created there) to your repository.
2.  Add a `GEMINI_API_KEY` secret to your repository secrets.
3.  (Optional) Create a `.github/gemini-reviewer.yml` file to customize exclusions and instructions.

## Usage

Comment `/gemini-review` on a Pull Request to trigger the review process. 