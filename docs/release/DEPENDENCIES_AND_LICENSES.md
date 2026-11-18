# 依賴、建置與授權核對

此表是目前已安裝測試環境的中繼資料，不是新的鎖版檔，也不是全新電腦安裝驗證。本輪沒有下載模型、重新安裝或升級依賴。

| 套件 | 本輪環境版本 | 授權中繼資料／注意 |
| --- | --- | --- |
| PyQt6 | 6.11.0 | GPL-3.0-only |
| psutil | 7.2.2 | BSD-3-Clause |
| numpy | 2.2.6 | BSD-3-Clause; full upstream notices also apply |
| opencv-python | 5.0.0.93 | Apache 2.0 |
| torch | 2.11.0+cu128 | BSD-3-Clause |
| faster-whisper | 1.2.1 | MIT |
| ctranslate2 | 4.8.2 | MIT |
| huggingface-hub | 2.2.0 | Apache-2.0 |
| filelock | 3.32.3 | MIT |
| PyAutoGUI | 0.9.54 | BSD |
| pyperclip | 1.11.0 | BSD |
| nvidia-ml-py | 13.615.71 | BSD |
| pythonnet | 3.1.0 | MIT |
| clr-loader | 0.3.1 | See upstream metadata |
| pyinstaller | 6.22.3 | GPL with bootloader exception; see upstream |

## 建置方式與限制

- 正式小型啟動器：`Build_Windows_Launcher.ps1` 使用 Windows 內建 .NET Framework C# 編譯器與 `01_Project/app_icon.ico`；來源 `03_Code/WindowsLauncher.cs`。目前 exe 是啟動入口，不內含 Python、模型或引擎。
- 完整應用包：既有 `AI_Director.spec` 供 `python -m PyInstaller AI_Director.spec` 使用。完整建置本輪 **NOT_RUN**；不能宣稱可直接發行獨立安裝包。
- `requirements.txt` 沒有宣告 PyInstaller；spec 又有 `watchdog` hidden import，但主要 runtime requirements 沒列它。這是完整打包需另外核對的建置依賴問題，不在本輪安裝或默默補依賴。
- 大部分 runtime 依賴使用最低版本範圍，Python.NET 在 Windows 依 Python 版本指定版本。現有環境有120項測試通過，不代表任意新版本組合或全新安裝已驗收。
- 引擎安裝器預設 b12359，CUDA 資產格式指定13.5；上游資產存在性、舊卡及驅動相容性需Owner確認。CPU備選仍需原引擎能啟動CPU與相應旗標，不下載另一引擎來修DLL問題。

## 應用程式授權：Owner 決策事項

遠端根目錄與本機副本沒有 LICENSE，GitHub metadata 的 license 亦為空。本輪沒有新增、替換或推定應用程式授權；不能把公開repo自動寫成MIT授權或任意可再散布。

已安裝 PyQt6 metadata 為 GPL-3.0-only；上游提供 GPLv3／商業雙授權。Owner需確認應用程式的授權及適用方案，再決定正式散布方式。這裡列出需核對的條件，不代替Owner授權選擇或法律判定。

- [PyQt 上游雙授權說明](https://www.riverbankcomputing.com/software/)
- [PyInstaller 授權與bootloader例外](https://www.pyinstaller.org/en/stable/license.html)：打包器例外不取代應用程式或其它依賴的授權。

## 感測 DLL 與其它素材

`third_party/cpu-sensor` 保留9個未修改 DLL、SHA256、NOTICE及上游來源。LibreHardwareMonitor、BlackSharp、DiskInfoToolkit、RAMSPDToolkit、HidSharp與.NET元件各自保留其授權，嵌入PawnIO模組亦有上游告知。來源連結與全文見 [NOTICE](../../third_party/cpu-sensor/NOTICE.md)。未附PawnIO系統驅動安裝程式。

現有DLL／CLR載入檢查不等於已完整判定所有散布義務；正式Release仍需Owner核對對應源碼可取得性、版本與告知文件。AI模型／mmproj、影片素材的授權另外核對，這次不附模型或影片。專案icon照原檔保留，未替Owner聲明第三方權利。
