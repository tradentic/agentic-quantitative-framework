# Workflows Overview

This folder contains automation for building, validating, and publishing the starter.

## Index

* **monthly-template-refresh.yml** — Ask Codex to rebuild the starter each month; opens a review PR on `template/YYYY-MM`. See docs: `docs/workflows/codex-automation.md`.
* **publish-template-release.yml** — Create a GitHub Release from a monthly branch (no merge into `main`). Docs: `docs/workflows/codex-automation.md`.
* **codex-autofix.yml** — On CI failure, Codex applies a minimal fix and opens a PR. Docs: `docs/workflows/codex-automation.md`.
* **docs-deploy.yml** — Ephemeral Docusaurus build that publishes everything in `docs/`. Docs: `docs/workflows/core-ci-and-docs.md`.
* **ci.yml** — Build + smoke + a11y; uploads evidence. Docs: `docs/workflows/core-ci-and-docs.md`.
* **ci-validate-embeddings.yml** — Installs the Python package and runs `scripts/audit_vector_dims.py` to ensure fingerprint width stays at 128.
* **ci-validate-prefect.yml** — Installs test dependencies and executes `pytest tests/flows/test_entrypoints.py` so every Prefect deployment entrypoint resolves to a real flow.
* **drift-reconcile.yml** — Weekly scaffold refresh PR. Docs: `docs/workflows/core-ci-and-docs.md`.

## One‑time setup

* **Secrets** → add `OPENAI_API_KEY` (Actions → Secrets).
* **Template repository** (optional) → Settings → General.
* **Actions permissions** → Read & write.
* **Pages** → Source: GitHub Actions.

## Conventions

* All scripts must be **non‑interactive** and use **pnpm**.
* CI artifacts live under `evidence/`.
* Monthly PRs are **review‑only**; releases are cut from `template/YYYY-MM` branches.
