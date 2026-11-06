import unittest
from energy import integrate, valid_power, energy_metrics, MinuteEnergy, window_result


class EnergyTests(unittest.TestCase):
    def test_units_and_boundaries(self):
        r = integrate([(-1, 5.), (1, 5.), (3, 5.), (5, 5.)], 0, 4, True)
        self.assertTrue(r['valid'])
        self.assertEqual(r['energy_j'], 20)
        self.assertEqual(r['average_w'], 5)
        self.assertEqual(r['projected_wh_per_day_at_this_workload'], 120)
        self.assertAlmostEqual(r['energy_wh'], 20 / 3600)

    def test_invalid_meter_and_gaps_never_become_zero_energy(self):
        for trace, verified in [([], True), ([(0, 5), (10, 5)], True),
                                ([(0, 5), (1, None), (2, 5)], True),
                                ([(0, 5), (1, 5), (2, 5)], False)]:
            r = integrate(trace, 0, 2, verified)
            self.assertFalse(r['valid'])
            self.assertIsNone(r['energy_j'])
        self.assertIsNone(valid_power({'sensor_ok': True, 'voltage_v': 5.1, 'current_a': .5, 'power_w': 2.55}))
        self.assertIsNone(valid_power({'sensor_ok': True, 'measurement_valid': True, 'voltage_v': .05, 'current_a': .5, 'power_w': .1}))

    def test_min_coverage_threshold(self):
        trace = [(t, 5.) for t in range(0, 97)]          # 96 of 100 s covered
        self.assertFalse(integrate(trace, 0, 100, True)['valid'])
        r = integrate(trace, 0, 100, True, min_coverage=0.95)
        self.assertTrue(r['valid'])
        self.assertAlmostEqual(r['coverage'], 0.96)
        self.assertEqual(r['average_w'], 5)

    def test_minute_energy_matches_integrate_and_survives_json(self):
        t0 = 1_700_000_030.0                          # mulai di tengah menit
        trace = [(t0 + i, 5.0 + (i % 7) * 0.1) for i in range(200)]
        e = MinuteEnergy(max_gap_s=2.5)
        for t, p in trace:
            e.add(t, p)
        ref = integrate(trace, t0, trace[-1][0], True)
        j, c = e.totals(t0)
        self.assertAlmostEqual(j, ref['energy_j'], places=6)
        self.assertAlmostEqual(c, ref['covered_s'], places=6)
        e2 = MinuteEnergy.from_json(e.to_json())
        self.assertEqual(e2.totals(t0), e.totals(t0))
        e.prune(t0 + 120)
        self.assertLess(e.totals(t0)[1], c)

    def test_minute_energy_never_bridges_gaps_or_invalid(self):
        e = MinuteEnergy(max_gap_s=2.5)
        for t, p in [(0, 5), (1, 5), (10, 5), (11, None), (12, 5), (13, 5)]:
            e.add(t, p)
        self.assertEqual(e.totals(0), (10.0, 2.0))   # hanya 0-1 dan 12-13
        e.add(12.5, 5)                                # sampel mundur diabaikan
        self.assertEqual(e.totals(0)[1], 2.0)

    def test_window_result_excludes_downtime_by_duration(self):
        r = window_result(500.0, 99.0, 100.0, True, 0.95)
        self.assertTrue(r['valid']); self.assertEqual(r['average_w'], 500 / 99)
        self.assertFalse(window_result(500.0, 90.0, 100.0, True, 0.95)['valid'])

    def test_incremental_is_separate_from_total(self):
        b = integrate([(0, 4), (1, 4), (2, 4)], 0, 2, True)
        a = integrate([(0, 5), (1, 5), (2, 5)], 0, 2, True)
        r = energy_metrics(b, a, 20, True)
        self.assertEqual(r['total_j_per_prediction'], .5)
        self.assertAlmostEqual(r['incremental_j_per_prediction'], .1)
        self.assertFalse(energy_metrics(b, a, 20, False)['valid'])


if __name__ == '__main__':
    unittest.main()
