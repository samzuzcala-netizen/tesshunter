"""Body-byte acquisition accounting with a shared, crash-safe byte reservation.

Each HTTP read reserves at most 1 MiB across all workers before reading. A failed
read is conservatively charged its reservation, with that uncertainty disclosed.
The lock is an OS byte-range lock, released even when a worker exits unexpectedly.
"""
import contextlib
import http.client
import json
import msvcrt
import os
import time
from common import ROOT, read, write, utc

STATE=ROOT/"manifests/acquisition_bytes.json"
LOCK=ROOT/"work/acquisition.lock"


@contextlib.contextmanager
def transaction():
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open("a+b") as handle:
        if handle.tell()==0:
            handle.write(b"0");handle.flush()
        timer=time.monotonic()
        while True:
            try:
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:
                if time.monotonic()-timer>20:raise
                time.sleep(.05)
        try:
            state=read(STATE) if STATE.exists() else dict(prior_bytes=85401427,cap_bytes=15000000000,
                measured_body_bytes=0,failed_read_upper_bytes=0,reservations={},workers={})
            yield state
            write(STATE,state,replace=STATE.exists())
        finally:
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)


def reserved_read(response, amount, original):
    pid=str(os.getpid())
    with transaction() as state:
        outstanding=sum(state["reservations"].values())
        free=state["cap_bytes"]-state["prior_bytes"]-state["measured_body_bytes"]-state["failed_read_upper_bytes"]-outstanding
        reserve=min(amount,1024*1024,free)
        if reserve<=0:raise RuntimeError("ACQUISITION_CAP: no remaining transfer bytes")
        state["reservations"][pid]=state["reservations"].get(pid,0)+reserve
    try:
        content=original(response,reserve)
    except BaseException:
        with transaction() as state:
            state["reservations"][pid]-=reserve
            state["failed_read_upper_bytes"]+=reserve
        raise
    with transaction() as state:
        state["reservations"][pid]-=reserve
        state["measured_body_bytes"]+=len(content)
        state["workers"][pid]=state["workers"].get(pid,0)+len(content)
        state["updated_utc"]=utc()
    return content


def install():
    original=http.client.HTTPResponse.read
    def metered(response,amt=None):
        if amt==0:return b""
        if response.isclosed():return b""
        chunks=[];remaining=amt
        while remaining is None or remaining<0 or remaining>0:
            if response.isclosed():break
            want=1024*1024 if remaining is None or remaining<0 else min(remaining,1024*1024)
            chunk=reserved_read(response,want,original)
            if not chunk:break
            chunks.append(chunk)
            if remaining is not None and remaining>=0:remaining-=len(chunk)
        return b"".join(chunks)
    def readinto(response,buffer):
        chunk=metered(response,len(buffer));buffer[:len(chunk)]=chunk;return len(chunk)
    http.client.HTTPResponse.read=metered
    http.client.HTTPResponse.readinto=readinto


def accounting():
    with transaction() as state:
        return dict(state)
