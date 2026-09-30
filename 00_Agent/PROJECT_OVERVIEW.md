# AI Director 專案架構師總覽手冊

> **版本**: 1.0 (Final Inventory)
> **生成時間**: 2025-02-17
> **架構師**: AI Director System
> **專案路徑**: `C:\Users\pan\Desktop\AI_Director`

---

## 📂 一、專案目錄結構與職掌定義 (Project Structure)

本專案採用標準化的 **MLOps / Data Pipeline** 架構，將資料流與代碼邏輯嚴格分離。

| 資料夾名稱 | 定位 (Role) | 核心職掌 (Function) |
| :--- | :--- | :--- |
| **`00_Agent`** | **大腦與控制中心** | 存放 Agent 規則、決策日誌 (`DECISION_LOG`)、專案狀態 (`PROJECT_STATE`) 與變更紀錄。 |
| **`01_Project`** | **專案定義區** | 存放專案範圍定義、需求文件與配置資訊。 |
| **`02_Data`** | **原始素材區** | (規劃中) 存放未處理的原始 Raw 影片與音軌。目前暫時由 `06_Test` 替代。 |
| **`03_Code`** | **運算引擎** | 包含所有 Python 腳本，執行從音訊/視覺處理到 LLM 推理的全套邏輯。 |
| **`04_Models`** | **模型權重區** | (規劃中) 存放本地化 LLM 權重或依賴檔案。目前由 HuggingFace 動態加載。 |
| **`05_Output`** | **產出物目錄** | **`analysis/`**: 中間 JSON 資料 (視覺、音訊、時間軸)。<br>**`reports/`**: 最終 LLM 決策與 DaVinci 標記。 |
| **`06_Test`** | **測試沙盒** | 存放測試用的小樣本影片 (test.mp4) 與音檔，用於 CI/CD 驗證。 |

---

## 🔄 二、資料流走向 (Data Flow Pipeline)

整個系統是一個嚴格的 **Sequential Pipeline (線性流程)**：

1.  **Input**: 原始影片/音訊檔案。
2.  **Perception Layer (感知層)**:
    *   **Audio**: 透過 `audio_transcribe.py` 將音軌轉寫為文字分段。
    *   **Vision**: 透過 `vision_analyze.py` (Qwen2-VL) 將影格轉換為視覺描述。
    *   *兩者輸出均為結構化 JSON，存入 `05_Output/analysis`。*
3.  **Integration Layer (整合層)**:
    *   **`integrate_timeline.py`**: 利用 **時間區間重疊算法 (Intersection Logic)**，將視覺與聽覺資料對齊，生成單一的 `timeline_integrated.json`。
4.  **Cognition Layer (認知層)**:
    *   **`director.py` (LLM Brain)**: 讀取對齊後的時間軸，由 **Qwen2.5-7B (4-bit)** 執行推理，輸出剪輯建議 (保留/刪除/轉場)。
5.  **Output Layer (輸出層)**:
    *   **`export_davinci_markers.py`**: 將 JSON 決策轉碼為 CSV，供專業剪輯軟體 (DaVinci Resolve) 讀取。

---

## 🛠️ 三、核心腳本模組詳細分析 (Code Modules)

以下為 `03_Code` 目錄下各模組的技術規格：

### 1. `video_extract.py` (前處理 - 待實作)
*   **狀態**: 🟡 空殼 (0 行程式碼)。
*   **定位**: 預計負責將影片切片或提取關鍵影格 (Keyframes) 供視覺分析使用。目前由 `06_Test` 手動提供的 `frame_*.jpg` 代替。

### 2. `audio_transcribe.py` (音訊感知)
*   **功能**: 使用 OpenAI Whisper (CPU 模式) 將音訊轉寫為文字。
*   **輸入**: `.wav` 音檔。
*   **輸出**: `audio_segments.json` (包含 `start`, `end`, `text`)。
*   **特點**: 為避免驅動衝突，強制使用 `device="cpu"`。

### 3. `vision_analyze.py` (視覺感知)
*   **功能**: 使用 `Qwen2-VL-2B-Instruct` (GPU 模式) 分析影格內容。
*   **輸入**: `frame_*.jpg` 影格圖片。
*   **輸出**: `visual_data.json` (包含 `start_time`, `visual_summary`)。
*   **特點**: 每 3 秒抽一張影格進行推論，以平衡解析度與運算效能。

### 4. `integrate_timeline.py` (時間軸聚合)
*   **功能**: **系統核心算法**。將「視覺時間軸」與「音訊時間軸」進行對齊 (Align)。
*   **邏輯**: 採用 **Intersection 算法** (例如：00:00-00:03 的視覺片段，會包含該區間內所有重疊的音訊文字)。
*   **輸出**: `timeline_integrated.json` (標準化的片段清單)。

### 5. `director.py` (LLM 導演推理)
*   **功能**: 系統大腦。將整合後的片段丟入 LLM。
*   **模型**: Qwen2.5-7B-Instruct (4-bit Quantized，節省顯存)。
*   **輸入**: `timeline_integrated.json`。
*   **輸出**: `director_decisions.json` (JSON 格式：包含 `recommendation`, `reason`, `confidence`)。
*   **Prompt 設計**: 系統提示詞定義了「專業剪輯導演」的角色，強制要求輸出 JSON 以利程式解析。

### 6. `main.py` (主控 Orchestrator)
*   **功能**: 串接所有腳本的入口點。
*   **特色功能**:
    *   **參數化執行**: 支援 `--skip-audio` 等參數跳過耗時步驟。
    *   **快取機制**: 偵測 JSON 檔案是否已存在，若存在則自動跳過重複運算。
    *   **Mock 模式**: 支援 `--mock` 參數進行無素材的快速驗證。

### 7. `export_davinci_markers.py` (DaVinci 標記匯出)
*   **功能**: 將 AI 決策轉換為人類剪輯師可理解的格式。
*   **輸入**: `director_decisions.json`。
*   **輸出**: `davinci_markers.csv`。
*   **轉碼邏輯**:
    *   將秒數轉換為 `HH:MM:SS:FF` (Timecode) 格式。
    *   **顏色映射**: 保留=🟢綠, 刪除=🔴紅, 待定=🟡黃。
    *   **備註欄**: 包含 AI 的決策理由與信心指數。

---

## 🎬 四、人機協同閉環 (Human-in-the-Loop Integration)

本系統的終點不是「自動剪輯」，而是「輔助剪輯」。閉環流程如下：

1.  **AI 預處理**: AI 讀取素材，自動標記出「精彩片段」與「廢片」，並計算信心指數。
2.  **CSV 匯入**: 剪輯師在 **DaVinci Resolve** 中匯入 `davinci_markers.csv`。
3.  **視覺化確認**: 剪輯師在時間軸上會看到彩色的 Marker (紅/綠/黃) 與 AI 的備註。
4.  **人工覆核**: 剪輯師依據 AI 建議 (例如：綠色區塊保留，紅色區塊刪除) 進行微調或刪除。
5.  **效率提升**: 透過 AI 預處理，剪輯師不再需要「逐幀檢查」，而是直接處理「決策結果」，大幅縮短 Rough Cut 的時間。

---

## 📝 五、專案狀態摘要

*   **穩定性**: ⭐⭐⭐⭐⭐ (腳本邏輯完整，錯誤處理機制良好)
*   **可擴展性**: ⭐⭐⭐⭐ (模块化設計清晰，可輕易替換 LLM 或 Whisper 模型)
*   **當前瓶頸**: `video_extract.py` 尚未實作，目前依賴手動提供的影格。
*   **下一步**: 實作 `video_extract.py` 並與 `main.py` 串接，實現全流程自動化。
