"""P3h-only image and real FSC heap gates, pure/stdlib; no IO at import.
NMT cache ABI/quiet-state checks are shared, NOT the P3g candidate identity.
"""
from powerlink_nmt_checks import (SNAPSHOT_BYTES, original_clients, validate_reply,
    validate_owner, validate_snapshot, match_replies, decode_snapshot)
SHA = 'ccfba235f8f3bcc79ab0c2a0e603b2d9cc01a7f3785985566660fb1672882ea8'
POOL_BYTES, FSC_HEAD_BYTES = 1048576, 32
CACHE_LAYOUT = [1504, 40, 80, 576, 496, 472, 472, 488, 40, 16, 24, 64, 80, 120, 160, 216, 256, 280, 376, 96, 40, 48, 88]
PRIVATE_SIZES = dict(snapshot=1504, g_ethLease=4, g_excInfoInternal=520, g_memRegion00=POOL_BYTES,
    g_memTotalSize=8, g_memUsage=8, g_memPeakUsage=8, g_memStartAddr=8, g_tskCbArray=8, g_tskMaxNum=4)
MIN_HEADROOM = 256 * 1024
# P3h constrained HOST model: 636816 peak - 131072 non-PLK reserve.
# This is a preflight allowance, NOT a proven RTOS worst-case bound.
MODEL_STACK_PEAK = 505744
MIN_INITIAL_FREE = MODEL_STACK_PEAK + MIN_HEADROOM

def validate_abi_report(proof, symbols):
    if (proof.get('passed') is not True or proof.get('candidate_sha256') != SHA or
            proof.get('cache_native') != CACHE_LAYOUT or proof.get('cache_aarch64') != CACHE_LAYOUT or
            proof.get('fsc_native') != [FSC_HEAD_BYTES, 8] or proof.get('fsc_aarch64') != [FSC_HEAD_BYTES, 8]):
        raise ValueError('missing pinned P3h native/AArch64 cache/FSC ABI proof')
    if proof.get('symbols') != {name:list(symbols[name][:2]) for name in PRIVATE_SIZES}:
        raise ValueError('ABI proof symbols do not match P3h ELF')

def validate_heap(values, pool, phase):
    names = ('g_memTotalSize', 'g_memUsage', 'g_memPeakUsage', 'g_memStartAddr')
    if phase not in ('COLD', 'STOPPED') or set(values) != set(names): raise ValueError('unknown heap phase/fields')
    if any(type(x) is not int or x < 0 for x in (*values.values(), pool)): raise ValueError('invalid heap metadata type')
    if not 0x7c200000 <= pool <= 0x7ca00000 - POOL_BYTES: raise ValueError('FSC pool outside UP2 private image')
    total, used, peak, start = (values[name] for name in names)
    if total != POOL_BYTES - FSC_HEAD_BYTES or start != pool or not used <= peak <= total:
        raise ValueError('not initialized P3h 1MiB FSC heap or corrupt counters')
    if total - peak < MIN_HEADROOM: raise ValueError('real FSC peak leaves less than reviewed 256KiB margin')
    if phase == 'COLD' and total - used < MIN_INITIAL_FREE:
        raise ValueError('insufficient free heap before the only NMT submission')
    return dict(candidate_sha256=SHA, phase=phase, pool_start=pool, pool_bytes=POOL_BYTES,
        scalars=dict(values), free_bytes=total-used, peak_headroom_bytes=total-peak,
        model_stack_peak_bytes=MODEL_STACK_PEAK, minimum_initial_free_bytes=MIN_INITIAL_FREE,
        minimum_headroom_bytes=MIN_HEADROOM,
        limit='Scalar FSC counters only, not a heap traversal, fragmentation/whole-program leak proof or real-time guarantee.')

def validate_heap_report(report, phase):
    if report != validate_heap(report['scalars'], report['pool_start'], phase): raise ValueError('heap report changed')
    return report

def match_heap(before, after):
    validate_heap_report(before, 'COLD'); validate_heap_report(after, 'STOPPED')
    if before['pool_start'] != after['pool_start'] or after['scalars']['g_memPeakUsage'] < before['scalars']['g_memPeakUsage']:
        raise ValueError('FSC region/peak regressed between the two phases')
    return dict(used_delta_bytes=after['scalars']['g_memUsage']-before['scalars']['g_memUsage'],
        peak_bytes=after['scalars']['g_memPeakUsage'], peak_headroom_bytes=after['peak_headroom_bytes'],
        limit='Usage delta recorded, not an exact leak verdict; RTOS/RPMsg background allocation is included.')
