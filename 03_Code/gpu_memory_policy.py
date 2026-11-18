"""Conservative additional headroom estimates in MiB, not allocations."""
import math


def system_headroom_mb(total_mb, primary=True):
    return math.ceil(max(2048 if primary else 1024, total_mb * (.20 if primary else .10)))


def whisper_headroom_mb(model):
    return 0  # ASR is CPU/INT8 resident; no CUDA weight allocation.
