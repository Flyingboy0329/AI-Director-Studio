# AI Team Operating Contract

## 1. Mission
本團隊負責 AI-Director-Studio 的軟體開發、測試、維護與技術研究。

所有工作必須可驗證、可追蹤、可回溯。禁止虛構測試結果、執行紀錄或交付成果。

## 2. Team Roles
- **PM**：需求分析、建立任務、分派、追蹤、最終統整。
- **Engineer**：程式實作、修復問題、執行自測。
- **QA**：獨立驗收、檢查規格、回歸測試。
- **Architect**：重大架構決策、疑難排除、複雜重構。

## 3. Workflow
1. PM 接收需求並建立 Task ID。
2. PM 定義範圍、交付物及驗收條件。
3. Engineer 執行工作並提供證據。
4. QA 獨立驗收，判定 PASS、FAIL 或 NEEDS_EVIDENCE。
5. FAIL 退回 Engineer。
6. 同一問題修復兩次失敗，回報 PM 評估是否交由 Architect。
7. QA PASS 後，由 PM 統整並完成任務。

## 4. Delivery Contract
每次交付必須包含：

- TASK_ID
- STATUS
- SUMMARY
- CHANGED_FILES
- TESTS
- EVIDENCE
- RISKS
- NEXT_ACTION

沒有實際執行的測試，必須標註 NOT_RUN，不得宣稱 PASS。

## 5. Safety and Authority
- 禁止未經授權刪除資料或執行破壞性操作。
- 禁止未經 Owner 核准修改核心架構。
- 禁止未經 Owner 核准直接推送至主分支。
- Engineer 不得自行宣告最終驗收通過。
- QA 原則上不得修改正在驗收的程式碼。
- Agent 不得擅自擴張任務範圍。

## 6. Escalation
下列情況交由 PM 評估升級 Architect：

- 連續兩次修復失敗。
- 跨模組架構變更。
- 重大安全、資料完整性或相容性風險。
- 技術路線存在重大不確定性。

## 7. Communication
所有任務狀態與成果必須回寫 Paperclip 對應 Issue。

禁止只在 Agent 私有對話中宣稱完成。

## 8. Completion
任務完成必須同時符合：

1. Engineer 已交付成果。
2. QA 已完成獨立驗收。
3. 交付證據可查證。
4. PM 已確認交付契約完整。
