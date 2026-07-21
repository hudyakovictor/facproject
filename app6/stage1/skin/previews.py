import cv2,numpy as np
def save_previews(root,bgr,A,mask,quality):
 root.mkdir(parents=True,exist_ok=True);colors=np.array([cv2.cvtColor(np.uint8([[[i*9%180,210,230]]]),cv2.COLOR_HSV2BGR)[0,0] for i in range(20)],np.uint8);layer=bgr.copy()
 for i in range(20):layer[A==i]=colors[i]
 overlay=np.where(mask[...,None],cv2.addWeighted(bgr,.55,layer,.45,0),bgr);cv2.imwrite(str(root/'atlas_A20_overlay.png'),overlay);q=np.clip(quality*255,0,255).astype(np.uint8);heat=cv2.applyColorMap(q,cv2.COLORMAP_TURBO);cv2.imwrite(str(root/'quality_weight.png'),np.where(mask[...,None],heat,0))

def save_wrinkle_overlay(root,bgr,skeleton,ridge_prob,ffhq_prob,mask):
 root.mkdir(parents=True,exist_ok=True)
 sk=np.asarray(skeleton,bool);overlay=bgr.copy();overlay[sk]=[0,0,255]
 cv2.imwrite(str(root/'wrinkle_skeleton.png'),np.where(mask[...,None],overlay,bgr))
 r=np.clip(ridge_prob*255,0,255).astype(np.uint8);heat=cv2.applyColorMap(r,cv2.COLORMAP_TURBO)
 cv2.imwrite(str(root/'wrinkle_ridge_heatmap.png'),np.where(mask[...,None],heat,0))
 if ffhq_prob is not None:
  p=np.clip(ffhq_prob*255,0,255).astype(np.uint8);fh=cv2.applyColorMap(p,cv2.COLORMAP_INFERNO)
  cv2.imwrite(str(root/'wrinkle_ffhq_heatmap.png'),np.where(mask[...,None],fh,0))
