"""P3j retained evidence gate: direct PRT taskEntry vs pthread args[0].
Pure decoder; NO board IO or recovery. Historical runner is unchanged.
"""
import struct
TCB_LAYOUT=[800,16,20,24,32,48]

def validate_threads(records, symbols, owner):
    if not 0 < owner < 64: raise ValueError('invalid PLKowner task id')
    base,size=symbols['ownerStack'][:2]
    if size!=32768 or not 0x7c200000<=base<=0x7ca00000-size: raise ValueError('ownerStack range/size')
    if not symbols['Worker'][1] or not symbols['OsPthreadWrapper'][1]: raise ValueError('missing task entries')
    found=[]
    for index,raw in enumerate(records):
        if len(raw)!=80: raise ValueError('not bounded TCB control prefix')
        stack,task=struct.unpack_from('<2I',raw,16)
        sp=struct.unpack_from('<Q',raw,0)[0]
        top,entry=struct.unpack_from('<2Q',raw,24)
        arg0=struct.unpack_from('<Q',raw,48)[0]
        if task==owner:
            if (stack!=32768 or entry!=symbols['Worker'][0] or top!=base or any(raw[48:80]) or
                    not base<=sp<=base+size): raise ValueError('PLKowner direct TCB/stack/args mismatch')
            found.append(dict(name='PLKowner',id=task,allocated_stack=stack,stack_base=top,entry=entry,
                entry_kind='direct-taskEntry@32',index=index))
        if entry==symbols['OsPthreadWrapper'][0]:
            for name in ('rpmsg_tty_task','rpmsg_listen_task'):
                if arg0==symbols[name][0]:
                    if stack!=4096 or task==owner or not 0x7c200000<=top<=0x7ca00000-stack or not top<=sp<=top+stack:
                        raise ValueError('RPMsg pthread TCB/stack mismatch')
                    found.append(dict(name=name,id=task,allocated_stack=stack,stack_base=top,entry=entry,
                        routine=arg0,entry_kind='OsPthreadWrapper@32,args[0]@48',index=index))
    if sorted((v['name'],v['allocated_stack']) for v in found)!=[('PLKowner',32768),('rpmsg_listen_task',4096),('rpmsg_tty_task',4096)]:
        raise ValueError('actual direct/pthread tasks missing or duplicate')
    if len({v['id'] for v in found})!=3: raise ValueError('duplicate task ids')
    return found
