import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as pipeline
from ai.semantic_analyzer import prepare_visual_observations, analyze_semantics


class ParallelMediaTests(unittest.TestCase):
    def test_both_schemes_overlap_and_wait_before_director(self):
        for separate in (False, True):
            with self.subTest(separate=separate), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); source=root/'clip.mp4';source.touch()
                audio_started=threading.Event();visual_started=threading.Event();audio_done=threading.Event()
                observation_done=threading.Event()
                settings={'llm_path':'llm.gguf','model_mode':'separate' if separate else 'llm_only'}
                if separate:settings.update(vlm_path='vlm.gguf',mmproj_path='projection.gguf')
                def audio(*args,**kwargs):
                    audio_started.set()
                    self.assertTrue(visual_started.wait(2))
                    if separate:self.assertTrue(observation_done.wait(2))
                    audio_done.set();return [{'start':0,'end':1,'text':'speech'}]
                def visual(*args,**kwargs):
                    visual_started.set();self.assertTrue(audio_started.wait(2))
                    return {'fps':30,'total_frames':30,'frames':[{'frame_idx':0,'score':50}]}
                cache={0:{'observation':{'visual_summary':'street'},'sent_images':1,'errors':[]}}
                def observations(*args,**kwargs):
                    self.assertFalse(audio_done.is_set());observation_done.set();return cache
                def director(video,vision,transcript,*args,**kwargs):
                    self.assertTrue(audio_done.is_set())
                    self.assertEqual(transcript[0]['text'],'speech')
                    self.assertEqual(kwargs['visual_cache'],cache if separate else None)
                    return {**vision,'semantic_windows':[{}],'degraded_windows':0}
                with patch.object(pipeline,'PROJ_ROOT',root),patch.object(pipeline,'split_media',return_value=('v.mp4','a.wav')), \
                     patch.object(pipeline,'analyze_audio',side_effect=audio),patch.object(pipeline,'analyze_vision',side_effect=visual), \
                     patch.object(pipeline,'prepare_visual_observations',side_effect=observations) as prepare, \
                     patch.object(pipeline,'analyze_semantics',side_effect=director),patch.object(pipeline,'build_markers',return_value='task.lua'), \
                     patch.object(pipeline,'submit_markers',return_value=False):
                    pipeline.run_main_pipeline(source,model_settings=settings)
                    self.assertEqual(prepare.call_count,int(separate))

    def test_audio_failure_never_produces_director_decision_or_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'clip.mp4';source.touch()
            with patch.object(pipeline,'PROJ_ROOT',root),patch.object(pipeline,'split_media',return_value=('v','a')), \
                 patch.object(pipeline,'analyze_audio',side_effect=RuntimeError('ASR failed')), \
                 patch.object(pipeline,'analyze_vision',return_value={'frames':[{}]}), \
                 patch.object(pipeline,'analyze_semantics') as director,patch.object(pipeline,'build_markers') as markers:
                with self.assertRaisesRegex(RuntimeError,'ASR failed'):
                    pipeline.run_main_pipeline(source,model_settings={'llm_path':'llm'})
                director.assert_not_called();markers.assert_not_called()

    def test_prepared_a_observation_is_reused_without_second_vlm_call(self):
        settings={'llm_path':'llm','vlm_path':'vlm','mmproj_path':'proj','model_mode':'separate',
                  'semantic_attempts':1,'semantic_retry_delay':0}
        vision={'fps':30,'total_frames':30,'frames':[{'frame_idx':0,'score':50}]}
        llm=Mock();vlm=Mock();vlm.analyze.return_value={'visual_summary':'street'}
        factory=lambda url,path:vlm if path=='vlm' else llm
        loader=Mock(return_value=[{'type':'image_url','image_url':{'url':'image'}}])
        cache=prepare_visual_observations('video',vision,settings,client_factory=factory,image_loader=loader)
        decision=dict(visual_summary='street',audio_summary='speech',relationship='related',reason='evidence',
                      event='walking',edit_suggestion='keep',strengths=[],weaknesses=[],recommendation='保留',score=60,confidence=.8)
        llm.analyze.return_value=decision
        result=analyze_semantics('video',vision,[{'start':0,'end':1,'text':'speech'}],settings,
                                client_factory=factory,image_loader=loader,visual_cache=cache)
        vlm.analyze.assert_called_once();loader.assert_called_once()
        self.assertEqual(result['semantic_windows'][0]['status'],'analyzed')


if __name__=='__main__':unittest.main()
