# Install

Unfaded needs Python 3.10 or newer and PyTorch. A CUDA GPU makes a print take seconds. The CPU works but is slow, see the timings in the README.

## From source

```bash
git clone https://github.com/Arthur031221/Unfaded
cd Unfaded
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Choosing a PyTorch build

`pip install -e .` pulls the default PyTorch wheel for your platform. If you want a specific CUDA build, install PyTorch first from the matching index and then install Unfaded. The code was developed on an RTX 5090 with torch 2.11 and CUDA 12.8.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e .
```

For a machine without a GPU use `https://download.pytorch.org/whl/cpu`.

## Model weights

Nothing is bundled. The first run of a step downloads what it needs into `~/.cache/unfaded/models` (override with `UNFADED_HOME`) and checks a pinned sha256. You can fetch everything up front:

```bash
unfaded models --fetch     # about 1.3 GB
unfaded models             # show what is installed
```

| Step | Weights | Size |
| --- | --- | --- |
| repair | scratch detector, big-lama | 452 MB, 206 MB |
| faces | YuNet, GFPGAN v1.4 | 0.2 MB, 349 MB |
| color | DDColor tiny | 220 MB |
| upscale | Real-ESRGAN x4plus | 67 MB |

The split and tone steps use plain OpenCV and need no weights.

## Platform notes

- **Linux with an NVIDIA GPU:** works with the CUDA wheels. Large prints are processed in tiles and windows so VRAM use stays bounded. Windows was not tested.
- **macOS:** `auto` picks CUDA or the CPU only. You can try `--device mps`, but Apple GPUs were not tested for this release.
- **No GPU:** pass `--device cpu`. Expect minutes per print instead of seconds.

## Development install

```bash
pip install -e ".[dev]"
pytest
```

See [CONTRIBUTING](../CONTRIBUTING.md).
