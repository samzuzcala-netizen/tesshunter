"""Synthetic controller payload. Never imports TessHunter or reads science."""
import json
from pathlib import Path
import subprocess
import sys
import time
import psutil

mode, destination = sys.argv[1:3]
path = Path(destination)
if mode == 'complete':
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"fixture": true}', encoding='utf-8')
elif mode == 'leaf':
    proc = psutil.Process()
    path.write_text(json.dumps(dict(pid=proc.pid, create_time=proc.create_time(), command=proc.cmdline())), encoding='utf-8')
    time.sleep(120)
elif mode == 'tree':
    subprocess.Popen([sys.executable, __file__, 'leaf', destination])
    time.sleep(120)
elif mode == 'orphan':
    subprocess.Popen([sys.executable, __file__, 'leaf', destination])
    time.sleep(.5)
elif mode == 'error':
    raise SystemExit(7)
else:
    raise ValueError(mode)
