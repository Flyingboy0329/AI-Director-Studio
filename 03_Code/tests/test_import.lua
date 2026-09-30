-- test_import.lua
local resolve = Resolve()
if not resolve then print("❌ 未能獲取 Resolve 物件"); return end
local pm = resolve:GetProjectManager()
local proj = pm:GetCurrentProject()
if not proj then print("❌ 未開啟專案"); return end
local timeline = proj:GetCurrentTimeline()
if not timeline then print("❌ 未開啟時間軸"); return end
local task_file = debug.getinfo(1, "s"):match("@?(.*/)")
if task_file then task_file = task_file:gsub("/$", "") .. "/../../05_Output/reports/davinci_markers.edl" else task_file = "../../05_Output/reports/davinci_markers.edl" end
local success = timeline:ImportIntoTimeline(task_file)
if success then print("✅ Lua 成功自動注入 Shot Region 標記！") else print("⚠️ 調用 ImportIntoTimeline 失敗") end
