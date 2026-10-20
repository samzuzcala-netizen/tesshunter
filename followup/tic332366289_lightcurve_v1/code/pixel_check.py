import common as C
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from ingest import load
fig,axes=plt.subplots(2,7,figsize=(19,6),layout='constrained')
for s,ax in zip(C.SECTORS,axes.flat):
    a=load(s,'pixel');v=a['median_image'];b=np.nanmedian(v)
    ax.imshow(np.arcsinh((v-b)/max(1,np.nanstd(v))),origin='lower',cmap='gray')
    yy,xx=np.where(a['small_mask']);ax.scatter(xx,yy,s=14,facecolor='none',edgecolor='cyan')
    yy,xx=np.where(a['opt_mask']);ax.scatter(xx,yy,s=25,facecolor='none',edgecolor='orange')
    ax.plot(*a['target_xy'],'r+');ax.set_title(f's{s}: target +\ncyan 3x3 / orange optimal');ax.set_xticks([0,10,20]);ax.set_yticks([0,10,20])
fig.suptitle('Input identity and aperture placement; pixel origin lower left')
fig.savefig(C.WS/'figures/aperture_identity.png',dpi=130);plt.close(fig)
print('Saved aperture_identity.png')
