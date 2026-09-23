#!/bin/bash
# Probe COM7 serial console state after stage4 update.img flash
PLINK="C:/Program Files/PuTTY/plink.exe"
LOG="I:/TL3572-EVM(Buildroot-2026.02)_Alpha_V1.1/stages/stage04-mica-mcs/worklog-20260916/logs/serial-probe-postflash.txt"

( sleep 14; taskkill //F //IM plink.exe 2>/dev/null; echo KILLER_DONE ) &

"$PLINK" -serial COM7 -sercfg 115200,8,N,1,N < /dev/null > "$LOG" 2>&1
echo CAPTURE_END
