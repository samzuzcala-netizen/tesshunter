"""Bounded Windows sharing-violation retries for controller records only.

An ordinary reader may briefly deny replacement of progress.json on Windows.
This never changes scientific deadlines, retries a science result, or rewrites
an immutable completed case. The original common.py remains unchanged.
"""
import time
import common as base

def transient_call(function,*args,**kwargs):
    started=time.monotonic();attempts=0
    while True:
        try:
            result=function(*args,**kwargs)
            if attempts:base.event('controller_record_sharing_retry',attempts=attempts,
                elapsed_seconds=time.monotonic()-started,path=str(args[0]) if args else None)
            return result
        except PermissionError:
            if time.monotonic()-started>=10:raise
            attempts+=1;time.sleep(min(.05*attempts,.5))

def write(path,value,*,replace=False):
    return transient_call(base.write,path,value,replace=replace)

def resume(text):
    return transient_call(base.resume,text)
