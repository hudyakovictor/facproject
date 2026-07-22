"""🔄 CALLBACK (pytest) → регрессии ревью skin-слоя (reviewed fixes pack).
"""
import inspect, unittest
from app6.stage2.skin.calibration import _split, _group_id
from app6.stage2.skin.chronology import analyze_temporal_observations
from app6.stage1.skin.wrinkles import classical
from app6.stage1.skin.wrinkles.ffhq_adapter import FFHQWrinkleAdapter

class ReviewedIntegrationTests(unittest.TestCase):
    def test_calibration_never_splits_capture_group(self):
        rows=[]
        for g in range(10):
            for frame in range(2):
                rows.append({'photo_id':f'{g}-{frame}','capture_event_id':f'event-{g}','pose_bin':'frontal','zones':[]})
        train,test=_split(rows,test_fraction=.2,seed=0)
        self.assertFalse(set(map(_group_id,train)) & set(map(_group_id,test)))
        self.assertTrue(test)

    def test_temporal_model_keeps_pose_separate(self):
        rows=[]
        for pose,base in [('frontal',0.0),('left_mid',100.0)]:
            for i,date in enumerate(('2000-01-01','2001-01-01','2002-01-01')):
                rows.append({'photo_id':f'{pose}-{i}','capture_event_id':f'{pose}-e{i}','date_start':date,
                             'pose_bin':pose,'expression_bin':'neutral','zone':'A01','family':'x',
                             'raw_value':base+i,'state':'usable'})
        out=analyze_temporal_observations(rows)
        self.assertEqual({x['pose_bin'] for x in out['series']},{'frontal','left_mid'})
        self.assertEqual(len(out['series']),2)

    def test_wrinkle_paths_are_not_pca_resorted(self):
        src=inspect.getsource(classical.detect)
        self.assertNotIn('argsort(q@vh',src)

    def test_ffhq_uses_safe_weights_loading(self):
        src=inspect.getsource(FFHQWrinkleAdapter._load)
        self.assertIn('weights_only=True',src)

if __name__=='__main__': unittest.main()
