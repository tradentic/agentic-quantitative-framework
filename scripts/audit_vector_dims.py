"""CLI utility that verifies fingerprint vectors remain 128-dimensional."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from features.pca_fingerprint import (
    DEFAULT_PCA_ARTIFACT_PATH,
    PCA_COMPONENTS,
    load_pca_reducer,
)
from framework.supabase_client import MissingSupabaseConfiguration, get_supabase_client


def _load_artifact(path: Path) -> None:
    if not path.exists():
        print(
            f"[audit] No PCA artifact found at {path}. Run fit_and_persist_pca to bootstrap it."
        )
        return
    reducer = load_pca_reducer(path)
    components = getattr(reducer, "n_components_", getattr(reducer, "n_components", None))
    print(
        f"[audit] Loaded PCA artifact {path} with {components} components (expected {PCA_COMPONENTS})."
    )


def _fetch_fingerprint_rows(limit: int | None) -> list[dict[str, Any]]:
    try:
        client = get_supabase_client()
    except MissingSupabaseConfiguration:
        print("[audit] Supabase credentials missing; skipping remote fingerprint inspection.")
        return []

    query = client.table("signal_fingerprints").select("id,fingerprint")
    if limit is not None:
        query = query.limit(limit)
    response = query.execute()
    data = getattr(response, "data", None)
    if data is None:
        raise RuntimeError("Supabase response did not include a data payload.")
    return list(data)


def audit_fingerprint_dimensions(
    *,
    artifact_path: Path = DEFAULT_PCA_ARTIFACT_PATH,
    limit: int | None = None,
) -> None:
    """Validate PCA artifacts and stored Supabase fingerprint dimensionality."""

    _load_artifact(artifact_path)
    rows = _fetch_fingerprint_rows(limit)
    mismatches: list[tuple[Any, int]] = []
    for row in rows:
        fingerprint = row.get("fingerprint", []) or []
        width = len(fingerprint)
        if width != PCA_COMPONENTS:
            mismatches.append((row.get("id"), width))
    if mismatches:
        raise SystemExit(
            "Detected fingerprint dimensionality mismatches: %s" % mismatches
        )
    print(
        f"[audit] Verified {len(rows)} Supabase fingerprint rows with width {PCA_COMPONENTS}."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-path",
        type=Path,
        default=DEFAULT_PCA_ARTIFACT_PATH,
        help="Path to the PCA artifact (defaults to artifacts/pca/minirocket_128.pkl).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for fingerprint rows fetched from Supabase.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit_fingerprint_dimensions(artifact_path=args.artifact_path, limit=args.limit)


if __name__ == "__main__":
    main()
