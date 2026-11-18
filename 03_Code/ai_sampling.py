"""AI image sampling policy, independent of technical CV sampling."""
import math

RATES = (0.25, 0.5, 1.0, 2.0, 4.0)


def validate_rate(value):
    if isinstance(value, bool):
        raise ValueError("AI 取樣頻率無效")
    rate = float(value)
    if rate not in RATES:
        raise ValueError("AI 取樣頻率必須是 0.25、0.5、1、2 或 4 張／秒")
    return rate


def sample_times(start, end, rate):
    rate = validate_rate(rate)
    if not math.isfinite(start) or not math.isfinite(end) or end <= start:
        raise ValueError("AI 取樣區間無效")
    return [start + i / rate for i in range(math.ceil((end-start)*rate))
            if start + i/rate < end - 1e-9] or [start]
