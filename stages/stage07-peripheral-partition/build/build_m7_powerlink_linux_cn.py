"""Build upstream Linux raw-socket CN peer ONLY. Never run/install on a board.
Fresh output mandatory; target/native ELF inspection is not protocol acceptance.
No UP2/UniProton firmware, MN configuration or historical source is modified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from prepare_m7_powerlink import prepare
STAGE=Path(__file__).resolve().parents[1]
OPTIONS=('MN','MNAPP_USERINTF','MNAPP_KERNELINTF','MNAPP_PCIEINTF','MNAPP_ZYNQINTF','MNDRV_PCAP','MN_SIM',
    'CNAPP_USERINTF','CNAPP_KERNELINTF','CNAPP_ZYNQINTF','CNDRV_PCAP','CN_SIM')

def build(destination,cc='gcc',aarch64=False):
    destination=destination.resolve()
    if destination.exists():raise FileExistsError('fresh Linux CN output required: '+str(destination))
    destination.mkdir(parents=True)
    env=dict(os.environ,SOURCE_DATE_EPOCH='1735689600',TZ='UTC',LC_ALL='C')
    tree=prepare(destination/'source')
    env['GIT_CEILING_DIRECTORIES']=str(tree.parent)
    patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
    for action in (['--check'],[],['--reverse','--check']):
        subprocess.run(['git','apply','--ignore-space-change']+action+[str(patch)],cwd=tree,env=env,check=True)
    machine=subprocess.check_output([cc,'-dumpmachine'],env=env,text=True).strip()
    if aarch64 and not machine.startswith('aarch64'):raise ValueError('not an AArch64 Linux compiler')
    common=['-DCMAKE_BUILD_TYPE=Release','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON','-DCFG_STORE_RESTORE=OFF',
        '-DCFG_USE_PCAP_EDRV=OFF','-DCFG_COMPILE_SHARED_LIBRARY=OFF','-DCMAKE_C_COMPILER='+cc,
        '-DCMAKE_C_ARCHIVE_CREATE=<CMAKE_AR> qcD <TARGET> <LINK_FLAGS> <OBJECTS>',
        '-DCMAKE_C_ARCHIVE_FINISH=<CMAKE_RANLIB> -D <TARGET>',
        '-DCMAKE_INSTALL_PREFIX='+str(destination/'install'),'-DCMAKE_PREFIX_PATH='+str(destination/'install'),
        '-DCMAKE_C_FLAGS=-ffile-prefix-map='+str(destination)+'=/repro/powerlink-cn -fdebug-prefix-map='+str(destination)+'=/repro/powerlink-cn']
    if aarch64:common+=['-DCMAKE_SYSTEM_NAME=Linux','-DCMAKE_SYSTEM_PROCESSOR=aarch64']
    def run(*args):subprocess.run(list(args),env=env,check=True)
    stack=destination/'stack';app=destination/'app'
    run('cmake','-S',str(tree/'stack'),'-B',str(stack),*common,'-DCFG_COMPILE_LIB_CN=ON',
        *('-DCFG_COMPILE_LIB_'+name+'=OFF' for name in OPTIONS))
    run('cmake','--build',str(stack),'--parallel','4')
    run('cmake','--install',str(stack))  # Only the fresh build output prefix, never system/board.
    run('cmake','-S',str(tree/'apps/demo_cn_console'),'-B',str(app),*common,
        '-DCFG_IP_STACK=OFF','-DCFG_BUILD_KERNEL_STACK=Link to Application')
    run('cmake','--build',str(app),'--parallel','4')
    commands=(stack/'compile_commands.json').read_text()
    if 'edrv-rawsock_linux.c' not in commands or 'edrv-pcap_linux.c' in commands:raise ValueError('not exclusively raw-socket EDRV')
    artifacts={}
    for path in (destination/'install/liboplkcn.a',app/'demo_cn_console'):
        artifacts[str(path.relative_to(destination))]=dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    binary=app/'demo_cn_console'
    for name,args in (('elf-header.txt',['-h']),('elf-dynamic.txt',['-d']),('elf-versions.txt',['-V'])):
        output=subprocess.check_output(['readelf',*args,str(binary)],env=env)
        with (destination/name).open('xb') as file:file.write(output)
    report=dict(role='CN',driver='edrv-rawsock_linux.c',compiler_machine=machine,
        compiler_version=subprocess.check_output([cc,'--version'],env=env,text=True).splitlines()[0],
        aarch64=aarch64,software_only=True,executed=False,board_contacted=False,artifacts=artifacts,
        deterministic_archives=True,source_date_epoch=env['SOURCE_DATE_EPOCH'],
        linux_cn_patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest(),
        limit='Unmodified CN demo behavior, NOT yet bounded/safe hardware runner; no network/PDO/timing acceptance.')
    with (destination/'build-report.json').open('x') as file:json.dump(report,file,indent=2);file.write('\n')
    print('Linux CN BUILD ONLY PASS '+json.dumps(report),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    parser.add_argument('--cc',default='gcc');parser.add_argument('--aarch64',action='store_true');args=parser.parse_args()
    build(args.destination,args.cc,args.aarch64)
