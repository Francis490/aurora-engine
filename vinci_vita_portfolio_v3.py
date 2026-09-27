"""
vinci_vita_portfolio_v3.py
AURORA ENGINE v4.1 — Portfolio con CLUSTER SCORE (no distribuzione forzata).

Cambio di paradigma (2026-09-27):
- Rimosso vincolo decadi >= 4
- Aggiunto cluster_score: premia numeri vicini (gap piccoli)
- La distribuzione è libera: le sestine possono concentrarsi in 2-3 decadi

Filosofia: le estrazioni reali spesso si concentrano in cluster.
Se la statistica dice che il pattern è "cluster + gap", il bot lo segue.
"""
import random
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


SUM_MIN = 240
SUM_MAX = 310


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
    # SCORING v4.1 — con CLUSTER SCORE
    # ==========================================
    def _score_cluster(self, combo: Tuple[int, ...]) -> float:
        """
        Premia le sestine con numeri VICINI tra loro (cluster).
        Penalizza i "buchi" enormi (gap singolo > 30).
        """
        s = sorted(combo)
        gaps = [s[i + 1] - s[i] for i in range(5)]
        avg_gap = sum(gaps) / 5.0
        max_gap = max(gaps)

        # Gap medio ideale: 10-15 (numeri vicini ma non adiacenti)
        # Se avg_gap = 12 → bonus 1.0
        # Se avg_gap = 24 → bonus 0.5
        # Se avg_gap = 36 → bonus 0.25
        gap_bonus = 1.0 / (1.0 + abs(avg_gap - 12) / 12.0)

        # Penalità per gap enorme
        if max_gap <= 25:
            max_gap_penalty = 1.0
        elif max_gap <= 35:
            max_gap_penalty = 0.7
        else:
            max_gap_penalty = 0.4

        return gap_bonus * max_gap_penalty

    def _score_trend(self, combo: Tuple[int, ...]) -> float:
        """Score: quanto i numeri sono 'caldi' recentemente."""
        hot_score = sum(self._hot_recent.get(n, 0) for n in combo) / 6.0
        s = sorted(combo)
        n_pari = sum(1 for x in s if x % 2 == 0)
        parity_ok = 1.0 if 2 <= n_pari <= 4 else 0.5
        return hot_score * parity_ok

    def _score_contrarian(self, combo: Tuple[int, ...]) -> float:
        """Score: quanto i numeri sono 'freddi' (gap alto)."""
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
    # SESTINA UNIFICATA (1 sola) — v4.1
    # ==========================================
    def build_single(self, pool: List[int], fp_engine=None,
                     crowd_model=None, bias_weights: Optional[Dict] = None,
                     verbose: bool = True) -> List[Dict]:
        """
        Genera UNA sestina ottimale SENZA anti-crowd,
        CON cluster score.
        """
        if len(pool) < 6:
            return []

        rng = random.Random(42)

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

        # Score composito v4.1: 40% trend + 25% contrarian + 35% cluster
        scored = []
        for combo in valid:
            s_trend = self._score_trend(combo)
            s_contr = self._score_contrarian(combo)
            s_cluster = self._score_cluster(combo)
            # Normalizza contrarian (avg_gap ~ 0-100) a 0-1
            s_contr_norm = min(1.0, s_contr / 50.0)
            composite = 0.40 * s_trend + 0.25 * s_contr_norm + 0.35 * s_cluster
            scored.append((combo, composite, s_trend, s_contr_norm, s_cluster))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return []

        best = scored[0]
        if verbose:
            print(f"[*] Migliore: {list(best[0])} (composite {best[1]:.3f})")
            print(f"    trend={best[2]:.3f} contrarian={best[3]:.3f} cluster={best[4]:.3f}")

        return [{
            "profilo": "UNIFIED_CLUSTER",
            "numeri": list(best[0]),
            "score_profilo": round(best[1], 4),
        }]
