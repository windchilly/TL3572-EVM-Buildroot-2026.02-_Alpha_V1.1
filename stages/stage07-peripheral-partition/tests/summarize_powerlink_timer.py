"""Summarize actual board raw counters; never substitute simulation for hardware."""
import json
from pathlib import Path
evidence = Path(__file__).resolve().parent / 'powerlink-timer-p3c-20261010'
board = json.loads((evidence / 'board-result.json').read_text())
snapshot = json.loads((evidence / 'board-snapshot-final.json').read_text())
assert board['passed'] and board['cleanup'] and len(board['cycles']) == 3
assert snapshot['seq'] == snapshot['done'] == 3 and snapshot['timer']['clean'] == 1
assert snapshot['before']['typer'] & (1 << 10) and snapshot['before']['group'] == 0
for name in ('cntv', 'priority27', 'priority30', 'group', 'config', 'typer', 'cpuControl', 'enabled'):
    assert snapshot['before'][name] == snapshot['after'][name], name
samples = []
for cycle in board['cycles']:
    assert all(cycle[name] == value for name, value in dict(rc='0', clean='1', samples='24', irqs='24', callbacks='24').items())
    hz = int(cycle['hz'])
    samples.append(dict(irq_late_ticks=int(cycle['irqLate']), callback_late_ticks=int(cycle['taskLate']),
                        irq_late_us=int(cycle['irqLate']) * 1000000 / hz,
                        callback_late_us=int(cycle['taskLate']) * 1000000 / hz,
                        system_ticks=int(cycle['ticks'])))
report = dict(phase='P3c hardware diagnostic sample, NOT industrial worst-case certification',
              periods_ns=[100000, 1000000, 10000000], samples_per_period_per_cycle=8,
              total_interrupts=72, total_task_callbacks=72, cycles=samples,
              max_observed_irq_late_us=max(x['irq_late_us'] for x in samples),
              max_observed_callback_late_us=max(x['callback_late_us'] for x in samples),
              cntfrq_hz=24000000, timer_access_irq_and_cleanup_passed=True,
              gic_securityextn=True, nonsecure_igroupr_read_zero=True,
              no_powerlink_mn_or_ethernet_test=True, candidate_sha256=board['candidate_sha256'])
(evidence / 'hardware-summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(report, indent=2))
