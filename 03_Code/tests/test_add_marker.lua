-- test_add_marker.lua
local resolve = Resolve()
if not resolve then return end
local pm = resolve:GetProjectManager()
if not pm then return end
local proj = pm:GetCurrentProject()
if not proj then return end
local tl = proj:GetCurrentTimeline()
if not tl then return end
tl:AddMarker(0, "Yellow", "AI DIRECTOR TEST", "Lua AddMarker Canary Test", 60)
resolve:DoModal("Resolve", "Marker Injected!", false)
