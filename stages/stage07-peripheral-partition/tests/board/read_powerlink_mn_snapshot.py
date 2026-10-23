"""Stable private-DRAM cache after physical OFF; never read controller MMIO.
Pinned P3f LP64 layout, not an independent replacement for hardware stop proof.
"""
import hashlib
import json
from pathlib import Path
import struct
import run_can_direct_pair as common
from integrated_mmu_resources import read_reserved_dram
from verify_integrated_elf import symbols_and_data
IMAGE = Path('/root/m7-powerlink-mn-p3f-fixed-20261023/tl3572-m7-powerlink-p3f-up-b.elf')
SHA = '47c0bb5425b9121b3db83572f47d684179962d226c1850123ecb19d1b662fda4'
def mn(raw, offset):
    result=dict(zip(('state','owner','lastError','lastEvent','nmtState'),struct.unpack_from('<5I',raw,offset)))
    result.update(zip(('processes','events'),struct.unpack_from('<2Q',raw,offset+24)))
    return result
def timer(raw, offset):
    names=('counter','ticks','affinity','interrupts','maxIrqLate','level','frequency','cntp','cntv',
        'enabled','pending','active','group','config','priority30','priority27','typer','cpuControl')
    return dict(zip(names,struct.unpack_from('<5Q13I',raw,offset)))
if __name__ == '__main__':
    common.confirm_up_cpus_off()
    if hashlib.sha256(IMAGE.read_bytes()).hexdigest()!=SHA: raise RuntimeError('not pinned fixed candidate')
    symbols=symbols_and_data(IMAGE)
    def private(name):
        address,size,_=symbols[name]
        if not 0x7c200000<=address<=0x7ca00000-size or size>2048: raise RuntimeError('not pinned private range')
        return read_reserved_dram(address,size)
    raw=private('snapshot')
    if len(raw)!=1008: raise RuntimeError('snapshot layout changed')
    lifecycle=raw[80:552]
    result=dict(zip(('result','clean','stage','stackError','loops','leaseBefore','leaseAfter','timerBefore','timerAfter',
        'rx','tx','txDescriptors','dropped','rxErrors','txErrors','fatal'),struct.unpack_from('<16I',lifecycle)))
    result.update(zip(('timerIrqs','timerCallbacks'),struct.unpack_from('<2Q',lifecycle,64)))
    result.update(initialized=mn(lifecycle,80),prepared=mn(lifecycle,120),final=mn(lifecycle,160),
        timerInitial=timer(lifecycle,280),timerFinal=timer(lifecycle,376))
    cache=dict(zip(('ready','pending','running','seq','done','cmd','rc','runtime','owner'),struct.unpack_from('<9I',raw)))
    exception=private('g_excInfoInternal')
    report=dict(limit='Stopped-core private cache; physical hardware stop/rebind proof is in board-test.log',
        owner_cache=cache,mn=mn(raw,40),lifecycle=result,ethLease=struct.unpack('<I',private('g_ethLease'))[0],
        exception=dict(cause=struct.unpack_from('<I',exception,112)[0],elr=hex(struct.unpack_from('<Q',exception,232)[0]),
            esr=hex(struct.unpack_from('<Q',exception,256)[0])),threads=[])
    pointer=struct.unpack('<Q',private('g_tskCbArray'))[0]
    maximum=struct.unpack('<I',private('g_tskMaxNum'))[0]
    if maximum>=64 or not 0x7c200000<=pointer<=0x7ca00000-(maximum+1)*800: raise RuntimeError('TCB bounds changed')
    for index in range(maximum+1):
        control=read_reserved_dram(pointer+index*800,80)
        target=struct.unpack_from('<Q',control,48)[0]
        for name in ('rpmsg_tty_task','rpmsg_listen_task'):
            if target==symbols[name][0]:
                report['threads'].append(dict(name=name,id=struct.unpack_from('<I',control,20)[0],
                    allocated_stack=struct.unpack_from('<I',control,16)[0]))
    if cache['done']!=1 or cache['running'] or cache['rc'] or not result['clean'] or result['loops']!=128:
        raise RuntimeError('not completed pinned GsOff lifecycle')
    print(json.dumps(report,indent=2))
