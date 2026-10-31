"""Read the pty a bsim device announces in <logfile>; exit 0 if `needle` arrives within 30 s. Never blocks."""
import os, re, select, sys, time

log, needle = sys.argv[1], sys.argv[2].encode()
end = time.time() + 30
path = None
while time.time() < end and not path:
    m = re.search(r"/dev/pts/\d+", open(log, errors="replace").read())
    path = m.group(0) if m else None
    time.sleep(0.2)
print("pty:", path)
if not path:
    sys.exit(1)
fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
buf = b""
while time.time() < end and needle not in buf:
    if select.select([fd], [], [], 0.5)[0]:
        buf += os.read(fd, 4096)
print("pty data:", buf[:120])
sys.exit(0 if needle in buf else 1)
