#!/usr/bin/env python3
"""Offline revalidation of saved RS485 evidence, ELF hashes and resource restoration."""
import hashlib
import json
from pathlib import Path
import struct
import sys

stage = Path(__file__).resolve().parents[1]
folder = stage / "tests/board/rs485-20261009"
sys.path.insert(0, str(stage / "tests/board"))
import run_rs485_pair as runner


def main():
    for name, baud in (("run-01-115200.log", 115200), ("run-02-38400.log", 38400),
                       ("run-03-9600.log", 9600), ("run-04-cpu-load.log", 115200),
                       ("run-05-reverse-stop.log", 115200)):
        text = (folder / name).read_text(encoding="utf-8")
        runner.validate_result(text, text, baud)
        assert f"OVERALL PASS RS485 baud={baud}" in text
        assert "CLEANUP PASS temporary clients removed; UART1/2 rebound; micad unchanged" in text
        assert "RESOURCE RESTORE PASS" in text
        assert text.count("PSCI OFF confirmed") == 4
        assert "Traceback" not in text and "direct FAIL" not in text
        print(f"ARCHIVED HARDWARE PASS {name}")
    assert "CPU LOAD CLEANUP PASS" in (folder / "run-04-cpu-load.log").read_text()
    assert "stop=('up-a-m7-rs485-115200', 'up-b-m7-rs485-115200')" in (folder / "run-05-reverse-stop.log").read_text()
    before = json.loads((folder / "resources-before.json").read_text())
    after = json.loads((folder / "final-resource-snapshot.json").read_text())
    for field in ("registers", "controllers", "micad", "boot_id"):
        assert before[field] == after[field], f"baseline changed: {field}"
    assert "m7-rs485" not in after["mcs_status"] and after["mcs_status"].count("Offline") == 2
    assert (folder / "build-repro.log").read_text().count("RUNTIME IMAGE REPRO PASS") == 6
    assert (folder / "build-inputs.log").read_text().count("RUNTIME IMAGE HASH/CMP PASS") == 6
    assert "RS232 codec PASS" in (folder / "build-first.log").read_text()
    state = (folder / "final-board-state.log").read_text()
    for path in sorted((stage / "firmware").glob("tl3572-m7-rs485-*.elf")):
        data = path.read_bytes()
        assert data[:6] == b"\x7fELF\x02\x01" and struct.unpack_from("<H", data, 18)[0] == 183
        digest = hashlib.sha256(data).hexdigest()
        assert f"{digest}  /root/m7-rs485-20261009/{path.name}" in state
        assert digest in (folder / "build-inputs.log").read_text()
        print(f"BOARD ELF HASH PASS {path.name} {digest}")
    entries = [line for line in (stage / "firmware/SHA256SUMS").read_text().splitlines() if line.strip()]
    for line in entries:
        digest, relative = line.split("  ", 1)
        assert hashlib.sha256((stage / "firmware" / relative).read_bytes()).hexdigest() == digest
    print(f"FIRMWARE MANIFEST PASS {len(entries)} entries")
    print("FINAL RESOURCE/BOOT/DAEMON IDENTICAL; FIVE PAIR/RESTORE/CLEANUP PASSES; SIX RUNTIME IMAGES MATCH")


if __name__ == "__main__":
    main()
