"""P3j runner-v2 stopped-core proof. Same ELF/cache ABI, corrected TCB gate.
Private DRAM only; independent CPU4/5 OFF before/after. No controller MMIO,
stop, cleanup or recovery; COLD/live completion helpers are NOT stop proof.
"""
import argparse
import json
from pathlib import Path
import struct
from powerlink_cycle_p3j_checks import SHA
from powerlink_cycle_p3j_tcb_checks import TCB_LAYOUT,validate_threads
import read_powerlink_cycle_p3j_snapshot as shared
IMAGE=Path('/root/m7-powerlink-cycle-p3j-v2-20261104/tl3572-m7-powerlink-p3j-up-b.elf')
image_symbols=shared.image_symbols

def validate_tcb_abi(proof, cache_proof):
    if (proof.get('passed') is not True or proof.get('candidate_sha256')!=SHA or
            proof.get('native')!=TCB_LAYOUT or proof.get('aarch64')!=TCB_LAYOUT or
            proof.get('fields')!=['sizeof(TagTskCb)','stackSize','taskPid','topOfStack','taskEntry','args'] or
            not cache_proof.get('rtos_archive_sha256') or proof.get('source_sha256',{}).get('demos/rk3572_mica/libs/libRK3572.a')!=cache_proof['rtos_archive_sha256']):
        raise ValueError('missing pinned P3j native/AArch64 TCB proof for the same RTOS library')

def read_cold_heap(image=IMAGE): return shared.read_cold_heap(image)
def read_completed(image=IMAGE): return shared.read_completed(image)

def read_stopped(image=IMAGE):
    import run_can_direct_pair as common
    from integrated_mmu_resources import read_reserved_dram
    symbols=image_symbols(image)
    common.confirm_up_cpus_off();private=shared.private_reader(symbols)
    report=shared.completed(private)
    report['heap']=shared.heap(private,symbols,'STOPPED')
    pointer=struct.unpack('<Q',private('g_tskCbArray'))[0]
    maximum=struct.unpack('<I',private('g_tskMaxNum'))[0]
    if maximum>=64 or not 0x7c200000<=pointer<=0x7ca00000-(maximum+1)*800:raise RuntimeError('pinned M6 TCB bounds changed')
    records=[read_reserved_dram(pointer+i*800,80) for i in range(maximum+1)]
    report['threads']=validate_threads(records,symbols,report['cycle']['owner'])
    report.update(tcb_pointer=pointer,tcb_maximum=maximum,tcb_prefix_hex=[raw.hex() for raw in records])
    common.confirm_up_cpus_off()
    report['limit']='Stopped-only 1504+608/real FSC/actual TCB metadata; fixed ELF and compiled TCB geometry, not stack watermark, worst latency, fragmentation or realtime acceptance.'
    return report

if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(read_stopped(),indent=2))
