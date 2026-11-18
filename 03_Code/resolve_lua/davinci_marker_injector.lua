-- DaVinci Resolve Marker Injector
local result_override = AI_DIRECTOR_RESULT_PATH
AI_DIRECTOR_RESULT_PATH = nil
local receipt_token = AI_DIRECTOR_RECEIPT_TOKEN
AI_DIRECTOR_RECEIPT_TOKEN = nil
local inline_task = AI_DIRECTOR_TASK_DATA
AI_DIRECTOR_TASK_DATA = nil
local no_receipt = AI_DIRECTOR_NO_RECEIPT
AI_DIRECTOR_NO_RECEIPT = nil
local resolveApp = resolve or (bmd and bmd.scriptapp and bmd.scriptapp("Resolve"))
if not resolveApp then
    print("❌ 無法取得 Resolve 物件，請確保 Resolve 處於運行狀態")
    return
end

local projectManager = resolveApp:GetProjectManager()
local project = projectManager:GetCurrentProject()
if not project then
    print("❌ 找不到目前開啟的 Project，請先進入專案剪輯頁面！")
    return
end

local mediaPool = project:GetMediaPool()
local rootFolder = mediaPool:GetRootFolder()

local task_file = AI_DIRECTOR_TASK_PATH
if not task_file or task_file == "" then
    task_file = "05_Output/test_marker_task.lua"
end

local task = inline_task
if not task then
    local f, err = loadfile(task_file)
    if not f then
        print("❌ 無法載入任務檔: " .. tostring(err))
        return
    end
    task = f()
end
if result_override then task.result_path = result_override end
local function native_receipt(path, text)
    -- Resolve's LuaJIT may retain FFI even when io/bmd.writefile are omitted.
    -- Write only the generated task receipt, without a shell or external process.
    local ok, result = pcall(function()
        local ffi = require("ffi")
        ffi.cdef[[
            int MultiByteToWideChar(unsigned int, unsigned long, const char *, int, unsigned short *, int);
            void *CreateFileW(const unsigned short *, unsigned long, unsigned long, void *, unsigned long, unsigned long, void *);
            int WriteFile(void *, const char *, unsigned long, unsigned long *, void *);
            int CloseHandle(void *);
        ]]
        local kernel = ffi.load("kernel32")
        local length = kernel.MultiByteToWideChar(65001, 0, path, #path, nil, 0)
        if length <= 0 then return false end
        local wide = ffi.new("unsigned short[?]", length + 1)
        if kernel.MultiByteToWideChar(65001, 0, path, #path, wide, length) ~= length then return false end
        local handle = kernel.CreateFileW(wide, 1073741824, 1, nil, 2, 128, nil)
        if handle == ffi.cast("void *", -1) then return false end
        local written = ffi.new("unsigned long[1]")
        local success = kernel.WriteFile(handle, text, #text, written, nil) ~= 0 and tonumber(written[0]) == #text
        kernel.CloseHandle(handle)
        return success
    end)
    return ok and result == true
end
local function publish_result(result)
    if no_receipt then return end
    local json = string.format('{"expected":%d,"written":%d,"coverage_ok":%s}',
        result.expected, result.written, tostring(result.coverage_ok))
    if result.clip_frames then
        json = string.sub(json, 1, -2) .. string.format(',"planned_frames":%d,"clip_frames":%d,"last_end_frame":%d}',
            task.total_frames, result.clip_frames, result.last_end_frame)
    end
    local saved = false
    if task.result_path then
        if bmd and bmd.writefile then
            local ok, value = pcall(bmd.writefile, task.result_path, result)
            saved = ok and value ~= false
        end
        if not saved and io and io.open then
            saved = pcall(function()
                local receipt, err = io.open(task.result_path, "w")
                if not receipt then error(err) end
                receipt:write(json)
                receipt:close()
            end)
        end
        if not saved then
            saved = native_receipt(task.result_path, json)
        end
    end
    -- Documented Fusion clipboard API also works without Lua's io library.
    -- A per-submission token prevents an old/unrelated clipboard from confirming.
    if receipt_token then
        local ok, value = pcall(function()
            local host = resolveApp:Fusion()
            return host:SetClipboard("AI_DIRECTOR_RECEIPT:" .. receipt_token .. ":" .. json)
        end)
        saved = saved or (ok and value ~= false)
    end
    if not saved then
        print("⚠️ 回執通道不可用（檔案／Fusion 剪貼簿）；保留結果，不要再次導入。")
    end
end

AI_DIRECTOR_SUBMISSIONS = AI_DIRECTOR_SUBMISSIONS or {}
local cached = AI_DIRECTOR_SUBMISSIONS[task_file]
if cached then
    print("ℹ️ 此任務已執行過，跳過重複導入。")
    publish_result(cached)
    return
end
AI_DIRECTOR_SUBMISSIONS[task_file] = { expected = #(task.video_markers or {}), written = 0, coverage_ok = false }
print("🔍 成功載入任務母帶: " .. tostring(task.video_clip_name))

local function clean_ai_markers(item)
    local markers = item:GetMarkers()
    if markers then
        for frame, m in pairs(markers) do
            local note = m.note or ""
            local owned = string.sub(m.customData or "", 1, 12) == "AI_DIRECTOR:"
            local legacy = string.find(note, "評分:", 1, true) and string.find(note, "【", 1, true)
            if owned or legacy then
                item:DeleteMarkerAtFrame(frame)
            end
        end
    end
end

local function find_clip_by_name(folder, target_name)
    local base_target = string.gsub(target_name, "%..*$", "")
    local clips = folder:GetClipList()
    for _, clip in ipairs(clips) do
        local cname = clip:GetName()
        -- 嚴格比對，排除暫存檔 _video.mp4
        if string.find(cname, target_name, 1, true) or (string.find(cname, base_target, 1, true) and not string.find(cname, "_video")) then
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

local v_clip = find_clip_by_name(rootFolder, task.video_clip_name)
if not v_clip and task.video_file_path then
    print("📥 媒體池未發現母帶，正在自動匯入原檔: " .. task.video_file_path)
    local imported_clips = mediaPool:ImportMedia({ task.video_file_path })
    if imported_clips and #imported_clips > 0 then
        v_clip = imported_clips[1]
        print("✅ 原始母帶已帶入 Media Pool (自帶音訊軌)！")
    else
        v_clip = find_clip_by_name(rootFolder, task.video_clip_name)
    end
end

local v_count = 0
local coverage_ok = true
local cursor = 0
local clip_frames = task.total_frames
if v_clip then
    local ok, frames = pcall(function() return tonumber(v_clip:GetClipProperty("Frames")) end)
    if ok and frames and frames > 0 and frames == math.floor(frames) then
        clip_frames = frames
    end
    if clip_frames ~= task.total_frames then
        print(string.format("⚠️ 影格數差異：分析=%d，Resolve=%d；尾段以 Resolve 實際邊界裁切，不丟棄餘數。", task.total_frames, clip_frames))
    end
    clean_ai_markers(v_clip)
    for _, m in ipairs(task.video_markers or {}) do
        local duration = math.min(m.duration_frames, clip_frames - m.start_frame)
        if m.start_frame ~= cursor or duration <= 0 then coverage_ok = false end
        cursor = m.start_frame + math.max(0, duration)
        local added = false
        if duration > 0 then
            added = v_clip:AddMarker(m.start_frame, m.color, m.name, m.note, duration, "AI_DIRECTOR:" .. task_file)
        end
        local actual = (v_clip:GetMarkers() or {})[m.start_frame]
        if added and actual and tonumber(actual.duration) == duration
                and actual.name == m.name and actual.note == m.note and actual.color == m.color then
            v_count = v_count + 1
        else
            coverage_ok = false
            print("❌ 標記寫入或回讀失敗，影格: " .. tostring(m.start_frame))
        end
    end
    print(string.format("=== [AI Director 寫入結果] 母帶 [%s] 標記回讀 %d 筆 ===", tostring(task.video_clip_name), v_count))
else
    coverage_ok = false
    print("❌ 依然找不到且無法匯入素材母帶: " .. tostring(task.video_clip_name))
end
coverage_ok = coverage_ok and cursor == clip_frames and v_count == #(task.video_markers or {})
print(string.format("[尾段回讀] 最後結束格=%d，Resolve 總格=%d，完整覆蓋=%s", cursor, clip_frames, tostring(coverage_ok)))
local result = { expected = #(task.video_markers or {}), written = v_count, coverage_ok = coverage_ok,
    clip_frames = clip_frames, last_end_frame = cursor }
AI_DIRECTOR_SUBMISSIONS[task_file] = result
publish_result(result)
