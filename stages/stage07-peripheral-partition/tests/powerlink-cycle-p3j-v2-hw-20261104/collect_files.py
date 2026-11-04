"""Post-success SFTP reads only; no board command, CPU/TTY/MMIO or writes."""
import hashlib
import json
import os
from pathlib import Path
import paramiko
HERE=Path(__file__).resolve().parent;STAGE=HERE.parents[1]
def digest(data):return hashlib.sha256(data).hexdigest()
if __name__=='__main__':
    result=json.loads((HERE/'board-result.json').read_text())
    if result['passed'] is not True or result['cleanup'] is not True:raise RuntimeError('not a success window')
    prepared=json.loads((STAGE/'tests/powerlink-cycle-p3j-v2-20261104/runtime-inputs.json').read_text())
    old=STAGE/'tests/powerlink-cycle-p3j-return-20261104'
    baseline=json.loads((old/'baseline.json').read_text())
    paths=dict(baseline['formal_files'])
    paths.update({'/root/m7-powerlink-cycle-p3j-20261104/'+name:value['sha256'] for name,value in baseline['files'].items()})
    paths.update({prepared['board_root']+'/'+name:value['sha256'] for name,value in prepared['files'].items()})
    paths.update({prepared['board_root']+'/board-result.json':digest((HERE/'board-result.json').read_bytes()),
        prepared['board_root']+'/ATTEMPTED':digest((HERE/'ATTEMPTED.txt').read_bytes()),
        '/root/m7-powerlink-cycle-p3j-20261104/ATTEMPTED':digest(baseline['marker'].encode()),
        '/root/m7-powerlink-cycle-p3j-20261104/board-result.json':baseline['original_result_sha256'],
        '/root/m7-powerlink-cycle-p3j-20261104/return-linux-20261104/return-result.json':digest((old/'return-result.json').read_bytes())})
    c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect('192.168.2.141',username='root',password=os.environ['POWERLINK_BOARD_PASSWORD'],timeout=15,banner_timeout=30)
    receipt={}
    try:
        with c.open_sftp() as s:
            for name,expected in paths.items():
                with s.open(name,'rb') as file:data=file.read()
                receipt[name]={'sha256':digest(data),'bytes':len(data)}
                if receipt[name]['sha256']!=expected:raise RuntimeError('file drift: '+name)
        with (HERE/'post-file-sha256.json').open('x',encoding='utf-8',newline='\n') as file:
            json.dump(dict(sftp_reads_only=True,files=receipt),file,indent=2);file.write('\n')
        print(str(len(receipt))+' unchanged files PASS; SFTP reads only')
    finally:c.close()
