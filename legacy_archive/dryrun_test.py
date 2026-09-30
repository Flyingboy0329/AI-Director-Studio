import sys
import os

# 嚴格遵照指令：精良配 🟡、傳說配 🔵
lua_content = '''return {
    schema_version = 2,
    task_id = "rpg_5tier_swapped_balls",
    video_clip_name = "japan_walk",
    audio_clip_name = "input_audio",
    video_markers = {
        {
            start_frame = 24,
            duration_frames = 24,
            color = "Yellow",
            name = "V_95",
            note = "[AI-DIRECTOR][VIDEO] 評分 95 | 【傳說 🔵】 | 完美構圖與光影"
        },
        {
            start_frame = 60,
            duration_frames = 24,
            color = "Purple",
            name = "V_85",
            note = "[AI-DIRECTOR][VIDEO] 評分 85 | 【史詩 🟣】 | 核心焦點清晰"
        },
        {
            start_frame = 96,
            duration_frames = 24,
            color = "Green",
            name = "V_65",
            note = "[AI-DIRECTOR][VIDEO] 評分 65 | 【優秀 🟢】 | 普通過渡空鏡"
        },
        {
            start_frame = 130,
            duration_frames = 24,
            color = "Cream",
            name = "V_40",
            note = "[AI-DIRECTOR][VIDEO] 評分 40 | 【普通 ⚪】 | 運鏡晃動瑕疵"
        }
    },
    audio_markers = {
        {
            start_frame = 24,
            duration_frames = 48,
            color = "Purple",
            name = "A_88",
            note = "[AI-DIRECTOR][AUDIO] 評分 88 | 【史詩 🟣】 | 關鍵清晰台詞"
        },
        {
            start_frame = 80,
            duration_frames = 36,
            color = "Blue",
            name = "A_75",
            note = "[AI-DIRECTOR][AUDIO] 評分 75 | 【精良 🟡】 | 常規環境背景音"
        }
    }
}'''

out_path = r"C:\Users\pan\Desktop\AI_Director\05_Output\test_marker_task.lua"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(lua_content)

print("✅ 色球互換任務檔已輸出至 05_Output！")

# 自動注入 DaVinci Resolve
sys.path.append(r"C:\Users\pan\Desktop\AI_Director\03_Code\bridge")
import auto_injector
auto_injector.run_auto_inject()