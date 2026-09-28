#!/usr/bin/env python3
"""Verify bidirectional physical CAN traffic between two Linux CAN interfaces."""

import argparse
import select
import socket
import struct
import time


CAN_RAW_FILTER = 1
CAN_RAW_FD_FRAMES = 5
CANFD_BRS = 0x01
CAN_SFF_MASK = 0x7FF
CLASSIC_FRAME = struct.Struct("=IB3x8s")
FD_FRAME = struct.Struct("=IBB2x64s")


def open_socket(interface, can_id, fd):
    channel = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    channel.setsockopt(socket.SOL_CAN_RAW, CAN_RAW_FILTER, struct.pack("=II", can_id, CAN_SFF_MASK))
    if fd:
        channel.setsockopt(socket.SOL_CAN_RAW, CAN_RAW_FD_FRAMES, 1)
    channel.settimeout(1.0)
    channel.bind((interface,))
    return channel


def payload(marker, sequence, size):
    prefix = marker + sequence.to_bytes(4, "big")
    return (prefix + bytes((sequence + offset) & 0xFF for offset in range(size - len(prefix))))[:size]


def encode(can_id, marker, sequence, fd):
    if fd:
        data = payload(marker, sequence, 64)
        return FD_FRAME.pack(can_id, len(data), CANFD_BRS, data), data
    data = payload(marker, sequence, 8)
    return CLASSIC_FRAME.pack(can_id, len(data), data), data


def decode(frame, fd):
    if fd:
        can_id, length, flags, data = FD_FRAME.unpack(frame)
        return can_id & CAN_SFF_MASK, data[:length], flags
    can_id, length, data = CLASSIC_FRAME.unpack(frame)
    return can_id & CAN_SFF_MASK, data[:length], 0


def direction(tx_name, rx_name, can_id, marker, count, fd, timeout):
    tx = open_socket(tx_name, can_id, fd)
    rx = open_socket(rx_name, can_id, fd)
    try:
        start = time.monotonic()
        for sequence in range(count):
            frame, expected = encode(can_id, marker, sequence, fd)
            tx.send(frame)
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"{rx_name} missed sequence {sequence}")
                ready, _, _ = select.select([rx], [], [], remaining)
                if not ready:
                    raise TimeoutError(f"{rx_name} missed sequence {sequence}")
                received_id, received, flags = decode(rx.recv(FD_FRAME.size if fd else CLASSIC_FRAME.size), fd)
                if received_id != can_id:
                    continue
                if received != expected:
                    raise ValueError(f"{rx_name} data mismatch at sequence {sequence}")
                if fd and not flags & CANFD_BRS:
                    raise ValueError(f"{rx_name} received FD frame without BRS at sequence {sequence}")
                break
        elapsed = time.monotonic() - start
        print(f"PASS {tx_name}->{rx_name}: {count}/{count} frames, id=0x{can_id:03x}, elapsed={elapsed:.3f}s")
    finally:
        tx.close()
        rx.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first")
    parser.add_argument("second")
    parser.add_argument("--count", type=int, default=256)
    parser.add_argument("--fd", action="store_true")
    parser.add_argument("--timeout", type=float, default=0.5)
    args = parser.parse_args()
    if args.count < 1 or args.timeout <= 0:
        parser.error("count and timeout must be positive")
    mode = "CAN FD+BRS" if args.fd else "Classic CAN"
    print(f"Testing {mode}: {args.first}<->{args.second}")
    direction(args.first, args.second, 0x321, b"A", args.count, args.fd, args.timeout)
    direction(args.second, args.first, 0x456, b"B", args.count, args.fd, args.timeout)
    print(f"PASS {mode}: bidirectional physical path verified")


if __name__ == "__main__":
    main()
