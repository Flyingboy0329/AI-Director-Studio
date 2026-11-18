"""Cooperative cancellation: stop at safe boundaries, never publish partial markers."""
import threading
import time


class LinkedCancellation:
    """Cancel a failed parallel peer without changing the caller's event."""
    def __init__(self, parent=None):
        self.parent = parent
        self.local = threading.Event()

    def is_set(self):
        return self.local.is_set() or (self.parent is not None and self.parent.is_set())

    def set(self):
        self.local.set()

    def wait(self, timeout):
        end = time.monotonic() + timeout
        while not self.is_set():
            remaining = end - time.monotonic()
            if remaining <= 0:
                return False
            self.local.wait(min(.1, remaining))
        return True


class AnalysisCancelled(RuntimeError):
    pass


def check_cancelled(event):
    if event is not None and event.is_set():
        raise AnalysisCancelled("分析已取消")
