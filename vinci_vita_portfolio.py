"""
vinci_vita_portfolio_v3.py
AURORA ENGINE v4.0 — Generatore sestina SENZA anti-crowd.

Cambio di paradigma (2026-09-26):
- RIMOSSO filtro anti-crowd (non serve, non aumenta P(6))
- RIMOSSO pool ristretto (tutti i 90 numeri sono eleggibili)
- Scoring basato SOLO su fingerprint statistici (transition, co-occurrence, gap, hot/cold)
- Massima varietà tra le sestine

Filosofia: se dobbiamo giocare, giochiamo numeri statisticamente validi.
Se vinciamo, dividiamo — ma almeno abbiamo giocato.
"""
import itertools
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

    def _score_trend(self, combo: Tuple[int, ...]) -> float:
        """Score: quanto i numeri sono 'caldi' recentemente."""
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
        """Score: quanto i numeri sono 'freddi' (gap alto)."""
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

    def build_single(self, pool: List[int], fp_engine=None,
                     verbose: bool = True) -> List[Dict]:
        """
        Genera UNA sestina ottimale SENZA anti-crowd.
        Combina 50% trend + 50% contrarian. Solo fingerprint statistici.
        """
        if len(pool) < 6:
            return []

        all_combos = []
        for combo in itertools.combinations(pool, 6):
            ssum = sum(combo)
            if SUM_MIN <= ssum <= SUM_MAX:
                all_combos.append(combo)

        if verbose:
            print(f"[*] Combinazioni totali: {len(all_combos)}")

        # Valida fingerprint (12/12) se disponibile
        valid_combos = []
        if fp_engine:
            from vinci_vita_generator import validate_sestina, extract_fingerprints
            fp = extract_fingerprints(self.history)
            for combo in all_combos:
                ok, _, _ = validate_sestina(list(combo), fp)
                if ok:
                    valid_combos.append(combo)
            if verbose:
                print(f"[*] Con 12/12 fingerprint: {len(valid_combos)}")
        else:
            valid_combos = all_combos

        if not valid_combos:
            valid_combos = all_combos

        # Score composito: 50% trend + 50% contrarian
        scored = []
        for combo in valid_combos:
            s_trend = self._score_trend(combo)
            s_contr = self._score_contrarian(combo)
            composite = 0.5 * s_trend + 0.5 * s_contr
            scored.append((combo, composite))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return []

        # Seleziona la migliore
        best = scored[0]
        if verbose:
            print(f"[*] Migliore: {list(best[0])} (score {best[1]:.3f})")

        return [{
            "profilo": "UNIFIED",
            "numeri": list(best[0]),
            "score_profilo": round(best[1], 4),
        }]
