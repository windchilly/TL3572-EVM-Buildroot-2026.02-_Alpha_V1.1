#!/bin/bash
# Stage4 CPU reservation - serial session 1:
# clean up micad/module via SSH then reboot, catch U-Boot autoboot via CR spam,
# printenv bootargs/bootcmd/bootdelay, then get killed by timer.
PLINK="C:/Program Files/PuTTY/plink.exe"
LOG="I:/TL3572-EVM(Buildroot-2026.02)_Alpha_V1.1/stages/stage04-mica-mcs/worklog-20260916/logs/serial-cpu-reserve-session1.txt"

# killer: after 80s kill all plink (only the serial one is left by then)
( sleep 80; taskkill //F //IM plink.exe 2>/dev/null; echo KILLER_DONE ) &

# at t+6s: stop micad, rmmod, reboot the board via SSH
( sleep 6
  "$PLINK" -ssh -batch -hostkey "SHA256:60CU6EkU00yhkNXzA1B87ln0nyy0+A5Oaubdn7fYn44" -pw "" root@192.168.2.143 "systemctl stop micad; rmmod mcs_km; sync; reboot" >/dev/null 2>&1
  echo REBOOT_ISSUED
) &

# serial feeder: CR every 0.7s for 70 rounds (~49s) to catch autoboot,
# then printenv commands
( for i in $(seq 1 70); do printf '\r'; sleep 0.7; done
  sleep 2
  printf 'printenv bootargs\r'
  sleep 4
  printf 'printenv bootcmd\r'
  sleep 4
  printf 'printenv bootdelay\r'
  sleep 4
) | "$PLINK" -serial COM7 -sercfg 115200,8,N,1,N > "$LOG" 2>&1

echo FEEDER_DONE
