"""Explicitly approved P3j-v2 window host transport. No automatic retries.
Phases preflight/upload/run/postflight are separate; run claims a permanent
LOCAL marker before its sole SSH invocation. Runner claims its BOARD marker.
Credentials come from POWERLINK_BOARD_PASSWORD, never from archived inputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import paramiko

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
STAGE=HERE.parents[1]
PREPARED=STAGE/'tests/powerlink-cycle-p3j-v2-20261104'
OLD=STAGE/'tests/powerlink-cycle-p3j-return-20261104'
RUNTIME=json.loads((PREPARED/'runtime-inputs.json').read_text())
ROOT=RUNTIME['board_root']
OLD_ROOT='/root/m7-powerlink-cycle-p3j-20261104'
SHA='4b4854157487a8ddfa07914c01efbe6c7215c1eed273f9e80e405f6b9c3d9c35'

def digest(data):return hashlib.sha256(data).hexdigest()
def save(name,value):
    with (HERE/name).open('x',encoding='utf-8',newline='\n') as out:
        json.dump(value,out,indent=2);out.write('\n')

def remote(client,code,name):
    _,out,err=client.exec_command('python3 -B -c '+shlex.quote(code))
    data,errors=out.read(),err.read();status=out.channel.recv_exit_status()
    with (HERE/name).open('xb') as log:log.write(data+errors+f'\nREAD_ONLY_EXIT={status}\n'.encode())
    if status:raise RuntimeError('read-only check failed; see '+name)
    return json.loads(data.decode().split('SNAPSHOT ',1)[1])

def verify_existing(sftp):
    baseline=json.loads((OLD/'baseline.json').read_text())
    for name,d in baseline['formal_files'].items():
        with sftp.open(name,'rb') as file:
            if digest(file.read())!=d:raise RuntimeError('formal file changed: '+name)
    expected=baseline['files']|{
        'ATTEMPTED':{'sha256':digest(baseline['marker'].encode())},
        'board-result.json':{'sha256':baseline['original_result_sha256']},
        'return-linux-20261104/return-result.json':{'sha256':digest((OLD/'return-result.json').read_bytes())},
    }
    for name,item in expected.items():
        with sftp.open(OLD_ROOT+'/'+name,'rb') as file:
            if digest(file.read())!=item['sha256']:raise RuntimeError('old window changed: '+name)

def verify_new(sftp):
    result={}
    for name,item in RUNTIME['files'].items():
        path=(REPO/item['path']).resolve();path.relative_to(REPO)
        data=path.read_bytes()
        if len(data)!=item['bytes'] or digest(data)!=item['sha256']:raise RuntimeError('local input changed: '+name)
        with sftp.open(ROOT+'/'+name,'rb') as file:received=file.read()
        result[name]={'bytes':len(received),'sha256':digest(received)}
        if received!=data:raise RuntimeError('board input readback mismatch: '+name)
    return result

READONLY="""
import sys,json
from pathlib import Path
sys.path.insert(0,'/root/m7-powerlink-cycle-p3j-20261104')
import run_powerlink_eth_probe as base
from run_powerlink_cycle_p3j_probe import linux_full
from powerlink_cycle_p3j_checks import original_clients
c=base.common
c.confirm_up_cpus_off()
original_clients(c.command('mcsctl','status'))
assert not list(Path('/dev').glob('ttyRPMSG*'))
assert not Path('/sys/module/m7_eth2_power_hold').exists()
assert c.command('uname','-r').strip()=='6.12.69-gf1b67c293213'
assert not int(Path('/proc/sys/kernel/tainted').read_text()) & 128
assert c.micad_state()['ActiveState']=='active'
linux_full(base)
assert not c.command('ip','-4','-o','addr','show','dev','eth1').strip()
assert not c.command('ip','route','show','dev','eth1').strip()
can=json.loads(c.command('ip','-j','link','show','type','can'))
assert len(can)==4 and all(x['operstate']=='DOWN' and 'UP' not in x['flags'] for x in can)
failed=c.command('systemctl','--failed','--no-legend','--plain')
assert not failed.strip()
report=dict(boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 micad=c.micad_state(),management=base.management(),peripherals=base.passive.snapshot(),
 clients=c.command('mcsctl','status'),taint=int(Path('/proc/sys/kernel/tainted').read_text()),
 failed_services=failed,can={x['ifname']:x['operstate'] for x in can},
 ethernet={p:c.command('ethtool',p) for p in ('eth1','eth2')},
 eth2_driver=str((base.DEVICE/'driver').resolve()),
 rpmsg=[],hold=False)
c.confirm_up_cpus_off()
print('SNAPSHOT '+json.dumps(report,sort_keys=True))
"""

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=('preflight','upload','run','postflight'))
    a=p.parse_args()
    client=paramiko.SSHClient();client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('192.168.2.141',username='root',password=os.environ['POWERLINK_BOARD_PASSWORD'],timeout=15,banner_timeout=30)
    try:
        with client.open_sftp() as s:
            verify_existing(s)
            if a.phase=='preflight':
                try:s.stat(ROOT)
                except FileNotFoundError:pass
                else:raise RuntimeError('new window already exists; do not overwrite/retry')
                save('preflight.json',remote(client,READONLY,'preflight.log'))
            elif a.phase=='upload':
                before=json.loads((HERE/'preflight.json').read_text())
                now=remote(client,READONLY,'before-upload.log')
                if now!=before:raise RuntimeError('baseline changed before upload')
                s.mkdir(ROOT)  # Must not exist. Never overwrite a previous window.
                for name,item in RUNTIME['files'].items():
                    data=(REPO/item['path']).read_bytes()
                    if len(data)!=item['bytes'] or digest(data)!=item['sha256']:raise RuntimeError('local input mismatch')
                    with s.open(ROOT+'/'+name,'wx') as file:file.write(data)
                receipt=dict(board='192.168.2.141',board_root=ROOT,client=RUNTIME['client'],
                    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
                    files=verify_new(s))
                save('board-input-sha256.json',receipt)
            elif a.phase=='run':
                receipt=json.loads((HERE/'board-input-sha256.json').read_text())
                if verify_new(s)!=receipt['files']:raise RuntimeError('uploaded inputs changed')
                now=remote(client,READONLY,'before-run.log')
                if now!=json.loads((HERE/'preflight.json').read_text()):raise RuntimeError('baseline changed before run')
                for name in ('ATTEMPTED','board-result.json','board-test.log'):
                    try:s.stat(ROOT+'/'+name)
                    except FileNotFoundError:pass
                    else:raise RuntimeError('window already attempted; NO retry')
                save('HOST_EXECUTION_ATTEMPTED.json',dict(source_commit=receipt['source_commit'],
                    board_root=ROOT,candidate_sha256=SHA,scope='new approved single v2 cycle'))
                command='set -Ce\ncd '+shlex.quote(ROOT)+'\npython3 -B -u run_powerlink_cycle_p3j_v2_probe.py --confirm-isolated-p3j-v2-cycle --sha256 '+SHA+' > board-test.log 2>&1'
                _,out,err=client.exec_command(command)
                data,errors=out.read(),err.read();status=out.channel.recv_exit_status()
                with (HERE/'ssh-execution.log').open('xb') as log:log.write(data+errors+f'\nBOARD_EXIT_CODE={status}\n'.encode())
                with s.open(ROOT+'/board-test.log','rb') as file:logdata=file.read()
                with (HERE/'board-test.log').open('xb') as log:log.write(logdata+f'\nBOARD_EXIT_CODE={status}\n'.encode())
                for remote_name,local_name in (('board-result.json','board-result.json'),('ATTEMPTED','ATTEMPTED.txt')):
                    with s.open(ROOT+'/'+remote_name,'rb') as file:data=file.read()
                    with (HERE/local_name).open('xb') as output:output.write(data)
                print(logdata.decode(errors='replace')[-5000:])
                if status:raise RuntimeError('physical window failed; NO retry/recovery; preserve resources')
            elif a.phase=='postflight':
                result=json.loads((HERE/'board-result.json').read_text())
                if not result['passed'] or not result['cleanup']:raise RuntimeError('failed window; no success-state assumption')
                if verify_new(s)!=json.loads((HERE/'board-input-sha256.json').read_text())['files']:raise RuntimeError('new inputs changed')
                now=remote(client,READONLY,'postflight.log');save('postflight.json',now)
                if now!=json.loads((HERE/'preflight.json').read_text()):raise RuntimeError('postflight baseline drift')
        print(a.phase+' PASS; no automatic second invocation')
    finally:client.close()

if __name__=='__main__':main()
