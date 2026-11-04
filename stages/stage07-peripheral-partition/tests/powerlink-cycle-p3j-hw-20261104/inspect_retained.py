"""Read-only retained P3j window. No stop/rebind/module/TTY writes or retry.
Reads small private metadata only, after independent CPU4/5 OFF proof.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import time
import paramiko
EVIDENCE=Path(__file__).resolve().parent
ROOT='/root/m7-powerlink-cycle-p3j-20261104'
CODE=r'''
import json,struct,sys
from pathlib import Path
sys.path.insert(0,'/root/m7-powerlink-cycle-p3j-20261104')
import run_can_direct_pair as c
import read_powerlink_cycle_p3j_snapshot as p
from integrated_mmu_resources import read_reserved_dram
c.confirm_up_cpus_off()
s=p.image_symbols(p.IMAGE);private=p.private_reader(s)
report=p.completed(private)
report['heap']=p.heap(private,s,'STOPPED')
ptr=struct.unpack('<Q',private('g_tskCbArray'))[0]
maximum=struct.unpack('<I',private('g_tskMaxNum'))[0]
if maximum>=64 or not 0x7c200000<=ptr<=0x7ca00000-(maximum+1)*800:raise RuntimeError('TCB bounds')
report['tcb_pointer']=ptr;report['tcb_maximum']=maximum;report['threads_raw']=[]
for i in range(maximum+1):
    raw=read_reserved_dram(ptr+i*800,80)
    report['threads_raw'].append(dict(index=i,raw_hex=raw.hex(),stack=struct.unpack_from('<I',raw,16)[0],
        task_id=struct.unpack_from('<I',raw,20)[0],entry=struct.unpack_from('<Q',raw,48)[0]))
report['dictionary_symbols']={n:list(s[n][:2]) for n in ('Worker','ownerStack','rpmsg_tty_task','rpmsg_listen_task')}
c.confirm_up_cpus_off()
print('PRIVATE_JSON '+json.dumps(report,sort_keys=True))
for command in (('uname','-a'),('cat','/proc/sys/kernel/random/boot_id'),('cat','/sys/devices/system/cpu/online'),
        ('cat','/proc/sys/kernel/tainted'),('systemctl','show','micad','-p','ActiveState','-p','MainPID','-p','NRestarts'),
        ('mcsctl','status'),('ip','-brief','address'),('ip','route'),('ethtool','eth1'),('ethtool','eth2'),('lsmod',),
        ('sha256sum','/lib/firmware/rk3572-uniproton-up-a.elf','/lib/firmware/rk3572-uniproton-up-b.elf'),
        ('systemctl','--failed','--no-pager')):
    print('READ_ONLY '+repr(command),flush=True);print(c.command(*command,check=False),flush=True)
'''
if __name__=='__main__':
    result=json.loads((EVIDENCE/'board-result.json').read_text())
    if result['cleanup'] is not False or result['submitted'] is not True:raise RuntimeError('not retained P3j window')
    c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect('192.168.2.141',username='root',password=os.environ['POWERLINK_BOARD_PASSWORD'],timeout=12)
        with (EVIDENCE/'retained-readonly.log').open('xb') as log:
            ch=c.get_transport().open_session();ch.set_combine_stderr(True)
            ch.exec_command('PYTHONDONTWRITEBYTECODE=1 python3 -c '+shlex.quote(CODE))
            data=bytearray()
            while True:
                if ch.recv_ready():chunk=ch.recv(65536);data.extend(chunk);log.write(chunk);log.flush()
                elif ch.exit_status_ready():break
                else:time.sleep(.1)
            status=ch.recv_exit_status();log.write(('\nREAD_ONLY_EXIT=%d\n'%status).encode())
        if status:raise RuntimeError(data.decode(errors='replace')[-3000:])
        report=json.loads(next(x.removeprefix('PRIVATE_JSON ') for x in data.decode().splitlines() if x.startswith('PRIVATE_JSON ')))
        with (EVIDENCE/'retained-private.json').open('x') as out:json.dump(report,out,indent=2)
        for key,size in (('snapshot',1504),('cycle',608)):
            raw=bytes.fromhex(report[key+'_hex'])
            if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=report[key+'_sha256']:raise RuntimeError('raw digest mismatch')
            with (EVIDENCE/('private-'+key+'.hex')).open('x') as out:out.write(raw.hex()+'\n')
        with c.open_sftp() as s:
            with s.open(ROOT+'/ATTEMPTED','rb') as source:data=source.read()
            with (EVIDENCE/'ATTEMPTED.txt').open('xb') as out:out.write(data)
        print(json.dumps({k:v for k,v in report.items() if k not in ('snapshot_hex','cycle_hex')},indent=2))
    finally:c.close()
