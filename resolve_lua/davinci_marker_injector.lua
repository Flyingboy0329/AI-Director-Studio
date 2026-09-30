-- resolve_lua/davinci_marker_injector.lua
-- 【全域覆蓋版本 v3.0】
-- 標準實作：使用 Resolve API 取得專案、絕對路徑載入任務檔、遞迴搜尋素材
-- 兼容 Resolve 沙盒環境 (無 io 函式庫依賴)

local function main()
    -- 1. 取得 Resolve 與專案環境
    local res = resolve or Resolve()
    local project = res:GetProjectManager():GetCurrentProject()
    local root = project:GetMediaPool():GetRootFolder()

    -- 2. 載入任務檔 (絕對路徑)
    local task_path = "C:/Users/pan/Desktop/AI_Director/05_Output/test_marker_task.lua"
    local task = dofile(task_path)
    if not task or task.schema_version ~= 2 then
        print("❌ 任務檔格式不符或讀取失敗")
        return
    end

    -- 3. 遞迴搜尋素材函式
    local function find_clip(folder, target_name)
        local lower_target = string.lower(target_name)
        -- 搜尋當前資料夾
        for _, clip in ipairs(folder:GetClipList() or {}) do
            if string.find(string.lower(clip:GetName()), lower_target, 1, true) then
                return clip
            end
        end
        -- 遞迴搜尋子資料夾
        for _, sub in ipairs(folder:GetSubFolderList() or {}) do
            local c = find_clip(sub, target_name)
            if c then return c end
        end
        return nil
    end

    -- 4. 尋找目標素材
    local v_clip = find_clip(root, task.video_clip_name)
    local a_clip = find_clip(root, task.audio_clip_name)

    local v_count, a_count = 0, 0

    -- 5. 注入視訊標記
    if v_clip then
        for _, m in ipairs(task.video_markers or {}) do
            -- AddMarker(time, color, name, note, duration)
            if v_clip:AddMarker(m.start_frame, m.color, m.name, m.note, m.duration_frames) then
                v_count = v_count + 1
            end
        end
    end

    -- 6. 注入音訊標記
    if a_clip then
        for _, m in ipairs(task.audio_markers or {}) do
            -- AddMarker(time, color, name, note, duration)
            if a_clip:AddMarker(m.start_frame, m.color, m.name, m.note, m.duration_frames) then
                a_count = a_count + 1
            end
        end
    end

    -- 7. 結算回報
    print(string.format("=== 完成：視訊寫入 %d 筆，音訊寫入 %d 筆 ===", v_count, a_count))
end

main()
