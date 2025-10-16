"""DeepLOB embeddings utilities.

This module exposes a light-weight DeepLOB implementation that focuses on
producing penultimate-layer embeddings for limit order book (LOB) snapshots.
It provides an ergonomic loader that can hydrate weights on either CPU or GPU
and a batch inference helper that returns an embedding per input window.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import torch
from torch import Tensor, device as Device, nn
from torch.utils.data import DataLoader, TensorDataset


@dataclass(frozen=True)
class DeepLOBConfig:
    """Configuration for the simplified DeepLOB encoder."""

    in_channels: int = 1
    conv_channels: Sequence[int] = (16, 32, 64)
    inception_channels: int = 64
    lstm_hidden_size: int = 64
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
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("`dropout` must be in [0, 1).")


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

    def forward(self, x: Tensor) -> Tensor:  # noqa: D401 - inherited docstring
        """Compute the inception block activations."""

        outputs = (self.branch1(x), self.branch3(x), self.branch5(x), self.branch_pool(x))
        return torch.cat(outputs, dim=1)


class DeepLOB(nn.Module):
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
        """Apply convolutional and inception blocks to produce sequence features."""

        features = self.conv_stack(x)
        features = self.inception(features)
        pooled = torch.mean(features, dim=-1)
        return pooled.permute(0, 2, 1)

    def extract_embeddings(self, x: Tensor) -> Tensor:
        """Return the penultimate embeddings for the provided LOB windows."""

        sequence = self.forward_features(x)
        sequence = self.dropout(sequence)
        outputs, _ = self.recurrent(sequence)
        return outputs[:, -1, :]

    def forward(self, x: Tensor) -> Tensor:  # noqa: D401 - inherited docstring
        """Alias for :meth:`extract_embeddings`."""

        return self.extract_embeddings(x)


def _resolve_device(device_hint: Device | str | None) -> Device:
    if device_hint is not None:
        return torch.device(device_hint)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_deeplob_model(
    *,
    config: DeepLOBConfig | None = None,
    state_dict_path: str | Path | None = None,
    device: Device | str | None = None,
) -> DeepLOB:
    """Instantiate a DeepLOB model and optionally load weights."""

    cfg = config or DeepLOBConfig()
    target_device = _resolve_device(device)
    model = DeepLOB(cfg)
    model.to(target_device)
    if state_dict_path is not None:
        state_dict = torch.load(Path(state_dict_path), map_location=target_device)
        model.load_state_dict(state_dict)
    model.eval()
    return model


@torch.no_grad()
def deeplob_embeddings(
    book: Tensor | Iterable[float],
    *,
    model: DeepLOB | None = None,
    batch_size: int = 32,
    device: Device | str | None = None,
) -> Tensor:
    """Generate DeepLOB embeddings for the provided book tensor."""

    if batch_size <= 0:
        raise ValueError("`batch_size` must be positive.")

    book_tensor = book if isinstance(book, Tensor) else torch.as_tensor(book)
    book_tensor = book_tensor.detach()
    if book_tensor.ndim != 4:
        raise ValueError("LOB snapshots must be a 4D tensor (batch, channels, levels, features).")
    if book_tensor.dtype != torch.float32:
        book_tensor = book_tensor.float()

    active_model = model or load_deeplob_model(device=device)
    target_device = next(active_model.parameters()).device
    if device is not None and torch.device(device) != target_device:
        target_device = torch.device(device)
        active_model = active_model.to(target_device)
    active_model.eval()

    dataset = TensorDataset(book_tensor)
    loader = DataLoader(dataset, batch_size=batch_size)

    outputs: list[Tensor] = []
    for (batch,) in loader:
        batch = batch.to(target_device)
        embeddings = active_model.extract_embeddings(batch)
        outputs.append(embeddings.cpu())

    return torch.cat(outputs, dim=0)


__all__ = [
    "DeepLOB",
    "DeepLOBConfig",
    "deeplob_embeddings",
    "load_deeplob_model",
]
