"""
vinci_vita_portfolio_v3.py
AURORA ENGINE v3.4 — Portfolio multi-profilo + Sestina UNIFICATA.

Modalità:
- build_single(): genera 1 sestina ottimale (A+B+C combinati)
- build(): genera 3 sestine separate (legacy, non usato)
"""
import itertools
import math
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


SUM_MIN = 240
SUM_MAX = 310

# Pesi compositi per sestina unificata
WEIGHT_A = 0.40
WEIGHT_B = 0.30
WEIGHT_C = 0.30


class AuroraPortfolioV3:

    def __init__(self, history: List[dict]):
        self.history = [d for d in history
                        if isinstance(d.get("numeri"), list) and len(d["numeri"]) == 8]
        self.n = len(self.history)
        self._freq = self._compute_freq()
        self._gaps = self._compute_gaps()
        self._hot_recent = self._compute_hot_recent(window=10)

    def _compute_freq(self) -> Dict[int, int]:
        freq = defaultdict(int)
        for d in self.history:
            for n in d["numeri"]:
                freq[n] += 1
        return dict(freq)

    def _compute_gaps(self) -> Dict[int, int]:
        gaps = {n: self.n for n in range(1, 91)}
        for idx, d in enumerate(reversed(self.history)):
            for n in d["numeri"]:
                if gaps[n] == self.n:
                    gaps[n] = idx
        return gaps

    def _compute_hot_recent(self, window: int = 10) -> Dict[int, int]:
        recent = self.history[-window:] if len(self.history) >= window else self.history
        freq = defaultdict(int)
        for d in recent:
            for n in d["numeri"]:
                freq[n] += 1
        return dict(freq)

    def _score_trend_follower(self, combo: Tuple[int, ...]) -> float:
        hot_score = sum(self._hot_recent.get(n, 0) for n in combo) / 6.0
        s = sorted(combo)
        n_pari = sum(1 for x in s if x % 2 == 0)
        n_low = sum(1 for x in s if x < 30)
        n_high = sum(1 for x in s if x > 60)
        parity_ok = 1.0 if 2 <= n_pari <= 4 else 0.5
        low_ok = 1.0 if 1 <= n_low <= 3 else 0.6
        high_ok = 1.0 if 2 <= n_high <= 4 else 0.6
        return hot_score * parity_ok * low_ok * high_ok

    def _score_contrarian(self, combo: Tuple[int, ...]) -> float:
        gaps = [self._gaps.get(n, 0) for n in combo]
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        s = sorted(combo)
        n_high = sum(1 for x in s if x > 60)
        n_low = sum(1 for x in s if x < 30)
        if n_high > 3:
            return avg_gap * 0.5
        if n_low < 1:
            return avg_gap * 0.7
        return avg_gap

    def _score_coverage(self, combo: Tuple[int, ...], crowd_model=None) -> float:
        if crowd_model:
            ac = crowd_model.anti_crowd_score_v3(list(combo))
        else:
            ac = sum(1.5 if n > 60 else (1.2 if n > 45 else 0.7) for n in combo)
        n_decades = len(set((n - 1) // 10 for n in combo))
        s = sorted(combo)
        spread = s[-1] - s[0]
        return ac * (n_decades / 6.0) * (spread / 80.0)

    def _portfolio_coverage(self, sestinas: List[List[int]]) -> float:
        all_nums = set()
        for s in sestinas:
            all_nums.update(s)
        if not all_nums:
            return 0.0
        unique_ratio = len(all_nums) / (6 * len(sestinas))
        decades = set((n - 1) // 10 for n in all_nums)
        decade_ratio = len(decades) / 9.0
        n_low = sum(1 for n in all_nums if n < 30)
        n_mid = sum(1 for n in all_nums if 30 <= n <= 60)
        n_high = sum(1 for n in all_nums if n > 60)
        total = len(all_nums)
        balance = 1.0 - (
            abs(n_low / total - 0.33) +
            abs(n_mid / total - 0.33) +
            abs(n_high / total - 0.33)
        ) / 2.0
        return 0.5 * unique_ratio + 0.3 * decade_ratio + 0.2 * balance

    # ==========================================
    # SESTINA UNIFICATA (1 sola)
    # ==========================================
    def build_single(self, pool: List[int], fp_engine=None,
                     crowd_model=None, bias_weights: Optional[Dict] = None,
                     verbose: bool = True) -> List[Dict]:
        """
        Genera UNA sola sestina ottimale combinando i 3 profili.
        Pesi: 40% trend, 30% contrarian, 30% coverage.
        """
        if len(pool) < 6:
            return []

        all_combos = []
        for combo in itertools.combinations(pool, 6):
            ssum = sum(combo)
            if SUM_MIN <= ssum <= SUM_MAX:
                all_combos.append(combo)

        if verbose:
            print(f"[*] Combinazioni valide: {len(all_combos)}")

        w_a = (bias_weights or {}).get("A_trend", 1.0)
        w_b = (bias_weights or {}).get("B_contrarian", 1.0)
        w_c = (bias_weights or {}).get("C_coverage", 1.0)

        scored = []
        for combo in all_combos:
            s_a = self._score_trend_follower(combo) * w_a
            s_b = self._score_contrarian(combo) * w_b
            s_c = self._score_coverage(combo, crowd_model) * w_c

            composite = WEIGHT_A * s_a + WEIGHT_B * s_b + WEIGHT_C * s_c
            scored.append((combo, composite, s_a, s_b, s_c))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return []

        best = scored[0]
        if verbose:
            print(f"[*] Migliore UNIFIED: {list(best[0])} (composite {best[1]:.3f})")
            print(f"    A={best[2]:.3f} B={best[3]:.3f} C={best[4]:.3f}")

        return [{
            "profilo": "UNIFIED",
            "numeri": list(best[0]),
            "score_profilo": round(best[1], 4),
        }]

    # ==========================================
    # LEGACY: 3 sestine separate
    # ==========================================
    def build(self, pool: List[int], fp_engine=None,
              crowd_model=None, bias_weights: Optional[Dict] = None,
              verbose: bool = True) -> List[Dict]:
        if len(pool) < 6:
            return []

        all_combos = []
        for combo in itertools.combinations(pool, 6):
            ssum = sum(combo)
            if SUM_MIN <= ssum <= SUM_MAX:
                all_combos.append(combo)

        scored = {
            "A_trend": [],
            "B_contrarian": [],
            "C_coverage": [],
        }
        for combo in all_combos:
            scored["A_trend"].append((combo, self._score_trend_follower(combo)))
            scored["B_contrarian"].append((combo, self._score_contrarian(combo)))
            scored["C_coverage"].append((combo, self._score_coverage(combo, crowd_model)))

        if bias_weights:
            for profile, items in scored.items():
                w = bias_weights.get(profile, 1.0)
                scored[profile] = [(c, s * w) for c, s in items]

        portfolio = []
        for profile, items in scored.items():
            items.sort(key=lambda x: x[1], reverse=True)
            if items:
                portfolio.append({
                    "profilo": profile,
                    "numeri": list(items[0][0]),
                    "score_profilo": round(items[0][1], 4),
                })

        return portfolio
