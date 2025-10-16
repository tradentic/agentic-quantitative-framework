---

id: core-ci-and-docs
title: Core CI & Docs Workflows
sidebar_label: Core CI & Docs
-----------------------------

This page documents the **baseline workflows** that keep the starter healthy and publish documentation.

---

## CI — Build, Smoke, A11y

**File:** `.github/workflows/ci.yml`
**Triggers:** push to `main`, pull_request

**What it runs**

* `pnpm install` (Corepack enabled)
* `pnpm exec playwright install --with-deps chromium`
* `pnpm build`
* `pnpm test:smoke`
* `pnpm test:a11y`
* Uploads `/evidence/**` artifacts (screenshots + a11y report)

**Pass conditions**

* Build succeeds
* Smoke test saves `evidence/startup-home-en-IE.png`
* A11y report contains **no serious/critical** violations
* Secret‑leak guard passes (no Supabase secret in client bundles)

**Run locally**

```bash
corepack enable && corepack prepare pnpm@latest --activate
pnpm install
pnpm exec playwright install --with-deps chromium
pnpm build && pnpm test:smoke && pnpm test:a11y
```

**Common failures**

* Playwright browsers not installed → run the `install` step locally
* A11y violations → fix markup/labels/contrast
* Secret string detected in `.next/static/**` → rework server/client Supabase usage

---

## Validate Embeddings — PCA fingerprint width

**File:** `.github/workflows/ci-validate-embeddings.yml`
**Triggers:** push to `main`, pull_request

**What it runs**

* `pip install .`
* `python scripts/audit_vector_dims.py`

The audit loads the persisted PCA reducer (if present) and inspects rows in `signal_fingerprints` via Supabase. Any vector that does not match the expected 128 components causes the workflow to fail.

**Run locally**

```bash
python -m pip install --upgrade pip
pip install .
python scripts/audit_vector_dims.py
```

**Common failures**

* PCA artifact missing → run `features/pca_fingerprint.py::fit_and_persist_pca`
* Supabase rows with incorrect width → recompute fingerprints before merging

---

## Validate Prefect Entrypoints — Deployment import smoke test

**File:** `.github/workflows/ci-validate-prefect.yml`
**Triggers:** push to `main`, pull_request

**What it runs**

* `pip install .[tests]`
* `pytest tests/flows/test_entrypoints.py`

The targeted pytest module loads `prefect.yaml`, imports each deployment entrypoint, and asserts the attribute resolves to a `prefect.Flow` with the expected name. This prevents drift between deployment metadata and the actual flow definitions.

**Run locally**

```bash
python -m pip install --upgrade pip
pip install .[tests]
pytest tests/flows/test_entrypoints.py
```

**Common failures**

* Entry point typo → fix the module path or attribute in `prefect.yaml`
* Flow renamed without updating deployment metadata → align the `flow_name` field or flow object name

---

## Drift Reconcile — Weekly refresh PR

**File:** `.github/workflows/drift-reconcile.yml`
**Triggers:** `cron`, workflow_dispatch

**Purpose**

* Re-run the scaffold weekly with the **current** CNA/Node/pnpm
* Update `scaffold.lock.json` and attach fresh `/evidence/**` artifacts
* Open a signed PR labelled `codex`

**Why**

* Surfaces breaking ecosystem changes early without polluting `main`

**Manual run**

* Actions → *drift-reconcile* → **Run workflow**

---

## Docs Deploy — GitHub Pages (Docusaurus, ephemeral)

**File:** `.github/workflows/docs-deploy.yml`
**Triggers:** push to `main`, workflow_dispatch

**How it works**

1. Bootstraps a Docusaurus site **at build time** (not committed):

   ```bash
   pnpm dlx create-docusaurus@latest website classic --typescript --skip-install
   ```
2. Installs deps in `website/`
3. `rsync` repo `docs/` → `website/docs/`
4. Patches `docusaurus.config.ts` with `url`/`baseUrl`/org/project
5. Builds and deploys via Pages actions

**Prereqs**

* Pages Source: **GitHub Actions**
* Node 24 runner (set in workflow)

**Gotchas**

* The CLI **does not** support `--no-git` anymore (we don’t pass it)
* If your repo name changes, the workflow recomputes `baseUrl` automatically

**View docs**

* After a successful run, your site appears at `https://<org>.github.io/<repo>/`

---

## Related specs

* `archive/legacy-starter-docs/docs/specs/CI.md` — gates, artifacts, and drift policy
* `archive/legacy-starter-docs/docs/specs/QA.md` — smoke/a11y expectations
* `archive/legacy-starter-docs/docs/specs/DEVENV.md` — devcontainer, pnpm, Playwright
