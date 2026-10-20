"""Debug wrapper: run s08_worker.main with a faulthandler stack dump after N seconds."""
import faulthandler
import sys
import time

faulthandler.dump_traceback_later(int(sys.argv[2]), exit=True)
t0 = time.time()
print("start", flush=True)
import s08_worker  # noqa: E402
print("imported", round(time.time() - t0, 1), flush=True)
s08_worker.main(sys.argv[1])
print("done", round(time.time() - t0, 1), flush=True)
