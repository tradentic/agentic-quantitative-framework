from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flows.similarity_scans import (
    SimilarityMatch,
    SimilarityQuery,
    build_filter_payload,
    dump_reports,
    load_similarity_query,
    parse_filter_args,
    perform_similarity_search,
)


def test_load_similarity_query(tmp_path: Path) -> None:
    payload = {
        "symbol": "AAPL",
        "window": "2024-01-01/2024-01-05",
        "embedding": [0.1, 0.2, 0.3],
        "metadata": {"note": "example"},
    }
    query_path = tmp_path / "query.json"
    query_path.write_text(json.dumps(payload), encoding="utf-8")

    query = load_similarity_query(query_path)

    assert query.symbol == "AAPL"
    assert query.window == "2024-01-01/2024-01-05"
    assert query.embedding == [0.1, 0.2, 0.3]
    assert query.metadata == {"note": "example"}


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"id": "abc", "score": 0.9}, 0.9),
        ({"id": "def", "similarity": 0.85}, 0.85),
        ({"id": "ghi", "distance": 0.5}, 1 / (1 + 0.5)),
    ],
)
def test_similarity_match_score_normalization(payload: dict[str, float], expected: float) -> None:
    match = SimilarityMatch.from_mapping(payload)
    assert pytest.approx(match.score) == expected


def test_dump_reports_creates_csv_and_markdown(tmp_path: Path) -> None:
    query = SimilarityQuery(symbol="AAPL", window="2024-01-01/2024-01-05", embedding=[0.1, 0.2])
    matches = [
        SimilarityMatch(
            identifier="row-1",
            score=0.95,
            asset_symbol="AAPL",
            time_range="2023-12-01/2023-12-05",
            metadata={"provenance_url": "https://example.com/row-1"},
        )
    ]

    outputs = dump_reports(query, matches, tmp_path)

    csv_path = Path(outputs["csv"])
    markdown_path = Path(outputs["markdown"])
    assert csv_path.exists()
    assert markdown_path.exists()

    csv_contents = csv_path.read_text(encoding="utf-8")
    md_contents = markdown_path.read_text(encoding="utf-8")
    assert "row-1" in csv_contents
    assert "Similarity Scan Report" in md_contents


def test_parse_filter_args_supports_multiple_types() -> None:
    filters = parse_filter_args(["regime_tag=bull", "limit=5", "active=true", "threshold=0.25"])
    assert filters == {
        "regime_tag": "bull",
        "limit": 5,
        "active": True,
        "threshold": pytest.approx(0.25),
    }


def test_build_filter_payload_respects_cross_symbol_flag(tmp_path: Path) -> None:
    query = SimilarityQuery(symbol="MSFT", window="2024-02", embedding=[0.1])

    scoped = build_filter_payload(query, user_filters={"regime_tag": "bear"}, allow_cross_symbol=False)
    assert scoped == {"asset_symbol": "MSFT", "regime_tag": "bear"}

    unscoped = build_filter_payload(query, user_filters={}, allow_cross_symbol=True)
    assert "asset_symbol" not in unscoped


def test_perform_similarity_search_invokes_nearest(monkeypatch: pytest.MonkeyPatch) -> None:
    query = SimilarityQuery(symbol="AAPL", window="2024-01", embedding=[0.2, 0.3])
    captured: dict[str, object] = {}

    def fake_nearest(embedding: list[float], k: int, filter_params: dict[str, object]) -> list[dict[str, object]]:
        captured["embedding"] = embedding
        captured["k"] = k
        captured["filter"] = filter_params
        return [
            {
                "id": "abc",
                "score": 0.88,
                "asset_symbol": "AAPL",
                "time_range": "2023-12",
            }
        ]

    monkeypatch.setattr("flows.similarity_scans.nearest", fake_nearest)

    matches = perform_similarity_search(query, k=3, filter_payload={"asset_symbol": "AAPL"})

    assert captured["embedding"] == [0.2, 0.3]
    assert captured["k"] == 3
    assert captured["filter"] == {"asset_symbol": "AAPL"}
    assert len(matches) == 1
    assert matches[0].identifier == "abc"
    assert pytest.approx(matches[0].score) == 0.88
