# Agent Instructions

This is a personal project where I use this to manually input transactions to track my spending. The target audience is only myself and as such, the project complexity should be simple enough for a junior-level engineer (me) to understand and manually add features and fix bugs on their own. Provide simple explanations for more complex topics or weird quirks for learning/understanding.

Refer to `docs/README.md` for more about project details.

## General Rules

- No em-dashes, avoid long prose and narration, be concise in language
- Prefer incremental and smaller changes, break large tasks into smaller sub-tasks
- Do not make any git commits, you can stage changes but leave it to the user to review and make commits

## Python Coding Standards

- Use `ruff` for linting and formatting. Any changes should be checked with `uv run ruff format` and `uv run ruff check`
- Add docstrings inside a module, function, class, or method. Keep them concise
- Comment sparingly. Keep comments concise

## Markdown Rules

- Avoid tables, prefer bullet points for easier human editing
- For longer markdown files, add table of contents at the top
- For long explanations, add a TLDR at the top
- No emojis
