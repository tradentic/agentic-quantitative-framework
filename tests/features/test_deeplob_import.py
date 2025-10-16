"""Import-time behaviour for the DeepLOB embeddings module."""

from __future__ import annotations

import logging
import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

module = importlib.import_module("features.deeplob_embeddings")


def test_deeplob_embeddings_logs_skip_when_torch_missing(monkeypatch, caplog):
    """The helper should raise a controlled error when torch is unavailable."""

    def _missing() -> None:  # pragma: no cover - simple stub
        raise ModuleNotFoundError("torch is not installed")

    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(module, "_load_torch_artifacts", _missing)

    with pytest.raises(module.DependencyUnavailable):
        module.deeplob_embeddings([[[]]])

    assert "optional dependency 'torch' is unavailable" in caplog.text


def test_load_deeplob_model_uses_env_configuration(monkeypatch, tmp_path):
    """Environment variables should drive weight hydration and device selection."""

    class _FakeDevice(str):
        pass

    class _FakeTorch:
        def __init__(self) -> None:
            self.loads: list[tuple[Path, _FakeDevice]] = []

        def device(self, value: str) -> _FakeDevice:
            return _FakeDevice(value)

        def load(self, path: Path, *, map_location: _FakeDevice) -> dict[str, str]:
            self.loads.append((Path(path), map_location))
            return {"payload": "ok"}

    class _FakeModel:
        def __init__(self, config: module.DeepLOBConfig) -> None:
            self.config = config
            self.to_calls: list[_FakeDevice] = []
            self.state_dict: dict[str, str] | None = None
            self.is_eval = False

        def to(self, device: _FakeDevice) -> "_FakeModel":
            self.to_calls.append(device)
            return self

        def load_state_dict(self, state: dict[str, str]) -> None:
            self.state_dict = state

        def eval(self) -> None:
            self.is_eval = True

    fake_torch = _FakeTorch()

    def _fake_loader() -> tuple[_FakeTorch, object, None, None, type[_FakeModel]]:
        return (fake_torch, object(), None, None, _FakeModel)

    monkeypatch.setattr(module, "_load_torch_artifacts", _fake_loader)

    weights_path = tmp_path / "deeplob.pt"
    weights_path.write_text("payload")

    monkeypatch.setenv("DEEPLOB_WEIGHTS_PATH", str(weights_path))
    monkeypatch.setenv("DEEPLOB_DEVICE", "cpu")

    model = module.load_deeplob_model()

    assert isinstance(model, _FakeModel)
    assert fake_torch.loads == [(weights_path, _FakeDevice("cpu"))]
    assert model.to_calls == [_FakeDevice("cpu")]
    assert model.state_dict == {"payload": "ok"}
    assert model.is_eval is True
