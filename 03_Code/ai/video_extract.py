import os
import shutil
import subprocess
from pathlib import Path

def get_ffmpeg_path():
    """動態尋找 FFmpeg 路徑：優先找程式同級目錄/tools目錄，其次找系統 PATH"""
    current_dir = Path(__file__).resolve().parent
    base_dir = current_dir.parent
    proj_root = base_dir.parent

    candidates = [
        base_dir / "ffmpeg.exe",
        base_dir / "tools" / "ffmpeg.exe",
        proj_root / "ffmpeg.exe",
        proj_root / "tools" / "ffmpeg.exe"
    ]

    for p in candidates:
        if p.exists():
            return str(p)

    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg

    return "ffmpeg"

def split_media(input_path, output_dir):
    input_file = Path(input_path).resolve()
    out_dir = Path(output_dir).resolve()

    if not input_file.exists():
        print(f"❌ 找不到輸入檔案: {input_file}")
        return None, None

    video_dir = out_dir / "video"
    audio_dir = out_dir / "audio"
    video_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    base_name = input_file.stem
    out_video = video_dir / f"{base_name}_video.mp4"
    out_audio = audio_dir / f"{base_name}_audio.wav"

    ffmpeg_bin = get_ffmpeg_path()
    print(f"[FFmpeg] 🛠️ 調用核心: {ffmpeg_bin}")
    print(f"[FFmpeg] 🎬 開始拆分視訊: {out_video.name}")

    cmd_v = [
        ffmpeg_bin, "-y", "-i", str(input_file),
        "-an", "-c:v", "copy", str(out_video)
    ]
    subprocess.run(cmd_v, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"[FFmpeg] 🎙️ 開始拆分音訊: {out_audio.name}")
    cmd_a = [
        ffmpeg_bin, "-y", "-i", str(input_file),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(out_audio)
    ]
    subprocess.run(cmd_a, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if out_video.exists() and out_audio.exists():
        return str(out_video), str(out_audio)
    return None, None
