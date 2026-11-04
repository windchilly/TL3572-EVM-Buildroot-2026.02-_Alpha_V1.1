"""Host transport for NEW approved P3j stopped-only Linux return, no cycle IO."""
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
EVIDENCE=Path(__file__).resolve().parent
STAGE=EVIDENCE.parents[1];REPO=STAGE.parents[1]
OLD=STAGE/'tests/powerlink-cycle-p3j-hw-20261104'
ROOT='/root/m7-powerlink-cycle-p3j-20261104'
WORK=ROOT+'/return-linux-20261104'
INVENTORY='''set -eu
uname -a
uptime
cat /proc/sys/kernel/random/boot_id
cat /sys/devices/system/cpu/online
cat /proc/sys/kernel/tainted
systemctl show micad -p MainPID -p NRestarts -p ActiveState
mcsctl status
ip -brief address
ip route
ethtool eth1 || true
ethtool eth2
lsmod
sha256sum /lib/firmware/rk3572-uniproton-up-a.elf /lib/firmware/rk3572-uniproton-up-b.elf
cat /etc/mica/tl3572-up-a.conf /etc/mica/tl3572-up-b.conf
ls -l /dev/ttyRPMSG* 2>/dev/null || true
systemctl --failed --no-pager
PYTHONDONTWRITEBYTECODE=1 python3 -c "import sys;sys.path.insert(0,'/root/m7-powerlink-cycle-p3j-20261104');import run_can_direct_pair as c;c.confirm_up_cpus_off()"
'''
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('preflight','run','postflight'))
    p.add_argument('--confirm-stopped-p3j-linux-return',action='store_true');a=p.parse_args()
    if a.action=='run' and not a.confirm_stopped_p3j_linux_return:raise RuntimeError('new explicit stopped-only return approval required')
    sys.path.insert(0,str(STAGE/'tests'))
    from verify_powerlink_cycle_p3j_hw_checkpoint import hardware_evidence,verify_manifest
    verify_manifest();hardware_evidence()
    client=paramiko.SSHClient();client.load_system_host_keys();client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.2.141',username='root',password=os.environ['POWERLINK_BOARD_PASSWORD'],timeout=12)
        if a.action!='run':
            with (EVIDENCE/(a.action+'.log')).open('xb') as log:
                _,out,err=client.exec_command(INVENTORY,timeout=40)
                data,errors=out.read(),err.read();status=out.channel.recv_exit_status()
                log.write(data+errors+('\nREAD_ONLY_EXIT=%d\n'%status).encode())
            print((data+errors).decode(errors='replace'));sys.exit(status)
        if not (EVIDENCE/'preflight.log').read_text().rstrip().endswith('READ_ONLY_EXIT=0'):raise RuntimeError('preflight not complete')
        if any((EVIDENCE/name).exists() for name in ('board-return.log','return-result.json','board-input-sha256.json')):
            raise RuntimeError('local return already attempted; NO overwrite/retry')
        old_result=json.loads((OLD/'board-result.json').read_text())
        before=json.loads(next(line[7:] for line in (OLD/'board-test.log').read_text().splitlines() if line.startswith('BEFORE ')))
        baseline=dict(before=before,completion=old_result['completion'],heap_before=old_result['heap_before'],
            retained=json.loads((OLD/'retained-private.json').read_text()),marker=(OLD/'ATTEMPTED.txt').read_text(),
            original_result_sha256=hashlib.sha256((OLD/'board-result.json').read_bytes()).hexdigest(),
            files=json.loads((OLD/'board-input-sha256.json').read_text())['files'],formal_files={})
        with client.open_sftp() as s:
            try:s.stat(WORK)
            except FileNotFoundError:pass
            else:raise RuntimeError('fixed return work already exists; NO overwrite/retry')
            try:s.stat(ROOT+'/LINUX_RETURN_ATTEMPTED')
            except FileNotFoundError:pass
            else:raise RuntimeError('permanent return marker already consumed')
            for name in ('/lib/firmware/rk3572-uniproton-up-a.elf','/lib/firmware/rk3572-uniproton-up-b.elf',
                    '/etc/mica/tl3572-up-a.conf','/etc/mica/tl3572-up-b.conf',
                    '/usr/libexec/m7/up_log_reader.py','/root/m7-eth-direct-20261010/m7_eth2_power_hold.ko'):
                with s.open(name,'rb') as source:data=source.read()
                baseline['formal_files'][name]=hashlib.sha256(data).hexdigest()
            expected={'/lib/firmware/rk3572-uniproton-up-a.elf':'9c5e55a268d9f59e180998848b79297945f2b7eb92ba6512d3869e9cd9ae89b8',
                '/lib/firmware/rk3572-uniproton-up-b.elf':'3357eb979263332a7a4ee606e90fbec90ac0363977a908c5c3a6862c250edde4',
                '/usr/libexec/m7/up_log_reader.py':'2066c5bf6d6a7c2507f9bf9243ece7b767582079971096db836c1c6bccec6f14',
                '/root/m7-eth-direct-20261010/m7_eth2_power_hold.ko':'b071d4346d0d3310e22ffd2d1ae9ce2dcc1f3a2784ae94efd05a0798a546fc8d'}
            if any(baseline['formal_files'][k]!=v for k,v in expected.items()):raise RuntimeError('original formal/hold/logger SHA mismatch')
            with (EVIDENCE/'baseline.json').open('x',encoding='utf-8',newline='\n') as out:json.dump(baseline,out,indent=2);out.write('\n')
            paths=[STAGE/'tests/board/return_powerlink_cycle_p3j_linux.py',STAGE/'tests/board/powerlink_cycle_p3j_tcb_checks.py',EVIDENCE/'baseline.json']
            s.mkdir(WORK);receipt=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                board='192.168.2.141',board_root=WORK,scope='stopped-only return; no UP start/stop/cycle',files={})
            for path in paths:
                s.put(str(path),WORK+'/'+path.name)
                with s.open(WORK+'/'+path.name,'rb') as source:data=source.read()
                digest=hashlib.sha256(data).hexdigest()
                if data!=path.read_bytes():raise RuntimeError('new return input readback mismatch')
                receipt['files'][path.name]=dict(path=path.relative_to(REPO).as_posix(),bytes=len(data),sha256=digest)
            with (EVIDENCE/'board-input-sha256.json').open('x') as out:json.dump(receipt,out,indent=2)
            sha=receipt['files']['baseline.json']['sha256']
            with (EVIDENCE/'board-return.log').open('xb') as log:
                ch=client.get_transport().open_session();ch.set_combine_stderr(True)
                ch.exec_command('PYTHONDONTWRITEBYTECODE=1 python3 -u '+WORK+'/return_powerlink_cycle_p3j_linux.py --confirm-stopped-p3j-linux-return --baseline-sha256 '+sha)
                while True:
                    if ch.recv_ready():data=ch.recv(65536);log.write(data);log.flush();print(data.decode(errors='replace'),end='',flush=True)
                    elif ch.exit_status_ready():break
                    else:time.sleep(.1)
                status=ch.recv_exit_status();log.write(('\nBOARD_RETURN_EXIT=%d\n'%status).encode())
            for remote,local in ((WORK+'/return-result.json','return-result.json'),(ROOT+'/LINUX_RETURN_ATTEMPTED','LINUX_RETURN_ATTEMPTED.txt')):
                try:
                    with s.open(remote,'rb') as source:data=source.read()
                except FileNotFoundError:print('Not created: '+remote);continue
                with (EVIDENCE/local).open('xb') as out:out.write(data)
            sys.exit(status)
    finally:client.close()
