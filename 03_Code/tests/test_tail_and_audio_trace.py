import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frame_windows import frame_windows
from ai.audio_analyzer import analyze_audio, WhisperRuntime


class TailAndAudioTests(unittest.TestCase):
    def test_resident_transcription_keeps_weights_and_persists_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav=Path(tmp)/'input.wav';wav.touch();output=Path(tmp)/'audio.json'
            runtime=WhisperRuntime();model=Mock()
            model.transcribe.return_value=(iter([]),SimpleNamespace(language='zh',language_probability=.96))
            metadata=dict(selected_model='small',resolved_model='cache',source='hub_cache',
                          device='cpu',device_index=0,compute_type='int8')
            with patch('ai.audio_analyzer.load_audio_model',return_value=(model,metadata)) as loader:
                runtime.ensure_ready(None,lambda _:None)
                analyze_audio(wav,output,runtime=runtime)
                loader.assert_called_once()
            model.model.unload_model.assert_not_called()
            self.assertIs(runtime.model,model)
            audit=json.loads(output.with_suffix('.metadata.json').read_text(encoding='utf-8'))
            self.assertEqual(audit['lifecycle'],'session-resident')
            self.assertEqual(audit['selected_model'],'small')
            self.assertEqual(audit['status'],'complete')
            runtime.unload(lambda _:None)

    def test_remainder_exact_multiple_short_clip_and_fractional_fps(self):
        for total, fps in ((2221, 30.00837694448698), (181, 30), (1, 30),
                           (360, 30), (217, 30000/1001)):
            intervals = frame_windows(total, fps)
            self.assertEqual(intervals[0][0], 0)
            self.assertEqual(intervals[-1][1], total)
            self.assertEqual(sum(end-start for start, end in intervals), total)
            self.assertTrue(all(a[1] == b[0] for a,b in zip(intervals,intervals[1:])))
        self.assertEqual(frame_windows(181, 30), [(0,180),(180,181)])
        self.assertEqual(frame_windows(360, 30), [(0,180),(180,360)])
        self.assertEqual(frame_windows(2221,30.00837694448698)[-1], (2161,2221))

    def test_whisper_ready_and_complete_have_audit_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); wav=root/'input.wav';wav.touch();output=root/'audio.json'
            seen=[]
            class Model:
                def __init__(self,path,**kwargs):
                    from unittest.mock import Mock
                    self.model=Mock()
                    audit=json.loads(output.with_suffix('.metadata.json').read_text(encoding='utf-8'))
                    self_outer.assertEqual(audit['status'],'loading')
                    seen.append((path,kwargs))
                def transcribe(self,*args,**kwargs):
                    segment=SimpleNamespace(start=0,end=1,text='hello',no_speech_prob=0.1,avg_logprob=-0.2,compression_ratio=1.)
                    return iter([segment]),SimpleNamespace(language='zh',language_probability=.96)
            self_outer=self
            logs=io.StringIO()
            with patch('ai.audio_analyzer.select_audio_device',return_value=('cuda','float16','medium',0,7)), \
                 patch('ai.audio_analyzer.resolve_whisper_model',return_value=('cached-model','project_local')) as download, \
                 patch('ai.audio_analyzer.WhisperModel',Model),redirect_stdout(logs):
                result=analyze_audio(wav,output,model_name='medium')
            audit=json.loads(output.with_suffix('.metadata.json').read_text(encoding='utf-8'))
            self.assertEqual((audit['status'],audit['source'],audit['segments']),('complete','project_local',1))
            self.assertEqual(audit['selected_model'],'medium')
            self.assertEqual(audit['device_index'],0)
            self.assertEqual(audit['release_status'],'unloaded')
            self.assertIn('UNLOADED',logs.getvalue())
            self.assertEqual(seen[0][0],'cached-model')
            self.assertEqual(len(result),1)
            self.assertIn('READY',logs.getvalue())
            self.assertIn('complete',logs.getvalue())
            self.assertEqual(download.call_args.args[0],'medium')

    def test_whisper_loading_failure_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wav=root/'in.wav';wav.touch();output=root/'audio.json'
            with patch('ai.audio_analyzer.select_audio_device',return_value=('cpu','int8','small',0,8)), \
                 patch('ai.audio_analyzer.resolve_whisper_model',return_value=('cache','project_local')), \
                 patch('ai.audio_analyzer.WhisperModel',side_effect=RuntimeError('load failed')):
                with self.assertRaises(RuntimeError):analyze_audio(wav,output)
            audit=json.loads(output.with_suffix('.metadata.json').read_text(encoding='utf-8'))
            self.assertEqual(audit['status'],'failed')
            self.assertEqual(audit['error_type'],'RuntimeError')
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
