# 發布副本驗證（2026-11-18）

此資料夾為獨立 GitHub 副本，原開發專案未修改；原來源與感測器共90個檔案雜湊核對一致。原先桌面 Release 快照亦未覆寫。

## 感測修正

- 排除開發者 .local 設定，同時把9個未修改的CPU感測相依DLL移入可發布 third_party/cpu-sensor，核對原SHA256一致。
- 副本程式及PyInstaller資源路徑改用公開資料夾；預設Windows依賴包含Python.NET，原始碼／正式啟動器皆檢查依賴。
- 保留MPL、Apache、MIT及上游嵌入元件授權／來源資訊。未附監控GUI或系統驅動安裝器。
- 增加開始使用、安裝與CPU診斷入口；提示詞範本置於根目錄。
- export_source.py已驗證再次匯出仍含感測DLL、授權及診斷入口。

## 已驗證

- 使用已安裝依賴的Python3.10：`python -X utf8 -B -m unittest discover -s 03_Code/tests -v`，exit0，120 tests，OK。
- `python -X utf8 -B 03_Code/check_cpu_sensor.py`，exit0：9個DLL雜湊正確，Python.NET／CLR載入成功，實際建構Computer且未開啟硬體。
- 在本副本重建Windows啟動器，`AI Director Studio.exe --check` exit0。檢查依賴不下載或載入AI模型。
- 乾淨檔案／個人路徑掃描通過，無.git、Codex、VS Code、虛擬環境、AI權重、影片、個人設定或測試日誌。
- 發布前清除本副本測試生成的.local／05_Output；不清理原專案。

## 尚未驗證

目前執行檢查的程序不是管理員，因此沒有讀取實際CPU溫度，也沒有繞過權限。實際顯示仍取決於使用者接受原程式UAC詢問、已安裝相容PawnIO、.NET及CPU Package感測器支援。未自動安裝或修改驅動；未在另一台全新電腦安裝依賴、未啟動模型推論／Resolve或完整GUI。

## 副本專屬差異

CPU資源公開路徑、預設依賴／launcher檢查、診斷腳本／測試、README／部署說明、授權／SHA256與匯出規則僅在此副本調整。既有影音分析、Whisper／CPU備選與Resolve流程自原專案複製，未另做產品重構。應用程式原本的授權選擇未改變，第三方授權不替代應用程式授權。
