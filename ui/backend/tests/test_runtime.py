from __future__ import annotations
import json,sys,tempfile,time,unittest
from pathlib import Path
from dpo.runtime import EventLog,RunManager,RunnerRegistry,RunnerSpec
class RuntimeTests(unittest.TestCase):
 def manager(self,root,specs):
  app=Path(root)/'app6';app.mkdir();(app/'x.py').write_text('x=1\n');return RunManager(RunnerRegistry(specs),app,Path(root)/'.data',Path(root)/'heavy')
 def wait(self,m,rid,limit=4):
  end=time.time()+limit
  while time.time()<end:
   r=m.get(rid)
   if r.status in {'succeeded','failed','cancelled','timed_out','interrupted'}:return r
   time.sleep(.03)
  self.fail('run did not finish')
 def test_success_failure_timeout_and_logs(self):
  with tempfile.TemporaryDirectory() as t:
   m=self.manager(t,[RunnerSpec('ok','ok','this',('arg',),2),RunnerSpec('fail','fail','module_that_does_not_exist',(),2),RunnerSpec('slow','slow','timeit',('-s','import time','time.sleep(2)'),1)])
   self.assertEqual(self.wait(m,m.submit('ok').id).status,'succeeded')
   self.assertEqual(self.wait(m,m.submit('fail').id).status,'failed')
   self.assertEqual(self.wait(m,m.submit('slow').id).status,'timed_out');m.shutdown()
 def test_cancel_and_allowlist(self):
  with tempfile.TemporaryDirectory() as t:
   m=self.manager(t,[RunnerSpec('slow','slow','timeit',('-s','import time','time.sleep(3)'),10)]);r=m.submit('slow');
   while m.get(r.id).status!='running':time.sleep(.01)
   m.cancel(r.id);self.assertEqual(self.wait(m,r.id).status,'cancelled')
   with self.assertRaises(ValueError):m.submit('../shell')
   m.shutdown()
 def test_malformed_events_are_isolated(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'e.jsonl';p.write_text('{bad}\n'+json.dumps({'schema':'other','seq':2})+'\n');log=EventLog(p);log.emit('ok');self.assertEqual([x['type'] for x in log.read()],['ok'])
 def test_recovery_marks_nonterminal_interrupted(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);app=root/'app6';app.mkdir();(app/'x.py').write_text('x=1');d=root/'.data'/'runs';d.mkdir(parents=True);(d/'a.json').write_text(json.dumps({'id':'a','runner_id':'x','status':'running','created_at':'x','code_hash':'','config_hash':'','seed':0}))
   m=RunManager(RunnerRegistry([]),app,root/'.data',root/'heavy');self.assertEqual(m.get('a').status,'interrupted');m.shutdown()
if __name__=='__main__':unittest.main()
