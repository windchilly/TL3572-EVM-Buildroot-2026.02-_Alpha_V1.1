from pathlib import Path
import unittest
from audit_powerlink_stack import CHAIN, audit, frame
def assembly(input_frame):
    sizes = (576,352,input_frame,176,608,80,80,752)
    parts = []
    for index, (name, size) in enumerate(zip(CHAIN, sizes)):
        parts.append(f'{index*256:016x} <{name}>:\n  0: 00000000 sub sp, sp, #0x{size:x}')
        if index+1 < len(CHAIN): parts.append(f'  4: 00000000 bl 100 <{CHAIN[index+1]}>')
    return '\n'.join(parts)
class StackBudgetTests(unittest.TestCase):
    def test_old_p3f_real_frame_regression(self):
        with self.assertRaisesRegex(ValueError, '4336'): audit(assembly(1712))
    def test_fixed_frame_and_reserve(self):
        result = audit(assembly(320))
        self.assertEqual(result['known_frames'], 2944)
        self.assertEqual(result['remaining_after_reserve'], 128)
    def test_unknown_or_missing_rejected(self):
        with self.assertRaises(ValueError): audit('')
        with self.assertRaises(ValueError): frame(['0: 00000000 ret'])
    def test_preindex_and_shift(self):
        self.assertEqual(frame(['0: 00000000 stp x30, x19, [sp, #-80]!']),80)
        self.assertEqual(frame(['0: 00000000 sub sp, sp, #0x1, lsl #12']),4096)
    def test_call_edges_required(self):
        with self.assertRaisesRegex(ValueError,'edge'): audit(assembly(320).replace('bl 100 <SecOutput>','bl 100 <Other>'))
    def test_reply_lifetime_and_guard(self):
        text=(Path(__file__).resolve().parents[1] / 'source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_powerlink_app.c').read_text()
        self.assertIn('static M7PowerlinkSnapshot out;',text)
        self.assertIn('static char reply[384];',text)
        self.assertIn('if (inputActive)',text)
        self.assertLess(text.index('out = snapshot;'),text.index('inputActive = 0;'))
    def test_final_candidate_audit_wires_budget(self):
        text=(Path(__file__).with_name('audit_powerlink_mn_probe.py')).read_text()
        self.assertIn('stack = stack_audit(assembly)',text)
        self.assertIn("report['rpmsg_stack_budget'] = stack",text)
if __name__ == '__main__': unittest.main()
