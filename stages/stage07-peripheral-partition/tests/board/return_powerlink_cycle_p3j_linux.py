"""Separately approved P3j stopped-only Linux return. NEVER starts/stops UP2.
Fixed original window. Any unknown/failure stops further mutations, no retry.
Original board-result/ATTEMPTED and all 19 inputs remain unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
ROOT=Path('/root/m7-powerlink-cycle-p3j-20261104')
CLIENT='up-b-m7-plk-cycle-p3j'
BOOT='63986874-c4a0-4c1a-95b0-a92deb7f3bae'
sys.path.insert(1,str(ROOT))
from powerlink_cycle_p3j_checks import SHA,match_replies,match_heap,original_clients
from powerlink_cycle_p3j_tcb_checks import validate_threads
from read_powerlink_cycle_p3j_snapshot import image_symbols,private_reader,completed,heap
from run_powerlink_cycle_p3j_probe import linux_full

def normalized(value): return json.loads(json.dumps(value))

def check_files(baseline):
    for name,item in baseline['files'].items():
        path=ROOT/name
        if path.name!=name or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256'] or path.stat().st_size!=item['bytes']:
            raise RuntimeError('original runtime input changed: '+name)
    if (ROOT/'ATTEMPTED').read_text()!=baseline['marker']: raise RuntimeError('original ATTEMPTED changed')
    if hashlib.sha256((ROOT/'board-result.json').read_bytes()).hexdigest()!=baseline['original_result_sha256']:
        raise RuntimeError('original failure result changed')
    for name,digest in baseline['formal_files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise RuntimeError('formal M6 file changed: '+name)

def check_baseline(base, baseline, retained):
    c=base.common
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=BOOT or baseline['before']['boot']!=BOOT:
        raise RuntimeError('not the approved P3j boot')
    if c.command('uname','-r').strip()!='6.12.69-gf1b67c293213':raise RuntimeError('kernel changed')
    if int(Path('/proc/sys/kernel/tainted').read_text()) & 128:raise RuntimeError('kernel Oops taint')
    if c.micad_state()!=baseline['before']['micad'] or normalized(base.management())!=baseline['before']['management']:
        raise RuntimeError('micad/management drift')
    base.passive.compare_snapshot(baseline['before']['peripherals'],base.passive.snapshot())
    if list(Path('/dev').glob('ttyRPMSG*')):raise RuntimeError('unexpected RPMsg endpoint')
    if retained:
        rows=[line.split() for line in c.command('mcsctl','status').splitlines() if line.strip()]
        if (not rows or rows[0]!=['Name','Assigned','CPU','State','Service'] or
                sorted(rows[1:])!=sorted([['up-a','4','Offline'],['up-b','5','Offline'],[CLIENT,'5','Offline']])):
            raise RuntimeError('not exactly original + stopped temporary clients')
        if (base.DEVICE/'driver').exists() or Path('/sys/class/net/eth1').exists() or not Path('/sys/module/m7_eth2_power_hold').exists():
            raise RuntimeError('not retained unbound ETH2/held state')
    else: original_clients(c.command('mcsctl','status'))
    check_files(baseline)

def read_stopped(base, baseline):
    from integrated_mmu_resources import read_reserved_dram
    c=base.common;c.confirm_up_cpus_off()
    symbols=image_symbols(ROOT/'tl3572-m7-powerlink-p3j-up-b.elf');private=private_reader(symbols)
    report=completed(private)
    for name in ('snapshot','cycle'):
        if report[name+'_sha256']!=baseline['retained'][name+'_sha256'] or report[name+'_hex']!=baseline['retained'][name+'_hex']:
            raise RuntimeError('stopped publication changed: '+name)
    match_replies(report,baseline['completion']['owner'],baseline['completion']['result'])
    report['heap']=heap(private,symbols,'STOPPED')
    report['heap_comparison']=match_heap(baseline['heap_before'],report['heap'])
    if report['heap']!=baseline['retained']['heap']:raise RuntimeError('stopped FSC metadata changed')
    pointer=struct.unpack('<Q',private('g_tskCbArray'))[0];maximum=struct.unpack('<I',private('g_tskMaxNum'))[0]
    if maximum>=64 or not 0x7c200000<=pointer<=0x7ca00000-(maximum+1)*800:raise RuntimeError('TCB bounds changed')
    records=[read_reserved_dram(pointer+i*800,80) for i in range(maximum+1)]
    if [r.hex() for r in records]!=[r['raw_hex'] for r in baseline['retained']['threads_raw']]:
        raise RuntimeError('stopped TCB records changed')
    report['threads']=validate_threads(records,symbols,report['cycle']['owner'])
    c.confirm_up_cpus_off()
    return report

def claim():
    with (ROOT/'LINUX_RETURN_ATTEMPTED').open('x',encoding='ascii') as out:
        out.write('candidate='+SHA+'\nboot='+BOOT+'\nscope=stopped-only-linux-return\n');out.flush();os.fsync(out.fileno())

def restore(base, baseline):
    c=base.common;report=dict(passed=False,cycle_reexecuted=False,cpu_stop_issued=False,candidate_sha256=SHA,
        boot_id=BOOT,attempted_mutations=[],completed_mutations=[],private_stopped=None,error=None)
    try:
        c.confirm_up_cpus_off();check_baseline(base,baseline,True)
        report['private_stopped']=read_stopped(base,baseline)
        check_baseline(base,baseline,True);c.confirm_up_cpus_off();claim()
        report['attempted_mutations'].append('remove-stopped-client');c.control('rm',CLIENT)
        report['completed_mutations'].append('remove-stopped-client')
        c.confirm_up_cpus_off()
        report['attempted_mutations'].append('bind-linux-eth2');(base.DRIVER/'bind').write_text(base.DEVICE.name)
        report['completed_mutations'].append('bind-linux-eth2')
        report['attempted_mutations'].append('linux-eth2-up');c.command('ip','link','set','eth1','up')
        report['completed_mutations'].append('linux-eth2-up')
        end=time.monotonic()+20
        while time.monotonic()<end:
            try: linux_full(base);break
            except (OSError,RuntimeError):time.sleep(.2)
        else:raise RuntimeError('Linux100Full/ANon restore timeout; retain hold')
        check_baseline(base,baseline,False);c.confirm_up_cpus_off()
        report['attempted_mutations'].append('release-hold');c.command('rmmod','m7_eth2_power_hold')
        report['completed_mutations'].append('release-hold')
        if Path('/sys/module/m7_eth2_power_hold').exists():raise RuntimeError('residual hold')
        linux_full(base);check_baseline(base,baseline,False);c.confirm_up_cpus_off()
        report['passed']=True
    except Exception as exc:report['error']=type(exc).__name__+': '+str(exc)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--confirm-stopped-p3j-linux-return',action='store_true')
    p.add_argument('--baseline-sha256',required=True);a=p.parse_args()
    if not a.confirm_stopped_p3j_linux_return or getattr(os,'geteuid',lambda:-1)()!=0:
        raise RuntimeError('separate stopped-only return approval and board root required')
    work=Path(__file__).resolve().parent
    if work!=ROOT/'return-linux-20261104':raise RuntimeError('wrong fixed return-tools directory')
    if (ROOT/'LINUX_RETURN_ATTEMPTED').exists() or (work/'return-result.json').exists():raise RuntimeError('return already attempted; NO retry')
    raw=(work/'baseline.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=a.baseline_sha256:raise RuntimeError('baseline SHA mismatch')
    import run_powerlink_eth_probe as base
    report=restore(base,json.loads(raw))
    with (work/'return-result.json').open('x') as out:json.dump(report,out,indent=2);out.write('\n')
    print('P3j RETURN RESULT '+json.dumps(report,sort_keys=True),flush=True)
    if not report['passed']:raise RuntimeError('RETURN FAILED; no retry/second action/automatic recovery: '+str(report['error']))
    print('P3j LINUX RETURN PASS: no cycle/start/stop/reboot; original result and ATTEMPTED preserved',flush=True)
