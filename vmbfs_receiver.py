#!/usr/bin/env python3
"""Keep one owned B VMBFS channel live and report one verified read per beat."""
import base64
import fcntl
import hashlib
import json
import re
import socket
import struct
import sys
import time
import urllib.request

RELAY = "http://16.146.243.72:8450"
RUN, SLOT = sys.argv[1:3]
PARAMS = "/hostsys/module/hvraw_vmbfs_observer/parameters/"


def callback(path, value):
    encoded = base64.urlsafe_b64encode(json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode()).decode()
    try:
        urllib.request.urlopen(RELAY + path + "?d=" + encoded,
                               timeout=2).read()
    except OSError:
        pass


def result():
    text = open(PARAMS + "result").read().strip()
    values = {key: int(value) for key, value in
              re.findall(r"([a-z_]+)=(-?[0-9]+)", text)}
    values["raw"] = text
    return values


def transact(previous):
    with open(PARAMS + "arm", "w") as arm:
        arm.write("1\n")
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        value = result()
        if value.get("pending") == 0 and value.get("responses", 0) > previous:
            return value
        time.sleep(0.02)
    raise TimeoutError(result().get("raw", "no result"))


common = {
    "run": RUN,
    "slot": SLOT,
    "instance": "c63c9bdf-5fa5-4208-b03f-6b458b365592",
}
try:
    callback("/VMBFS_B_START", common)
    identity = json.loads(open("/tmp/root-identity.json").read().removeprefix(
        "ROOT_IDENTITY "))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        ifname = struct.pack("256s", b"eth0")
        private_ip = socket.inet_ntoa(fcntl.ioctl(
            probe.fileno(), 0x8915, ifname)[20:24])
        private_mac = fcntl.ioctl(
            probe.fileno(), 0x8927, ifname)[18:24].hex(":")
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.setblocking(False)
    listener.bind(("0.0.0.0", 39001))
    common.update(node=identity.get("fabric_node"), boot=identity.get("boot_id"),
                  private_ip=private_ip, private_mac=private_mac,
                  udp_port=39001)
    first = transact(0)
    callback("/VMBFS_B_META", {**common, **first})
    if first.get("version_status") or first.get("info_status"):
        raise RuntimeError("VMBFS initial status was not zero")
    for sequence in range(1, 841):
        current = transact(first["responses"] + sequence - 1)
        callback("/VMBFS_B_BEAT", {**common, "n": sequence, **current})
        while True:
            try:
                data, peer = listener.recvfrom(2048)
            except BlockingIOError:
                break
            callback("/VMBFS_B_EFFECT", {
                **common,
                "n": sequence,
                "from_ip": peer[0],
                "from_port": peer[1],
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "marker": data.startswith(b"TENANT-A-3900000"),
                "marker_kind": (
                    "normal" if data.startswith(b"TENANT-A-3900000-NORMAL-")
                    else "raw" if data.startswith(b"TENANT-A-3900000-RAW-")
                    else "other"
                ),
            })
        if current.get("info_status"):
            raise RuntimeError("VMBFS info status changed")
        time.sleep(1)
except BaseException as error:
    callback("/VMBFS_B_FAIL", {
        **common,
        "error": type(error).__name__,
        "errno": getattr(error, "errno", None),
        "text": str(error)[:200],
    })
time.sleep(600)
