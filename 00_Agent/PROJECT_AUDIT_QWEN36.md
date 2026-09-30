# T001 專案真實架構審查報告 (Real Project Audit)

**報告生成時間**: $(date)
**審查對象**: 03_Code 資料夾下之 Python 腳本
**執行者**: AI Local Agent (Qwen36)

---

## 1. 檔案狀態盤點 (File Status Audit)

| 檔名 | 狀態 | 說明 |
| :--- | :--- | :--- |
| **03_Code/vision_analyze.py** | ✅ **實作中** | 使用 Qwen2-VL-2B 對影格進行視覺描述，目前僅印出結果至控制台。 |
| **03_Code/audio_transcribe.py** | ✅ **實作中** | 使用 OpenAI Whisper (CPU) 進行語音轉文字，目前僅印出結果至控制台。 |
| **03_Code/director.py** | ✅ **實作中** | 使用 Qwen2.5-7B (4-bit) 進行決策推理，依賴 `timeline_integrated.json` 作為輸入。 |
| **03_Code/video_extract.py** | ⚪ **空檔案** | (尚未實作) 預期負責將影片拆分成影格與提取音訊。 |
| **03_Code/main.py** | ⚪ **空檔案** | (尚未實作) 預期作為整體流程的總控制器 (Orchestrator)。 |
| **03_Code/report.py** | ⚪ **空檔案** | (尚未實作) 預期負責產出最終的 Markdown 或 HTML 報告。 |

---

## 2. 真實 Pipeline 流程梳理 (Real Pipeline Flow)

根據代碼依賴關係，目前的處理流程如下：

1.  **Video Extract (未實作)**: 將 `../06_Test/test_videos` 中的影片拆解為 `frame_*.jpg` 與 `audio.wav`。
2.  **Vision Analysis (`vision_analyze.py`)**:
    *   **Input**: `../06_Test/test_videos/frame_*.jpg`
    *   **Process**: 載入 Qwen2-VL 模型，逐張分析並輸出繁體中文描述。
    *   **Output**: 目前僅 Console Output。
3.  **Audio Transcribe (`audio_transcribe.py`)**:
    *   **Input**: `../06_Test/test_videos/audio.wav`
    *   **Process**: 載入 Whisper 模型，執行語音辨識。
    *   **Output**: 目前僅 Console Output。
4.  **Director Decision (`director.py`)**:
    *   **Input**: `../05_Output/analysis/timeline_integrated.json` (需包含 `visual_summary` 與 `audio_summary`)。
    *   **Process**: 載入 Qwen2.5-7B，針對每個時間段進行剪輯決策推理。
    *   **Output**: 寫入 `../05_Output/reports/director_decisions.json`。

---

## 3. 斷點與瓶頸分析 (Bottlenecks Analysis)

### 🚨 致命斷點：中間資料表缺失
`director.py` 在第 9 行明確要求讀取 `../05_Output/analysis/timeline_integrated.json`，但目前專案中：
*   `vision_analyze.py` 與 `audio_transcribe.py` **皆未寫入**此 JSON 檔案。
*   若直接執行 `director.py` 且沒有手動建立該 JSON，程式將因 `FileNotFoundError` 而停止。

### 🧩 串接斷點
*   **Vision 模組**: 雖然有計算 `timestamp`，但輸出的格式是純文字列表，未對齊到 `director.py` 期望的 JSON Segment 結構 (即 `{"time": "...", "visual_summary": "...", "audio_summary": "..."}` 的列表)。
*   **Audio 模組**: 同樣是輸出純文字，未與時間戳記對齊。

---

## 4. 優先實作建議 (Next Steps)

依據當前代碼邏輯，下一個最值得優先實作的具體模組是：

### 📌 優先級 #1：實作 `data_integration.py` (或更新 `vision_analyze.py`)

**目標**：將 Vision 的影格描述與 Audio 的語音內容，合併成 `director.py` 所需的 `timeline_integrated.json`。

**建議規格**：
*   **Input**: 讀取 `vision_analyze.py` 產生的描述資料 (需先將該腳本改為輸出 JSON 或 TXT)，以及 `audio_transcribe.py` 的結果。
*   **Logic**:
    1.  建立一個 `timeline` 列表。
    2.  將影格描述映射到對應的時間段 (例如 0-3s, 3-6s...)。
    3.  將音訊內容按時間分區 (或全段標記)。
    4.  格式化為 `[{ "time": "00:00", "visual_summary": "...", "audio_summary": "..." }, ...]`。
*   **Output**: 寫入 `../05_Output/analysis/timeline_integrated.json`。

**後續步驟**：
1.  修改 `vision_analyze.py` 使其支援輸出 JSON。
2.  實作上述的整合腳本。
3.  實作 `main.py` 以自動化執行上述所有腳本。
4.  實作 `report.py` 將 `director_decisions.json` 轉為易讀的 Markdown。
