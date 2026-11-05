"""P4c compile-only Linux CN lifecycle library; execute mock-IO tests, never CN."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from prepare_m7_powerlink import prepare
from build_m7_powerlink_linux_cn import OPTIONS
from apply_m7_powerlink_cn_lifecycle import apply
STAGE=Path(__file__).resolve().parents[1]
CASES=('unarmed','normal','no_transport','partial_init','thread_failure','kernel_info_failure','target_failure',
       'join_eventk','join_hres','join_eventu','join_timeru','clock_failure','edrv_failure','transport_unclosed',
       'transport_inflight','transport_fault','user_release_failure','kernel_release_failure','kernel_retval_failure',
       'double_create','wrong_owner','real_threads','missing_worker','duplicate_slot','early_kernel_cleanup','environment_failure')
WORKER_CASES=('normal','sem_close_failure','timer_delete_failure','queue_exit_failure')
WRAPS=('m7_cn_edrv_stats','edrv_exit','pthread_create','pthread_clockjoin_np','clock_gettime','target_init',
       'ctrlucal_init','ctrlucal_checkKernelStack','memmap_init','ctrlu_checkKernelStackInfo','ctrlu_initStack',
       'sdocom_exit','nmtcnu_exit','nmtu_exit','pdou_exit','eventu_exit','dllucal_exit','errhndu_exit','timeru_exit',
       'pdok_exit','nmtk_exit','dllk_exit','hrestimer_exit','dllkcal_exit','eventk_exit','errhndk_exit','obdal_exit',
       'obdu_exit','timesyncu_exit','timesynck_exit','ctrlucal_executeCmd','ctrlu_exit','memmap_shutdown','target_cleanup','socket')
WORKER_WRAPS=('m7_cn_edrv_stats','edrv_exit','sem_open','sem_close','sem_unlink','timer_create','timer_settime',
    'timer_delete','sigtimedwait','pthread_clockjoin_np','eventkcal_initQueueCircbuf','eventucal_initQueueCircbuf',
    'eventkcal_exitQueueCircbuf','eventucal_exitQueueCircbuf','eventkcal_setSignalingCircbuf','eventucal_setSignalingCircbuf',
    'eventkcal_getEventCountCircbuf','eventucal_getEventCountCircbuf','eventkcal_processEventCircbuf',
    'eventucal_processEventCircbuf','eventu_postEvent','socket')

def build(destination,cc='gcc',aarch64=False):
    destination=destination.resolve()
    if destination.exists():raise FileExistsError('fresh P4c output required')
    destination.mkdir(parents=True)
    env=dict(os.environ,SOURCE_DATE_EPOCH='1735689600',TZ='UTC',LC_ALL='C')
    tree=prepare(destination/'source');env['GIT_CEILING_DIRECTORIES']=str(tree.parent)
    machine=subprocess.check_output([cc,'-dumpmachine'],env=env,text=True).strip()
    if aarch64 and not machine.startswith('aarch64'):raise ValueError('not an AArch64 compiler')
    patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
    for action in (['--check'],[],['--reverse','--check']):
        subprocess.run(['git','apply','--ignore-space-change']+action+[str(patch)],cwd=tree,env=env,check=True)
    generated=apply(tree)
    transport=STAGE/'source/powerlink/linux-cn/transport'
    for source,target in (('edrv-m7-cn.c','edrv-rawsock_linux.c'),('m7_cn_edrv.h','m7_cn_edrv.h')):
        shutil.copyfile(transport/source,tree/'stack/src/kernel/edrv'/target)
    common=['-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_COMPILER='+cc,'-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
        '-DCFG_STORE_RESTORE=OFF','-DCFG_USE_PCAP_EDRV=OFF','-DCFG_COMPILE_SHARED_LIBRARY=OFF',
        '-DCMAKE_INSTALL_PREFIX='+str(destination/'install'),
        '-DCMAKE_C_ARCHIVE_CREATE=<CMAKE_AR> qcD <TARGET> <LINK_FLAGS> <OBJECTS>',
        '-DCMAKE_C_ARCHIVE_FINISH=<CMAKE_RANLIB> -D <TARGET>',
        '-DCMAKE_C_FLAGS=-ffile-prefix-map='+str(destination)+'=/repro/powerlink-cn-lifecycle']
    if aarch64:common+=['-DCMAKE_SYSTEM_NAME=Linux','-DCMAKE_SYSTEM_PROCESSOR=aarch64']
    def run(*args):subprocess.run(list(args),env=env,check=True)
    stack=destination/'stack'
    run('cmake','-S',str(tree/'stack'),'-B',str(stack),*common,'-DCFG_COMPILE_LIB_CN=ON',
        *('-DCFG_COMPILE_LIB_'+name+'=OFF' for name in OPTIONS))
    run('cmake','--build',str(stack),'--parallel','4');run('cmake','--install',str(stack))
    library=destination/'install/liboplkcn.a'
    if not aarch64:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        for kind,wraps,cases in (('lifecycle',WRAPS,CASES),('workers',WORKER_WRAPS,WORKER_CASES)):
            executable=destination/('mock-'+kind+'-tests')
            run(cc,'-std=gnu11','-O2','-g','-fno-strict-aliasing','-D_GNU_SOURCE','-D_POSIX_C_SOURCE=200112L',
                '-Wall','-Wextra','-Werror','-UNDEBUG',
                '-I'+str(tree/'stack/include'),'-I'+str(tree/'contrib'),'-I'+str(tree/'stack/proj/linux/liboplkcn'),
                str(STAGE/('tests/test_powerlink_cn_'+kind+'.c')),str(library),'-o',str(executable),'-pthread','-lrt',
                '-Wl,'+','.join('--wrap='+x for x in wraps))
            for case in cases:run('timeout','5s',str(executable),case)
    with (destination/'archive-elf-headers.txt').open('xb') as file:
        file.write(subprocess.check_output(['readelf','-h',str(library)],env=env))
    sources=[STAGE/'build/apply_m7_powerlink_cn_lifecycle.py',STAGE/'build/build_m7_powerlink_cn_lifecycle.py',
             STAGE/'tests/test_powerlink_cn_lifecycle.c',STAGE/'tests/test_powerlink_cn_workers.c']
    sources+=[x for folder in ('lifecycle','transport') for x in (STAGE/'source/powerlink/linux-cn'/folder).glob('*') if x.is_file()]
    report=dict(phase='P4c Linux CN quiesce-before-free foundation',aarch64=aarch64,compiler_machine=machine,
        library=dict(bytes=library.stat().st_size,sha256=hashlib.sha256(library.read_bytes()).hexdigest()),
        input_sha256={p.relative_to(STAGE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        generated_sha256=generated,mock_lifecycle_tests=0 if aarch64 else len(CASES),
        mock_io_real_worker_tests=0 if aarch64 else len(WORKER_CASES),
        board_contacted=False,peer_executed=False,runtime_ready=False,
        limit='No runnable CN/frontend or all-module live integration; IPC namespace, timer signal lifetimes, paired MN/config remain pending.')
    with (destination/'build-report.json').open('x') as file:json.dump(report,file,indent=2);file.write('\n')
    print('P4c BUILD PASS '+json.dumps(report),flush=True)
    return report
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    parser.add_argument('--cc',default='gcc');parser.add_argument('--aarch64',action='store_true');args=parser.parse_args()
    build(args.destination,args.cc,args.aarch64)
