from __future__ import annotations
import cv2,numpy as np
FEATURES=('lbp_entropy','lbp_uniform_fraction','glcm_contrast','glcm_homogeneity','glcm_energy','gabor_energy','gabor_anisotropy','spectral_entropy','spectral_high_ratio','structure_coherence','log_blob_density','local_mad','lab_L_median','lab_a_median','lab_b_median','lab_a_mad','chroma_mad','color_entropy')
def _lbp(g):
 c=g[1:-1,1:-1];o=np.zeros(g.shape,np.uint8);q=np.zeros(c.shape,np.uint8)
 for k,(dy,dx) in enumerate(((-1,-1),(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1))):q|=((g[1+dy:g.shape[0]-1+dy,1+dx:g.shape[1]-1+dx]>=c).astype(np.uint8)<<k)
 o[1:-1,1:-1]=q;return o
def _glcm(g,m,L=16):
 q=np.clip((g*L).astype(int),0,L-1);M=np.zeros((L,L));
 for dy,dx in ((0,1),(1,0),(1,1),(1,-1),(0,2),(2,0)):
  ya=slice(max(0,-dy),min(g.shape[0],g.shape[0]-dy));yb=slice(max(0,dy),min(g.shape[0],g.shape[0]+dy));xa=slice(max(0,-dx),min(g.shape[1],g.shape[1]-dx));xb=slice(max(0,dx),min(g.shape[1],g.shape[1]+dx));v=m[ya,xa]&m[yb,xb];a=q[ya,xa][v];b=q[yb,xb][v];np.add.at(M,(a,b),1);np.add.at(M,(b,a),1)
 if M.sum()==0:return (np.nan,)*3
 P=M/M.sum();i,j=np.indices(P.shape);return np.sum(P*(i-j)**2),np.sum(P/(1+(i-j)**2)),np.sqrt(np.sum(P*P))
def _spectrum(g,m):
 y,x=np.where(m)
 if len(x)<128:return np.nan,np.nan
 x0,x1=x.min(),x.max()+1;y0,y1=y.min(),y.max()+1;a=g[y0:y1,x0:x1];q=m[y0:y1,x0:x1];Y,X=np.mgrid[:a.shape[0],:a.shape[1]];coef=np.linalg.lstsq(np.c_[X[q],Y[q],np.ones(q.sum())],a[q],rcond=None)[0];a=(a-(coef[0]*X+coef[1]*Y+coef[2]))*q;P=abs(np.fft.fftshift(np.fft.fft2(a*np.outer(np.hanning(a.shape[0]),np.hanning(a.shape[1])))))**2;cy,cx=np.array(P.shape)//2;R=np.hypot(*np.mgrid[-cy:P.shape[0]-cy,-cx:P.shape[1]-cx]);p=P[R>1];p/=p.sum()+1e-12;return -np.sum(p*np.log(p+1e-12))/np.log(max(2,len(p))),P[R>max(P.shape)*.2].sum()/(P.sum()+1e-12)
def extract_texture_features(bgr,w,A,S,min_support=100):
 g=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY).astype(np.float32)/255.;lab=cv2.cvtColor(bgr,cv2.COLOR_BGR2LAB).astype(np.float32);lab[...,0]/=255.;lab[...,1:]=(lab[...,1:]-128)/128.;lbp=_lbp(g);gab=np.stack([abs(cv2.filter2D(g,cv2.CV_32F,cv2.getGaborKernel((15,15),3,t,6,.6))) for t in np.linspace(0,np.pi,8,endpoint=False)]);gx=cv2.Sobel(g,cv2.CV_32F,1,0);gy=cv2.Sobel(g,cv2.CV_32F,0,1);Jx=cv2.GaussianBlur(gx*gx,(0,0),2);Jy=cv2.GaussianBlur(gy*gy,(0,0),2);Jxy=cv2.GaussianBlur(gx*gy,(0,0),2);coh=np.sqrt((Jx-Jy)**2+4*Jxy**2)/(Jx+Jy+1e-6);log=abs(cv2.Laplacian(cv2.GaussianBlur(g,(0,0),1.4),cv2.CV_32F));rows=[]
 for level,zmap,n,prefix in [('A20',A,20,'A'),('S40',S,40,'S')]:
  for i in range(n):
   m=(zmap==i)&(w>0);support=float(w[m].sum());v=np.full(len(FEATURES),np.nan,np.float32);state='usable' if support>=min_support and m.sum()>=128 else 'not_measurable'
   if state=='usable':
    h=np.bincount(lbp[m],weights=w[m],minlength=256).astype(float);h/=h.sum()+1e-12;bits=np.unpackbits(np.arange(256,dtype=np.uint8)[:,None],axis=1);uniform=np.sum(abs(np.diff(np.c_[bits,bits[:,0]],axis=1)),axis=1)<=2;v[0]=-np.sum(h*np.log(h+1e-12));v[1]=h[uniform].sum();v[2:5]=_glcm(g,m);e=np.array([np.average(x[m],weights=w[m]) for x in gab]);v[5]=e.mean();v[6]=(e.max()-e.min())/(e.mean()+1e-8);v[7:9]=_spectrum(g,m);v[9]=np.average(coh[m],weights=w[m]);v[10]=np.mean(log[m]>=np.percentile(log[m],90));med=np.median(g[m]);v[11]=np.median(abs(g[m]-med));lv=lab[m];v[12:15]=np.median(lv,axis=0);v[15]=np.median(abs(lv[:,1]-v[13]));ch=np.hypot(lv[:,1],lv[:,2]);v[16]=np.median(abs(ch-np.median(ch)));hh,_=np.histogram(lv[:,1],bins=16,range=(-1,1),weights=w[m]);hh=hh/(hh.sum()+1e-12);v[17]=-np.sum(hh*np.log(hh+1e-12))
   rows.append({'zone_level':level,'zone_id':f'{prefix}{i+1:02d}','state':state,'effective_support':support,'values':v})
 return rows
