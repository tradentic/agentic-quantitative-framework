"""Audit vector dimensions across Supabase schema and Python entrypoints."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
import yaml

MIGRATIONS_DIR = Path("supabase/migrations")
PREFECT_FILE = Path("prefect.yaml")
SUPABASE_CLIENT = Path("framework/supabase_client.py")
FINGERPRINT_FLOW = Path("flows/embeddings_and_fingerprints.py")


@dataclass
class AuditIssue:
    scope: str
    message: str


def _extract_vector_columns() -> dict[tuple[str, str], set[int]]:
    """Return a mapping of (table, column) to declared vector dimensions."""

    pattern_table = re.compile(
        r"create\s+table\s+if\s+not\s+exists\s+public\.([a-z0-9_]+)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )
    pattern_column = re.compile(r"([a-z0-9_]+)\s+vector\((\d+)\)", re.IGNORECASE)

    columns: dict[tuple[str, str], set[int]] = {}

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        text = path.read_text()
        for table_match in pattern_table.finditer(text):
            table_name = table_match.group(1)
            column_block = table_match.group(2)
            for column_match in pattern_column.finditer(column_block):
                column_name, dim_text = column_match.groups()
                key = (table_name, column_name)
                columns.setdefault(key, set()).add(int(dim_text))

    return columns


def _load_prefect_target_dims() -> dict[str, int]:
    """Map Prefect deployment names to configured target dimensions."""

    if not PREFECT_FILE.exists():
        return {}

    data = yaml.safe_load(PREFECT_FILE.read_text()) or {}
    result: dict[str, int] = {}
    for deployment in data.get("deployments", []):
        entrypoint = deployment.get("entrypoint", "")
        if "fingerprint_vectorization" not in entrypoint:
            continue
        parameters = deployment.get("parameters", {}) or {}
        target_dim = parameters.get("target_dim")
        if isinstance(target_dim, int):
            result[deployment.get("name", entrypoint)] = target_dim
    return result


def _extract_embedding_validator_dim() -> int | None:
    text = SUPABASE_CLIENT.read_text()
    match = re.search(r"len\(value\)\s*!=\s*(\d+)", text)
    return int(match.group(1)) if match else None


def _extract_fingerprint_default_dim() -> int | None:
    text = FINGERPRINT_FLOW.read_text()
    match = re.search(r"target_dim:.*?=\s*(\d+)", text)
    return int(match.group(1)) if match else None


def _summarise_dims(columns: dict[tuple[str, str], set[int]]) -> dict[tuple[str, str], int]:
    summarised: dict[tuple[str, str], int] = {}
    for key, dims in columns.items():
        if not dims:
            continue
        if len(dims) > 1:
            raise ValueError(f"Multiple dimensions declared for {key}: {sorted(dims)}")
        summarised[key] = next(iter(dims))
    return summarised


def audit() -> tuple[list[str], list[AuditIssue]]:
    columns = _summarise_dims(_extract_vector_columns())
    successes: list[str] = []
    issues: list[AuditIssue] = []

    expected_embedding_dim = columns.get(("signal_embeddings", "embedding"))
    validator_dim = _extract_embedding_validator_dim()
    if expected_embedding_dim is None:
        issues.append(AuditIssue("schema", "signal_embeddings.embedding not found"))
    elif validator_dim != expected_embedding_dim:
        issues.append(
            AuditIssue(
                "framework/supabase_client.py",
                f"Embedding validator expects {validator_dim}, schema declares {expected_embedding_dim}",
            )
        )
    else:
        successes.append(
            f"signal_embeddings.embedding -> {expected_embedding_dim} dims (framework validator matches)"
        )

    expected_fingerprint_dim = columns.get(("signal_fingerprints", "fingerprint"))
    fingerprint_default = _extract_fingerprint_default_dim()
    prefect_dims = _load_prefect_target_dims()

    if expected_fingerprint_dim is None:
        issues.append(AuditIssue("schema", "signal_fingerprints.fingerprint not found"))
    else:
        if fingerprint_default != expected_fingerprint_dim:
            issues.append(
                AuditIssue(
                    "flows/embeddings_and_fingerprints.py",
                    f"Default target_dim is {fingerprint_default}, schema declares {expected_fingerprint_dim}",
                )
            )
        else:
            successes.append(
                "flows/embeddings_and_fingerprints fingerprint target_dim matches schema"
            )

        for name, dim in sorted(prefect_dims.items()):
            if dim != expected_fingerprint_dim:
                issues.append(
                    AuditIssue(
                        f"prefect.yaml ({name})",
                        f"Configured target_dim {dim} != schema {expected_fingerprint_dim}",
                    )
                )
            else:
                successes.append(f"prefect deployment '{name}' target_dim matches schema")

    expected_text_dim = columns.get(("text_chunks", "embedding"))
    if expected_text_dim is not None:
        successes.append(f"text_chunks.embedding -> {expected_text_dim} dims")

    return successes, issues


def main() -> int:
    try:
        successes, issues = audit()
    except ValueError as exc:
        print(f"Audit failed: {exc}")
        return 1

    for line in successes:
        print(f"PASS: {line}")

    if issues:
        for issue in issues:
            print(f"FAIL [{issue.scope}]: {issue.message}")
        return 1

    print("All vector dimensions are aligned with the schema.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
