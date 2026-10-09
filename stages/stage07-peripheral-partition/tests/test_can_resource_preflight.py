#!/usr/bin/env python3
"""Decode synthetic snapshots without touching board registers."""

import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "can_resource_preflight", Path(__file__).parent / "board/can_resource_preflight.py")
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


class CanResourcePreflightTests(unittest.TestCase):
    def values(self, profile):
        values = dict.fromkeys(PREFLIGHT.gic_addresses(profile["spi"] + 32).values(), 0)
        values.update({PREFLIGHT.CRU + 0x82C: 0, PREFLIGHT.CRU + 0xA2C: 0,
                       profile["clksel"]: 3 << 7,
                       profile["iomux"]: profile["iomux_value"]})
        return values

    def test_live_dt_pin_fields_are_disjoint(self):
        self.assertEqual(PREFLIGHT.RESOURCES["can1"]["iomux"], 0x2608608C)
        self.assertEqual(PREFLIGHT.RESOURCES["can3"]["iomux"], 0x2608203C)
        for profile in PREFLIGHT.RESOURCES.values():
            self.assertTrue(PREFLIGHT.decode_resource(profile, self.values(profile))
                            ["pinmux_matches_live_dt"])

    def test_spi_numbers_are_converted_to_intids(self):
        self.assertEqual(PREFLIGHT.RESOURCES["can1"]["spi"] + 32, 185)
        self.assertEqual(PREFLIGHT.RESOURCES["can3"]["spi"] + 32, 187)
        self.assertEqual(PREFLIGHT.gic_addresses(185)["target"], 0x2A6018B8)
        self.assertEqual(PREFLIGHT.gic_addresses(187)["config"], 0x2A601C2C)
        with self.assertRaises(ValueError):
            PREFLIGHT.gic_addresses(27)

    def test_shared_gic_word_uses_only_own_fields(self):
        for name, intid, target, priority in (("can1", 185, 0x10, 0xA0),
                                              ("can3", 187, 0x20, 0x90)):
            profile = PREFLIGHT.RESOURCES[name]
            values = self.values(profile)
            gic = PREFLIGHT.gic_addresses(intid)
            values[gic["target"]] = 0x20001000
            values[gic["priority"]] = 0x9000A000
            values[gic["enabled"]] = 1 << (intid % 32)
            decoded = PREFLIGHT.decode_resource(profile, values)
            self.assertEqual(decoded["gic_target_mask"], target)
            self.assertEqual(decoded["gic_priority"], priority)
            self.assertTrue(decoded["gic_enabled"])
            self.assertFalse(decoded["gic_edge_triggered"])

    def test_gate_reset_and_divider_decoding(self):
        profile = PREFLIGHT.RESOURCES["can1"]
        values = self.values(profile)
        values[PREFLIGHT.CRU + 0x82C] = 1 << 9
        values[PREFLIGHT.CRU + 0xA2C] = 1 << 10
        values[profile["clksel"]] = (1 << 12) | (4 << 7)
        decoded = PREFLIGHT.decode_resource(profile, values)
        self.assertTrue(decoded["hclk_gated"])
        self.assertFalse(decoded["baudclk_gated"])
        self.assertFalse(decoded["hclk_reset_asserted"])
        self.assertTrue(decoded["can_reset_asserted"])
        self.assertEqual(decoded["clock_parent_selector"], 1)
        self.assertEqual(decoded["clock_divider"], 5)

    def test_other_controller_bits_do_not_change_own_state(self):
        profile = PREFLIGHT.RESOURCES["can3"]
        values = self.values(profile)
        values[PREFLIGHT.CRU + 0x82C] = (1 << 9) | (1 << 10)
        values[PREFLIGHT.CRU + 0xA2C] = (1 << 9) | (1 << 10)
        decoded = PREFLIGHT.decode_resource(profile, values)
        self.assertFalse(decoded["hclk_gated"])
        self.assertFalse(decoded["baudclk_gated"])
        self.assertFalse(decoded["hclk_reset_asserted"])
        self.assertFalse(decoded["can_reset_asserted"])


if __name__ == "__main__":
    unittest.main()
