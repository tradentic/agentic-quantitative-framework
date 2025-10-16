# VS Code Extensions — Secure Defaults

Extensions can read files and environment variables; some send telemetry. Treat them as potential **secret exfiltration** vectors.

## Defaults (installed by devcontainer)

- `dbaeumer.vscode-eslint` — ESLint
- `deque-systems.vscode-axe-linter` — Accessibility linting
- `DavidAnson.vscode-markdownlint` — Markdown quality
- (Plus workflow helpers already in `devcontainer.json`: Tailwind IntelliSense, GitHub Actions/PRs, Supabase extension)

> **Intentionally not installed**: coding‑agent chat extensions; keep secrets safer by using CLIs when possible.

## Removed / not recommended here

- **Prettier extension** — removed to avoid unwanted formatting churn. Use `pnpm format` in CI if you add Prettier at the app level.
- **Chrome Extension Dev Tools** — not relevant to this repo.

## Suggested (not installed by default)

- `openai.chatgpt`
- `anthropic.claude-code`
- `saoudrizwan.claude-dev` (Cline)

Prefer **CLIs** instead of editor extensions when working with secrets:

- `codex` (OpenAI Codex CLI)
- `claude` (Anthropic Claude Code CLI)
- Optional: `gemini`, `goose`, `plandex` (see `scripts/` installers)

## Hardening tips

- Keep extension list minimal in `devcontainer.json`.
- Disable extension auto‑updates on critical workspaces.
- Avoid pasting secrets into extension sidebars.
- Use a separate window for editing highly sensitive files.
