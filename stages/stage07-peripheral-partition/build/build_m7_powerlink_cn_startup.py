"""P4e compile-only library and real-stack mocked-network regressions, never CN."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
from prepare_m7_powerlink import prepare
from build_m7_powerlink_linux_cn import OPTIONS
from build_m7_powerlink_cn_private import PRIVATE_CASES,PRIVATE_WRAPS,FORBIDDEN
from build_m7_powerlink_cn_lifecycle import CASES,WRAPS
from apply_m7_powerlink_cn_startup import apply
STAGE=Path(__file__).resolve().parents[1]
CONTROL_CASES=tuple(case for case in CASES if case!='early_kernel_cleanup')
STARTUP_CASES=('normal','early_kernel_cleanup','bind_failure','partial_thread','socket_failure',
               'rx_delivery','tx_acceptance','tx_short','rx_io_failure','sem_wait_failure','event_clock_failure',
               'sem_post_failure','timer_post_failure','dispatch_failure','startup_timeout','stop_pending','join_failure')
STARTUP_WRAPS=('socket','realpath','ioctl','bind','setsockopt','poll','recvfrom','send','close',
    'pthread_create','pthread_clockjoin_np','sem_destroy','pthread_cond_destroy','sem_clockwait','sem_post',
    'clock_gettime','eventu_postEvent','sem_open','sem_unlink','shm_open','shm_unlink','timer_create',
    'system','pthread_setschedparam')

def build(destination,cc='gcc',aarch64=False):
    destination=destination.resolve()
    if destination.exists():raise FileExistsError('fresh P4e output required')
    destination.mkdir(parents=True)
    env=dict(os.environ,SOURCE_DATE_EPOCH='1735689600',TZ='UTC',LC_ALL='C')
    tree=prepare(destination/'source');env['GIT_CEILING_DIRECTORIES']=str(tree.parent)
    machine=subprocess.check_output([cc,'-dumpmachine'],env=env,text=True).strip()
    if aarch64 and not machine.startswith('aarch64'):raise ValueError('not an AArch64 compiler')
    patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
    for action in (['--check'],[],['--reverse','--check']):
        subprocess.run(['git','apply','--ignore-space-change']+action+[str(patch)],cwd=tree,env=env,check=True)
    generated=apply(tree)
    common=['-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_COMPILER='+cc,'-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
        '-DCFG_STORE_RESTORE=OFF','-DCFG_USE_PCAP_EDRV=OFF','-DCFG_COMPILE_SHARED_LIBRARY=OFF',
        '-DCMAKE_INSTALL_PREFIX='+str(destination/'install'),
        '-DCMAKE_C_ARCHIVE_CREATE=<CMAKE_AR> qcD <TARGET> <LINK_FLAGS> <OBJECTS>',
        '-DCMAKE_C_ARCHIVE_FINISH=<CMAKE_RANLIB> -D <TARGET>',
        '-DCMAKE_C_FLAGS=-Werror=implicit-function-declaration -ffile-prefix-map='+str(destination)+'=/repro/powerlink-cn-startup']
    if aarch64:common+=['-DCMAKE_SYSTEM_NAME=Linux','-DCMAKE_SYSTEM_PROCESSOR=aarch64']
    def run(*args):subprocess.run(list(args),env=env,check=True)
    run('cmake','-S',str(tree/'stack'),'-B',str(destination/'stack'),*common,'-DCFG_COMPILE_LIB_CN=ON',
        *('-DCFG_COMPILE_LIB_'+name+'=OFF' for name in OPTIONS))
    run('cmake','--build',str(destination/'stack'),'--parallel','4');run('cmake','--install',str(destination/'stack'))
    library=destination/'install/liboplkcn.a'
    undefined=subprocess.check_output(['nm','-u',str(library)],env=env,text=True)
    for name in FORBIDDEN:
        if any(line.split()[-1:]==[name] for line in undefined.splitlines()):raise ValueError('forbidden reference: '+name)
    (destination/'undefined-symbols.txt').write_text(undefined,encoding='utf-8',newline='\n')
    if not aarch64:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        groups=(('control',WRAPS+('m7_cn_edrv_activate',),CONTROL_CASES),
                ('private',PRIVATE_WRAPS+('m7_cn_ready','m7_cn_wait_ready'),PRIVATE_CASES),
                ('stack',STARTUP_WRAPS,STARTUP_CASES))
        for kind,wraps,cases in groups:
            extra=[]
            if kind=='stack':
                extra=['-I'+str(tree/'apps/common/src')];objectfile=destination/'mock-cia401-obd.o'
                run(cc,'-std=gnu99','-O2','-Wall','-Wextra','-D_GNU_SOURCE','-DNMT_MAX_NODE_ID=0',
                    '-DCONFIG_INCLUDE_PDO','-DCONFIG_INCLUDE_SDO_ASND','-DCONFIG_INCLUDE_MASND',
                    '-I'+str(tree/'stack/include'),'-I'+str(tree/'contrib'),'-I'+str(tree/'apps/common/objdicts/CiA401_CN'),
                    '-I'+str(tree/'apps/common/src'),'-c',str(tree/'apps/common/src/obdcreate/obdcreate.c'),'-o',str(objectfile))
                extra.append(str(objectfile))
            executable=destination/('mock-'+kind+'-tests')
            run(cc,'-std=gnu11','-O2','-g','-fno-strict-aliasing','-D_GNU_SOURCE','-D_POSIX_C_SOURCE=200112L',
                '-Wall','-Wextra','-Werror','-UNDEBUG',
                '-I'+str(tree/'stack/include'),'-I'+str(tree/'contrib'),'-I'+str(tree/'stack/proj/linux/liboplkcn'),
                *extra,str(STAGE/'tests'/('test_powerlink_cn_startup_'+kind+'.c')),str(library),'-o',str(executable),
                '-pthread','-lrt','-Wl,'+','.join('--wrap='+x for x in wraps))
            for case in cases:run('timeout','5s',str(executable),case)
    (destination/'archive-elf-headers.txt').write_bytes(subprocess.check_output(['readelf','-h',str(library)],env=env))
    sources=[STAGE/'build/apply_m7_powerlink_cn_startup.py',STAGE/'build/build_m7_powerlink_cn_startup.py']
    sources+=list((STAGE/'tests').glob('test_powerlink_cn_startup_*.c'))
    sources+=[STAGE/'tests'/name for name in ('test_powerlink_cn_lifecycle.c','test_powerlink_cn_private.c')]
    sources+=[x for folder in ('startup','private','lifecycle','transport') for x in (STAGE/'source/powerlink/linux-cn'/folder).glob('*') if x.is_file()]
    report=dict(phase='P4e full-stack delivery activation gate',aarch64=aarch64,compiler_machine=machine,
        library=dict(bytes=library.stat().st_size,sha256=hashlib.sha256(library.read_bytes()).hexdigest()),
        input_sha256={p.relative_to(STAGE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources)},
        generated_sha256=generated,mock_control_tests=0 if aarch64 else len(CONTROL_CASES),
        private_tests=0 if aarch64 else len(PRIVATE_CASES),mock_stack_tests=0 if aarch64 else len(STARTUP_CASES),
        forbidden_undefined_symbols=list(FORBIDDEN),board_contacted=False,peer_executed=False,runtime_ready=False,
        limit='Real stack/EDRV, fake OS network. No executable CN/frontend, no active NMT reset/start, no paired MN/config.')
    with (destination/'build-report.json').open('x') as file:json.dump(report,file,indent=2);file.write('\n')
    print('P4e BUILD PASS '+json.dumps(report),flush=True);return report
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    parser.add_argument('--cc',default='gcc');parser.add_argument('--aarch64',action='store_true');args=parser.parse_args()
    build(args.destination,args.cc,args.aarch64)
