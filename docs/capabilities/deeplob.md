# DeepLOB Order Book Embeddings

## Motivation
- Capture nonlinear microstructure patterns from raw limit order book (LOB) snapshots without hand-crafted features.
- Provide dense vectors that can be indexed in pgvector or fed into downstream labeling/regime models.
- Offer a portable alternative when TS2Vec or heavy temporal transformers are unavailable.

## Inputs & Outputs
- **Inputs:**
  - Tensor of LOB windows shaped ``(batch, channels, levels, features)`` where levels correspond to price levels and features cover bid/ask attributes.
  - Optional path to pretrained DeepLOB weights (``.pt``/``.pth``) for domain-specific fine-tuning.
  - Optional device hint (``"cuda"`` or ``"cpu"``) to steer inference hardware.
- **Outputs:**
  - Float32 tensor of shape ``(batch, hidden_size)`` representing the penultimate LSTM activations.
  - Embeddings are detached from gradients and ready for storage or similarity search.

## Configuration
- ``DeepLOBConfig`` fields control architecture depth and widths:
  - ``in_channels``: number of feature channels per LOB snapshot (default 1).
  - ``conv_channels``: tuple defining successive 2D convolution widths.
  - ``inception_channels``: channel count of the inception aggregator.
  - ``lstm_hidden_size``: output width (and embedding dimension) of the recurrent head.
  - ``dropout``: applied before the LSTM to regularise activations.
- ``load_deeplob_model`` auto-selects GPU if available; override via ``device="cpu"`` for deterministic CPU execution.

## CLI Example
```bash
python - <<'PY'
import torch
from features.deeplob_embeddings import DeepLOBConfig, deeplob_embeddings, load_deeplob_model

config = DeepLOBConfig(in_channels=1, conv_channels=(16, 32, 64), inception_channels=64, lstm_hidden_size=64)
model = load_deeplob_model(config=config)
book = torch.randn(128, config.in_channels, 40, 32)
vectors = deeplob_embeddings(book, model=model, batch_size=32)
print(vectors.shape)
PY
```

## Failure Modes
- ``ValueError`` if the supplied tensor does not match the required 4D shape or batch size is invalid.
- ``RuntimeError`` when provided weights do not align with the configured architecture.
- ``ModuleNotFoundError`` is avoided—PyTorch is a declared dependency and the loader gracefully falls back to CPU when CUDA is unavailable.

## Validation Checks
- Unit tests ensure embeddings returned for random tensors match the configured hidden dimension and remain finite.
- Configuration dataclass validates convolutional channel definitions and dropout ranges.
- Batch inference path exercises CPU fallback ensuring deterministic penultimate vectors without GPU access.
