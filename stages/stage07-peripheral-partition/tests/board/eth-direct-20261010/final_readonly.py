"""Post-failure safety inventory only; no load/unload/PM/UP lifecycle operations."""
import json
from pathlib import Path
import sys
sys.path.insert(0, '/root/m7-eth-direct-20261010')
import run_can_direct_pair as common
import run_integrated_passive as passive

common.confirm_up_cpus_off()
print('MCS', common.command('mcsctl', 'status'))
print('MICAD', json.dumps(common.micad_state()))
print('BOOT', Path('/proc/sys/kernel/random/boot_id').read_text().strip())
print('KERNEL_TAINT', Path('/proc/sys/kernel/tainted').read_text().strip())
print('MODULES', common.command('lsmod'))
print('POWER_HOLD_INITSTATE', Path('/sys/module/m7_eth2_power_hold/initstate').read_text().strip())
print('RPMSG_ENDPOINTS', list(map(str, Path('/dev').glob('ttyRPMSG*'))))
print('ETH1', common.command('ip', '-br', 'addr', 'show', 'dev', 'eth0'))
print('ROUTE', common.command('ip', 'route'))
print('ETH2_OWNER', Path('/sys/class/net/eth1/device/driver').resolve())
print('ETH2/3_LINK', [dict(port=p, carrier=Path(f'/sys/class/net/{p}/carrier').read_text().strip(),
                             speed=Path(f'/sys/class/net/{p}/speed').read_text().strip()) for p in ('eth1', 'eth2')])
print('INDUSTRIAL_SNAPSHOT', json.dumps(passive.snapshot(), sort_keys=True))
print('FAILED_UNITS', common.command('systemctl', '--failed', '--no-legend', '--plain'))
print('NO forced unload, module retry, controller handoff, network transmit, reboot or flash')
