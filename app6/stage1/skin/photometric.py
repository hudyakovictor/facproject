import cv2,numpy as np
from ..status_logger import log_status, log_blocker, log_warning
def branches(bgr,mask):
 log_status("branches", "complete")
 raw=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY).astype(np.float32)/255.;base=cv2.GaussianBlur(raw,(0,0),max(3,min(raw.shape)*.025));norm=(raw-base);s=1.4826*np.median(abs(norm[mask]-np.median(norm[mask]))) if np.any(mask) else 1.;norm=np.clip(norm/max(s,1e-4),-6,6);norm[~mask]=0;return {'raw_luminance':raw.astype(np.float16),'low_frequency_normalized':norm.astype(np.float16),'normalization_scale':np.array(s,np.float32),'semantics':np.array('raw primary; normalized for ridge/texture sensitivity only')}
