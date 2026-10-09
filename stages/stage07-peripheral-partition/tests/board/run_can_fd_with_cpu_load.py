#!/usr/bin/env python3
"""Reuse the bounded Linux CPU load, running the FD pair instead of classic."""
import run_can_irq_with_cpu_load as load
import run_can_fd_pair as fd

if __name__ == "__main__":
    load.irq = fd
    load.main()
