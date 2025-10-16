---

id: codex-automation
title: Automations with Codex — Monthly Template, Template Releases, and CI Autofix
sidebar_label: Codex automations
--------------------------------

This page documents the GitHub Actions we use to (1) rebuild the starter **monthly** with Codex, (2) publish a **Template Release** from that monthly branch *without merging to* `main`, and (3) let Codex **autofix CI** failures by opening a minimal patch PR.

> We invoke the official **`openai/codex-action`** inside GitHub Actions. It installs the Codex CLI and starts a secure proxy to the Responses API, with safety controls that reduce privileges available to Codex during the run.

---

## One‑time setup (required)

1. **Actions secret** — add your API key

   * Repo → **Settings → Secrets and variables → Actions** → **New repository secret**
   * Name: `OPENAI_API_KEY`

2. **Template repository** (optional)

   * Repo → **Settings → General** → **Template repository** (toggle on)
   * Why: enables the **Use this template** button. By default it uses the default branch; see *Template releases* below.

3. **Workflow permissions**

   * Repo → **Settings → Actions → General → Workflow permissions** → enable **Read and write permissions** (so Actions can create branches & PRs).

4. **GitHub Pages enabled** (for docs)

   * Repo → **Settings → Pages** → **Source: GitHub Actions** (we deploy via the `docs-deploy` workflow).

> Tip: Keep these steps in a checklist for new repos cloned from this template.

---

## Monthly template refresh

**Workflow:** `.github/workflows/monthly-template-refresh.yml`

**What it does**

* On the 1st of each month (03:20 UTC), checks out `main` and calls Codex with a prompt that instructs it to **follow our archived starter docs** in `archive/legacy-starter-docs/docs/specs` (AGENTS, SPEC, DEVENV, UI overlays) to build a **fresh Next.js + Supabase scaffold** in the repo root.
* Writes a short summary to `PLAN.md` (CNA & Node versions, packages, validation results).
* Commits results to a new branch: `template/YYYY-MM` and opens a PR for review (you **do not need to merge** this PR).

**Review model**

* The PR is for human sanity check only. After review, you can **publish a Template Release** from the branch and **close the PR unmerged**.

**Manual run**

* Actions → *monthly-template-refresh* → **Run workflow**. Optional input: `overlay` (`none`/`radix`/`shadcn`/`radix+shadcn`).

**Security**

* We use `safety-strategy: drop-sudo` and `sandbox: workspace-write` to minimize privileges. If Codex needs to download anything, do it **before** the Codex step.

---

## Publish a Template Release (no merge into `main`)

**Workflow:** `.github/workflows/publish-template-release.yml`

**What it does**

* On **manual dispatch**, targets a branch like `template/2025-10`, creates tag `template-2025-10`, and publishes a **GitHub Release** using `PLAN.md` as the body.
* Consumers can download the release archive or you can maintain a separate template repo.

**Why not merge?**

* The monthly branch is a **frozen snapshot** of the freshest scaffold. Keeping it separate avoids churn on `main` (which holds the archived starter docs and workflows).

**Template repository UX**

* If you turned on **Template repository**, the **Use this template** button uses the **default branch** by default. You (or consumers) can also choose to **include all branches** when creating a repo from the template so `template/YYYY-MM` is available.
* Alternative: maintain a dedicated **template repo** whose default branch is force‑updated monthly from your `template/YYYY-MM`.

---

## Codex autofix for CI failures

**Workflow:** `.github/workflows/codex-autofix.yml`

**What it does**

* Watches your primary CI workflow (e.g., `CI`). When that workflow finishes **failed**, this listener checks out the failing SHA, runs Codex with a guard‑railed prompt to apply the **smallest possible fix**, reruns the checks, and opens a PR back to the failing branch.

**Scope control**

* The prompt instructs Codex to only fix what’s needed to make CI green (build + smoke + a11y), avoiding refactors.
* Safety: `safety-strategy: drop-sudo`, `sandbox: workspace-write`.

---

## Docs site deploy (this page)

**Workflow:** `.github/workflows/docs-deploy.yml`

**What it does**

* Bootstraps a Docusaurus site **ephemerally** in CI (not committed), rsyncs the repo’s `docs/` into `website/docs/`, builds, and deploys to GitHub Pages.
* Because this page lives at `docs/workflows/codex-automation.md`, it will appear under the site’s **Docs** section automatically.

**Run it**

* Push to `main` or trigger via **Run workflow**.

---

## Files & prompts referenced

* **AGENTS:** `archive/legacy-starter-docs/docs/specs/AGENTS.md` — non‑interactive scaffold rules (root, pnpm, validations)
* **SPEC:** `archive/legacy-starter-docs/docs/specs/SPEC.md` — directory layout, scripts, i18n, Supabase SSR
* **DEVENV:** `archive/legacy-starter-docs/docs/specs/DEVENV.md` — devcontainer expectations
* **UI overlays:** `archive/legacy-starter-docs/docs/specs/UI-OVERLAYS.md`
* **Security & extensions:** `.devcontainer/EXTENSIONS.md`

Make sure these docs stay accurate — the monthly prompt tells Codex to follow them *exactly*.

---

## Troubleshooting

* **Codex lacks network** (downloads fail): preinstall deps in steps **before** `openai/codex-action`, or temporarily use `sandbox: danger-full-access` (riskier).
* **PR template/Issue templates not showing**: ensure files are on the **default branch** and follow GitHub path/name rules under `.github/`.
* **Docs deploy fails with `--no-git`**: the Docusaurus CLI no longer supports that flag (we’ve removed it in the workflow).
* **pnpm global bin errors in devcontainer**: ensure `PNPM_HOME` exists and is on `PATH`; our scripts set it to `$HOME/.local/share/pnpm`.

---

## FAQ

**Do I have to merge the monthly PR?**
No. It’s for review only. Publish the Template Release from the branch, then close the PR unmerged.

**How do I switch the overlay?**
Manual run of *monthly-template-refresh* lets you pass `overlay`. The scheduled run defaults to `none` (change in YAML if needed).

**Can Codex touch secrets?**
The action starts a secure proxy with your `OPENAI_API_KEY`. Use the default **drop-sudo** strategy and avoid exposing additional secrets in the workspace.

---

## At-a-glance checklist

* [ ] `OPENAI_API_KEY` secret set (Actions → Secrets)
* [ ] (Optional) **Template repository** enabled
* [ ] Actions workflow permissions: **Read and write**
* [ ] Pages source: **GitHub Actions**
* [ ] Workflows present:

  * monthly‑template‑refresh
  * publish‑template‑release
  * codex‑autofix
  * docs‑deploy

That’s it — you now have a fully automated, reviewable, and releasable monthly template pipeline with Codex, plus a safety‑net that keeps CI green.
