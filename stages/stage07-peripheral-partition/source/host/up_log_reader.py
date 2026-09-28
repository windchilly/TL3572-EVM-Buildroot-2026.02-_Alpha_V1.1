#!/usr/bin/env python3
"""Read one UniProton instance's reserved-memory boot log without using a UART."""

import argparse
import logging
from logging.handlers import RotatingFileHandler
import mmap
import os
from pathlib import Path
import struct
import time


MAGIC = 0x55374C47
VERSION = 1
REGION_SIZE = 0x200000
HEADER_SIZE = 0x1000
RECORD_SIZE = 512
RECORD_COUNT = (REGION_SIZE - HEADER_SIZE) // RECORD_SIZE
TEXT_SIZE = RECORD_SIZE - 16
CLIENTS = {"up-a": (4, 0x7B000000), "up-b": (5, 0x7C000000)}


def read_header(region, expected_cpu):
    magic, version, cpu, record_size, count, boot, seq, truncated = struct.unpack_from(
        "<8I", region, 0
    )
    if (magic, version, cpu, record_size, count) != (
        MAGIC, VERSION, expected_cpu, RECORD_SIZE, RECORD_COUNT
    ):
        return None
    return boot, seq, truncated


def read_new_records(region, last_seq, current_seq):
    first_seq = max(last_seq + 1, current_seq - RECORD_COUNT + 1, 1)
    records = []
    for seq in range(first_seq, current_seq + 1):
        offset = HEADER_SIZE + ((seq - 1) % RECORD_COUNT) * RECORD_SIZE
        # Device memory on arm64 cannot be read with unaligned accesses.
        record = bytes(region[offset : offset + RECORD_SIZE])
        committed, boot, length, _ = struct.unpack_from("<4I", record, 0)
        if committed != seq or length > TEXT_SIZE:
            continue
        data = record[16 : 16 + length]
        if int.from_bytes(region[offset : offset + 4], "little") != seq:
            continue
        records.append((seq, boot, data.decode("utf-8", errors="replace")))
    return first_seq, records


def console_emit(message):
    print(message, end="" if message.endswith("\n") else "\n", flush=True)


class FileEmitter:
    def __init__(self, output_dir, client):
        output_dir.mkdir(mode=0o750, parents=True, exist_ok=True)
        self.handler = RotatingFileHandler(
            output_dir / f"{client}.log", maxBytes=4 * 1024 * 1024,
            backupCount=3, encoding="utf-8",
        )
        self.handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        self.client = client

    def __call__(self, message):
        record = logging.LogRecord(
            f"m7-up-log-{self.client}", logging.INFO, "", 0,
            message.rstrip("\n"), (), None,
        )
        self.handler.handle(record)

    def close(self):
        self.handler.close()


def monitor(region, client, expected_cpu, follow, interval, emit=console_emit):
    last_seq = 0
    last_boot = None
    last_truncated = 0
    while True:
        header = read_header(region, expected_cpu)
        if header is not None:
            boot, current_seq, truncated = header
            if current_seq < last_seq:
                last_seq = 0  # Memory was reset or the sequence wrapped.
            if boot != last_boot:
                emit(f"[{client}] boot={boot} seq={current_seq}")
                last_boot = boot
            if current_seq > last_seq:
                first_seq, records = read_new_records(region, last_seq, current_seq)
                if first_seq > last_seq + 1:
                    emit(f"[{client}] overwritten={first_seq - last_seq - 1}")
                for seq, record_boot, message in records:
                    emit(f"[{client} boot={record_boot} seq={seq}] {message}")
                last_seq = current_seq
            if truncated != last_truncated:
                emit(f"[{client}] truncated_total={truncated}")
                last_truncated = truncated
        elif not follow:
            raise RuntimeError(f"{client}: log header not initialized")
        if not follow:
            return
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True, choices=CLIENTS)
    parser.add_argument("--follow", action="store_true")
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--source", default="/dev/mem", help="physical memory device or a 2 MiB test image")
    parser.add_argument("--output-dir", type=Path, help="persistent directory for per-instance rotating logs")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")
    if args.output_dir is not None and not args.output_dir.is_absolute():
        parser.error("--output-dir must be an absolute path")

    cpu, base = CLIENTS[args.client]
    offset = base if args.source == "/dev/mem" else 0
    fd = os.open(args.source, os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, REGION_SIZE, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=offset) as region:
            emit = console_emit if args.output_dir is None else FileEmitter(args.output_dir, args.client)
            try:
                monitor(region, args.client, cpu, args.follow, args.interval, emit)
            finally:
                if isinstance(emit, FileEmitter):
                    emit.close()
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
