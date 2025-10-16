# PR title

## Description
Explain what changed and why. Link issues (e.g., closes #123) and include screenshots for UI changes.

## Type of change
- [ ] Fix (bug)
- [ ] Feature / task
- [ ] Docs
- [ ] CI / tooling

## How to test
Provide exact commands and expected outcomes.

```sh
# example
pnpm build
pnpm test:smoke
pnpm test:a11y
```

## Checklist
- [ ] I ran `pnpm build` locally with no errors
- [ ] I ran `pnpm test:smoke` and `pnpm test:a11y` (if applicable)
- [ ] Secrets are not leaked into client bundles (build guard passes)
- [ ] Updated docs where necessary (README / SPEC / DEVENV / QA)
- [ ] Added or updated evidence (screenshots in `evidence/` or CI artifacts)
- [ ] For scripts/CI, commands are non-interactive and idempotent
- [ ] `scaffold.lock.json` updated if the scaffold/tools changed

---

### For coding agents
Follow repo conventions:
- **Do not** scaffold into subfolders
- Use **pnpm** (Corepack non-interactive)
- Prefer **Publishable/Secret** Supabase keys; backfill Anon/Service Role
- Keep PR diffs minimal and focused; include file paths and reasons in commit messages

