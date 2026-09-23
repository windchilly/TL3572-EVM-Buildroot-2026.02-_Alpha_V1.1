#!/usr/bin/env python3
"""Assemble a TL3572 RKFW update.img around an AFPTool-rebuilt firmware.img.

Layout (reverse-engineered 2026-09-16, stage 3):
  0x00..0x66   RKFW header (vendor copy, only fw_size u32@0x25 updated)
  0x66..fw_off vendor boot area (kept byte-identical)
  fw_off..     AFP firmware.img (RKAF magic, AFPTool -pack output)
  last 32      whole-file MD5 lowercase hex
"""
import struct, hashlib, sys

vendor_path, fw_path, out_path = sys.argv[1:4]

with open(vendor_path, 'rb') as f:
    vendor = f.read()

hdr = bytearray(vendor[:0x66])
boot_off = struct.unpack_from('<I', hdr, 0x19)[0]
fw_off   = struct.unpack_from('<I', hdr, 0x21)[0]
old_fw   = struct.unpack_from('<I', hdr, 0x25)[0]

# Sanity: vendor tail MD5 and fw_size must validate our parsing.
body, md5tail = vendor[:-32], vendor[-32:]
assert md5tail == hashlib.md5(body).hexdigest().encode(), 'vendor md5 mismatch'
assert boot_off == 0x66, hex(boot_off)
assert old_fw == len(vendor) - 32 - fw_off, (old_fw, len(vendor) - 32 - fw_off)

boot_area = vendor[boot_off:fw_off]
with open(fw_path, 'rb') as f:
    fw = f.read()
assert fw[:4] == b'RKAF', fw[:4]

struct.pack_into('<I', hdr, 0x25, len(fw))
out = bytes(hdr) + boot_area + fw
md5 = hashlib.md5(out).hexdigest().encode()

with open(out_path, 'wb') as f:
    f.write(out)
    f.write(md5)

print('boot_area=%d fw=%d total=%d' % (len(boot_area), len(fw), len(out) + 32))
print('fw_size@0x25=0x%x' % len(fw))
print('md5=%s' % md5.decode())
