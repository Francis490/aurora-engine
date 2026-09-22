"""
vinci_vita_portfolio_v3.py
AURORA ENGINE v3.2 — Portfolio 3 sestine multi-profilo.

Profili:
- A_trend: numeri hot recenti + struttura bilanciata
- B_contrarian: numeri cold con gap alto
- C_coverage: anti-crowd + copertura decadi

Uso:
    from vinci_vita_portfolio_v3 import AuroraPortfolioV3
    p3 = AuroraPortfolioV3(history)
    portfolio = p3.build(pool, bias_weights=bias_weights)
"""
import itertools
import math
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


SUM_MIN = 240
SUM_MAX = 310


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

        if verbose:
            print(f"[*] Combinazioni valide nel pool: {len(all_combos)}")

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

        best = {}
        for profile, items in scored.items():
            items.sort(key=lambda x: x[1], reverse=True)
            best[profile] = items[0]
            if verbose:
                print(f"[*] Migliore {profile}: {list(items[0][0])} (score {items[0][1]:.3f})")

        portfolio = [
            {"profilo": "A_trend", "numeri": list(best["A_trend"][0]),
             "score_profilo": round(best["A_trend"][1], 4)},
            {"profilo": "B_contrarian", "numeri": list(best["B_contrarian"][0]),
             "score_profilo": round(best["B_contrarian"][1], 4)},
            {"profilo": "C_coverage", "numeri": list(best["C_coverage"][0]),
             "score_profilo": round(best["C_coverage"][1], 4)},
        ]

        portfolio = self._fix_overlaps(portfolio, scored)
        coverage = self._portfolio_coverage([p["numeri"] for p in portfolio])
        if verbose:
            print(f"[*] Coverage portafoglio: {coverage:.4f}")

        return portfolio

    def _fix_overlaps(self, portfolio: List[Dict], scored: Dict,
                      max_overlap: int = 2) -> List[Dict]:
        ov_ab = len(set(portfolio[0]["numeri"]) & set(portfolio[1]["numeri"]))
        if ov_ab > max_overlap:
            for combo, sc in scored["B_contrarian"][1:]:
                ov = len(set(portfolio[0]["numeri"]) & set(combo))
                ov_c = len(set(portfolio[2]["numeri"]) & set(combo))
                if ov <= max_overlap and ov_c <= max_overlap:
                    portfolio[1] = {
                        "profilo": "B_contrarian",
                        "numeri": list(combo),
                        "score_profilo": round(sc, 4),
                    }
                    break

        ov_ac = len(set(portfolio[0]["numeri"]) & set(portfolio[2]["numeri"]))
        if ov_ac > max_overlap:
            for combo, sc in scored["C_coverage"][1:]:
                ov = len(set(portfolio[0]["numeri"]) & set(combo))
                ov_b = len(set(portfolio[1]["numeri"]) & set(combo))
                if ov <= max_overlap and ov_b <= max_overlap:
                    portfolio[2] = {
                        "profilo": "C_coverage",
                        "numeri": list(combo),
                        "score_profilo": round(sc, 4),
                    }
                    break

        return portfolio
