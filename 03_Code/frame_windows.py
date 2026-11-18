"""Half-open frame intervals, including any non-empty remainder at the tail."""
import math


def frame_windows(total_frames, fps, seconds=6.0):
    total_frames = int(total_frames)
    if total_frames <= 0 or not math.isfinite(fps) or fps <= 0 or seconds <= 0:
        raise ValueError("影片影格數／FPS／區間長度無效")
    step = fps * seconds
    result = []
    for index in range(math.ceil(total_frames / step)):
        start = min(total_frames, round(index * step))
        end = min(total_frames, round((index + 1) * step))
        if end > start:
            result.append((start, end))
    if not result or result[-1][1] != total_frames:
        raise ValueError("區間未覆蓋影片尾格")
    return result
