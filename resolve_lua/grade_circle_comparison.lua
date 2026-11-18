-- Run manually in the Resolve Lua console. No models, imports or file writes.
-- Adds a NEW test timeline using an existing video; never changes source markers.
local app = resolve or (bmd and bmd.scriptapp and bmd.scriptapp("Resolve"))
local project = app and app:GetProjectManager():GetCurrentProject()
if not project then print("請先開啟 Resolve 專案。") return end
local pool = project:GetMediaPool()
local folder = pool:GetCurrentFolder()
local source = nil
for _, clip in ipairs(folder:GetClipList() or {}) do
    local props = clip:GetClipProperty() or {}
    if (tonumber(props.Frames) or 0) > 0 and (props["File Path"] or "") ~= "" then
        source = clip
        break
    end
end
if not source then print("目前媒體資料夾沒有可用影片；請切到含影片的資料夾再執行。") return end

-- Default / VS16 emoji / VS15 text presentation retain the circle character.
-- Sky/Cyan/Lemon change ONLY Resolve's native marker, not the emoji's RGB.
local cases = {
    {"B1 原始藍球", "Blue", "🔵"},
    {"B2 藍球 Emoji（正式候選）", "Blue", "🔵️"},
    {"B3 藍球 Text（可能單色）", "Blue", "🔵︎"},
    {"B4 天藍原生標記", "Sky", "🔵️"},
    {"B5 青藍原生標記", "Cyan", "🔵️"},
    {"Y1 原始黃球", "Yellow", "🟡"},
    {"Y2 黃球 Emoji（正式候選）", "Yellow", "🟡️"},
    {"Y3 黃球 Text（可能單色）", "Yellow", "🟡︎"},
    {"Y4 淺黃原生標記", "Lemon", "🟡️"},
    {"R1 白灰參考", "Cream", "⚪"},
    {"R2 綠色參考", "Green", "🟢"},
    {"R3 紫色參考", "Purple", "🟣"},
}
local name = "AI_Director_色球對照_" .. tostring(project:GetTimelineCount() + 1)
local timeline = pool:CreateTimelineFromClips(name, {source})
if not timeline then print("無法建立測試時間軸；既有素材標記未修改。") return end
local frames = timeline:GetEndFrame() - timeline:GetStartFrame()
local step = math.floor(frames / (#cases + 1))
if step < 1 then print("測試時間軸太短，無法排列全部候選；未新增標記。") return end
local count = 0
for index, case in ipairs(cases) do
    local added = timeline:AddMarker(index * step, case[2], case[3] .. " " .. case[1],
        "請分別檢查灰底與黑底提示框：色球是否同色、是否仍為圓形。原生標記色=" .. case[2],
        math.max(1, math.floor(step * 0.8)), "AI_DIRECTOR_COLOR_PREVIEW")
    if added then count = count + 1 else print("候選未新增：" .. case[1] .. " / " .. case[2]) end
end
project:SetCurrentTimeline(timeline)
print("色球對照已建立：" .. name .. "，" .. count .. "/" .. #cases .. " 筆。")
print("只新增測試時間軸與時間軸標記；原始素材標記與既有時間軸未修改。")
print("請比較 B1/B2/B3 與 Y1/Y2/Y3 在兩種提示框的顏色；B4/B5/Y4 只比較原生標記色。")
