import ctypes,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.submission import submit_markers
from pipeline.director_decision import score_to_rpg_tier

class OnceTests(unittest.TestCase):
    def test_blue_yellow_use_circles_with_explicit_emoji_presentation(self):
        blue,label=score_to_rpg_tier(50)
        self.assertEqual(blue,'Blue')
        self.assertIn('\U0001f535\ufe0f',label)
        self.assertIn('藍',label)
        self.assertNotIn('🔹',label)
        yellow,label=score_to_rpg_tier(90)
        self.assertEqual(yellow,'Yellow')
        self.assertIn('\U0001f7e1\ufe0f',label)
        self.assertIn('黃',label)
        self.assertNotIn('⭐',label)

    def test_equal_five_tiers(self):
        for score,color in [(0,'Cream'),(19.99,'Cream'),(20,'Green'),(39.99,'Green'),(40,'Blue'),(59.99,'Blue'),(60,'Purple'),(70,'Purple'),(79.99,'Purple'),(80,'Yellow'),(100,'Yellow')]:
            self.assertEqual(score_to_rpg_tier(score)[0],color)

    def test_interrupted_or_malformed_claim_never_resends(self):
        for contents in ('', '{"status":"submission_started"}'):
            with tempfile.TemporaryDirectory() as tmp:
                task=Path(tmp)/'task.lua';task.touch()
                (task.parent/'resolve_submission.json').write_text(contents)
                send=Mock()
                self.assertFalse(submit_markers(task,send));send.assert_not_called()

    def test_exception_and_confirmed_are_both_not_repeated(self):
        for response in ('exception','success'):
            with tempfile.TemporaryDirectory() as tmp:
                task=Path(tmp)/'task.lua';task.touch()
                send=Mock(side_effect=RuntimeError('timeout')) if response=='exception' else Mock(return_value=(True,'ok'))
                self.assertEqual(submit_markers(task,send),response=='success')
                self.assertEqual(submit_markers(task,send),response=='success')
                send.assert_called_once()

    def test_lua_without_io_clipboard_ack_and_duplicate_guard(self):
        dll=Path(os.environ.get('PROGRAMFILES',''))/'Blackmagic Design/DaVinci Resolve/lua5.1.dll'
        if not dll.exists():self.skipTest('Installed Lua 5.1 runtime unavailable')
        lua=ctypes.CDLL(str(dll))
        lua.luaL_newstate.restype=ctypes.c_void_p
        lua.luaL_openlibs.argtypes=[ctypes.c_void_p]
        lua.luaL_loadstring.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
        lua.lua_pcall.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int]
        lua.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p]
        lua.lua_tolstring.restype=ctypes.c_char_p
        lua.lua_getfield.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_char_p]
        lua.lua_toboolean.argtypes=[ctypes.c_void_p,ctypes.c_int]
        lua.lua_close.argtypes=[ctypes.c_void_p]
        injector=(Path(__file__).resolve().parents[2]/'resolve_lua/davinci_marker_injector.lua').read_text(encoding='utf-8-sig')
        script='''
local task={video_clip_name='sample.mp4',total_frames=272,video_markers={}}
for i=0,44 do task.video_markers[#task.video_markers+1]={start_frame=i*6,duration_frames=6,color='Purple',name='Grade',note='Advice'} end
task.video_markers[45].duration_frames=8
local writes=0
local markers={[999]={note='[human note]',name='personal',duration=1}}
local clip={GetName=function() return 'sample.mp4' end,GetMarkers=function() return markers end,
GetClipProperty=function(self,key) return '271' end,
DeleteMarkerAtFrame=function(self,frame) markers[frame]=nil end,
AddMarker=function(self,frame,color,name,note,duration,custom) if frame+duration>271 then return false end; writes=writes+1;markers[frame]={color=color,name=name,note=note,duration=duration,customData=custom};return true end}
local folder={GetClipList=function()return {clip}end,GetSubFolderList=function()return {}end}
local pool={GetRootFolder=function()return folder end}
local project={GetMediaPool=function()return pool end}
local pm={GetCurrentProject=function()return project end}
local packet=''
local fusion={SetClipboard=function(self,value) packet=value;return true end}
resolve={GetProjectManager=function()return pm end,Fusion=function()return fusion end}
loadfile=function()return function()return task end end
io=nil;bmd={};AI_DIRECTOR_TASK_PATH='unique-task.lua';AI_DIRECTOR_RECEIPT_TOKEN='first'
local function inject()
'''+injector+'''
end
inject()
assert(writes==45,'expected 45 writes')
assert(packet:find('AI_DIRECTOR_RECEIPT:first:',1,true)==1,'missing token')
assert(packet:find('"written":45',1,true),'wrong count')
assert(packet:find('"coverage_ok":true',1,true),'coverage not confirmed')
assert(markers[264].duration==7,'tail remainder was not clamped to Resolve boundary')
assert(packet:find('"last_end_frame":271',1,true),'tail receipt missing')
AI_DIRECTOR_RECEIPT_TOKEN='second';inject()
assert(writes==45,'duplicate import')
assert(packet:find('AI_DIRECTOR_RECEIPT:second:',1,true)==1,'cached receipt missing')
assert(markers[999],'human marker deleted')
NATIVE_AVAILABLE=pcall(require,'ffi')
'''
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        receipt = Path(temporary.name) / '回執.json'
        script = script.replace('local writes=0', 'task.result_path=' + json.dumps(receipt.as_posix(),ensure_ascii=False) + '\nlocal writes=0')
        comparison=(Path(__file__).resolve().parents[2]/'resolve_lua/grade_circle_comparison.lua').read_text(encoding='utf-8-sig')
        script += '''
local preview_count=0
local preview_timeline={GetStartFrame=function()return 1000 end,GetEndFrame=function()return 1271 end,
AddMarker=function(self,frame,color,name,note,duration,custom)
    assert(frame>=0 and frame+duration<=271,'preview out of range')
    assert(custom=='AI_DIRECTOR_COLOR_PREVIEW')
    preview_count=preview_count+1;return true
end}
clip.GetClipProperty=function(self,key)if key then return '271' end;return {Frames='271',['File Path']='sample.mp4'} end
pool.GetCurrentFolder=function()return folder end
pool.CreateTimelineFromClips=function(self,name,clips)assert(clips[1]==clip);return preview_timeline end
project.GetTimelineCount=function()return 1 end
project.SetCurrentTimeline=function(self,timeline)assert(timeline==preview_timeline);return true end
local function preview()
'''+comparison+'''
end
preview()
assert(preview_count==12,'missing circle comparison cases')
assert(writes==45,'preview modified source markers')
-- Emulate Python deleting the job before Resolve executes the inline payload.
AI_DIRECTOR_TASK_PATH='deleted-job/marker_task.lua'
AI_DIRECTOR_TASK_DATA=assert(loadstring([[local t={video_clip_name='sample.mp4',total_frames=272,video_markers={}};
for i=0,44 do t.video_markers[#t.video_markers+1]={start_frame=i*6,duration_frames=6,color='Purple',name='Grade',note='Advice'} end;
t.video_markers[45].duration_frames=8;return t]]))()
AI_DIRECTOR_NO_RECEIPT=true
local previous_packet=packet
loadfile=function()error('must not read deleted job')end
inject()
assert(writes==90,'inline task did not run without job file')
assert(packet==previous_packet,'receipt unexpectedly emitted for inline dispatch')
assert(AI_DIRECTOR_TASK_DATA==nil and AI_DIRECTOR_NO_RECEIPT==nil,'inline globals leaked')
'''
        state=lua.luaL_newstate()
        try:
            lua.luaL_openlibs(state)
            code=lua.luaL_loadstring(state,script.encode('utf-8'))
            if code==0:code=lua.lua_pcall(state,0,0,0)
            self.assertEqual(code,0,lua.lua_tolstring(state,-1,None))
            lua.lua_getfield(state,-10002,b'NATIVE_AVAILABLE')
            native_available=bool(lua.lua_toboolean(state,-1))
            if native_available:
                self.assertEqual(json.loads(receipt.read_text(encoding='utf-8'))['last_end_frame'],271)
            print('Native Lua FFI receipt tested:',native_available)
        finally:lua.lua_close(state)

if __name__=='__main__':unittest.main()
