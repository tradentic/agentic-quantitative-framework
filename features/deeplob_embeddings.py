"""DeepLOB embeddings utilities.

This module exposes a light-weight DeepLOB implementation that focuses on
producing penultimate-layer embeddings for limit order book (LOB) snapshots.
It provides an ergonomic loader that can hydrate weights on either CPU or GPU
and a batch inference helper that returns a 128-dimensional embedding per
input window.

Two environment variables control runtime behaviour when weights are not
explicitly provided:

``DEEPLOB_WEIGHTS_PATH``
    Path to a serialized DeepLOB state dict. When supplied, the loader verifies
    the file exists before attempting to hydrate it.

``DEEPLOB_DEVICE``
    Torch device string (for example ``"cpu"`` or ``"cuda:0"``). If unset, the
    runtime defaults to CPU execution to maximise compatibility with
    lightweight environments.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, NamedTuple, Sequence, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing aids
    from torch import Tensor  # type: ignore
    from torch import device as Device  # type: ignore
else:  # pragma: no cover - executed when torch is unavailable
    Tensor = Any
    Device = Any


logger = logging.getLogger(__name__)


class DependencyUnavailable(RuntimeError):
    """Raised when an optional dependency or artifact is unavailable."""


class _TorchArtifacts(NamedTuple):
    torch: Any
    nn: Any
    data_loader: Any
    tensor_dataset: Any
    deep_lob_cls: type


_TORCH_ARTIFACTS: _TorchArtifacts | None = None
DeepLOB: type[Any] = Any


def _load_torch_artifacts() -> _TorchArtifacts:
    """Import torch lazily and construct runtime classes."""

    global _TORCH_ARTIFACTS, DeepLOB
    if _TORCH_ARTIFACTS is not None:
        return _TORCH_ARTIFACTS

    try:
        import torch  # type: ignore
        from torch import nn  # type: ignore
        from torch.utils.data import DataLoader, TensorDataset  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
        raise ModuleNotFoundError(
            "DeepLOB embeddings require the optional dependency 'torch'. Install it with `pip install torch`."
        ) from exc

    class InceptionBlock(nn.Module):
        """A small inception-style block inspired by the DeepLOB architecture."""

        def __init__(self, in_channels: int, out_channels: int, momentum: float) -> None:
            super().__init__()
            if out_channels < 4:
                raise ValueError("`out_channels` must be at least 4 for the inception block.")

            base = max(1, out_channels // 4)
            tail = out_channels - base * 3
            branch_channels = (base, base, base, tail)

            self.branch1 = nn.Sequential(
                nn.Conv2d(in_channels, branch_channels[0], kernel_size=1, bias=False),
                nn.BatchNorm2d(branch_channels[0], momentum=momentum),
                nn.ELU(),
            )
            self.branch3 = nn.Sequential(
                nn.Conv2d(in_channels, branch_channels[1], kernel_size=1, bias=False),
                nn.BatchNorm2d(branch_channels[1], momentum=momentum),
                nn.ELU(),
                nn.Conv2d(
                    branch_channels[1],
                    branch_channels[1],
                    kernel_size=(3, 1),
                    padding=(1, 0),
                    bias=False,
                ),
                nn.BatchNorm2d(branch_channels[1], momentum=momentum),
                nn.ELU(),
            )
            self.branch5 = nn.Sequential(
                nn.Conv2d(in_channels, branch_channels[2], kernel_size=1, bias=False),
                nn.BatchNorm2d(branch_channels[2], momentum=momentum),
                nn.ELU(),
                nn.Conv2d(
                    branch_channels[2],
                    branch_channels[2],
                    kernel_size=(5, 1),
                    padding=(2, 0),
                    bias=False,
                ),
                nn.BatchNorm2d(branch_channels[2], momentum=momentum),
                nn.ELU(),
            )
            self.branch_pool = nn.Sequential(
                nn.MaxPool2d(kernel_size=(3, 1), stride=1, padding=(1, 0)),
                nn.Conv2d(in_channels, branch_channels[3], kernel_size=1, bias=False),
                nn.BatchNorm2d(branch_channels[3], momentum=momentum),
                nn.ELU(),
            )

        def forward(self, x: Tensor) -> Tensor:  # type: ignore[override]
            outputs = (self.branch1(x), self.branch3(x), self.branch5(x), self.branch_pool(x))
            return torch.cat(outputs, dim=1)

    class _DeepLOB(nn.Module):
        """Simplified DeepLOB model that returns penultimate embeddings."""

        def __init__(self, config: DeepLOBConfig) -> None:
            super().__init__()
            self.config = config
            layers: list[nn.Module] = []
            in_ch = config.in_channels
            for idx, out_ch in enumerate(config.conv_channels):
                layers.extend(
                    [
                        nn.Conv2d(in_ch, out_ch, kernel_size=(1, 2), bias=False),
                        nn.BatchNorm2d(out_ch, momentum=config.batch_norm_momentum),
                        nn.ELU(),
                    ]
                )
                if idx < len(config.conv_channels) - 1:
                    layers.append(nn.MaxPool2d(kernel_size=(1, 2)))
                in_ch = out_ch
            self.conv_stack = nn.Sequential(*layers)
            self.inception = InceptionBlock(
                in_channels=in_ch,
                out_channels=config.inception_channels,
                momentum=config.batch_norm_momentum,
            )
            self.dropout = nn.Dropout(config.dropout)
            self.recurrent = nn.LSTM(
                input_size=config.inception_channels,
                hidden_size=config.lstm_hidden_size,
                num_layers=1,
                batch_first=True,
            )

        def forward_features(self, x: Tensor) -> Tensor:
            features = self.conv_stack(x)
            features = self.inception(features)
            pooled = torch.mean(features, dim=-1)
            return pooled.permute(0, 2, 1)

        def extract_embeddings(self, x: Tensor) -> Tensor:
            sequence = self.forward_features(x)
            sequence = self.dropout(sequence)
            outputs, _ = self.recurrent(sequence)
            return outputs[:, -1, :]

        def forward(self, x: Tensor) -> Tensor:  # type: ignore[override]
            return self.extract_embeddings(x)

    DeepLOB = _DeepLOB
    _TORCH_ARTIFACTS = _TorchArtifacts(torch, nn, DataLoader, TensorDataset, _DeepLOB)
    return _TORCH_ARTIFACTS


def _project_embeddings_to_dim(embeddings: Tensor, target_dim: int, torch_mod: Any) -> Tensor:
    """Zero-pad or truncate embeddings to match ``target_dim``."""

    current_dim = embeddings.shape[-1]
    if current_dim == target_dim:
        return embeddings
    if current_dim < target_dim:
        pad_width = target_dim - current_dim
        return torch_mod.nn.functional.pad(embeddings, (0, pad_width))
    return embeddings[..., :target_dim]


@dataclass(frozen=True)
class DeepLOBConfig:
    """Configuration for the simplified DeepLOB encoder."""

    in_channels: int = 1
    conv_channels: Sequence[int] = (16, 32, 64)
    inception_channels: int = 64
    lstm_hidden_size: int = 64
    embedding_dim: int = 128
    dropout: float = 0.1
    batch_norm_momentum: float = 0.1

    def __post_init__(self) -> None:
        if self.in_channels <= 0:
            raise ValueError("`in_channels` must be positive.")
        if not self.conv_channels:
            raise ValueError("`conv_channels` must define at least one layer.")
        if any(channel <= 0 for channel in self.conv_channels):
            raise ValueError("All `conv_channels` entries must be positive.")
        if self.inception_channels <= 0:
            raise ValueError("`inception_channels` must be positive.")
        if self.lstm_hidden_size <= 0:
            raise ValueError("`lstm_hidden_size` must be positive.")
        if self.embedding_dim <= 0:
            raise ValueError("`embedding_dim` must be positive.")
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("`dropout` must be in [0, 1).")


def _resolve_device(torch_mod: Any, device_hint: Device | str | None) -> Any:
    """Resolve the target device from an explicit hint or environment value."""

    env_hint = os.getenv("DEEPLOB_DEVICE")
    if device_hint is not None:
        return torch_mod.device(device_hint)
    if env_hint:
        return torch_mod.device(env_hint)
    return torch_mod.device("cpu")


def _resolve_weights_path(path_hint: str | Path | None) -> Path | None:
    """Resolve and validate the DeepLOB weights path if provided."""

    candidate = path_hint or os.getenv("DEEPLOB_WEIGHTS_PATH")
    if candidate is None:
        return None

    weights_path = Path(candidate).expanduser()
    if not weights_path.exists():
        raise FileNotFoundError(f"DeepLOB weights not found at: {weights_path}")
    return weights_path


def load_deeplob_model(
    *,
    config: DeepLOBConfig | None = None,
    state_dict_path: str | Path | None = None,
    device: Device | str | None = None,
) -> Any:
    """Instantiate a DeepLOB model and optionally load weights."""

    torch, nn, _, _, deep_lob_cls = _load_torch_artifacts()
    cfg = config or DeepLOBConfig()
    target_device = _resolve_device(torch, device)
    model = deep_lob_cls(cfg)
    model.to(target_device)
    weights_path = _resolve_weights_path(state_dict_path)
    if weights_path is not None:
        state_dict = torch.load(weights_path, map_location=target_device)
        model.load_state_dict(state_dict)
    model.eval()
    return model


def deeplob_embeddings(
    book: Tensor | Iterable[float],
    *,
    model: Any | None = None,
    batch_size: int = 32,
    device: Device | str | None = None,
) -> Any:
    """Generate 128-dimensional DeepLOB embeddings for the provided book tensor."""

    try:
        torch, _, data_loader, tensor_dataset, _ = _load_torch_artifacts()
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in tests
        logger.warning(
            "DeepLOB embeddings requested but optional dependency 'torch' is unavailable: %s",
            exc,
        )
        raise DependencyUnavailable("torch/DeepLOB not installed") from exc
    if batch_size <= 0:
        raise ValueError("`batch_size` must be positive.")

    book_tensor = book if isinstance(book, Tensor) else torch.as_tensor(book)
    book_tensor = book_tensor.detach()
    if book_tensor.ndim != 4:
        raise ValueError("`book` must have shape (batch, channels, depth, width).")

    inferred_device = _resolve_device(torch, device)
    if model is None:
        try:
            model = load_deeplob_model(device=inferred_device)
        except FileNotFoundError as exc:  # pragma: no cover - exercised in tests
            logger.warning(
                "DeepLOB embeddings requested but weights file could not be located: %s",
                exc,
            )
            raise DependencyUnavailable("DeepLOB weights not found") from exc
    else:
        model = model.to(inferred_device)

    if book_tensor.device != inferred_device:
        book_tensor = book_tensor.to(inferred_device)

    dataset = tensor_dataset(book_tensor)
    loader = data_loader(dataset, batch_size=batch_size)

    outputs: list[Any] = []
    target_dim = getattr(getattr(model, "config", None), "embedding_dim", 128)

    with torch.no_grad():
        for (batch,) in loader:
            embeddings = model.extract_embeddings(batch)
            embeddings = _project_embeddings_to_dim(embeddings, target_dim, torch)
            outputs.append(embeddings.cpu())
    return torch.cat(outputs, dim=0)


__all__ = [
    "DeepLOB",
    "DeepLOBConfig",
    "DependencyUnavailable",
    "deeplob_embeddings",
    "load_deeplob_model",
]
