"""Selectable per-server context limits; 1K = 1024 tokens."""
CONTEXT_SIZES = (4096, 8192, 12288, 16384, 24576, 32768)
DEFAULT_CONTEXT = 8192


def validate_context(value):
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if type(value) is not int or value not in CONTEXT_SIZES:
        raise ValueError("Context 必須是 4K、8K、12K、16K、24K 或 32K")
    return value
