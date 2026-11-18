"""Manual GPU smoke test: start selected GGUF, describe a local image, summarize supplied text.

Does not import/modify Resolve. Uses synthetic transcript, not microphone audio.
"""
import base64
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.semantic_analyzer import LocalModelClient, validate_decision
from model_runtime import ModelRuntime
from path_utils import get_project_root, load_local_settings


def main():
    root = get_project_root()
    settings = load_local_settings("model_settings.json")
    runtime = ModelRuntime()
    try:
        runtime.ensure_ready(settings, lambda msg: print(msg, flush=True))
        client = LocalModelClient(settings.get("llm_url", "http://127.0.0.1:8080"), settings["llm_path"], timeout=180)
        client.check(require_images=True)
        image_path = root / "01_Project" / "app_icon.png"
        observation = client.analyze("visual_observer.md", [
            {"type": "text", "text": "影格時間 0.000 秒；測試圖片，請描述可見內容。"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image_path.read_bytes()).decode("ascii")}},
        ])
        print("IMAGE_RESULT", json.dumps(observation, ensure_ascii=False), flush=True)
        result = validate_decision(client.analyze("director.md", json.dumps({
            "start_sec": 0, "end_sec": 6, "visual_observation": observation,
            "transcript": [{"start": 0.5, "end": 4, "text": "這是我們的 AI 導演軟體圖示。"}],
            "editor_context": "軟體介紹影片", "audio_input": "人工測試文字，非真實音訊",
        }, ensure_ascii=False)))
        destination = root / "05_Output" / "review" / "gemma_smoke_result.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({"image": str(image_path), "visual_observation": observation,
            "decision": result, "synthetic_transcript": True}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("DECISION_RESULT", json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        runtime.stop()


if __name__ == "__main__":
    main()
