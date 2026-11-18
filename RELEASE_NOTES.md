# Release notes — v1.1.0-rc.1（草稿）

狀態：**DRAFT / NEEDS_OWNER_REVIEW**。建議標籤尚未建立；不是已發布版本。比較基準：origin/main `9f9f1a741786adb420000167cec1a09641be4a94`；既有發行標籤 v1.0.0 指向 `469a9136ee2a0e281b2ab9f2787a63825df1249e`。發布日期待 Owner 核准。

## 版本定位

從舊版技術特徵／語音流程，整理成可選本機視覺模型、逐字稿與剪輯建議的工作臺。**AI recommends, human decides.** 本輪僅整理發布文件、忽略規則、封裝白名單及差異報告，沒有新增產品功能或修改推論架構。

## 本機現有、建議納入新版的功能

- 方案A：獨立VLM＋LLM＋Faster-whisper；CPU語音與視覺觀察並行，完成後整合。
- 方案B：原生多模態主模型＋相容mmproj＋Faster-whisper；語音與技術分析並行，資料齊備後才做畫面理解與整合。
- GGUF／投影選擇、READY檢查、Context 4K–32K及AI影格頻率0.25–4張／秒。
- 偵測GPU可用顯存與動態分層；雙CUDA卡副卡90%為估算目標，非占用保證。
- 有限CPU／RAM備選；自管GPU啟動的可辨識顯存錯誤只按角色重試一次。
- Whisper CPU／INT8、RAM規劃與載入日誌；專案內完整模型離線重用、缺檔續傳與下載鎖。
- 4–48GB靜態硬體配置指南，按架構與參數規模描述，全部為Estimated／Experimental候選。
- Windows Lua橋接、Media Pool素材Marker、尾段覆蓋、一次提交及送出後job清理。
- 正式小型Windows啟動器、簡約工作臺、CPU感測DLL／授權／SHA256及診斷入口。

## 此次文件準備

- 重寫README：產品定位、兩種架構、快速開始、硬體、Marker語義、生命週期與證據範圍。
- 舊Repository連結改為AI-Director-Studio；不用舊名稱的自動重新導向。
- 更新.gitignore，防止模型、素材、環境、個人設定、測試／建置產物誤加；保留必要公開感測DLL與授權。
- 修正來源包白名單，保留新版README封面、Release草稿與公開審查文件，避免封裝後相對連結失效；另補2項封裝回歸測試。
- 建議上傳／排除／已追蹤生成檔停止追蹤清單，並提供Owner手動Git步驟。未執行暫存、提交、推送、合併或Release建立。

## 升級與保存注意

1. 更新前先停止監看並卸除舊模型；不將其它電腦的.local帶入新版。
2. 保留原影片、模型、歷史任務與工作證據。git rm --cached僅是Owner未來可選的索引清理，不等於刪本機資料，也不清除Git歷史。
3. Whisper權重不附在來源包；本機完整時不下載，刪除／損壞／換大小或下載中斷仍可能需要補齊。
4. Lua submitted只是已送出；Marker實際寫入仍要在Resolve核對。成功送出job會清理，逐字稿／metadata不永久保存。
5. Stop Sentinel保留模型，卸除由模型區管理。GGUF背景服務與程式內Whisper的生命週期不同。

## 發行前仍需Owner確認

- 建議先用v1.1.0-rc.1，完成實機驗收後再考慮v1.1.0；GUI目前仍顯示v1.0，沒有集中版本來源。
- 應用程式尚無根目錄LICENSE；確認PyQt6 GPLv3／商業方案與第三方授權，不擅自套用MIT或其它授權。
- 確認CUDA引擎資產／驅動、舊顯卡、全新環境安裝，以及完整PyInstaller建置。小型啟動器不是含Python的獨立包。
- 以短片完成實際模型／Resolve寫入、取消／卸除與管理員CPU讀溫驗收。當前單元／模擬測試不取代這些證據。
- 對遠端現有快取、生成任務、舊runtime及歷史個人路徑做Owner審查；未自行改寫歷史。

完整差異、敏感掃描、測試與NOT_RUN清單見 [發布準備報告](docs/release/RELEASE_PREPARATION_REPORT.md)。
