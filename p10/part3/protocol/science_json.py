"""Use the repository's established finite JSON conversion for measured records."""
import math


def safe(value):
    import numpy as np
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [safe(v) for v in value]
    if isinstance(value,np.generic):return safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value
