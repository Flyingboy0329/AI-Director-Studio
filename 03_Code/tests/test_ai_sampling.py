import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai_sampling import sample_times, validate_rate
from ai.semantic_analyzer import analyze_semantics
from test_semantics import decision


class SamplingTests(unittest.TestCase):
    def test_real_extraction_rate_and_one_frame_remainder(self):
        import tempfile
        import cv2
        import numpy as np
        from ai.semantic_analyzer import extract_images
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sampling.avi'
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),30,(64,64))
            if not writer.isOpened():self.skipTest('MJPG writer unavailable')
            try:
                for index in range(181):
                    writer.write(np.full((64,64,3),index%255,dtype=np.uint8))
            finally:writer.release()
            for rate,expected in ((1,6),(4,24)):
                images=extract_images(path,0,6,rate)
                self.assertEqual(sum(item['type']=='image_url' for item in images),expected)
            images=extract_images(path,6,181/30,4)
            self.assertEqual(sum(item['type']=='image_url' for item in images),1)

    def test_all_rates_counts_and_short_tail(self):
        for rate,count in ((.25,2),(.5,3),(1,6),(2,12),(4,24)):
            times=sample_times(0,6,rate)
            self.assertEqual(len(times),count)
            self.assertEqual(times[0],0)
            self.assertTrue(all(0<=t<6 for t in times))
            self.assertEqual(sample_times(72,72+1/30,rate),[72])
        self.assertEqual(sample_times(0,6,1),[0,1,2,3,4,5])
        for bad in (0,-1,3,float('nan'),True):
            with self.assertRaises(ValueError):validate_rate(bad)

    def test_rate_and_actual_image_count_reach_model_and_result(self):
        received=[]
        class Client:
            def __init__(self,*args):pass
            def check(self,**kwargs):pass
            def analyze(self,name,content):
                if name=='visual_observer.md':
                    received.append(content)
                    return {'visual_summary':'test'}
                return decision()
        def loader(path,start,end,rate):
            return [{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,fake'}} for _ in sample_times(start,end,rate)]
        result=analyze_semantics('fake',{'fps':30,'total_frames':181,'frames':[{'frame_idx':0,'score':50}]},[],
            {'llm_path':'test.gguf','llm_mmproj_path':'projector.gguf','model_mode':'llm_only','ai_sampling_fps':4},
            client_factory=Client,image_loader=loader)
        self.assertEqual([w['sent_image_count'] for w in result['semantic_windows']],[24,1])
        self.assertEqual(result['ai_sampling_fps'],4)
        self.assertEqual(sum(item.get('type')=='image_url' for item in received[0]),24)
        self.assertEqual(result['semantic_windows'][-1]['end_frame'],181)

if __name__=='__main__':unittest.main()
