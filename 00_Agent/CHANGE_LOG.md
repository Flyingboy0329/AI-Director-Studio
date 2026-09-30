# CHANGE LOG

## [2026-09-28] - Resolve Lua API 核心存取測試 (v3.5)
- 🧪 建立最小可行性驗證腳本 `test_timeline.lua`：專注測試 `project:GetCurrentTimeline()` API 回傳物件。
- 🔄 實作頁面切換邏輯：取得 Timeline 成功則切至 `edit` 頁面，無 Timeline 則切至 `media` 頁面，避開 Console 輸出限制。
- 📉 極簡化依賴：不呼叫 `AddMarker`、不讀寫 EDL/檔案，純驗證物件階層與頁面控制權。
- 📝 提供逐行註解說明，方便 Agent 快速理解 Resolve 內部 API 結構。

## [2026-09-28] - DaVinci 內部 Lua 橋接腳本實裝 (v3.4 Zero-Hand Test)
- 🧪 建立最小可行性驗證 POC：編寫 `03_Code/test_import.lua`，透過內部 `Resolve()` 物件直接存取 Project 與 Timeline。
- 🌉 突破免費版 IPC 限制：不依賴外部 Python 腳本或 PowerShell，直接在 Resolve 內部環境調用 `timeline:ImportIntoTimeline()`。
- 📂 部署路徑明確：產出檔案已就緒於專案目錄，提供複製指令至 `...\Scripts\Utility\` 目錄。
- ✅ 實作 Zero-Hand Test 流程：開啟 DaVinci → 工作區 ➔ 腳本 ➔ AI_Director_Test 即可驗證標記注入。

## [2026-09-28] - DaVinci 官方動態載入模組實裝 (v3.3 API 重構)
- 🔄 重構 `auto_apply_markers.py`：移除舊版 `bmd` 依賴與 PowerShell Toast 腳本。
- 🧩 實裝官方動態載入樣板：透過 `sys.path` 追加 `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules` 並導入 `DaVinciResolveScript`。
- ✅ 完善自動匯入邏輯：依序取得 `ProjectManager` -> `CurrentProject` -> `CurrentTimeline`，調用 `timeline.ImportIntoTimeline(EDL_PATH)` 自動注入標記。
- 🖥️ 修復 PowerShell 語法錯誤：改為乾淨的終端輸出與狀態提示，提升跨環境相容性。

## [2026-09-28] - 路徑緊急校準：Watchdog 監控目錄修正 (v3.2)
- 🔄 修正 `main.py` 預設監控路徑：由 `01_Input` 全面更新為實際存在的 `02_Data` 目錄。
- 🛡️ 強化 Watchdog 防呆機制：新增檔案類型過濾，自動排除 `_temp`、`.tmp`、`.part` 等暫存檔，避免觸發半成品 Pipeline。
- 📁 自動目錄創建：`os.makedirs(video_dir, exist_ok=True)` 確保 `02_Data` 路徑穩定存在。
- 📝 同步更新 CLI 提示與專案狀態文件。

## [2024-XX-XX] - DaVinci Resolve Shot Region v3.1 升級 (系統整合與自動化作業)
- 🚀 實作端到端無人值守管線：重構 `main.py` 為 Pipeline Runner，依序執行 6 大步驟並具備錯誤攔截。
- 🤖 新增 Watchdog 模式 (`python main.py --watch`)：常駐監控 `01_Input/` 目錄，自動觸發素材分析流程。
- 🎨 編寫 DaVinci 專屬自動注入模組 `auto_apply_markers.py`：
  - 支援 BMD Script API 自動載入 EDL 標記至當前 Timeline。
  - 具備 Windows 系統通知備援機制，確保免費版用戶亦能即時獲知分析完成。
- 🛡️ 提升系統穩定性：單一環節失敗自動寫入日誌並安全中斷，避免資料損毀。

## [2024-XX-XX] - DaVinci Resolve Shot Region v3.0 升級 (系統核心升級)
- 🧠 實裝「連續鏡頭語義聚合演算法 (aggregate_shot_regions)」：將逐秒評分自動聚合為符合影視剪輯概念的 Shot Region。
- 📏 非均等長度支援：聚合鏡頭長度動態計算，最短 2 秒，最長 8 秒，跨越顯著斷層 (差值>65) 強制切鏡。
- 🎨 標準 CMX3600 Extension 結構：輸出包含 `|C:`, `|M:評分:XXYY/ZZ`, `|D:` 完整語法。
- 📄 產出 `shot_regions_summary.json`：記錄每個聚合鏡頭的起迄範圍、分數與語義標籤，便於後期追蹤。
- 🚀 系統全面升級為 AI Shot Region 語義聚合架構，支援一鍵識別完整可用鏡頭。

## [2024-XX-XX] - DaVinci Resolve Shot Region v2.4 升級 (重大語法修復)
- 🐛 修復 CMX3600 管線符號衝突：將 `|M:` 內部分隔符由 `|` 改為 `/`
- 🔧 標記格式升級為 `|M:評分:{grade}{score}/{core_tag}`，徹底恢復區間光帶與評語顯示
- ⚠️ 解決 `|D:` 標籤被截斷問題，時長與 Shot Region 功能完全正常化
- 📄 同步更新 `format_marker_text` 邏輯並重新產出 EDL 檔案

## [2024-XX-XX] - DaVinci Resolve Shot Region v2.3 升級
- 🎯 UI 排版極限精煉：標記文字強制前綴「評分:」，格式統一為 `|M:評分:{grade}{score}|{core_tag}`
- 📏 字元嚴格壓制在 10 字以內，徹底杜絕 DaVinci 白色 Overlay 表頭截斷
- 🔢 維持長條光帶 `|D:` 邏輯：精確對應 72/96/72/72/48 幀數區間
- 🔄 同步更新 `format_marker_text` 與 `map_grade` 映射邏輯，並重新產出 EDL 檔案

## [2024-XX-XX] - DaVinci Resolve Shot Region v2.2 升級
- 🟢 恢復 Shot Region 區間光帶：確保 `|D:` 幀數精確計算（3秒=72 / 4秒=96 / 2秒=48），時間軸長條與時長欄位完整顯示
- ✍️ 補回精華理由：標記文字全面升級為 `【{grade}{score}分】{reason_short}` 格式
- 📏 字數嚴格壓制於 16 字以內，徹底解決懸浮框 '...' 截斷問題
- 🔄 同步更新 `generate_edl` 與 `generate_test_region_edl` 產出邏輯
- 📄 重新產出 `05_Output/reports/test_region_markers.edl` 與 `davinci_markers.edl`

## [2024-XX-XX] - DaVinci Resolve Shot Region v2.1.1 升級
- 🐛 修復 `KeyError: 'reid'`
- 🔄 統一資料結構鍵名：`reid` -> `reel` (Reel Name)

## [2024-XX-XX] - DaVinci Resolve Shot Region v2.1 升級
- 🐛 修復 `TypeError: unsupported operand type(s) for -: 'str' and 'str'`
- ⚙️ 新增 `tc_to_frames(tc_str, fps=24)` 時間碼解析函式

## [2024-XX-XX] - DaVinci Resolve Shot Region v2.0 升級
- 🎨 修正顏色映射錯位：精良 -> ResolveColorCyan (清爽亮藍)
- 🏷️ 品級更名：最低檔由「垃圾」全面更名為「普通」
- ✂️ 懸浮框文字極簡化：去除外層括號，格式精簡為 `{grade}{score}分|{status}/{feature}`

## [2024-XX-XX] - 初始實裝
- ✅ 實裝 `generate_test_region_edl(output_path)` 支援 `|C:` / `|D:` 區間標記