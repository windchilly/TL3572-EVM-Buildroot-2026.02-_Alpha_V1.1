#!/usr/bin/env python3
"""Read-only MCS PSCI query: succeed only when every selected UP CPU is OFF."""

import argparse
import fcntl
import os
import struct
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cpu", type=int, nargs="+", choices=(4, 5))
    args = parser.parse_args()
    all_off = True
    fd = os.open("/dev/mcs", os.O_RDONLY)
    try:
        for cpu in args.cpu:
            # Match MCS struct cpu_info and _IOW('A', 2, int).
            info = struct.pack("<I4xQ", cpu, 0)
            try:
                fcntl.ioctl(fd, 0x40044102, info)
                print(f"CPU{cpu}: PSCI OFF confirmed")
            except OSError as error:
                all_off = False
                print(f"CPU{cpu}: OFF not confirmed: {error}")
    finally:
        os.close(fd)
    return 0 if all_off else 1


if __name__ == "__main__":
    sys.exit(main())
