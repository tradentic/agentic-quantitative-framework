# VS Code Extensions

Extensions can read workspace files and environment variables. Install only
what you trust.

## Included by default

- `dbaeumer.vscode-eslint` — for linting the docs site when applicable
- `DavidAnson.vscode-markdownlint` — keeps documentation consistent
- `github.vscode-github-actions` and `GitHub.vscode-pull-request-github`
- `Supabase.vscode-supabase-extension` — manages the local stack

## Optional additions

- `ms-python.python` — rich Python language support (installed manually)
- `charliermarsh.ruff` — integrates Ruff if you prefer linting in-editor
- `prisma.prisma` — if you edit Supabase schemas frequently

## Safety tips

- Disable auto-updates for extensions that interact with secrets.
- Use the CLI equivalents (`poetry`, `supabase`) when handling credentials.
- Consider a separate VS Code profile when working with production keys.
