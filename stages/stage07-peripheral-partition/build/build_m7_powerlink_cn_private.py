"""P4d compile-only private Linux CN library, execute IO-guarded tests only."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
from prepare_m7_powerlink import prepare
from build_m7_powerlink_linux_cn import OPTIONS
from build_m7_powerlink_cn_lifecycle import CASES as CONTROL_CASES,WRAPS as CONTROL_WRAPS
from apply_m7_powerlink_cn_private import apply
STAGE=Path(__file__).resolve().parents[1]
PRIVATE_CASES=('queue_roundtrip','queue_owner_first','queue_threads','queue_process_isolation','queue_alloc_failure','queue_bounds',
    'sem_normal','sem_init_first','sem_init_second','sem_destroy_failure','timer_once','timer_modify','timer_delete_reuse',
    'timer_capacity','timer_bad_handle','timer_zero','inflight_delete','hres_once','hres_repeat','hres_capacity',
    'cond_clock_failure','thread_failure','clock_failure','post_failure','cond_destroy_failure')
PRIVATE_WRAPS=('m7_cn_stopping','m7_cn_can_release','m7_cn_fail','m7_cn_thread_create','eventu_postEvent',
    'sem_init','sem_destroy','pthread_condattr_setclock','pthread_cond_destroy','clock_gettime','calloc',
    'socket','sem_open','sem_unlink','shm_open','shm_unlink','timer_create')
FORBIDDEN=('sem_open','sem_close','sem_unlink','shm_open','shm_unlink','timer_create','timer_settime','timer_delete','sigwaitinfo','sigtimedwait')
STACK_CASES=('normal','partial_edrv','partial_thread','pdo_mutex_failure')
STACK_WRAPS=('m7_cn_edrv_stats','edrv_init','edrv_getMacAddr','edrv_exit','edrv_sendTxBuffer','pthread_create',
    'pthread_clockjoin_np','sem_destroy','pthread_cond_destroy','socket','sem_open','sem_unlink','shm_open',
    'shm_unlink','timer_create','system','pthread_setschedparam','oplk_execNmtCommand')

def build(destination,cc='gcc',aarch64=False):
    destination=destination.resolve()
    if destination.exists():raise FileExistsError('fresh P4d output required')
    destination.mkdir(parents=True)
    env=dict(os.environ,SOURCE_DATE_EPOCH='1735689600',TZ='UTC',LC_ALL='C')
    tree=prepare(destination/'source');env['GIT_CEILING_DIRECTORIES']=str(tree.parent)
    machine=subprocess.check_output([cc,'-dumpmachine'],env=env,text=True).strip()
    if aarch64 and not machine.startswith('aarch64'):raise ValueError('not an AArch64 compiler')
    patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
    for action in (['--check'],[],['--reverse','--check']):
        subprocess.run(['git','apply','--ignore-space-change']+action+[str(patch)],cwd=tree,env=env,check=True)
    generated=apply(tree)
    for source,target in (('edrv-m7-cn.c','edrv-rawsock_linux.c'),('m7_cn_edrv.h','m7_cn_edrv.h')):
        shutil.copyfile(STAGE/'source/powerlink/linux-cn/transport'/source,tree/'stack/src/kernel/edrv'/target)
    common=['-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_COMPILER='+cc,'-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
        '-DCFG_STORE_RESTORE=OFF','-DCFG_USE_PCAP_EDRV=OFF','-DCFG_COMPILE_SHARED_LIBRARY=OFF',
        '-DCMAKE_INSTALL_PREFIX='+str(destination/'install'),
        '-DCMAKE_C_ARCHIVE_CREATE=<CMAKE_AR> qcD <TARGET> <LINK_FLAGS> <OBJECTS>',
        '-DCMAKE_C_ARCHIVE_FINISH=<CMAKE_RANLIB> -D <TARGET>',
        '-DCMAKE_C_FLAGS=-ffile-prefix-map='+str(destination)+'=/repro/powerlink-cn-private']
    if aarch64:common+=['-DCMAKE_SYSTEM_NAME=Linux','-DCMAKE_SYSTEM_PROCESSOR=aarch64']
    def run(*args):subprocess.run(list(args),env=env,check=True)
    stack=destination/'stack'
    run('cmake','-S',str(tree/'stack'),'-B',str(stack),*common,'-DCFG_COMPILE_LIB_CN=ON',
        *('-DCFG_COMPILE_LIB_'+name+'=OFF' for name in OPTIONS))
    run('cmake','--build',str(stack),'--parallel','4');run('cmake','--install',str(stack))
    library=destination/'install/liboplkcn.a'
    undefined=subprocess.check_output(['nm','-u',str(library)],env=env,text=True)
    for name in FORBIDDEN:
        if any(line.split()[-1:]==[name] for line in undefined.splitlines()):raise ValueError('forbidden library reference: '+name)
    (destination/'undefined-symbols.txt').write_text(undefined,encoding='utf-8',newline='\n')
    if not aarch64:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        for kind,source,wraps,cases in (('control','test_powerlink_cn_lifecycle.c',CONTROL_WRAPS,CONTROL_CASES),
                                       ('private','test_powerlink_cn_private.c',PRIVATE_WRAPS,PRIVATE_CASES),
                                       ('stack','test_powerlink_cn_private_stack.c',STACK_WRAPS,STACK_CASES)):
            executable=destination/('mock-'+kind+'-tests')
            extra=[]
            if kind=='stack':
                extra=['-I'+str(tree/'apps/common/src')]
                objectfile=destination/'mock-cia401-obd.o'
                run(cc,'-std=gnu99','-O2','-Wall','-Wextra','-D_GNU_SOURCE','-DNMT_MAX_NODE_ID=0',
                    '-DCONFIG_INCLUDE_PDO','-DCONFIG_INCLUDE_SDO_ASND','-DCONFIG_INCLUDE_MASND',
                    '-I'+str(tree/'stack/include'),'-I'+str(tree/'contrib'),'-I'+str(tree/'apps/common/objdicts/CiA401_CN'),
                    '-I'+str(tree/'apps/common/src'),'-c',str(tree/'apps/common/src/obdcreate/obdcreate.c'),'-o',str(objectfile))
                extra.append(str(objectfile))
            run(cc,'-std=gnu11','-O2','-g','-fno-strict-aliasing','-D_GNU_SOURCE','-D_POSIX_C_SOURCE=200112L',
                '-Wall','-Wextra','-Werror','-UNDEBUG',
                '-I'+str(tree/'stack/include'),'-I'+str(tree/'contrib'),'-I'+str(tree/'stack/proj/linux/liboplkcn'),
                *extra,str(STAGE/'tests'/source),str(library),'-o',str(executable),'-pthread','-lrt',
                '-Wl,'+','.join('--wrap='+x for x in wraps))
            for case in cases:run('timeout','5s',str(executable),case)
    with (destination/'archive-elf-headers.txt').open('xb') as file:file.write(subprocess.check_output(['readelf','-h',str(library)],env=env))
    sources=[STAGE/'build/apply_m7_powerlink_cn_private.py',STAGE/'build/build_m7_powerlink_cn_private.py',
             STAGE/'tests/test_powerlink_cn_private.c',STAGE/'tests/test_powerlink_cn_private_stack.c']
    sources+=[x for folder in ('private','lifecycle','transport') for x in (STAGE/'source/powerlink/linux-cn'/folder).glob('*') if x.is_file()]
    report=dict(phase='P4d private IPC and generation timer library',aarch64=aarch64,compiler_machine=machine,
        library=dict(bytes=library.stat().st_size,sha256=hashlib.sha256(library.read_bytes()).hexdigest()),
        input_sha256={p.relative_to(STAGE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources)},
        generated_sha256=generated,mock_control_tests=0 if aarch64 else len(CONTROL_CASES),private_tests=0 if aarch64 else len(PRIVATE_CASES),
        mock_stack_tests=0 if aarch64 else len(STACK_CASES),
        forbidden_undefined_symbols=list(FORBIDDEN),board_contacted=False,peer_executed=False,runtime_ready=False,
        limit='No executable CN/frontend or paired MN/config; private timers are not hard realtime, app arguments remain app-owned.')
    with (destination/'build-report.json').open('x') as file:json.dump(report,file,indent=2);file.write('\n')
    print('P4d BUILD PASS '+json.dumps(report),flush=True);return report
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    parser.add_argument('--cc',default='gcc');parser.add_argument('--aarch64',action='store_true');args=parser.parse_args()
    build(args.destination,args.cc,args.aarch64)
