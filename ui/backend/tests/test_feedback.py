import subprocess,sys,tempfile,unittest
from pathlib import Path
from dpo.feedback import BackupManager,apply_patch,build_capsule,build_spec,classify_failure,diff_touched_paths,revert_patch_commit,run_isolated_patch

class ClassifyTests(unittest.TestCase):
 def test_succeeded_with_passed_checks_returns_none(self):
  self.assertIsNone(classify_failure({"status":"succeeded"},[],{"passed":True,"checks":[]}))
 def test_no_measurable_output_is_p0(self):
  cr={"passed":False,"checks":[{"check":"pipeline_complete","ok":False,"detail":"нет analysis_validation.json"}]}
  c=classify_failure({"status":"failed"},["x"],cr);self.assertEqual(c.priority,"P0");self.assertEqual(c.category,"no_measurable_output")
 def test_scientific_contract_violation_is_p1(self):
  cr={"passed":False,"checks":[{"check":"pair_status","ok":False,"detail":"mismatch"}]}
  c=classify_failure({"status":"failed"},[],cr);self.assertEqual(c.priority,"P1")
 def test_crash_without_checks_is_p0(self):
  c=classify_failure({"status":"failed"},["Traceback (most recent call last):","ModuleNotFoundError: x"],None)
  self.assertEqual(c.priority,"P0");self.assertEqual(c.category,"pipeline_crash")
 def test_cancelled_is_p3_and_timeout_is_p1(self):
  self.assertEqual(classify_failure({"status":"cancelled"},[],None).priority,"P3")
  self.assertEqual(classify_failure({"status":"timed_out"},[],None).priority,"P1")

class SpecCapsuleTests(unittest.TestCase):
 def test_spec_includes_suspected_functions_from_matrix(self):
  cr={"passed":False,"checks":[{"check":"pair_status","ok":False,"detail":"x"}]}
  c=classify_failure({"status":"failed"},[],cr)
  matrix=[{"code":"stage2/engine.py:f","blocks":["stability"],"what":"desc","status":"implemented"}]
  spec=build_spec({"id":"r1","runner_id":"app6-regression","seed":1,"code_hash":"abc"},c,scenario_id="S01",scenario_block="stability",function_matrix=matrix)
  self.assertEqual(spec["priority"],"P1");self.assertEqual(len(spec["suspected_functions"]),1)
 def test_capsule_is_written_and_bounded(self):
  with tempfile.TemporaryDirectory() as d:
   spec={"schema":"dpo-fix-spec-v1","priority":"P0"}
   out=build_capsule(spec,tuple(f"line{i}" for i in range(100)),capsule_root=Path(d))
   self.assertTrue(Path(out["path"]).is_file());self.assertEqual(len(out["capsule"]["log_excerpt"]),40)

class BackupRollbackTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  (self.root/"a.py").write_text("x=1\n");self.backups=self.root/"_backups"
  self.mgr=BackupManager(self.backups,self.root)
 def tearDown(self):self.tmp.cleanup()
 def test_rollback_restores_modified_file(self):
  bid=self.mgr.create(["a.py"]);(self.root/"a.py").write_text("x=2\n")
  self.mgr.rollback(bid);self.assertEqual((self.root/"a.py").read_text(),"x=1\n")
 def test_rollback_deletes_newly_created_file(self):
  bid=self.mgr.create(["b.py"]);(self.root/"b.py").write_text("new\n")
  self.mgr.rollback(bid);self.assertFalse((self.root/"b.py").is_file())
 def test_refuses_git_directory_and_path_escape(self):
  with self.assertRaises(ValueError):self.mgr.create([".git/config"])
  with self.assertRaises(ValueError):self.mgr.create(["../outside.py"])

class ApplyPatchTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  subprocess.run(["git","init","-q"],cwd=self.root,check=True)
  (self.root/"a.py").write_text("x=1\n")
  subprocess.run(["git","add","."],cwd=self.root,check=True)
  subprocess.run(["git","-c","user.email=t@t.co","-c","user.name=t","commit","-q","-m","init"],cwd=self.root,check=True)
  self.mgr=BackupManager(self.root/"_backups",self.root)
 def tearDown(self):self.tmp.cleanup()
 def _diff(self):
  return subprocess.run(["git","diff"],cwd=self.root,capture_output=True,text=True).stdout
 def test_apply_then_rollback_roundtrip(self):
  (self.root/"a.py").write_text("x=2\n");diff=self._diff();subprocess.run(["git","checkout","--","a.py"],cwd=self.root,check=True)
  self.assertEqual(diff_touched_paths(diff),["a.py"])
  result=apply_patch(diff,allowed_root=self.root,backup_manager=self.mgr)
  self.assertEqual((self.root/"a.py").read_text(),"x=2\n")
  self.mgr.rollback(result["backup_id"]);self.assertEqual((self.root/"a.py").read_text(),"x=1\n")
 def test_rejects_diff_without_target(self):
  with self.assertRaises(ValueError):diff_touched_paths("not a diff")

class IsolatedPatchTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.repo=Path(self.tmp.name)
  subprocess.run(["git","init","-q"],cwd=self.repo,check=True)
  (self.repo/"app6").mkdir();(self.repo/"app6/a.py").write_text("x=1\n")
  subprocess.run(["git","add","."],cwd=self.repo,check=True)
  subprocess.run(["git","-c","user.email=t@t.co","-c","user.name=t","commit","-q","-m","init"],cwd=self.repo,check=True)
  self.allowed_root=self.repo/"app6";self.mgr=BackupManager(self.repo/"_backups",self.allowed_root)
 def tearDown(self):self.tmp.cleanup()
 def _diff(self,new_content):
  (self.allowed_root/"a.py").write_text(new_content)
  diff=subprocess.run(["git","diff","--relative"],cwd=self.allowed_root,capture_output=True,text=True).stdout
  subprocess.run(["git","checkout","--","a.py"],cwd=self.allowed_root,check=True)
  return diff
 def test_passing_tests_commit_and_change_real_file(self):
  diff=self._diff("x=2\n")
  passing_cmd=[sys.executable,"-c","import sys;content=open('app6/a.py').read();sys.exit(0 if 'x=2' in content else 1)"]
  result=run_isolated_patch(diff,allowed_root=self.allowed_root,backup_manager=self.mgr,test_cmd=passing_cmd,timeout=30)
  self.assertTrue(result["passed"]);self.assertTrue(result["applied"]);self.assertIsNotNone(result["commit_sha"])
  self.assertEqual((self.allowed_root/"a.py").read_text(),"x=2\n")
  wt=subprocess.run(["git","worktree","list"],cwd=self.repo,capture_output=True,text=True).stdout
  self.assertEqual(len(wt.strip().splitlines()),1)
 def test_failing_tests_leave_real_tree_untouched(self):
  diff=self._diff("x=2\n")
  failing_cmd=[sys.executable,"-c","import sys;sys.exit(1)"]
  result=run_isolated_patch(diff,allowed_root=self.allowed_root,backup_manager=self.mgr,test_cmd=failing_cmd,timeout=30)
  self.assertFalse(result["passed"]);self.assertFalse(result["applied"]);self.assertIsNone(result["commit_sha"])
  self.assertEqual((self.allowed_root/"a.py").read_text(),"x=1\n")
 def test_revert_undoes_commit(self):
  diff=self._diff("x=2\n")
  passing_cmd=[sys.executable,"-c","import sys;sys.exit(0)"]
  result=run_isolated_patch(diff,allowed_root=self.allowed_root,backup_manager=self.mgr,test_cmd=passing_cmd,timeout=30)
  revert_patch_commit(result["commit_sha"],allowed_root=self.allowed_root)
  self.assertEqual((self.allowed_root/"a.py").read_text(),"x=1\n")

if __name__=="__main__":unittest.main()
