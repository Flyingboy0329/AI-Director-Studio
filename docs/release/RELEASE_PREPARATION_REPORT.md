# GitHub 發布準備與差異報告

- **TASK_ID:** REL-PREP-20261118
- **STATUS:** PREPARED / NEEDS_OWNER_REVIEW；這不是獨立QA或正式發行核准。
- **檢查時間:** 2026-11-18T14:20:59+08:00（Asia/Taipei）
- **目標:** [Flyingboy0329/AI-Director-Studio](https://github.com/Flyingboy0329/AI-Director-Studio)
- **SUMMARY:** 只整理指定發布副本的README、SVG識別、忽略規則、封裝白名單與發布／審查文件；推論／GUI／C#／Lua／spec內容未變，僅更新export_source.py與新增封裝測試，原開發資料夾與既有ZIP未修改。

## 1. Git、分支與遠端盤點

| 範圍 | 實際狀態 |
| --- | --- |
| 指定發布副本 | 沒有.git；無自己的branch、remote、tracked/index。不能把它當成已同步的Git工作樹 |
| 原開發repo（唯讀） | main，HEAD `2381e04`；現有origin/main `9f9f1a7`，落後3個commit；remote仍使用舊名 `peepeepoopoo`。未改remote、未fetch進原repo |
| 原repo工作目錄盤點 | staged 0，unstaged 50，untracked status entries 98；含大量既有工作，不適合直接整包覆蓋／git add . |
| 隔離遠端基準 | 由正確URL取得的新clone；main與origin/main一致、工作樹乾淨；HEAD `9f9f1a741786adb420000167cec1a09641be4a94` |
| 遠端標籤 | 僅v1.0.0，指向469a9136ee2a0e281b2ab9f2787a63825df1249e |
| 既有Release | v1.0.0；標題包含Beta但API prerelease=false。舊說明有production-ready／CUDA FP16／timeline等敘述，不能沿用為新版實測承諾 |

GitHub連線只讀取repo／Release metadata；無留言、寫檔、commit、push、merge、tag或Release建立。原repo的Git index SHA256前後一致。遠端clone只用於證據與比對，不是建議Owner直接發布的工作樹。

## 2. 本機與origin/main差異

比較前發布副本115檔；遠端71個tracked檔。共同19檔：14有內容差異、3僅EOL／BOM差異、2完全一致；本機獨有96檔、遠端獨有52檔。這是本次文件修改前的基準數字，不把remote-only直接當成刪除。

主要既有內容差異：

- `01_Project/user_config.json`
- `03_Code/ai/audio_analyzer.py`
- `03_Code/ai/video_extract.py`
- `03_Code/ai/vision_analyzer.py`
- `03_Code/app_gui.py`
- `03_Code/bridge/auto_injector.py`
- `03_Code/main.py`
- `03_Code/pipeline/director_decision.py`
- `03_Code/resolve_lua/davinci_marker_injector.lua`
- `03_Code/watch_folder.py`
- `04_Models/.gitkeep`
- `AI_Director.spec`
- `README.md`
- `resolve_lua/davinci_marker_injector.lua`

完整檔案層級狀態見 [FILE_COMPARISON.csv](FILE_COMPARISON.csv)，含新功能模組、測試、感測DLL與文件的ADD／UPDATE建議。表格為一次檢查checkpoint，不作會自我遞迴的文件checksum。

- 建議source commit：**125檔**，見 [PROPOSED_UPLOAD_FILES.txt](PROPOSED_UPLOAD_FILES.txt)。包含必要原始碼、設定範本、啟動／建置來源、文件、測試、9個DLL及授權。
- 建議停止追蹤生成檔：**26檔**，見 [UNTRACK_GENERATED_FILES.txt](UNTRACK_GENERATED_FILES.txt)。只提議git rm --cached，不刪實體資料，不清Git歷史。
- 遠端獨有且預設保留：**26檔**，見 [REMOTE_ONLY_KEEP_FILES.txt](REMOTE_ONLY_KEEP_FILES.txt)。AGENTS、歷史文件、legacy及舊測試不能因乾淨副本沒帶就鏡像刪掉；若要封存或改寫路徑，另請Owner決策。
- 不上傳清單見 [PROPOSED_EXCLUDE_FILES.txt](PROPOSED_EXCLUDE_FILES.txt)。根目錄新exe保留在本機，建議作Release資產；C#來源與build腳本進source commit。

## 3. .gitignore與資料安全

新增對模型／mmproj／Whisper權重、影音、環境、API金鑰檔、私鑰、個人設定、日誌、測試／建置輸出、開發工具與封裝檔的排除。`01_Project/*.json`是審過的相對路徑範本，不誤當個人設定刪除。必要的third_party感測DLL、授權、SHA256允許加入，避免再次漏溫度感測。24個允許／拒絕路徑fixture通過，含模型、影片、secret、環境與公開DLL。

已追蹤檔不因.gitignore自動消失。對26個生成檔只提供索引停止追蹤方案；未執行git rm、未刪影片／模型／歷史證據。既有tracked治理文件即使符合新增忽略政策也不擅自移出索引。

### 敏感掃描結果（只記位置，不記匹配值）

| 範圍 | 結果 |
| --- | --- |
| 本機115檔初始副本 | 0個已知金鑰／私鑰／憑證URL／個人路徑模式命中 |
| 既有桌面ZIP | 0個上述模式命中；原ZIP SHA256 `0fbf2dded1f21e2a438344ec54a155f4eae0837f88faa83aa1f10fd9a8a73209` 保持不變 |
| 遠端main | 45個命中，全部是個人路徑，不是識別出的API金鑰 |
| 遠端所有可達refs歷史 | 74個<=2MiB blob已掃描，47個個人路徑命中；未識別出所檢查的金鑰／私鑰模式 |
| 模型／影片／環境 | 本機公開候選未發現GGUF、mmproj、AI權重、影片、虛擬環境或實際使用者設定；感測DLL不是AI權重 |

模式包括GitHub／HF／OpenAI形式token、AWS access key、私鑰、帶密碼URL及字面secret賦值。不是完整DLP／二進位鑑識，也未下載舊Release資產內容作掃描；不能據此保證所有未知格式秘密不存在。授權文本中的作者／上游來源不是待刪個人機器路徑。

遠端現行命中位置：

| 檔案 | 類別 | 行號（binary只作定位） |
| --- | --- | --- |
| `00_Agent/AGENT_RULES.md` | personal_path | 10 |
| `00_Agent/PROJECT_OVERVIEW.md` | personal_path | 6 |
| `03_Code/__pycache__/audio_transcribe.cpython-310.pyc` | personal_path | 32 |
| `03_Code/__pycache__/director.cpython-310.pyc` | personal_path | 7 |
| `03_Code/__pycache__/export_davinci_markers.cpython-310.pyc` | personal_path | 12 |
| `03_Code/__pycache__/integrate_timeline.cpython-310.pyc` | personal_path | 23 |
| `03_Code/__pycache__/main.cpython-310.pyc` | personal_path | 7 |
| `03_Code/__pycache__/main.cpython-311.pyc` | personal_path | 7 |
| `03_Code/__pycache__/video_extract.cpython-310.pyc` | personal_path | 18 |
| `03_Code/__pycache__/vision_analyze.cpython-310.pyc` | personal_path | 32 |
| `03_Code/__pycache__/watch_folder.cpython-310.pyc` | personal_path | 5 |
| `03_Code/ai/__pycache__/audio_analyzer.cpython-310.pyc` | personal_path | 7 |
| `03_Code/ai/__pycache__/audio_analyzer.cpython-310.pyc` | personal_path | 25 |
| `03_Code/ai/__pycache__/audio_analyzer.cpython-310.pyc` | personal_path | 25 |
| `03_Code/ai/__pycache__/audio_analyzer.cpython-311.pyc` | personal_path | 9 |
| `03_Code/ai/__pycache__/audio_analyzer.cpython-311.pyc` | personal_path | 53 |
| `03_Code/ai/__pycache__/audio_analyzer.cpython-311.pyc` | personal_path | 53 |
| `03_Code/ai/__pycache__/video_extract.cpython-310.pyc` | personal_path | 15 |
| `03_Code/ai/__pycache__/video_extract.cpython-310.pyc` | personal_path | 16 |
| `03_Code/ai/__pycache__/video_extract.cpython-310.pyc` | personal_path | 16 |
| `03_Code/ai/__pycache__/video_extract.cpython-311.pyc` | personal_path | 15 |
| `03_Code/ai/__pycache__/video_extract.cpython-311.pyc` | personal_path | 24 |
| `03_Code/ai/__pycache__/video_extract.cpython-311.pyc` | personal_path | 24 |
| `03_Code/ai/__pycache__/vision_analyzer.cpython-310.pyc` | personal_path | 9 |
| `03_Code/ai/__pycache__/vision_analyzer.cpython-310.pyc` | personal_path | 31 |
| `03_Code/ai/__pycache__/vision_analyzer.cpython-310.pyc` | personal_path | 31 |
| `03_Code/ai/__pycache__/vision_analyzer.cpython-311.pyc` | personal_path | 7 |
| `03_Code/ai/__pycache__/vision_analyzer.cpython-311.pyc` | personal_path | 61 |
| `03_Code/ai/__pycache__/vision_analyzer.cpython-311.pyc` | personal_path | 61 |
| `03_Code/ai/audio_analyzer.py` | personal_path | 90 |
| `03_Code/ai/audio_analyzer.py` | personal_path | 91 |
| `03_Code/ai/video_extract.py` | personal_path | 44 |
| `03_Code/ai/video_extract.py` | personal_path | 45 |
| `03_Code/ai/vision_analyzer.py` | personal_path | 98 |
| `03_Code/ai/vision_analyzer.py` | personal_path | 99 |
| `03_Code/bridge/__pycache__/auto_injector.cpython-310.pyc` | personal_path | 4 |
| `03_Code/bridge/__pycache__/auto_injector.cpython-310.pyc` | personal_path | 4 |
| `03_Code/bridge/__pycache__/auto_injector.cpython-311.pyc` | personal_path | 4 |
| `03_Code/bridge/__pycache__/auto_injector.cpython-311.pyc` | personal_path | 6 |
| `03_Code/pipeline/__pycache__/director_decision.cpython-310.pyc` | personal_path | 6 |
| `03_Code/resolve_lua/davinci_marker_injector.lua` | personal_path | 13 |
| `AI Director Studio.lnk` | personal_path | 2 |
| `legacy_archive/dryrun_test.py` | personal_path | 58 |
| `legacy_archive/dryrun_test.py` | personal_path | 65 |
| `resolve_lua/davinci_marker_injector.lua` | personal_path | 13 |

歷史位置與blob識別碼見 [SENSITIVE_SCAN_RESULTS.json](SENSITIVE_SCAN_RESULTS.json)，沒有洩露匹配字串。更新main或git rm --cached不清除歷史；如Owner決定歷史清理，另開任務，本輪不改寫。

## 4. README與公開配置指南

README重做識別封面、清楚導航、兩種Mermaid架構圖、安裝與啟動流程、硬體／GPU分層、CPU備選、Whisper儲存與生命週期、Media Pool Marker、資料清理與驗證界線。圖片是SVG專案識別，沒有捏造執行中的產品截圖。SVG已用既有Qt離線渲染並檢視；此環境Qt字型資料庫預設為空，預覽程序讀取既有Windows字型後正常，未安裝／散布字型。GitHub端Mermaid／HTML實際呈現尚待Owner預覽。

舊repo URL在新版公開文件不再使用；目標皆為AI-Director-Studio。硬體指南維持GUI共用靜態來源：4–48GB、方案A／B與B參數規模，不綁Qwen／Gemma等品牌；SmolVLM／SmolVLM2僅輕量家族例外。指南矩陣全為Estimated／Experimental，沒有Verified。

## 5. 版本、建置與授權風險

建議 **v1.1.0-rc.1**：相較v1.0.0已有大量新能力，但實機整合與乾淨安裝仍欠證據，宜先候選版。完成Owner審核及實機驗收再考慮v1.1.0；沒有自行建立版本檔、tag或Release。

發布前需Owner決策：

1. **授權未定**：沒有應用程式LICENSE；PyQt6 metadata GPL-3.0-only，上游有GPLv3／商業方案。不能宣稱MIT或無條件可再散布；感測DLL告知不代替應用程式授權。未改授權。
2. **版本字串不一致**：GUI標題／badge仍為v1.0，沒有集中版本來源；候選版本只是提案。發布前應核准要保留舊UI識別或另做版本中繼資料調整。
3. **建置未驗收**：完整PyInstaller包NOT_RUN；spec的hidden imports含未列入runtime requirements的watchdog，與現用PyInstaller版本相容性需建置驗證。小型exe不是獨立Python安裝包。
4. **環境範圍**：多數requirements未鎖版；只有目前Python／套件組合測試，不宣稱fresh install或所有Python3.10+均可用。引擎安裝器資產／CUDA／舊卡需另驗。
5. **GPU／Resolve／讀溫**：分層90%為估算；缺回執不能代表寫入已確認；實際模型品質、所有Resolve組合及管理員讀溫未在本輪驗收。
6. **舊資料保留**：原ZIP是改README前快照，SHA保留；不能拿它當已更新的正式Release。舊版remote仍有個人路徑／runtime／cache，要按Owner決策精確處理，不做整包覆蓋或鏡像刪除。

詳細環境與授權見 [DEPENDENCIES_AND_LICENSES.md](DEPENDENCIES_AND_LICENSES.md)、[TEST_ENVIRONMENT.json](TEST_ENVIRONMENT.json)。

## 6. TESTS與EVIDENCE

| 檢查 | 觀察結果 |
| --- | --- |
| unittest discover全部既有測試 | exit0，122 tests，OK，0.718s（原有120＋封裝2）；不等於coverage百分比／GPU整合證明 |
| CPU感測診斷（未--read） | exit0，9個DLL雜湊及Python.NET／CLR載入成功；目前非管理員，未讀實際溫度 |
| 小型啟動器--check | exit0；只驗檔案／Python依賴，未開完整GUI |
| .gitignore fixture | PASS，17個拒絕＋7個允許，DLL／licenses未被誤排除 |
| SVG | 解析／離線渲染與視覺檢視通過；GitHub實際預覽NOT_RUN |
| 推論／GUI／C#／Lua/spec 前後比對 | SHA256一致；僅export_source.py封裝清單及新增2項封裝測試變動 |
| 原開發repo index、既有ZIP | SHA256一致；未更改原工作區或舊ZIP |
| 大型模型／完整GPU／Resolve／管理員讀溫／fresh install／完整PyInstaller | NOT_RUN |

原始命令輸出與文件備份放在本機被忽略的.local/release-prep；公開報告不含完整使用者路徑或憑證。此為本次自我驗證，沒有宣稱已經完成遠端AGENTS要求的獨立QA／PM最終核准，最終交付仍等待Owner審核。

## 7. CHANGED_FILES與NEXT_ACTION

本輪變更類型：README.md、.gitignore、RELEASE_NOTES.md、啟動／開始使用文件、docs/assets/project-banner.svg及docs/release下的差異／清單／依賴／測試／手動步驟文件；另改export_source.py的封裝白名單、補test_release_export.py，確保封面／草稿／必要DLL不漏包。推論與GUI產品code未變。歷史manifest不再建議作source commit，檔案仍保留本機。

Owner先審README與Release草稿、授權／版本／實機缺口，再依 [MANUAL_GIT_STEPS.md](MANUAL_GIT_STEPS.md) 的新clone與精確清單逐段操作。所有git add、rm --cached、commit、push、merge、tag與GitHub Release寫入均 **NOT_EXECUTED**。無任何模型下載、依賴重裝、實體資料刪除或歷史重寫。

## 8. 候選附件（未發布）

桌面另準備 `AI_Director_Studio_v1.1.0-rc.1_source_DRAFT.zip` 與同名 `.sha256`。候選包只供Owner審核，沒有建立GitHub Release或版本標籤；根目錄小型exe作附件保留，不列入source commit。原 `AI_Director_GitHub_20261118.zip` SHA保持不變，是文件改版前快照。候選包不等於授權／版本／實機驗收已完成，應依Owner最後審核內容重建正式附件。
