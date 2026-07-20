from __future__ import annotations
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageOps,ExifTags
def decode_oriented(path):
 """Deterministic EXIF transpose followed by RGB→BGR; returns provenance."""
 with Image.open(path) as im:
  encoded_size=list(im.size);mode=im.mode;ex=im.getexif();orientation=int(ex.get(274,1));icc=im.info.get('icc_profile');wanted={'Make','Model','Software','DateTime','DateTimeOriginal','LensModel'};tags={ExifTags.TAGS.get(k,str(k)):str(v) for k,v in ex.items() if ExifTags.TAGS.get(k,str(k)) in wanted};oriented=ImageOps.exif_transpose(im).convert('RGB');rgb=np.asarray(oriented)
 bgr=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
 return bgr,{'decoder':'Pillow.ImageOps.exif_transpose','encoded_size':encoded_size,'oriented_size':[int(bgr.shape[1]),int(bgr.shape[0])],'encoded_mode':mode,'exif_orientation':orientation,'orientation_applied':orientation not in (0,1),'icc_profile_present':bool(icc),'exif_camera_processing':tags,'source_hypotheses':{'scanned':'unknown','upscaled':'unknown','recompressed':'unknown'},'output':'uint8_sRGB_assumed_if profile not converted'}
