# 03_Code/bridge/export_markers.py
"""
【Bridge 匯出模組 v2】
將 AI 分析結果轉換為 DaVinci Resolve 可讀之 Lua 任務檔
支援 Schema v2 (影音分離雙清單標記)
"""

import os
import json
import datetime

def escape_lua_string(s):
    """基礎字串轉義，確保 Lua 語法安全"""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

def export_dual_clip_task(task_id, video_name, audio_name, video_markers, audio_markers, output_path):
    """
    匯出雙清單標記任務檔 (Lua schema v2)
    Args:
        task_id (str): 任務識別碼
        video_name (str): 純視訊檔名 (如 japan_walk_video.mp4)
        audio_name (str): 純音訊檔名 (如 japan_walk_audio.wav)
        video_markers (list): 視覺評語標記列表
        audio_markers (list): 語音/台詞評語標記列表
        output_path (str): 輸出路徑
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 安全序列化標記陣列 (轉為 Lua table 字串)
    def to_lua_table(markers):
        if not markers:
            return "{}"
        # 使用 json 轉換後，替換部分語法使其符合 Lua 格式
        raw = json.dumps(markers, indent=4, ensure_ascii=False)
        return "{" + raw.replace(":", " = ").replace(",", ",\n", 1) + "}"

    lua_content = f"""return {{
    schema_version = 2,
    task_id = "{escape_lua_string(task_id)}",
    timestamp = "{datetime.datetime.now().isoformat()}",
    video_clip_name = "{escape_lua_string(video_name)}",
    audio_clip_name = "{escape_lua_string(audio_name)}",
    video_markers = {json.dumps(video_markers, indent=4, ensure_ascii=False)},
    audio_markers = {json.dumps(audio_markers, indent=4, ensure_ascii=False)}
}}
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(lua_content)
    print(f"[Bridge] ✅ Lua 任務檔已產出: {output_path}")
    return output_path

if __name__ == "__main__":
    # 單元測試 / 手動執行範例
    export_dual_clip_task(
        task_id="demo_v2_001",
        video_name="japan_walk_video.mp4",
        audio_name="japan_walk_audio.wav",
        video_markers=[{"time": 1.5, "label": "Yellow", "comment": "scenic landscape detected"}],
        audio_markers=[{"time": 2.0, "label": "Blue", "comment": "voiceover segment start"}],
        output_path="05_Output/test_marker_task.lua"
    )
