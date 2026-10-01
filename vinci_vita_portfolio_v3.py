"""
vinci_vita_portfolio_v3.py
AURORA ENGINE v5.0 — Generatore sestina semplice.

FIX (2026-10-01):
- Rimosso ogni filtro binario (fingerprint, overlap, cluster, trend).
- Genera sestina con somma 240-310, numeri unici 1-90.
- Punto. Niente altro.

Motivazione:
- EV negativo, nessun filtro cambia P(6) = 1/622M.
- Meglio generatore onesto e trasparente che scoring inutile.
"""
import random
import time
from typing import List, Dict


SUM_MIN = 240
SUM_MAX = 310
DEFAULT_SAMPLES = 50_000


class AuroraPortfolioV3:

    def __init__(self, history: List[dict]):
        self.history = [d for d in history
                        if isinstance(d.get("numeri"), list) and len(d["numeri"]) == 8]
        self.n = len(self.history)

    def build_single(self, pool: List[int], verbose: bool = True,
                     seed: int = None, **kwargs) -> List[Dict]:
        """
        Genera UNA sestina con somma 240-310.
        Campionamento uniforme con reiezione sulla somma.
        """
        if len(pool) < 6:
            return []

        if seed is None:
            seed = int(time.time())
        rng = random.Random(seed)

        candidates = []
        attempts = 0
        max_attempts = DEFAULT_SAMPLES * 10

        while len(candidates) < DEFAULT_SAMPLES and attempts < max_attempts:
            attempts += 1
            try:
                combo = tuple(sorted(rng.sample(pool, 6)))
            except ValueError:
                break
            if SUM_MIN <= sum(combo) <= SUM_MAX:
                candidates.append(combo)

        if verbose:
            print(f"[*] Candidati validi (somma {SUM_MIN}-{SUM_MAX}): "
                  f"{len(candidates)}")

        if not candidates:
            return []

        chosen = rng.choice(candidates)

        if verbose:
            print(f"[*] Sestina scelta: {list(chosen)} (somma {sum(chosen)})")

        return [{
            "profilo": "SIMPLE",
            "numeri": list(chosen),
            "score_profilo": 1.0,
        }]

    def build_multiple(self, pool: List[int], n: int,
                       verbose: bool = True,
                       base_seed: int = None, **kwargs) -> List[Dict]:
        """
        Versione semplificata: chiamata con n=1 dal engine.
        Se n>1, genera n sestine indipendenti.
        """
        results = []
        for i in range(n):
            seed_i = (base_seed + i) if base_seed else None
            r = self.build_single(pool, verbose=verbose, seed=seed_i)
            if r:
                results.append(r[0])
        return results
