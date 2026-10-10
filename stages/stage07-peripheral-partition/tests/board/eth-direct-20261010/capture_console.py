"""Passive UART0 capture: never send, with DTR/RTS deasserted before open."""
import argparse
from pathlib import Path
import time

import serial

parser = argparse.ArgumentParser()
parser.add_argument('--port', default='COM7')
parser.add_argument('--baud', type=int, default=115200)
parser.add_argument('--seconds', type=int, default=900)
parser.add_argument('--wake-console', action='store_true',
                    help='Send one carriage return to UART0 debug console only')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
port = serial.Serial(port=None, baudrate=args.baud, timeout=0.2)
port.dtr = False
port.rts = False
port.port = args.port
port.open()
print(f'CAPTURE {args.port} {args.baud} 8N1; {args.output}', flush=True)
total = 0
try:
    with args.output.open('xb') as output:
        if args.wake_console:
            port.write(b'\r')
            port.flush()
            print('UART0 debug console: one carriage return sent', flush=True)
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            data = port.read(max(port.in_waiting, 1))
            if data:
                output.write(data)
                output.flush()
                total += len(data)
                print(data.decode('utf-8', errors='replace'), end='', flush=True)
finally:
    port.close()
    print(f'\nCAPTURE CLOSED bytes={total}; wake_console={args.wake_console}', flush=True)
