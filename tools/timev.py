"""Stand-in for `/usr/bin/time -v` on nodes without GNU time (node6, job 412923).

Usage: python -I tools/timev.py CMD [ARGS...]
Runs CMD, then appends to stderr the GNU time -v lines that our logs are
grepped for: elapsed wall clock, user/system time, maximum resident set size
(kbytes, largest single process among waited-for descendants, as GNU time) and
the exit status. Exits with CMD's exit status.
"""
import resource
import subprocess
import sys
import time

if len(sys.argv) < 2:
    sys.exit("usage: timev.py CMD [ARGS...]")
t0 = time.monotonic()
rc = subprocess.call(sys.argv[1:])
wall = time.monotonic() - t0
ru = resource.getrusage(resource.RUSAGE_CHILDREN)
m, s = divmod(wall, 60)
h, m = divmod(int(m), 60)
elapsed = f"{h}:{m:02d}:{s:05.2f}" if h else f"{m}:{s:05.2f}"
print(f'\tCommand being timed: "{" ".join(sys.argv[1:])}"', file=sys.stderr)
print(f"\tUser time (seconds): {ru.ru_utime:.2f}", file=sys.stderr)
print(f"\tSystem time (seconds): {ru.ru_stime:.2f}", file=sys.stderr)
print(f"\tElapsed (wall clock) time (h:mm:ss or m:ss): {elapsed}", file=sys.stderr)
print(f"\tMaximum resident set size (kbytes): {ru.ru_maxrss}", file=sys.stderr)
print(f"\tExit status: {rc if rc >= 0 else 128 - rc}", file=sys.stderr)
sys.exit(rc if rc >= 0 else 128 - rc)
