"""P3j final cumulative candidate/dual-compiler ABI/ISA/stack audit; NO board."""
import argparse,json,hashlib,struct,subprocess,tempfile
from pathlib import Path
from audit_powerlink_owner import audit,text_symbols
from audit_powerlink_eth import lse_instructions
from audit_powerlink_stack import audit as stack_audit,functions,frame
from verify_integrated_elf import symbols_and_data
STAGE=Path(__file__).resolve().parents[1]
LAYOUT=[608,8,480,496,520,532,544,576,584,1504]
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','full','toolchain','baseline'):p.add_argument(name,type=Path)
    a=p.parse_args();audit(a.build,a.full,a.toolchain,a.baseline,up2_fsc=0x100000)
    prefix=str(a.toolchain/'bin/aarch64-none-elf-');image=a.build/'tl3572-m7-integrated-up-b.elf'
    symbols=symbols_and_data(image)
    for name,size in (('snapshot',1504),('cycleResult',608),('cycleReady',4),('cycleAttempted',4)):
        if symbols[name][1]!=size or not 0x7c200000<=symbols[name][0]<=0x7ca00000-size:raise ValueError('new/old BSS ABI mismatch: '+name)
    required={'m7_cycle_probe','Rk3572PowerlinkCycleSnapshot','m7_edrv_tx_pending','m7_hrestimer_pending',
        'm7_nmt_probe','m7_mn_probe','m7_edrv_probe','m7_eth_probe','m7_timer_probe'}
    if required-text_symbols(prefix,image):raise ValueError('cumulative probe dropped')
    if 'm7_cycle_probe' in symbols_and_data(a.build/'tl3572-m7-integrated-up-a.elf'):raise ValueError('UP1 acquired cycle probe')
    assembly=subprocess.check_output([prefix+'objdump','-d',str(image)],text=True)
    if lse_instructions(assembly):raise ValueError('LSE in final candidate')
    stack=stack_audit(assembly);blocks=functions(assembly)
    known_frames={name:frame(blocks[name]) for name in ('Worker','m7_cycle_probe')}
    if sum(known_frames.values())+8192>32768:raise ValueError('known owner/probe frames exceed reserved budget')
    commands=json.loads((a.build/'m7-powerlink-p3j-up-b/compile_commands.json').read_text())
    app=[x for x in commands if x['file'].endswith('/rk3572_powerlink_app.c')]
    if len(app)!=1 or '-DM7_POWERLINK_CYCLE_PROBE=1' not in app[0]['command']:raise ValueError('actual app gate absent')
    with tempfile.TemporaryDirectory(prefix='m7-cycle-abi-') as directory:
        work=Path(directory)
        flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(STAGE/'source/powerlink/port'),
            '-I',str(STAGE/'source/overlay/uniproton/demos/rk3572_mica/apps/openamp'),str(STAGE/'tests/test_powerlink_cycle_probe_abi.c')]
        subprocess.run(['gcc',*flags,'-DM7_NATIVE_LAYOUT','-o',str(work/'native')],check=True)
        native=json.loads(subprocess.check_output([str(work/'native')],text=True))
        subprocess.run([prefix+'gcc',*flags,'-mcpu=cortex-a53','-mgeneral-regs-only','-mno-outline-atomics','-c','-o',str(work/'cross.o')],check=True)
        cross=list(struct.unpack('<10I',symbols_and_data(work/'cross.o')['m7_cycle_layout'][2]))
        if native!=LAYOUT or cross!=LAYOUT:raise ValueError('native/AArch64 cycle ABI mismatch')
    report=json.loads((a.build/'owner-audit.json').read_text())
    report.update(phase='P3j one-shot guarded MN cycle SOFTWARE ONLY',hardware_tested=False,
        commands=['PLK '+name for name in ('status','env-init','env-exit','timer-probe','timer-status','eth-probe','eth-status',
            'edrv-probe','edrv-status','mn-probe','mn-status','nmt-probe','nmt-status','cycle-probe','cycle-status')],
        cycle_abi=1,cycle_layout_native=native,cycle_layout_aarch64=cross,old_snapshot_bytes=1504,
        cycle_private_symbols={name:list(symbols[name][:2]) for name in ('cycleResult','cycleReady','cycleAttempted')},
        rpmsg_stack_budget=stack,known_owner_frames=known_frames,
        owner_stack_limit='Known frames+8KiB reserve only, NOT full call/IRQ worst-case proof',
        candidate_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        limits='No board runner, cache/FSC stopped-core proof or isolated cycle authorization. Software guards check only after calls return; not a preemptive watchdog or real-time acceptance.')
    (a.build/'cycle-probe-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('P3j FINAL software ELF/old1504+new608 dual-compiler ABI/ISA/stack PASS; NO BOARD')
