"""Pinned P3g reply/private-cache validation, stdlib only; NO IO at import.
Private cache is evidence only after physical CPU4/5 OFF, never live MMIO.
"""
import struct
from powerlink_eth_checks import fields
SHA = '85e78eb4bb150633e695014b5ecc55401a048a2707175a031b97a2e00567f68e'
SNAPSHOT_BYTES, NMT_OFFSET, NMT_BYTES, LIFE_BYTES = 1504, 80, 496, 472

def original_clients(text):
    lines = [x.split() for x in text.splitlines() if x.strip()]
    if (not lines or lines[0] != ['Name', 'Assigned', 'CPU', 'State', 'Service'] or
            sorted(lines[1:]) != [['up-a', '4', 'Offline'], ['up-b', '5', 'Offline']]):
        raise ValueError('requires ONLY the two original Offline clients')

def validate_reply(reply):
    result = fields(reply, 'PLK UP2 NMT')
    expected = dict(rc='0', clean='1', stage='6', stack='0x0', reset='1', off='1', reached='0x21c',
        state='0', nmt='0x0', rx='0', tx='0', txdesc='0', rxerr='0', txerr='0', fatal='0', lease='0/0', timer='0/0')
    if set(result) != set(expected) | {'resetLoops', 'offLoops'} or any(result.get(k) != v for k, v in expected.items()):
        raise ValueError('bounded NMT result incomplete/failed/not stopped')
    if any(not 1 <= int(result[k]) <= 32 for k in ('resetLoops', 'offLoops')):
        raise ValueError('NMT transition outside pinned process bound')
    return result

def validate_owner(state, result):
    expected = dict(ready='1', pending='0', running='0', seq='1', done='1', cmd='7', rc='0x0', runtime='0x0',
        state='0', nmt='0x0', mode='bounded-NMT-diagnostic')
    loops = int(result['resetLoops']) + int(result['offLoops'])
    if any(state.get(k) != v for k, v in expected.items()) or not 0 < int(state.get('owner', '0')) < 64:
        raise ValueError('NMT owner not completed/COLD')
    if int(state.get('processes', '-1')) != loops or int(state.get('events', '0')) < 6:
        raise ValueError('NMT process/event evidence missing')

def mn(raw, offset):
    result = dict(zip(('state', 'owner', 'lastError', 'lastEvent', 'nmtState'), struct.unpack_from('<5I', raw, offset)))
    result.update(zip(('processes', 'events'), struct.unpack_from('<2Q', raw, offset + 24)))
    return result

def timer(raw, offset):
    names = ('counter', 'ticks', 'affinity', 'interrupts', 'maxIrqLate', 'level', 'frequency', 'cntp', 'cntv',
        'enabled', 'pending', 'active', 'group', 'config', 'priority30', 'priority27', 'typer', 'cpuControl')
    return dict(zip(names, struct.unpack_from('<5Q13I', raw, offset)))

def decode_snapshot(raw):
    if len(raw) != SNAPSHOT_BYTES: raise ValueError('not pinned P3g 1504-byte snapshot')
    cache = dict(zip(('ready', 'pending', 'running', 'seq', 'done', 'cmd', 'rc', 'runtime', 'owner'), struct.unpack_from('<9I', raw)))
    life = raw[NMT_OFFSET:NMT_OFFSET + LIFE_BYTES]
    result = dict(zip(('result', 'clean', 'stage', 'stackError', 'loops', 'leaseBefore', 'leaseAfter', 'timerBefore',
        'timerAfter', 'rx', 'tx', 'txDescriptors', 'dropped', 'rxErrors', 'txErrors', 'fatal'), struct.unpack_from('<16I', life)))
    result.update(zip(('timerIrqs', 'timerCallbacks'), struct.unpack_from('<2Q', life, 64)))
    result.update(initialized=mn(life, 80), prepared=mn(life, 120), final=mn(life, 160),
        active=dict(zip(('mac', 'tx', 'rx', 'dma', 'macIrq', 'dmaIrq'), struct.unpack_from('<6I', life, 216))),
        stopped=dict(zip(('mac', 'tx', 'rx', 'dma', 'macIrq', 'dmaIrq'), struct.unpack_from('<6I', life, 256))),
        timerInitial=timer(life, 280), timerFinal=timer(life, 376))
    extra = dict(zip(('resetSubmitted', 'offSubmitted', 'resetLoops', 'offLoops', 'reached'), struct.unpack_from('<5I', raw, NMT_OFFSET + LIFE_BYTES)))
    return dict(cache=cache, mn=mn(raw, 40), lifecycle=result, nmt=extra, other_probes_untouched=not any(raw[576:]))

def validate_snapshot(raw):
    report = decode_snapshot(raw); cache, life, extra = report['cache'], report['lifecycle'], report['nmt']
    expected = dict(ready=1, pending=0, running=0, seq=1, done=1, cmd=7, rc=0, runtime=0)
    if any(cache[k] != v for k, v in expected.items()) or not 0 < cache['owner'] < 64:
        raise ValueError('stopped-core mailbox is not a completed one-shot NMT probe')
    if (life['result'], life['clean'], life['stage'], life['stackError']) != (0, 1, 6, 0):
        raise ValueError('private lifecycle failed/incomplete')
    if (extra['resetSubmitted'], extra['offSubmitted'], extra['reached']) != (1, 1, 0x21c) or any(
            not 1 <= extra[k] <= 32 for k in ('resetLoops', 'offLoops')):
        raise ValueError('private NMT transitions incomplete')
    loops = extra['resetLoops'] + extra['offLoops']
    if life['loops'] != loops or report['mn'] != life['final'] or not report['other_probes_untouched']:
        raise ValueError('private cumulative cache inconsistent or another probe executed')
    for name, state in (('initialized', 1), ('prepared', 2), ('final', 0)):
        status = life[name]
        if status['state'] != state or status['owner'] != cache['owner'] or status['lastError'] or status['nmtState']:
            raise ValueError('private MN lifecycle states/owner/error changed')
        if name != 'final' and (status['events'] or status['processes']): raise ValueError('MN not initially dormant')
    if life['final']['processes'] != loops or life['final']['events'] < 6: raise ValueError('private event/pump proof missing')
    for name in ('leaseBefore', 'leaseAfter', 'timerBefore', 'timerAfter', 'rx', 'tx', 'txDescriptors', 'rxErrors',
                 'txErrors', 'fatal', 'timerIrqs', 'timerCallbacks'):
        if life[name]: raise ValueError('private traffic/error/lease evidence: ' + name)
    active, stopped = life['active'], life['stopped']
    if (active['mac'] & 0x0030e003 != 0xc003 or not active['tx'] & 1 or not active['rx'] & 1 or
            active['dma'] & 1 or active['macIrq'] or active['dmaIrq']): raise ValueError('active MAC not100-half/no IRQ')
    if stopped['mac'] & 3 or stopped['tx'] & 1 or stopped['rx'] & 1 or stopped['dma'] & 1 or stopped['macIrq'] or stopped['dmaIrq']:
        raise ValueError('private DMA/MAC stop not proved')
    before, after = life['timerInitial'], life['timerFinal']
    for value in (before, after):
        if value['cntp'] & 1 or (value['enabled'] | value['pending'] | value['active']) & (1 << 30):
            raise ValueError('CNTP/PPI30 not quiet')
        if value['frequency'] != 24000000 or value['level'] != 1: raise ValueError('timer context/frequency changed')
    for name in ('affinity', 'priority30', 'priority27', 'typer', 'cpuControl'):
        if before[name] != after[name]: raise ValueError('timer/GIC preservation changed: ' + name)
    if ((before['cntv'] ^ after['cntv']) & 3 or (before['enabled'] ^ after['enabled']) & (1 << 27) or
            (before['group'] ^ after['group']) & (1 << 30) or (before['config'] ^ after['config']) & (1 << 29)):
        raise ValueError('OS tick or own GIC fields changed')
    if after['counter'] < before['counter'] or after['ticks'] < before['ticks']:
        raise ValueError('counter/tick not monotonic in bounded test')
    return report

def match_replies(report, state, result):
    validate_owner(state, result)
    extra, life = report['nmt'], report['lifecycle']
    for private, public in (('resetLoops', 'resetLoops'), ('offLoops', 'offLoops')):
        if extra[private] != int(result[public]): raise ValueError('RPMsg/private loop mismatch')
    if (report['cache']['owner'] != int(state['owner']) or life['final']['processes'] != int(state['processes']) or
            life['final']['events'] != int(state['events'])): raise ValueError('RPMsg/private owner or counters mismatch')
