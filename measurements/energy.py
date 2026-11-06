"""Energy integration with explicit calibration, missing-data and coverage checks."""
import math


def valid_power(channel):
    if not isinstance(channel, dict) or channel.get('sensor_ok') is not True or channel.get('measurement_valid') is not True:
        return None
    v, i, p = (channel.get(k) for k in ('voltage_v', 'current_a', 'power_w'))
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in (v, i, p)):
        return None
    if not 4 <= v <= 6 or not -0.01 <= i < 3.2 or p < 0 or abs(p - v * i) > 0.03:
        return None
    return float(p)


def integrate(trace, start, end, verified=False, max_gap_s=2.5, min_coverage=0.99):
    """Clip linear segments to the window; never bridge invalid/missing samples.

    Times are host monotonic MQTT receipt timestamps, not ADC trigger timestamps.
    Boundary samples may lie just outside the window. Data must cover >= min_coverage (default 99%).
    """
    duration = end - start
    if duration <= 0:
        raise ValueError('Window duration must be positive')
    joules = covered = 0.0
    for (ta, pa), (tb, pb) in zip(trace, trace[1:]):
        if pa is None or pb is None or not 0 < tb - ta <= max_gap_s:
            continue
        a, b = max(start, ta), min(end, tb)
        if b <= a:
            continue
        va = pa + (pb - pa) * (a - ta) / (tb - ta)
        vb = pa + (pb - pa) * (b - ta) / (tb - ta)
        joules += (va + vb) / 2 * (b - a)
        covered += b - a
    reasons = []
    if not verified:
        reasons.append('meter_not_verified')
    if covered < duration * min_coverage:
        reasons.append('insufficient_valid_power_coverage')
    valid = not reasons
    return {'valid': valid, 'reasons': reasons, 'duration_s': duration,
            'covered_s': covered, 'coverage': covered / duration,
            'energy_j': joules if valid else None,
            'energy_wh': joules / 3600 if valid else None,
            'average_w': joules / covered if valid and covered else None,
            'projected_wh_per_day_at_this_workload': joules / covered * 24 if valid and covered else None}


def energy_metrics(baseline, active, predictions, all_requests_matched):
    ready = baseline['valid'] and active['valid'] and predictions > 0 and all_requests_matched
    if not ready:
        return {'valid': False, 'total_j_per_prediction': None,
                'incremental_j_per_prediction': None, 'reason': 'valid_power_and_complete_inference_counts_required'}
    incremental = active['energy_j'] - baseline['average_w'] * active['duration_s']
    return {'valid': True, 'total_j_per_prediction': active['energy_j'] / predictions,
            'incremental_j_per_prediction': incremental / predictions,
            'incremental_resolved_above_baseline': incremental > 0,
            'note': 'Negative/near-zero differences require uncertainty analysis; no clamping.'}


class MinuteEnergy:
    """Energy accumulated per wall-clock minute, so a live window survives restarts.

    Same rules as integrate(): linear segments between consecutive valid samples, never across
    invalid/missing samples or gaps > max_gap_s. Times are epoch seconds (ESP32 sample time).
    """

    def __init__(self, max_gap_s=2.5):
        self.max_gap_s = max_gap_s
        self.buckets = {}          # minute start (int epoch s) -> [joules, covered_s]
        self.last = None           # (t, p) of the previous sample

    def add(self, t, p):
        if self.last is not None and t <= self.last[0]:
            return
        prev, self.last = self.last, (t, p)
        if prev is None or prev[1] is None or p is None or not 0 < t - prev[0] <= self.max_gap_s:
            return
        ta, pa = prev
        a = ta
        while a < t:                                   # split the segment at minute boundaries
            b = min(t, (math.floor(a / 60) + 1) * 60)
            va = pa + (p - pa) * (a - ta) / (t - ta)
            vb = pa + (p - pa) * (b - ta) / (t - ta)
            bucket = self.buckets.setdefault(int(math.floor(a / 60) * 60), [0.0, 0.0])
            bucket[0] += (va + vb) / 2 * (b - a)
            bucket[1] += b - a
            a = b

    def totals(self, start):
        """(joules, covered_s) of whole minutes from the minute containing start onwards."""
        m0 = math.floor(start / 60) * 60
        j = c = 0.0
        for m, (bj, bc) in self.buckets.items():
            if m >= m0:
                j += bj; c += bc
        return j, c

    def prune(self, before):
        for m in [m for m in self.buckets if m + 60 <= before]:
            del self.buckets[m]

    def to_json(self):
        return {'max_gap_s': self.max_gap_s, 'buckets': {str(m): v for m, v in self.buckets.items()}}

    @classmethod
    def from_json(cls, d):
        e = cls(d.get('max_gap_s', 2.5))
        e.buckets = {int(m): [float(v[0]), float(v[1])] for m, v in d.get('buckets', {}).items()}
        return e


def window_result(joules, covered, duration, verified, min_coverage):
    """Same fields as integrate() for a window whose duration already excludes recorder downtime."""
    reasons = []
    if not verified:
        reasons.append('meter_not_verified')
    if duration <= 0 or covered < duration * min_coverage:
        reasons.append('insufficient_valid_power_coverage')
    valid = not reasons
    return {'valid': valid, 'reasons': reasons, 'duration_s': duration,
            'covered_s': covered, 'coverage': covered / duration if duration > 0 else None,
            'energy_j': joules if valid else None,
            'energy_wh': joules / 3600 if valid else None,
            'average_w': joules / covered if valid and covered else None,
            'projected_wh_per_day_at_this_workload': joules / covered * 24 if valid and covered else None}
