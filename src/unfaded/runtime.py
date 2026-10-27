"""Device selection and small torch helpers shared by every model wrapper."""

from __future__ import annotations

import torch


def pick_device(preference: str = "auto") -> torch.device:
    if preference == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(preference)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but no CUDA device is available")
    return device


def describe(device: torch.device) -> str:
    if device.type == "cuda":
        return torch.cuda.get_device_name(device)
    return "CPU"


def free_memory() -> None:
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
