"""Prefect flow that runs pgvector similarity scans for signal fingerprints."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from framework.supabase_client import MissingSupabaseConfiguration, nearest
from prefect import flow, get_run_logger, task


@dataclass(slots=True)
class SimilarityQuery:
    """Normalized representation of a similarity scan request."""

    symbol: str
    window: str
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol)
        self.window = str(self.window)
        if not self.symbol:
            raise ValueError("`symbol` is required for a similarity scan.")
        if not self.window:
            raise ValueError("`window` is required for a similarity scan.")
        if not self.embedding:
            raise ValueError("`embedding` must contain at least one dimension.")
        self.embedding = [float(value) for value in self.embedding]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SimilarityQuery":
        """Construct a query from a mapping containing symbol, window, and embedding."""

        embedding = payload.get("embedding") or payload.get("vector")
        if embedding is None:
            raise ValueError("Payload missing `embedding` or `vector` field.")
        symbol = payload.get("symbol") or payload.get("asset_symbol")
        if symbol is None:
            raise ValueError("Payload missing `symbol` or `asset_symbol` field.")
        window = payload.get("window") or payload.get("time_range")
        if window is None:
            raise ValueError("Payload missing `window` or `time_range` field.")
        metadata = payload.get("metadata") or payload.get("meta") or {}
        return cls(symbol=str(symbol), window=str(window), embedding=list(embedding), metadata=dict(metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "window": self.window,
            "embedding": list(self.embedding),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class SimilarityMatch:
    """Structured match returned by the pgvector similarity search."""

    identifier: str
    score: float
    asset_symbol: str | None = None
    time_range: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SimilarityMatch":
        identifier = str(payload.get("id") or payload.get("identifier") or payload.get("match_id"))
        if not identifier:
            raise ValueError("Similarity match payload missing an identifier.")
        metadata = payload.get("metadata") or payload.get("meta") or {}
        score = _resolve_similarity_score(payload)
        return cls(
            identifier=identifier,
            score=score,
            asset_symbol=_coerce_optional_str(payload.get("asset_symbol") or payload.get("symbol")),
            time_range=_coerce_optional_str(
                payload.get("time_range") or payload.get("window") or payload.get("time_window")
            ),
            metadata=dict(metadata),
        )

    def as_dict(self, *, include_metadata: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.identifier,
            "score": self.score,
            "asset_symbol": self.asset_symbol,
            "time_range": self.time_range,
        }
        if include_metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _resolve_similarity_score(payload: Mapping[str, Any]) -> float:
    if "score" in payload and payload["score"] is not None:
        return float(payload["score"])
    if "similarity" in payload and payload["similarity"] is not None:
        return float(payload["similarity"])
    if "distance" in payload and payload["distance"] is not None:
        distance = float(payload["distance"])
        return 1.0 / (1.0 + max(distance, 0.0))
    raise ValueError("Similarity payload missing score/similarity/distance field.")


def load_similarity_query(path: Path) -> SimilarityQuery:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise TypeError("Similarity query file must contain a JSON object.")
    return SimilarityQuery.from_mapping(payload)


def _safe_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return sanitized or "query"


def _timestamp_suffix() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def build_filter_payload(
    query: SimilarityQuery, *, user_filters: Mapping[str, Any] | None = None, allow_cross_symbol: bool = False
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if not allow_cross_symbol:
        payload["asset_symbol"] = query.symbol
    if user_filters:
        payload.update(user_filters)
    return payload


def perform_similarity_search(
    query: SimilarityQuery, *, k: int, filter_payload: Mapping[str, Any] | None = None
) -> list[SimilarityMatch]:
    matches = nearest(query.embedding, k=k, filter_params=dict(filter_payload or {}))
    return [SimilarityMatch.from_mapping(item) for item in matches]


def extract_provenance_url(metadata: Mapping[str, Any]) -> str | None:
    for key in ("provenance_url", "source_url", "artifact_url", "url", "href"):
        value = metadata.get(key)
        if value:
            return str(value)
    return None


def write_csv_report(matches: Sequence[SimilarityMatch], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "id", "score", "asset_symbol", "time_range", "provenance"])
        for idx, match in enumerate(matches, start=1):
            writer.writerow(
                [
                    idx,
                    match.identifier,
                    f"{match.score:.6f}",
                    match.asset_symbol or "",
                    match.time_range or "",
                    extract_provenance_url(match.metadata) or "",
                ]
            )


def write_markdown_report(query: SimilarityQuery, matches: Sequence[SimilarityMatch], output_path: Path) -> None:
    lines = ["# Similarity Scan Report", "", f"**Symbol:** `{query.symbol}`", f"**Window:** `{query.window}`", ""]
    if matches:
        lines.extend(["| Rank | Match ID | Score | Symbol | Window | Provenance |", "| --- | --- | --- | --- | --- | --- |"])
        for idx, match in enumerate(matches, start=1):
            provenance = extract_provenance_url(match.metadata)
            if provenance:
                link = f"[link]({provenance})"
            else:
                link = ""
            lines.append(
                "| {rank} | {identifier} | {score:.6f} | {symbol} | {window} | {provenance} |".format(
                    rank=idx,
                    identifier=match.identifier,
                    score=match.score,
                    symbol=match.asset_symbol or "",
                    window=match.time_range or "",
                    provenance=link,
                )
            )
    else:
        lines.append("No similar windows were found for the provided embedding.")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def dump_reports(query: SimilarityQuery, matches: Sequence[SimilarityMatch], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{_safe_component(query.symbol)}_{_safe_component(query.window)}_{_timestamp_suffix()}"
    csv_path = output_dir / f"{base_name}.csv"
    markdown_path = output_dir / f"{base_name}.md"
    write_csv_report(matches, csv_path)
    write_markdown_report(query, matches, markdown_path)
    return {"csv": str(csv_path), "markdown": str(markdown_path)}


def parse_filter_args(raw_filters: Sequence[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in raw_filters:
        if "=" not in item:
            raise ValueError(f"Filter '{item}' must be in key=value format.")
        key, value = item.split("=", 1)
        parsed[key] = _coerce_filter_value(value)
    return parsed


def _coerce_filter_value(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    return value


@task
def _load_query_task(query_path: str) -> SimilarityQuery:
    return load_similarity_query(Path(query_path))


@task
def _build_filters_task(
    query: SimilarityQuery, user_filters: Mapping[str, Any] | None, allow_cross_symbol: bool
) -> dict[str, Any]:
    return build_filter_payload(query, user_filters=user_filters, allow_cross_symbol=allow_cross_symbol)


@task
def _search_task(query: SimilarityQuery, k: int, filter_payload: Mapping[str, Any] | None) -> list[SimilarityMatch]:
    return perform_similarity_search(query, k=k, filter_payload=filter_payload)


@task
def _dump_reports_task(query: SimilarityQuery, matches: Sequence[SimilarityMatch], output_dir: str) -> dict[str, str]:
    return dump_reports(query, matches, Path(output_dir))


@flow(name="signal-similarity-scan")
def similarity_scan_flow(
    *,
    query_path: str,
    k: int = 5,
    output_dir: str = "reports/similarity",
    user_filters: Mapping[str, Any] | None = None,
    allow_cross_symbol: bool = False,
) -> dict[str, Any]:
    """Execute a pgvector similarity scan for the provided query embedding."""

    logger = get_run_logger()
    query = _load_query_task(query_path)
    filter_payload = _build_filters_task(query, user_filters, allow_cross_symbol)
    matches = _search_task(query, k, filter_payload)
    report_paths = _dump_reports_task(query, matches, output_dir)

    if matches:
        for idx, match in enumerate(matches, start=1):
            logger.info(
                "Rank %d -> id=%s score=%.6f symbol=%s window=%s",
                idx,
                match.identifier,
                match.score,
                match.asset_symbol,
                match.time_range,
            )
    else:
        logger.warning("No matches returned for symbol=%s window=%s", query.symbol, query.window)

    return {
        "query": query.as_dict(),
        "matches": [match.as_dict() for match in matches],
        "reports": report_paths,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a pgvector similarity scan over signal embeddings.")
    parser.add_argument("query_path", help="Path to a JSON file describing the query embedding.")
    parser.add_argument("--k", type=int, default=5, help="Number of nearest neighbours to retrieve.")
    parser.add_argument(
        "--output-dir", default="reports/similarity", help="Directory where CSV and Markdown reports are written."
    )
    parser.add_argument(
        "--filter",
        action="append",
        default=[],
        help="Additional Supabase filter in key=value format. Repeatable.",
    )
    parser.add_argument(
        "--allow-cross-symbol",
        action="store_true",
        help="Allow matches across different asset symbols instead of constraining to the query symbol.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        filters = parse_filter_args(args.filter)
    except ValueError as exc:  # pragma: no cover - argparse usage error
        parser.error(str(exc))
        return 2

    try:
        result = similarity_scan_flow(
            query_path=args.query_path,
            k=args.k,
            output_dir=args.output_dir,
            user_filters=filters,
            allow_cross_symbol=args.allow_cross_symbol,
        )
    except MissingSupabaseConfiguration as exc:
        parser.error(str(exc))
        return 2

    matches = result.get("matches", [])
    if not matches:
        print("No matches found.")
        return 0

    for idx, match in enumerate(matches, start=1):
        identifier = match.get("id")
        score_value = float(match.get("score") or 0.0)
        symbol = match.get("asset_symbol") or ""
        window = match.get("time_range") or ""
        print(f"{idx}. id={identifier} score={score_value:.6f} symbol={symbol} window={window}")
    reports = result.get("reports", {})
    if reports:
        print(f"CSV report: {reports.get('csv')}")
        print(f"Markdown report: {reports.get('markdown')}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
