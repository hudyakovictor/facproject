from __future__ import annotations
import csv,numpy as np
class PosePolicy:
 def __init__(self,path):
  self.rows={}
  with open(path,encoding='utf8') as f:
   for r in csv.DictReader(f):self.rows[r['zone_code'],int(r['yaw_bin_center_deg'])]=(r['status'],float(r['weight']))
  self.centers=sorted({x[1] for x in self.rows})
 def weights(self,A,yaw):
  c=min(self.centers,key=lambda x:abs(x-float(yaw)));w=np.zeros(A.shape,np.float32)
  for i in range(20):w[A==i]=self.rows[f'A{i+1:02d}',c][1]
  return w,{'yaw_input_deg':float(yaw),'selected_center_deg':c,'convention':'+yaw exposes anatomical-left; qualify against 3DDFA golden poses'}
