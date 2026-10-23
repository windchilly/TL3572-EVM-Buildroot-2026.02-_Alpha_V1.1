#!/usr/bin/env python3
"""Linux ETH2/ETH3 physical smoke test, NOT a UP2 direct-drive test. No IP/routes changed."""
import argparse
import json
from pathlib import Path
import socket
import struct
import time
import zlib

ETHERTYPE = 0x88B5  # Local experimental EtherType; not an industrial protocol.
MAGIC = b"M7ETH3L2"


def frame(destination, source, role, sequence, length):
    pattern = bytes((sequence + i) & 255 for i in range(length - 38))
    record = struct.pack("!8sIII", MAGIC, role, sequence, len(pattern)) + pattern
    return destination + source + struct.pack("!H", ETHERTYPE) + record + struct.pack("!I", zlib.crc32(record))


def receive(endpoint, expected):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        endpoint.settimeout(max(0.01, deadline - time.monotonic()))
        packet, address = endpoint.recvfrom(2048)
        if address[2] == 4 or packet[14:22] != MAGIC:  # Never accept local PACKET_OUTGOING.
            continue
        if packet != expected or zlib.crc32(packet[14:-4]) != struct.unpack("!I", packet[-4:])[0]:
            raise RuntimeError("physical receive failed MAC/role/sequence/pattern/CRC check")
        return
    raise RuntimeError("physical receive timeout")


def preflight():
    left = Path("/sys/class/net/eth1")
    if ((left / "device").resolve().name != "2a040000.ethernet" or
            (left / "device/driver").resolve().name != "rk_gmac-dwmac"):
        raise RuntimeError("ETH2 is not the reviewed Linux GMAC1; do not touch ETH1/UP ownership")
    peers = [port for port in Path("/sys/class/net").iterdir()
             if (port / "device/driver").exists() and (port / "device/driver").resolve().name == "sr9900"]
    if len(peers) != 1 or peers[0].name == "eth0":
        raise RuntimeError("expected exactly one distinct SR9900 ETH3")
    right = peers[0]
    if "/1-1.4.1/" not in str((right / "device").resolve()):
        raise RuntimeError("SR9900 is not on the reviewed onboard ETH3 USB port")
    for port in (left, right):
        if (port / "carrier").read_text().strip() != "1":
            raise RuntimeError(f"no physical carrier on {port.name}")
        if (port / "speed").read_text().strip() != "100" or (port / "duplex").read_text().strip() != "full":
            raise RuntimeError("expected 100Mb/s full-duplex board loop")
    return left, right


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-board-loop", action="store_true", help="explicit isolated ETH2-to-ETH3 wiring confirmation")
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.count <= 10000:
        parser.error("count must be 1..10000")
    left, right = preflight()
    if not args.confirm_board_loop:
        print(json.dumps(dict(mode="read-only preflight", ports=[left.name, right.name])))
        return
    left_mac, right_mac = [bytes.fromhex((port / "address").read_text().strip().replace(":", "")) for port in (left, right)]
    results = []
    with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE)) as a, \
            socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE)) as b:
        a.bind((left.name, 0)); b.bind((right.name, 0))
        for length in (64, 1514):
            started = time.monotonic()
            for sequence in range(args.count):
                request = frame(right_mac, left_mac, 1, sequence, length)
                reply = frame(left_mac, right_mac, 2, sequence, length)
                if a.send(request) != length:
                    raise RuntimeError("short ETH2 send")
                receive(b, request)
                if b.send(reply) != length:
                    raise RuntimeError("short ETH3 send")
                receive(a, reply)
            result = dict(raw_frame_bytes_excluding_fcs=length, frames_each_direction=args.count,
                          bytes_each_direction=length * args.count, elapsed_s=time.monotonic() - started,
                          role_sequence_pattern_crc="PASS", result="PASS")
            results.append(result)
            print(json.dumps(result), flush=True)
    print(json.dumps(dict(result="LINUX PHYSICAL L2 PASS", up2_direct_drive=False,
                          ports=[left.name, right.name], results=results)), flush=True)


if __name__ == "__main__":
    main()
