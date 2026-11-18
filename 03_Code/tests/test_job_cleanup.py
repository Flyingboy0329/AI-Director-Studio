import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from job_cleanup import cleanup_job, mark_job_owned
import main as pipeline


class JobCleanupTests(unittest.TestCase):
    def make_job(self, root):
        original=root/'original.mp4';original.write_bytes(b'original unchanged')
        job=root/'05_Output'/'jobs'/('a'*32)
        job.mkdir(parents=True)
        mark_job_owned(job,original)
        (job/'video').mkdir();(job/'video'/'generated.mp4').write_bytes(b'temporary')
        (job/'marker_task.lua').write_text('return {}')
        return original,job

    def test_delete_only_owned_job_log_files_and_preserve_source_and_other_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original,job=self.make_job(root)
            sibling=job.parent/('b'*32);sibling.mkdir();(sibling/'keep').write_text('keep')
            output=io.StringIO()
            with redirect_stdout(output):self.assertTrue(cleanup_job(job,original,root))
            self.assertFalse(job.exists())
            self.assertEqual(original.read_bytes(),b'original unchanged')
            self.assertTrue((sibling/'keep').exists())
            self.assertIn('generated.mp4',output.getvalue())
            self.assertIn('原掃描檔案不會被刪除',output.getvalue())

    def test_refuse_outside_root_missing_ownership_source_inside_and_reparse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original,job=self.make_job(root)
            self.assertFalse(cleanup_job(root,original,root))
            self.assertFalse(cleanup_job(job,job/'video'/'generated.mp4',root))
            with patch('job_cleanup._linked',return_value=True):
                self.assertFalse(cleanup_job(job,original,root))
            with patch('job_cleanup._linked',side_effect=lambda path: path.name=='generated.mp4'):
                self.assertFalse(cleanup_job(job,original,root))
            self.assertTrue((job/'video'/'generated.mp4').exists())
            (job/'.ai_director_job.json').unlink()
            self.assertFalse(cleanup_job(job,original,root))
            self.assertTrue((job/'video'/'generated.mp4').exists())
            self.assertTrue(original.exists())

    def test_locked_file_failure_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original,job=self.make_job(root)
            with patch('job_cleanup.shutil.rmtree',side_effect=PermissionError('locked')):
                self.assertFalse(cleanup_job(job,original,root))
            self.assertTrue(job.exists());self.assertTrue(original.exists())

    def test_pipeline_only_cleans_after_dispatch_and_cleanup_failure_does_not_retry(self):
        for delivered in (False,True):
            with self.subTest(delivered=delivered),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);original=root/'source.mp4';original.touch()
                def markers(**kwargs):
                    path=Path(kwargs['output_lua_path']);path.write_text('return {}');return path
                with patch.object(pipeline,'PROJ_ROOT',root), \
                     patch.object(pipeline,'split_media',return_value=('temp.mp4','temp.wav')), \
                     patch.object(pipeline,'analyze_audio',return_value=[]), \
                     patch.object(pipeline,'analyze_vision',return_value={'frames':[{}]}), \
                     patch.object(pipeline,'build_markers',side_effect=markers), \
                     patch.object(pipeline,'submit_markers',return_value=delivered), \
                     patch.object(pipeline,'cleanup_job',side_effect=OSError('busy')) as cleanup:
                    self.assertEqual(pipeline.run_main_pipeline(original,model_settings={}),delivered)
                    self.assertEqual(cleanup.call_count,int(delivered))
                    self.assertTrue(original.exists())

    def test_pipeline_success_removes_real_owned_job_but_failed_dispatch_keeps_it(self):
        for delivered in (False,True):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);original=root/'source.mp4';original.write_bytes(b'keep')
                def split(source,destination):
                    job=Path(destination);v=job/'generated.mp4';a=job/'generated.wav'
                    v.write_bytes(b'temp');a.write_bytes(b'temp');return str(v),str(a)
                def markers(**kwargs):
                    path=Path(kwargs['output_lua_path']);path.write_text('return {}');return path
                with patch.object(pipeline,'PROJ_ROOT',root),patch.object(pipeline,'split_media',side_effect=split), \
                     patch.object(pipeline,'analyze_audio',return_value=[]), \
                     patch.object(pipeline,'analyze_vision',return_value={'frames':[{}]}), \
                     patch.object(pipeline,'build_markers',side_effect=markers), \
                     patch.object(pipeline,'submit_markers',return_value=delivered):
                    self.assertEqual(pipeline.run_main_pipeline(original,model_settings={}),delivered)
                self.assertEqual(len(list((root/'05_Output'/'jobs').iterdir())),0 if delivered else 1)
                self.assertEqual(original.read_bytes(),b'keep')

if __name__=='__main__':unittest.main()
