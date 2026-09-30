import os
import subprocess
from pathlib import Path

def split_media(input_path, output_dir):
    input_file = Path(input_path)
    out_dir = Path(output_dir)
    
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
    
    print(f"[FFmpeg] 🎬 開始拆分視訊: {out_video.name}")
    # 無損抽取視訊軌，移除音訊 (-an)
    cmd_v = [
        "ffmpeg", "-y", "-i", str(input_file),
        "-map", "0:v:0", "-c:v", "copy", "-an",
        str(out_video)
    ]
    subprocess.run(cmd_v, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    
    print(f"[FFmpeg] 🎙️ 開始拆分音訊 (廣播級 PCM 48000Hz 2ch): {out_audio.name}")
    # 抽取音訊，轉為 Resolve 相容度最高的 16-bit 48kHz 立體聲 WAV
    cmd_a = [
        "ffmpeg", "-y", "-i", str(input_file),
        "-vn", "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2",
        str(out_audio)
    ]
    subprocess.run(cmd_a, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    
    print("✅ [FFmpeg] 影音物理分離完成！")
    return str(out_video), str(out_audio)

if __name__ == "__main__":
    test_input = r"C:\Users\pan\Desktop\AI_Director\02_Data\japan_walk.mp4"
    out_base = r"C:\Users\pan\Desktop\AI_Director\02_Data"
    split_media(test_input, out_base)