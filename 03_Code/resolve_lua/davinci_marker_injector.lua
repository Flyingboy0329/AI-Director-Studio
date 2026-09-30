-- DaVinci Resolve Marker Injector (支援自動匯入素材版)
local resolveApp = resolve or (bmd and bmd.scriptapp and bmd.scriptapp("Resolve"))
if not resolveApp then
    print("❌ 無法取得 Resolve 物件")
    return
end

local projectManager = resolveApp:GetProjectManager()
local project = projectManager:GetCurrentProject()
local mediaPool = project:GetMediaPool()
local rootFolder = mediaPool:GetRootFolder()

local task_path = "C:/Users/pan/Desktop/AI_Director/05_Output/test_marker_task.lua"
local f = loadfile(task_path)
if not f then
    print("❌ 無法載入任務檔: " .. task_path)
    return
end
local task = f()

local function clean_ai_markers(item)
    local markers = item:GetMarkers()
    if markers then
        for frame, m in pairs(markers) do
            local note = m.note or ""
            if string.find(note, "%[AI%-V%]") or string.find(note, "%[AI%-A%]") or string.find(note, "%[AI%-DIRECTOR%]") then
                item:DeleteMarkerAtFrame(frame)
            end
        end
    end
end

local function find_clip_by_name(folder, target_name)
    local clips = folder:GetClipList()
    for _, clip in ipairs(clips) do
        local cname = clip:GetName()
        if string.find(cname, target_name, 1, true) then
            return clip
        end
    end
    local subfolders = folder:GetSubFolderList()
    for _, sub in ipairs(subfolders) do
        local found = find_clip_by_name(sub, target_name)
        if found then return found end
    end
    return nil
end

-- 尋找素材；若媒體池沒有，自動從實體檔案匯入！
local v_clip = find_clip_by_name(rootFolder, task.video_clip_name)
if not v_clip and task.video_file_path then
    print("📥 媒體池未發現素材，正在自動從實體路徑匯入: " .. task.video_file_path)
    local imported_clips = mediaPool:ImportMedia({ task.video_file_path })
    if imported_clips and #imported_clips > 0 then
        v_clip = imported_clips[1]
        print("✅ 素材已自動匯入 Media Pool！")
    else
        -- 二次搜尋防呆
        v_clip = find_clip_by_name(rootFolder, task.video_clip_name)
    end
end

local v_count = 0
if v_clip then
    clean_ai_markers(v_clip)
    for _, m in ipairs(task.video_markers) do
        v_clip:AddMarker(m.start_frame, m.color, m.name, m.note, m.duration_frames)
        v_count = v_count + 1
    end
    print(string.format("=== [P1 實測成功] 素材 [%s] 標記寫入 %d 筆 ===", task.video_clip_name, v_count))
else
    print("❌ 依然找不到且無法匯入素材: " .. tostring(task.video_clip_name))
end