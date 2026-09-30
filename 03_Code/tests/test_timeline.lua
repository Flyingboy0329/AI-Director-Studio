-- test_timeline.lua
local resolve = Resolve()
if not resolve then return end
local pm = resolve:GetProjectManager()
local proj = pm:GetCurrentProject()
if not proj then return end
local tl = proj:GetCurrentTimeline()
if tl then resolve:OpenPage("edit") else resolve:OpenPage("media") end
