# Owner 審核後的手動 Git 步驟

以下只供Owner逐段審核後手動執行，本輪沒有執行任何git add／rm --cached／commit／push／merge／tag／GitHub Release建立。不要把發布資料夾直接覆蓋既有儲存庫再用鏡像刪除。

## 1. 從正確遠端建立乾淨工作區

PowerShell：

```powershell
$desktop = [Environment]::GetFolderPath('Desktop')
$source = Join-Path $desktop 'AI_Director_GitHub_20261118'
$work = Join-Path $desktop 'AI-Director-Studio-owner-review'
# 目標若已存在，改用新的資料夾名稱；不要刪既有工作區。
git clone https://github.com/Flyingboy0329/AI-Director-Studio.git $work
git -C $work remote -v
git -C $work switch -c release/v1.1.0-rc.1-prep
git -C $work status --short --branch
```

發布副本本身沒有.git，所以不能直接假設它的origin／main／index存在。原開發repo有大量未提交修改且remote仍用舊名稱；這裡用新clone保留遠端AGENTS、歷史文件及既有內容，不更動原開發repo。

## 2. 依清單逐檔複製，保留遠端獨有資料

```powershell
$files = @(Get-Content -LiteralPath (Join-Path $source 'docs\release\PROPOSED_UPLOAD_FILES.txt') -Encoding UTF8 | Where-Object { $_.Trim() })
foreach ($relative in $files) {
    if ([IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\/])\.\.([\/]|$)') { throw 'Invalid relative path' }
    $from = Join-Path $source $relative
    $to = Join-Path $work $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $to) | Out-Null
    Copy-Item -LiteralPath $from -Destination $to
}
git -C $work status --short
git -C $work diff --stat
git -C $work diff --check
```

這只複製經建議的來源檔，不做任何實體刪除；remote-only清單不代表要刪掉。AGENTS與歷史工作證據保留。根目錄小型exe建議放Release資產，不放來源commit；需要時從C#重建。

## 3. Owner 確認後才停止追蹤生成檔（可選）

```powershell
$generated = @(Get-Content -LiteralPath (Join-Path $source 'docs\release\UNTRACK_GENERATED_FILES.txt') -Encoding UTF8 | Where-Object { $_.Trim() })
# 僅移除Git index，不刪除本機檔案；這不是歷史清理。
git -C $work rm --cached --ignore-unmatch -- $generated
```

新版.gitignore不會自動讓舊tracked快取消失。此步只針對列出的快取、生成輸出、舊捷徑與舊pythonw；不把歷史文件、影片、模型或工作證據作為實體清理目標。舊程式／歷史文件中的個人路徑與Git歷史仍需Owner另外審查，本輪未改寫。

## 4. 精確暫存與人工審查

```powershell
# 僅在Owner確認上述清單與差異後手動執行；不要使用 git add .
git -C $work add -- $files
git -C $work diff --cached --name-status
git -C $work diff --cached --stat
git -C $work diff --cached --check
```

提交前在同一套已安裝依賴的Python環境執行：

```powershell
Push-Location $work
python -X utf8 -B -m unittest discover -s 03_Code/tests -v
python -X utf8 -B 03_Code/check_cpu_sensor.py
Pop-Location
```

本任務到此交付可審查資料。**不提供已執行commit或push的假象**；請Owner處理授權、版本字串與實機驗收決策後，再另行決定提交、推送、標籤及Release。可考慮的commit主旨：`Prepare local-model workstation source and release documentation`。

## 已保留的ZIP

原桌面AI_Director_GitHub_20261118.zip保留未改；它仍是本次README改版前的快照，不要把它當成已更新的正式Release。檔案名含DRAFT的新候選包也不是已發布版本，須審核後再重建／命名。
