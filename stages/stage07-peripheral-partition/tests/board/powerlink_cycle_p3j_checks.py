"""Pinned P3j CYCLE ABI and successful completion gates. Pure stdlib, no IO.
Old NMT completion checks MUST NOT be applied to a transmitting cycle probe.
"""
import struct
from powerlink_eth_checks import fields
from powerlink_nmt_checks import mn, timer, original_clients

SHA = '4b4854157487a8ddfa07914c01efbe6c7215c1eed273f9e80e405f6b9c3d9c35'
SNAPSHOT_BYTES, CYCLE_BYTES = 1504, 608
CACHE_LAYOUT = [1504,40,80,576,496,472,472,488,40,16,24,64,80,120,160,216,256,280,376,96,40,48,88]
CYCLE_LAYOUT = [608,8,480,496,520,532,544,576,584,1504]
POOL_BYTES, FSC_HEAD_BYTES = 1048576, 32
MIN_HEADROOM, MODEL_STACK_PEAK = 262144, 505744
MIN_INITIAL_FREE = MIN_HEADROOM + MODEL_STACK_PEAK
PRIVATE_SIZES = dict(snapshot=1504, cycleResult=608, cycleReady=4, cycleAttempted=4,
    g_ethLease=4, g_excInfoInternal=520, g_memRegion00=POOL_BYTES,
    g_memTotalSize=8, g_memUsage=8, g_memPeakUsage=8, g_memStartAddr=8,
    g_tskCbArray=8, g_tskMaxNum=4, ownerTask=4)
U32_NAMES = ('resetSubmitted','offSubmitted','reached','stopCycleCalls','owner','pending','maxPending',
    'pendingAtStop','txBeforeRun','txAtStop','runLoops','drainLoops','offLoops','contextValid','watchdogTrips','frequency')
U64_NAMES = ('startCounter','endCounter','runCounter','lastTxCounter','pendingCounter','maxGapTicks','maxLateTicks','skippedPeriods')
PUBLIC = dict(abi='1', bytes='608', rc='0', clean='1', stage='9', stack='0x0', reset='1', off='1',
    reached='0x2fd', pending='0', stopCalls='1', trips='0', context='1')

def validate_reply(reply):
    result = fields(reply, 'PLK UP2 CYCLE')
    if set(result) != set(PUBLIC) | {'loops','run','drain','tx'} or any(result.get(k) != v for k,v in PUBLIC.items()):
        raise ValueError('P3j CYCLE incomplete/failed/not stopped')
    values = {k:int(result[k]) for k in ('loops','run','drain','tx')}
    if (not 1 <= values['tx'] <= 1024 or not 1 <= values['loops'] < 4000000 or
            not 0 < values['run'] < values['loops'] or not 0 < values['drain'] < values['loops'] or
            values['run'] + values['drain'] >= values['loops']):
        raise ValueError('P3j public process/traffic bounds invalid')
    return result

def validate_owner(state, result):
    validate_reply('PLK UP2 CYCLE ' + ' '.join(k+'='+v for k,v in result.items()))
    expected = dict(ready='1',pending='0',running='0',seq='1',done='1',cmd='8',rc='0x0',runtime='0x0',
        state='0',nmt='0x0',mode='bounded-cycle-diagnostic')
    if (set(state) != set(expected) | {'owner','processes','events'} or
            any(state.get(k) != v for k,v in expected.items()) or not 0 < int(state['owner']) < 64 or
            int(state['processes']) != int(result['loops']) or int(state['events']) < 10):
        raise ValueError('P3j owner not completed/COLD or missing process/event evidence')

def decode_cycle(raw):
    if len(raw) != CYCLE_BYTES: raise ValueError('not P3j 608B result')
    abi, size = struct.unpack_from('<2I', raw)
    if (abi,size) != (1,CYCLE_BYTES): raise ValueError('P3j result ABI mismatch')
    life = raw[8:480]
    result = dict(zip(('result','clean','stage','stackError','loops','leaseBefore','leaseAfter','timerBefore',
        'timerAfter','rx','tx','txDescriptors','dropped','rxErrors','txErrors','fatal'),struct.unpack_from('<16I',life)))
    result.update(zip(('timerIrqs','timerCallbacks'),struct.unpack_from('<2Q',life,64)))
    result.update(initialized=mn(life,80),prepared=mn(life,120),final=mn(life,160),
        active=dict(zip(('mac','tx','rx','dma','macIrq','dmaIrq'),struct.unpack_from('<6I',life,216))),
        stopped=dict(zip(('mac','tx','rx','dma','macIrq','dmaIrq'),struct.unpack_from('<6I',life,256))),
        timerInitial=timer(life,280),timerFinal=timer(life,376))
    cycle = dict(abi=abi,bytes=size)
    cycle.update(zip(U32_NAMES,struct.unpack_from('<16I',raw,480)))
    cycle.update(zip(U64_NAMES,struct.unpack_from('<8Q',raw,544)))
    return dict(lifecycle=result,cycle=cycle)

def validate_snapshot(raw, cycle_raw, ready, attempted):
    if len(raw) != SNAPSHOT_BYTES or (ready,attempted) != (1,1):
        raise ValueError('P3j cache/result not published exactly once')
    report = decode_cycle(cycle_raw); life,c = report['lifecycle'],report['cycle']
    cache = dict(zip(('ready','pending','running','seq','done','cmd','rc','runtime','owner'),struct.unpack_from('<9I',raw)))
    report.update(cache=cache,mn=mn(raw,40))
    expected = dict(ready=1,pending=0,running=0,seq=1,done=1,cmd=8,rc=0,runtime=0)
    if any(cache[k] != v for k,v in expected.items()) or not 0 < cache['owner'] < 64 or any(raw[80:]):
        raise ValueError('P3j mailbox incomplete or another probe executed')
    if (life['result'],life['clean'],life['stage'],life['stackError']) != (0,1,9,0):
        raise ValueError('P3j lifecycle failed/incomplete')
    if (c['resetSubmitted'],c['offSubmitted'],c['reached'],c['stopCycleCalls'],c['contextValid'],
            c['watchdogTrips'],c['frequency'],c['pending']) != (1,1,0x2fd,1,1,0,24000000,0):
        raise ValueError('P3j command/context/timer/pending evidence invalid')
    if c['owner'] != cache['owner'] or report['mn'] != life['final']:
        raise ValueError('P3j private owner/status inconsistent')
    for name,state in (('initialized',1),('prepared',2),('final',0)):
        s = life[name]
        if s['state'] != state or s['owner'] != c['owner'] or s['lastError'] or s['nmtState']:
            raise ValueError('P3j lifecycle owner/error/state invalid')
        if name != 'final' and (s['events'] or s['processes']): raise ValueError('P3j not initially dormant')
    if (not 1 <= life['loops'] < 4000000 or life['final']['processes'] != life['loops'] or life['final']['events'] < 10 or
            not 1 <= c['offLoops'] <= 32 or not c['runLoops'] or not c['drainLoops'] or
            c['runLoops'] + c['drainLoops'] + c['offLoops'] >= life['loops']):
        raise ValueError('P3j process/phase bounds invalid')
    for name in ('leaseBefore','leaseAfter','timerBefore','timerAfter','rx','rxErrors','txErrors','fatal','txDescriptors'):
        if life[name]: raise ValueError('P3j unexpected lease/error/traffic: '+name)
    # txDescriptors is unused by this probe (always zero), not completed TX.
    if (not 0 <= c['txBeforeRun'] < c['txAtStop'] <= life['tx'] <= 1024 or
            not 0 <= c['pendingAtStop'] <= c['maxPending'] < 8 or
            life['tx'] != c['txAtStop'] + c['pendingAtStop'] or not life['timerIrqs'] or not life['timerCallbacks']):
        raise ValueError('P3j completion/drain/IRQ evidence missing')
    start,end,run = c['startCounter'],c['endCounter'],c['runCounter']
    if (not start <= run <= end or not 0 < end-start < 8000*24000 or
            not start <= c['lastTxCounter'] <= end or not start <= c['pendingCounter'] <= end or
            c['maxGapTicks'] > end-start or c['maxLateTicks'] > 500*24 or c['skippedPeriods']):
        raise ValueError('P3j clock/budget/late evidence invalid')
    # Snapshot has no reset/drain/stopCounter: these are necessary bounds only.
    # Pinned production code enforces the exact NMT/Operational/drain deadlines.
    if c['txAtStop']-c['txBeforeRun'] < 256 and end-run < 100*24000:
        raise ValueError('P3j neither time nor TX completion limit reached')
    active,stopped = life['active'],life['stopped']
    if (active['mac'] & 0x0030e003 != 0xc003 or not active['tx'] & 1 or not active['rx'] & 1 or
            active['dma'] & 1 or active['macIrq'] or active['dmaIrq']): raise ValueError('P3j active MAC not100half/noIRQ')
    if stopped['mac'] & 3 or stopped['tx'] & 1 or stopped['rx'] & 1 or stopped['dma'] & 1 or stopped['macIrq'] or stopped['dmaIrq']:
        raise ValueError('P3j DMA/MAC stop not proved')
    before,after = life['timerInitial'],life['timerFinal']
    for t in (before,after):
        if t['frequency'] != 24000000 or t['level'] != 4 or t['cntp'] & 1 or (t['enabled']|t['pending']|t['active']) & (1<<30):
            raise ValueError('P3j CNTP/PPI30 not quiet')
    for name in ('affinity','priority30','priority27','typer','cpuControl'):
        if before[name] != after[name]: raise ValueError('P3j timer/GIC preservation: '+name)
    if ((before['cntv']^after['cntv']) & 3 or (before['enabled']^after['enabled']) & (1<<27) or
            (before['group']^after['group']) & (1<<30) or (before['config']^after['config']) & (1<<29) or
            not start == before['counter'] <= after['counter'] <= end or after['ticks'] < before['ticks']):
        raise ValueError('P3j OS tick/GIC/clock preservation invalid')
    return report

def match_replies(report, state, result):
    validate_owner(state,result)
    c,life = report['cycle'],report['lifecycle']
    for key,value in dict(loops=life['loops'],run=c['runLoops'],drain=c['drainLoops'],tx=life['tx']).items():
        if int(result[key]) != value: raise ValueError('P3j RPMsg/private mismatch: '+key)
    if (int(state['owner']) != c['owner'] or int(state['processes']) != life['final']['processes'] or
            int(state['events']) != life['final']['events']): raise ValueError('P3j RPMsg/private owner counters differ')

def validate_abi_report(proof, symbols):
    if (proof.get('passed') is not True or proof.get('candidate_sha256') != SHA or
            proof.get('cache_native') != CACHE_LAYOUT or proof.get('cache_aarch64') != CACHE_LAYOUT or
            proof.get('cycle_native') != CYCLE_LAYOUT or proof.get('cycle_aarch64') != CYCLE_LAYOUT or
            proof.get('fsc_native') != [32,8] or proof.get('fsc_aarch64') != [32,8] or
            proof.get('symbols') != {name:list(symbols[name][:2]) for name in PRIVATE_SIZES}):
        raise ValueError('missing pinned P3j native/AArch64/cache/cycle/FSC/private-symbol proof')

def validate_heap(values, pool, phase):
    names = ('g_memTotalSize','g_memUsage','g_memPeakUsage','g_memStartAddr')
    if phase not in ('COLD','STOPPED') or set(values) != set(names): raise ValueError('unknown FSC phase/fields')
    if any(type(x) is not int or x < 0 for x in (*values.values(),pool)): raise ValueError('invalid FSC metadata type')
    total,used,peak,start = (values[name] for name in names)
    if (not 0x7c200000 <= pool <= 0x7ca00000-POOL_BYTES or total != POOL_BYTES-FSC_HEAD_BYTES or
            start != pool or not used <= peak <= total): raise ValueError('invalid P3j 1MiB FSC geometry/counters')
    if total-peak < MIN_HEADROOM or (phase == 'COLD' and total-used < MIN_INITIAL_FREE):
        raise ValueError('insufficient P3j reviewed FSC allowance/headroom')
    return dict(candidate_sha256=SHA,phase=phase,pool_start=pool,pool_bytes=POOL_BYTES,scalars=dict(values),
        free_bytes=total-used,peak_headroom_bytes=total-peak,minimum_headroom_bytes=MIN_HEADROOM,
        minimum_initial_free_bytes=MIN_INITIAL_FREE,model_stack_peak_bytes=MODEL_STACK_PEAK,
        limit='Scalar FSC metadata only, not fragmentation, exact leak or real-time proof.')

def validate_heap_report(report, phase):
    if report != validate_heap(report['scalars'],report['pool_start'],phase): raise ValueError('P3j heap report changed')
    return report

def match_heap(before, after):
    validate_heap_report(before,'COLD'); validate_heap_report(after,'STOPPED')
    if before['pool_start'] != after['pool_start'] or after['scalars']['g_memPeakUsage'] < before['scalars']['g_memPeakUsage']:
        raise ValueError('P3j FSC pool/peak regressed')
    return dict(used_delta_bytes=after['scalars']['g_memUsage']-before['scalars']['g_memUsage'],
        peak_bytes=after['scalars']['g_memPeakUsage'],peak_headroom_bytes=after['peak_headroom_bytes'],
        limit='Includes RTOS/RPMsg allocations; usage delta is not an exact leak verdict.')
