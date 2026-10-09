"""Offline compare the latest validated single-interface IRQ ELFs and old integration."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from audit_integrated_mmu import audit

firmware = Path(__file__).resolve().parents[3] / 'firmware'
results = []
for prefix in ('tl3572-m7-can-irq', 'tl3572-m7-can-fd4', 'tl3572-m7-rs232-115200',
               'tl3572-m7-rs485-115200', 'tl3572-m7-integrated'):
    for role in ('a', 'b'):
        image = firmware / f'{prefix}-up-{role}.elf'
        results.append(dict(**audit(image), sha256=hashlib.sha256(image.read_bytes()).hexdigest()))
print(json.dumps(results, indent=2))
