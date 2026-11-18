# CPU 溫度部署與排錯

## 上次遺漏的原因

原開發版從被 .gitignore 排除的 .local/cpu-sensor-libs 讀 DLL。只匯出乾淨原始碼會漏掉整組感測器。此副本改用公開 third_party/cpu-sensor，預設依賴包含 Python.NET；launcher 也檢查該依賴。原開發資料夾沒有修改。

## 必要條件

- Windows、相容 .NET Framework（上游 net472，即 4.7.2 或相容後續版本）。
- 使用本程式相同 Python 安裝 requirements.txt，包含依 Python 版本選擇的 Python.NET。
- 保留 third_party/cpu-sensor 的完整相依 DLL；附檔不是驅動安裝程式。
- 既有相容 PawnIO 驅動；參考官方 https://pawnio.eu/ ，由使用者依官方流程安裝。不自動安裝、停用保護或繞過 UAC。
- 接受原介面 CPU 溫度管理員詢問。拒絕仍可分析，只是溫度可能 N/A。
- CPU 實際提供可讀的 CPU Package 感測器。只接受唯一有效的 Package 值，不以其它數字冒充。

## 檢查

`python 03_Code/check_cpu_sensor.py` 驗證 SHA256、Python.NET、CLR 載入與 Computer 建構，不啟動硬體讀取。

以已取得管理員權限的終端執行 `python 03_Code/check_cpu_sensor.py --read` 才讀溫度；一般權限時明確跳過，不自行提權。

程式溫度計滑鼠提示也顯示 DLL／HTTP 來源或失敗原因。沒有有效值就 N/A；DLL 失敗後30秒再試，不保留失敗前的舊值。HTTP 備選仍是本機127.0.0.1:8085，不會傳送到外部服務。

## 發布

DLL 未修改，SHA256與原開發版一致。可重現的依賴集合／上游授權與來源見 third_party/cpu-sensor/NOTICE.md。沒有連帶授權應用程式原始碼，也沒有附上或安裝 PawnIO 系統驅動。打包 spec 與 export_source.py 均保留這組檔案，避免下一次匯出再遺漏。
