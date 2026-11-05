"""P4b compile-only CN transport library. Fresh tree, no peer executable/run.
Historical P4a builder/archive/binaries and UP2 firmware remain unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from prepare_m7_powerlink import prepare
from build_m7_powerlink_linux_cn import OPTIONS
STAGE=Path(__file__).resolve().parents[1]

def build(destination,cc='gcc',aarch64=False):
    destination=destination.resolve()
    if destination.exists():raise FileExistsError('fresh P4b output required')
    destination.mkdir(parents=True)
    env=dict(os.environ,SOURCE_DATE_EPOCH='1735689600',TZ='UTC',LC_ALL='C')
    tree=prepare(destination/'source');env['GIT_CEILING_DIRECTORIES']=str(tree.parent)
    machine=subprocess.check_output([cc,'-dumpmachine'],env=env,text=True).strip()
    if aarch64 and not machine.startswith('aarch64'):raise ValueError('not an AArch64 compiler')
    patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
    for action in (['--check'],[],['--reverse','--check']):
        subprocess.run(['git','apply','--ignore-space-change']+action+[str(patch)],cwd=tree,env=env,check=True)
    transport=STAGE/'source/powerlink/linux-cn/transport'
    source=tree/'stack/src/kernel/edrv'
    shutil.copyfile(transport/'edrv-m7-cn.c',source/'edrv-rawsock_linux.c')
    shutil.copyfile(transport/'m7_cn_edrv.h',source/'m7_cn_edrv.h')
    common=['-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_COMPILER='+cc,'-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
        '-DCFG_STORE_RESTORE=OFF','-DCFG_USE_PCAP_EDRV=OFF','-DCFG_COMPILE_SHARED_LIBRARY=OFF',
        '-DCMAKE_INSTALL_PREFIX='+str(destination/'install'),
        '-DCMAKE_C_ARCHIVE_CREATE=<CMAKE_AR> qcD <TARGET> <LINK_FLAGS> <OBJECTS>',
        '-DCMAKE_C_ARCHIVE_FINISH=<CMAKE_RANLIB> -D <TARGET>',
        '-DCMAKE_C_FLAGS=-ffile-prefix-map='+str(destination)+'=/repro/powerlink-cn-transport']
    if aarch64:common+=['-DCMAKE_SYSTEM_NAME=Linux','-DCMAKE_SYSTEM_PROCESSOR=aarch64']
    def run(*args):subprocess.run(list(args),env=env,check=True)
    stack=destination/'stack'
    run('cmake','-S',str(tree/'stack'),'-B',str(stack),*common,'-DCFG_COMPILE_LIB_CN=ON',
        *('-DCFG_COMPILE_LIB_'+name+'=OFF' for name in OPTIONS))
    run('cmake','--build',str(stack),'--parallel','4');run('cmake','--install',str(stack))
    if not aarch64:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        executable=destination/'mock-transport-tests'
        run(cc,'-std=gnu11','-O2','-g','-fno-strict-aliasing','-D_GNU_SOURCE','-D_POSIX_C_SOURCE=200112L','-Wall','-Wextra','-Werror','-UNDEBUG',
            '-I'+str(tree/'stack/include'),'-I'+str(tree/'contrib'),'-I'+str(tree/'stack/proj/linux/liboplkcn'),
            str(STAGE/'tests/test_powerlink_cn_transport.c'),'-o',str(executable),'-pthread',
            '-Wl,--wrap=socket,--wrap=ioctl,--wrap=bind,--wrap=setsockopt,--wrap=close,--wrap=realpath',
            '-Wl,--wrap=pthread_create,--wrap=pthread_clockjoin_np,--wrap=clock_gettime,--wrap=poll,--wrap=recvfrom,--wrap=send')
        cases=('unarmed','identity_driver','identity_port','wrong_interface','socket_failure','index_failure',
            'bind_failure','membership_failure','mac_failure','thread_failure','normal','callback_free','bad_tx',
            'send_failure','short_send','tx_limit','deadline','rx','rx_filter','rx_limit','deferred',
            'join_failure','close_failure','clock_after_fault','real_thread','wrong_owner','busy_tx','bad_tx_source',
            'inflight_timeout','init_clock_failure','init_close_failure','poll_failure','rx_oversize','rx_bad_meta')
        for case in cases:run('timeout','5s',str(executable),case)
    library=destination/'install/liboplkcn.a'
    with (destination/'archive-elf-headers.txt').open('xb') as file:
        file.write(subprocess.check_output(['readelf','-h',str(library)],env=env))
    report=dict(phase='P4b default-unarmed transport component only',aarch64=aarch64,compiler_machine=machine,
        library=dict(bytes=library.stat().st_size,sha256=hashlib.sha256(library.read_bytes()).hexdigest()),
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(transport.glob('*')) if p.is_file()},
        mock_network_tests=0 if aarch64 else len(cases),board_contacted=False,peer_executed=False,runtime_ready=False,
        limit='No frontend, full-stack teardown fix, MN/CN config or hardware proof; callback stalls retain state.')
    with (destination/'build-report.json').open('x') as file:json.dump(report,file,indent=2);file.write('\n')
    print('P4b BUILD PASS '+json.dumps(report),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination',type=Path)
    p.add_argument('--cc',default='gcc');p.add_argument('--aarch64',action='store_true');a=p.parse_args()
    build(a.destination,a.cc,a.aarch64)
