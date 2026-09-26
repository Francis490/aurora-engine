"""
vinci_vita_portfolio_v3.py
AURORA ENGINE v4.0 — Portfolio senza anti-crowd + build_single random sampling.

FIX (2026-09-26):
- build_single usa campionamento casuale (200K) invece di iterazione esaustiva
  (C(90,6) = 622M combinazioni → troppo pesante)
- Anti-crowd rimosso dallo scoring
"""
import itertools
import random
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


SUM_MIN = 240
SUM_MAX = 310

# Pesi compositi
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
    # SESTINA UNIFICATA (1 sola) — v4.0 RANDOM SAMPLING
    # ==========================================
    def build_single(self, pool: List[int], fp_engine=None,
                     crowd_model=None, bias_weights: Optional[Dict] = None,
                     verbose: bool = True) -> List[Dict]:
        """
        Genera UNA sestina ottimale SENZA anti-crowd.

        FIX (2026-09-26): usa campionamento casuale (200K) invece di
        iterazione esaustiva C(90,6)=622M. Tempo: ~5-10s.
        """
        if len(pool) < 6:
            return []

        rng = random.Random(42)  # riproducibile

        n_target = 200_000
        candidates_raw = []
        seen = set()

        attempts = 0
        max_attempts = n_target * 5

        while len(candidates_raw) < n_target and attempts < max_attempts:
            attempts += 1
            try:
                combo = tuple(sorted(rng.sample(pool, 6)))
            except ValueError:
                break
            if combo in seen:
                continue
            seen.add(combo)
            if SUM_MIN <= sum(combo) <= SUM_MAX:
                candidates_raw.append(combo)

        if verbose:
            print(f"[*] Campioni validi (somma {SUM_MIN}-{SUM_MAX}): {len(candidates_raw)}")

        if not candidates_raw:
            return []

        # Valida fingerprint (12/12) se disponibile
        valid = []
        if fp_engine:
            try:
                from vinci_vita_generator import validate_sestina, extract_fingerprints
                fp = extract_fingerprints(self.history)
                for combo in candidates_raw:
                    ok, _, _ = validate_sestina(list(combo), fp)
                    if ok:
                        valid.append(combo)
                if verbose:
                    print(f"[*] Con 12/12 fingerprint: {len(valid)}")
            except Exception as e:
                if verbose:
                    print(f"[!] Fingerprint check errore: {e}")
                valid = candidates_raw
        else:
            valid = candidates_raw

        if not valid:
            valid = candidates_raw

        # Score composito: 50% trend + 50% contrarian
        scored = []
        for combo in valid:
            s_trend = self._score_trend_follower(combo)
            s_contr = self._score_contrarian(combo)
            composite = 0.5 * s_trend + 0.5 * s_contr
            scored.append((combo, composite))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return []

        best = scored[0]
        if verbose:
            print(f"[*] Migliore: {list(best[0])} (score {best[1]:.3f})")

        return [{
            "profilo": "UNIFIED",
            "numeri": list(best[0]),
            "score_profilo": round(best[1], 4),
        }]

    # ==========================================
    # LEGACY: 3 sestine separate (non usato)
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
