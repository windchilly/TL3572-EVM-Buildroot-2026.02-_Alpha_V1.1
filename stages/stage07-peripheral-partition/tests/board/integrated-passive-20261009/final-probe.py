import json
from pathlib import Path
import sys
sys.path.insert(0, '/root/m7-integrated-20261009')
import run_integrated_passive as runner
print('READ-ONLY FINAL CHECK; no run command, unbind, controller writes or lifecycle operation')
print(runner.common.command('mcsctl', 'status'))
runner.common.confirm_up_cpus_off()
print('MICAD', json.dumps(runner.common.micad_state()))
print('BOOT_ID', Path('/proc/sys/kernel/random/boot_id').read_text().strip())
print('RPMSG_ENDPOINTS', list(map(str, Path('/dev').glob('ttyRPMSG*'))))
print('SNAPSHOT', json.dumps(runner.snapshot(), sort_keys=True))
print('FAILED_UNITS', runner.common.command('systemctl', '--failed', '--no-legend', '--plain'))
print('ETH1', runner.common.command('ip', '-br', 'link', 'show', 'dev', 'eth0'))
pid = int(runner.common.micad_state()['MainPID'])
print('MICAD_EXE', Path(f'/proc/{pid}/exe').resolve())
print('MICAD_FD_COUNT', len(runner.handles(pid)))
