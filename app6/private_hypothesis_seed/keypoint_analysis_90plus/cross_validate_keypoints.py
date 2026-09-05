import pandas as pd, numpy as np, glob, re
from pathlib import Path
B=Path('/data/raw/archive2'); O=Path('/data/analysis2')
def load(pref,n):
 fs=sorted(B.glob(pref+'_*.csv')); stems=[]; A=[]; V=[]
 for f in fs:
  d=pd.read_csv(f).sort_values('landmark_id'); stems.append(re.sub('^'+pref+'_','',f.stem)); A.append(d[['x','y','z']].to_numpy()); V.append(d.visible.to_numpy())
 return stems,np.stack(A),np.stack(V)
def norm(A,idx):
 out=[]
 for a in A:
  q=a-a[idx].mean(0); q/=np.sqrt(np.mean(np.sum(q[idx]**2,1))); out.append(q)
 return np.stack(out)
def score_coords(Q,idx):
 X=Q[:,idx,:].reshape(len(Q),-1); m=np.median(X,0); mad=1.4826*np.median(np.abs(X-m),0); mad[mad<1e-8]=np.std(X,0)[mad<1e-8]+1e-8; Z=np.abs((X-m)/mad); return np.mean(np.sort(Z,axis=1)[:,-18:],1)
s106,A106,V106=load('ldm106_aligned',106); s134,A134,V134=load('ldm134_aligned',134)
i106=np.where(V106.mean(0)>=.9)[0]; i134=np.where(V134.mean(0)>=.9)[0]
sc106=score_coords(norm(A106,i106),i106); sc134=score_coords(norm(A134,i134),i134)
d=pd.DataFrame({'stem':s106,'score106_coords':sc106}).merge(pd.DataFrame({'stem':s134,'score134_coords':sc134}),on='stem')
d['rank106']=d.score106_coords.rank(ascending=False); d['rank134']=d.score134_coords.rank(ascending=False)
d['both_top25']=(d.rank106<=25)&(d.rank134<=25)
d.to_csv(O/'keypoint_106_134_crosscheck.csv',index=False)
print('rank correlation',d[['score106_coords','score134_coords']].corr(method='spearman').iloc[0,1])
print('top25 overlap',int(d.both_top25.sum()))
print(d.sort_values(['both_top25','rank106'],ascending=[False,True]).query('both_top25').to_string(index=False))
# texture ABA B overlap
try:
 tex=pd.read_csv('/data/analysis/aba_top25.csv'); geo=pd.read_csv(O/'keypoint_aba_top25.csv').head(25)
 def col(df,opts):
  for x in opts:
   if x in df.columns:return x
 tc=col(tex,['b_filename','B','b_file']); gc='b_filename'
 if tc:
  ov=set(tex[tc].astype(str)) & set(geo[gc].astype(str)); print('texture/keypoint ABA B overlap',len(ov),sorted(ov))
except Exception as e: print('texture compare error',e)
