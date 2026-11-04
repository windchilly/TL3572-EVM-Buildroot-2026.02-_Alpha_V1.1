"""One human-approved P3j hardware window; readonly inventory is separate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import paramiko

repo = Path.cwd().resolve()
stage = repo / 'stages/stage07-peripheral-partition'
evidence = stage / 'tests/powerlink-cycle-p3j-hw-20261104'
prepared = stage / 'tests/powerlink-cycle-p3j-runner-20261104'
manifest = json.loads((prepared / 'runtime-inputs.json').read_text())
root = manifest['board_root']
assert root == '/root/m7-powerlink-cycle-p3j-20261104'
assert len(manifest['files']) == 19
sha = '4b4854157487a8ddfa07914c01efbe6c7215c1eed273f9e80e405f6b9c3d9c35'
parser = argparse.ArgumentParser(__doc__)
parser.add_argument('action', choices=('preflight', 'run', 'postflight', 'capture'))
args = parser.parse_args()
evidence.mkdir(exist_ok=True)
for line in (prepared / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    path = (repo / name).resolve(); path.relative_to(repo)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
for name, item in manifest['files'].items():
    path = (repo / item['path']).resolve(); path.relative_to(repo)
    data = path.read_bytes()
    assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], name
print('LOCAL fixed 727-SHA archive and 19 runtime inputs PASS', flush=True)
c = paramiko.SSHClient(); c.load_system_host_keys()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect('192.168.2.141', username='root', password=os.environ['POWERLINK_BOARD_PASSWORD'], timeout=12)
    if args.action == 'capture':
        result = json.loads((evidence / 'board-result.json').read_text())
        assert result['passed'] is True and result['cleanup'] is True
        proof = result['private_stopped']
        for key, size in (('snapshot',1504),('cycle',608)):
            raw = bytes.fromhex(proof[key + '_hex'])
            assert len(raw) == size and hashlib.sha256(raw).hexdigest() == proof[key + '_sha256']
            with (evidence / ('private-' + key + '.hex')).open('x') as out: out.write(raw.hex() + '\n')
        with c.open_sftp() as s:
            with s.open(root + '/ATTEMPTED', 'rb') as remote: marker = remote.read()
        with (evidence / 'ATTEMPTED.txt').open('xb') as out: out.write(marker)
        print('Actual runner stopped-core 1504B+608B raw evidence and permanent ATTEMPTED archived; no extra MMIO/commands', flush=True)
        sys.exit(0)
    if args.action != 'run':
        command = '''set -e
uname -a
uptime
cat /proc/sys/kernel/random/boot_id
cat /sys/devices/system/cpu/online
cat /proc/sys/kernel/tainted
systemctl show micad -p ActiveState -p MainPID -p NRestarts
mcsctl status
ip -brief address
ip route
ethtool eth1
ethtool eth2
lsmod
sha256sum /usr/libexec/m7/up_log_reader.py
sha256sum /root/m7-eth-direct-20261010/m7_eth2_power_hold.ko
cat /etc/mica/tl3572-up-a.conf /etc/mica/tl3572-up-b.conf
sha256sum /lib/firmware/rk3572-uniproton-up-a.elf /lib/firmware/rk3572-uniproton-up-b.elf
ls -l /dev/ttyRPMSG* 2>/dev/null || true
systemctl --failed --no-pager
PYTHONDONTWRITEBYTECODE=1 python3 -c "import sys; sys.path.insert(0,'/root/m7-powerlink-mn-p3f-fixed-20261023'); import run_can_direct_pair as c; c.confirm_up_cpus_off()"
'''
        if args.action == 'preflight': command += 'test ! -e ' + shlex.quote(root) + '\n'
        with (evidence / (args.action + '.log')).open('xb') as log:
            _, out, err = c.exec_command(command, timeout=40)
            data, errors = out.read(), err.read(); status = out.channel.recv_exit_status()
            log.write(data + errors + f'\nREAD_ONLY_EXIT={status}\n'.encode())
        print((data + errors).decode(errors='replace'), flush=True)
        sys.exit(status)
    assert (evidence / 'preflight.log').read_bytes().endswith(b'READ_ONLY_EXIT=0\n')
    for name in ('board-test.log', 'board-result.json', 'board-input-sha256.json'):
        assert not (evidence / name).exists(), 'refuse any rerun/overwrite: ' + name
    with c.open_sftp() as s:
        try: s.stat(root)
        except FileNotFoundError: s.mkdir(root)
        else: raise RuntimeError('P3j root exists; refuse upload/overwrite/rerun')
        receipt = dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
            board='192.168.2.141', board_root=root, client=manifest['client'], files={})
        for name, item in manifest['files'].items():
            target = root + '/' + name
            s.put(str(repo / item['path']), target)
            with s.open(target, 'rb') as remote: data = remote.read()
            actual = hashlib.sha256(data).hexdigest()
            assert actual == item['sha256'] and len(data) == item['bytes'], name
            receipt['files'][name] = dict(bytes=len(data), sha256=actual)
        with (evidence / 'board-input-sha256.json').open('x') as out: json.dump(receipt, out, indent=2)
        print('BOARD upload/readback 19 exact files PASS; execute ONCE now', flush=True)
        with (evidence / 'board-test.log').open('xb') as log:
            ch = c.get_transport().open_session(); ch.set_combine_stderr(True)
            ch.exec_command('PYTHONDONTWRITEBYTECODE=1 python3 -u ' + root +
                '/run_powerlink_cycle_p3j_probe.py --confirm-isolated-p3j-cycle --sha256 ' + sha)
            while True:
                if ch.recv_ready():
                    data = ch.recv(65536); log.write(data); log.flush()
                    print(data.decode(errors='replace'), end='', flush=True)
                elif ch.exit_status_ready(): break
                else: time.sleep(.1)
            status = ch.recv_exit_status(); log.write(f'\nBOARD_EXIT_CODE={status}\n'.encode())
        try:
            with s.open(root + '/board-result.json', 'rb') as remote: data = remote.read()
            json.loads(data)
            with (evidence / 'board-result.json').open('xb') as out: out.write(data)
        except FileNotFoundError: print('No board-result.json; no empty placeholder created', flush=True)
        print('P3j single approved hardware window EXIT=' + str(status), flush=True)
        sys.exit(status)
finally: c.close()
