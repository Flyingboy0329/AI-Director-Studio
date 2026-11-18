"""Conservative CPU INT8 planning budgets, not measured model requirements."""
import psutil

RAM_GIB = {"tiny": .5, "base": 1., "small": 2., "medium": 4., "large-v3": 8., "turbo": 6.}


def ram_budget():
    memory = psutil.virtual_memory()
    reserve = max(2., memory.total / 1024**3 * .20)
    available = memory.available / 1024**3
    return available, reserve, max(0., available - reserve)


def process_rss_gib():
    try:
        return psutil.Process().memory_info().rss / 1024**3
    except (psutil.Error, OSError):
        return None
