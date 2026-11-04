"""Compile actual P3j RTOS TCB geometry; no firmware/RTOS execution or board IO."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'tests/board'))
from powerlink_cycle_p3j_tcb_checks import TCB_LAYOUT
from powerlink_cycle_p3j_checks import SHA
sys.path.pop(0)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('uniproton','toolchain','report'):p.add_argument(name,type=Path)
    a=p.parse_args();root=a.uniproton
    first=[root/'demos/rk3572_mica/include',root/'output/libc/include',root/'src/include/uapi',
        root/'src/core/kernel/include',root/'src/arch/include',root/'src/arch/cpu/armv8/common/include',
        root/'src/utility/lib/include',root/'src/mem/include']
    rest=sorted({x.parent for x in (root/'src').rglob('*_external.h')
        if not any(v in x.parts for v in ('x86_64','armv7-m','riscv64'))})
    includes=[v for v in dict.fromkeys(first+rest) if v.is_dir()]
    flags=['-std=gnu11','-O2']+[value for path in includes for value in ('-I',str(path))]
    fixture=STAGE/'tests/test_powerlink_cycle_p3j_tcb_abi.c'
    values={}
    with tempfile.TemporaryDirectory(prefix='p3j-tcb-layout-') as directory:
        work=Path(directory)
        for name,cc,copy in (('native','gcc','objcopy'),('aarch64',str(a.toolchain/'bin/aarch64-none-elf-gcc'),str(a.toolchain/'bin/aarch64-none-elf-objcopy'))):
            obj=work/(name+'.o');raw=work/(name+'.bin')
            subprocess.run([cc,*flags,'-c',str(fixture),'-o',str(obj)],check=True)
            subprocess.run([copy,'--dump-section','.m7_tcb_layout='+str(raw),str(obj)],check=True)
            values[name]=list(struct.unpack('<6I',raw.read_bytes()))
            if values[name]!=TCB_LAYOUT:raise ValueError('real TCB compiler layout mismatch: '+name)
    files={x.relative_to(root).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in (
        root/'src/core/kernel/include/prt_task_external.h',root/'demos/rk3572_mica/include/prt_buildef.h',
        root/'src/libc/litelibc/src/thread/pthread_create.c',root/'demos/rk3572_mica/libs/libRK3572.a')}
    report=dict(passed=True,candidate_sha256=SHA,native=values['native'],aarch64=values['aarch64'],
        fields=['sizeof(TagTskCb)','stackSize','taskPid','topOfStack','taskEntry','args'],source_sha256=files,
        limit='Actual RTOS headers/config compiled only, no firmware change, stack watermark or RTOS execution.')
    with a.report.open('x') as out:json.dump(report,out,indent=2);out.write('\n')
    print('P3j ACTUAL RTOS TCB native/AArch64 PASS: '+json.dumps(report))
