#!/bin/bash
# Stage4 v4 verification: capture serial during reboot into maxcpus=7 kernel
PLINK="C:/Program Files/PuTTY/plink.exe"
LOG="I:/TL3572-EVM(Buildroot-2026.02)_Alpha_V1.1/stages/stage04-mica-mcs/worklog-20260916/logs/serial-verify-stage4-v4-maxcpus.txt"

# at t+8s: reboot the board via SSH
( sleep 8
  "$PLINK" -ssh -batch -hostkey "SHA256:60CU6EkU00yhkNXzA1B87ln0nyy0+A5Oaubdn7fYn44" -pw "" root@192.168.2.143 "reboot" >/dev/null 2>&1
  echo REBOOT_ISSUED
) &

# at t+170s: kill all plink (only the serial capture is left)
( sleep 170; taskkill //F //IM plink.exe 2>/dev/null; echo KILLER_DONE ) &

# capture serial, no input
"$PLINK" -serial COM7 -sercfg 115200,8,N,1,N < /dev/null > "$LOG" 2>&1
echo CAPTURE_END
