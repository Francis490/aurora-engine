"""
vinci_vita_portfolio_v3.py
AURORA ENGINE v4.2 — Portfolio con CLUSTER SCORE + fingerprint engine.

FIX (2026-09-29):
- fp_engine ora è USATO davvero (score_sestina nel composite)
- Nessuna enumerazione completa: usa random.sample
- Rimosso il parametro crowd_model/bias_weights non usati

Cambio di paradigma (2026-09-27):
- Rimosso vincolo decadi >= 4
- Aggiunto cluster_score: premia numeri vicini (gap piccoli)
"""
import random
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


SUM_MIN = 240
SUM_MAX = 310
DEFAULT_SAMPLES = 100_000


class AuroraPortfolioV3:

    def __init__(self, history: List[dict]):
        self.history = [d for d in history
                        if isinstance(d.get("numeri"), list) and len(d["numeri"]) == 8]
        self.n = len(self.history)
        self._gaps = self._compute_gaps()
        self._hot_recent = self._compute_hot_recent(window=10)

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

    # ==========================================
    # SCORING
    # ==========================================
    def _score_cluster(self, combo: Tuple[int, ...]) -> float:
        s = sorted(combo)
        gaps = [s[i + 1] - s[i] for i in range(5)]
        avg_gap = sum(gaps) / 5.0
        max_gap = max(gaps)

        gap_bonus = 1.0 / (1.0 + abs(avg_gap - 12) / 12.0)

        if max_gap <= 25:
            max_gap_penalty = 1.0
        elif max_gap <= 35:
            max_gap_penalty = 0.7
        else:
            max_gap_penalty = 0.4

        return gap_bonus * max_gap_penalty

    def _score_trend(self, combo: Tuple[int, ...]) -> float:
        hot_score = sum(self._hot_recent.get(n, 0) for n in combo) / 6.0
        s = sorted(combo)
        n_pari = sum(1 for x in s if x % 2 == 0)
        parity_ok = 1.0 if 2 <= n_pari <= 4 else 0.5
        return hot_score * parity_ok

    def _score_contrarian(self, combo: Tuple[int, ...]) -> float:
        gaps = [self._gaps.get(n, 0) for n in combo]
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
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
        return 0.6 * unique_ratio + 0.4 * decade_ratio

    # ==========================================
    # SESTINA UNIFICATA (1 sola) — v4.2
    # ==========================================
    def build_single(self, pool: List[int], fp_engine=None,
                     verbose: bool = True,
                     n_samples: int = DEFAULT_SAMPLES,
                     seed: int = 42) -> List[Dict]:
        """
        Genera UNA sestina ottimale.
        Composite v4.2: 25% trend + 15% contrarian + 20% cluster + 40% fingerprint.
        """
        if len(pool) < 6:
            return []

        rng = random.Random(seed)
        candidates = []
        seen = set()
        attempts = 0
        max_attempts = n_samples * 10

        while len(candidates) < n_samples and attempts < max_attempts:
            attempts += 1
            try:
                combo = tuple(sorted(rng.sample(pool, 6)))
            except ValueError:
                break
            if combo in seen:
                continue
            seen.add(combo)
            if SUM_MIN <= sum(combo) <= SUM_MAX:
                candidates.append(combo)

        if verbose:
            print(f"[*] Campioni validi (somma {SUM_MIN}-{SUM_MAX}): {len(candidates)}")

        if not candidates:
            return []

        # Valida fingerprint 12/12
        valid = []
        fp = None
        if fp_engine:
            try:
                from vinci_vita_generator import validate_sestina, extract_fingerprints
                fp = extract_fingerprints(self.history)
                for combo in candidates:
                    ok, _, _ = validate_sestina(list(combo), fp)
                    if ok:
                        valid.append(combo)
                if verbose:
                    print(f"[*] Con 12/12 fingerprint: {len(valid)}")
            except Exception as e:
                if verbose:
                    print(f"[!] Fingerprint check errore: {e}")
                valid = candidates
        else:
            valid = candidates

        if not valid:
            valid = candidates

        # Composite scoring v4.2
        scored = []
        for combo in valid:
            s_trend = self._score_trend(combo)
            s_contr = self._score_contrarian(combo)
            s_contr_norm = min(1.0, s_contr / 50.0)
            s_cluster = self._score_cluster(combo)

            fp_score = 0.5
            if fp_engine:
                try:
                    fp_score = fp_engine.score_sestina(list(combo))["composite"]
                except Exception:
                    pass

            composite = (0.25 * s_trend +
                         0.15 * s_contr_norm +
                         0.20 * s_cluster +
                         0.40 * fp_score)

            scored.append((combo, composite, s_trend, s_contr_norm, s_cluster, fp_score))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return []

        best = scored[0]
        if verbose:
            print(f"[*] Migliore: {list(best[0])} (composite {best[1]:.3f})")
            print(f"    trend={best[2]:.3f} contrarian={best[3]:.3f} "
                  f"cluster={best[4]:.3f} fingerprint={best[5]:.3f}")

        return [{
            "profilo": "UNIFIED_CLUSTER",
            "numeri": list(best[0]),
            "score_profilo": round(best[1], 4),
        }]
