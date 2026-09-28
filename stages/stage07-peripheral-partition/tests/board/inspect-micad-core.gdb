# Addresses match only the original M6 micad core captured on 2026-09-28.
# Resolve relocated symbols again before inspecting a different core/boot.
set pagination off
thread 1
bt
x/gx 0x55788d4800
disassemble 0x55788c58a0,0x55788c5910
disassemble 0x55788c8940,0x55788c89d0
disassemble 0x55788c7da0,0x55788c7e40
quit
