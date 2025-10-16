# Devcontainer Scripts

Scripts that run automatically are stored in `.devcontainer/scripts/`.

| Script | Purpose |
| --- | --- |
| `post-create.sh` | Installs Poetry dependencies and Docusaurus packages when available. |
| `post-start.sh` | Ensures the Supabase stack is online and syncs `.env.local`. |

Shared utilities that are reused outside the container live under
`scripts/infra/`. The Supabase environment synchroniser has been moved there so
it can be called from CI or local terminals.
