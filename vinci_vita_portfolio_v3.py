"""
vinci_vita_portfolio_v3.py
AURORA ENGINE v5.6 — Generatore pattern-based.

Cambio di paradigma (2026-10-05):
- Il generatore ora usa i pattern del report (analyze_history.py):
  - Top 15 caldi (frequenze più alte)
  - Terzine ricorrenti (>= 2 occorrenze)
  - Quadruple ricorrenti (>= 2 occorrenze)
  - Coppie top 10
  - Parità 4P/2D (configurazione più frequente, 31.2%)
- Somma comunque vincolata a 240-310.

Pipeline:
1. Estrae pattern dallo storico (frequenze, terzine, quadruple, coppie)
2. Costruisce sestine candidate che rispettano:
   - Somma 240-310
   - 4 numeri pari / 2 dispari (o 2P/4D)
   - Almeno 1 coppia top 10
   - Almeno 1 terzina ricorrente (o quadrupla)
   - Maggioranza di numeri caldi
3. Sceglie casualmente (seed deterministico) tra i candidati validi.

NOTA: matematicamente questo non aumenta P(6). Il generatore resta onesto
sul fatto che non predice nulla. Ma produce sestine che "sembrano" estratte
dal pattern reale, come richiesto.

FIX (2026-10-01):
- Rimosso ogni filtro binario precedente.
- Mantenuta interfaccia build_single / build_multiple.
"""
import random
import time
from collections import Counter
from itertools import combinations
from typing import List, Dict, Optional


SUM_MIN = 240
SUM_MAX = 310
DEFAULT_SAMPLES = 50_000

# Configurazione pesi (modificabili)
TOP_N_HOT = 15              # quanti "caldi" considerare dal report
MIN_HOT_IN_SESTINA = 3      # minimo numeri caldi in ogni sestina
PREFERRED_HOT = 4           # numero ideale di caldi
MIN_TRIPLE_FREQ = 2         # terzine con almeno questa freq
MIN_QUAD_FREQ = 2           # quadruple con almeno questa freq
PAIR_FREQ_THRESHOLD = 4     # coppie con almeno questa freq


class AuroraPortfolioV3:

    def __init__(self, history: List[dict]):
        self.history = [d for d in history
                        if isinstance(d.get("numeri"), list) and len(d["numeri"]) == 8]
        self.n = len(self.history)
        self._patterns = None

    # ==========================================
    # ANALISI PATTERN
    # ==========================================
    def _extract_patterns(self):
        """Estrae pattern dallo storico. Cache per non ricalcolare."""
        if self._patterns is not None:
            return self._patterns

        freq = Counter()
        for d in self.history:
            for n in d.get("numeri", []):
                freq[n] += 1

        # Top caldi
        sorted_hot = sorted(range(1, 91), key=lambda n: freq[n], reverse=True)
        hot_numbers = sorted_hot[:TOP_N_HOT]

        # Terzine ricorrenti (>= MIN_TRIPLE_FREQ)
        triple_counter = Counter()
        for d in self.history:
            nums = sorted(d.get("numeri", []))
            for t in combinations(nums, 3):
                triple_counter[t] += 1
        top_triples = [t for t, c in triple_counter.items()
                       if c >= MIN_TRIPLE_FREQ]

        # Quadruple ricorrenti (>= MIN_QUAD_FREQ)
        quad_counter = Counter()
        for d in self.history:
            nums = sorted(d.get("numeri", []))
            for q in combinations(nums, 4):
                quad_counter[q] += 1
        top_quads = [q for q, c in quad_counter.items()
                     if c >= MIN_QUAD_FREQ]

        # Coppie top (>= PAIR_FREQ_THRESHOLD)
        pair_counter = Counter()
        for d in self.history:
            nums = sorted(d.get("numeri", []))
            for p in combinations(nums, 2):
                pair_counter[p] += 1
        top_pairs = [p for p, c in pair_counter.items()
                     if c >= PAIR_FREQ_THRESHOLD]

        # Fallback: se troppo poche coppie, prendi le top 10
        if len(top_pairs) < 10:
            top_pairs = [p for p, _ in pair_counter.most_common(10)]

        self._patterns = {
            "freq": dict(freq),
            "hot_numbers": set(hot_numbers),
            "top_triples": top_triples,
            "top_quads": top_quads,
            "top_pairs": set(top_pairs),
        }
        return self._patterns

    # ==========================================
    # VALIDAZIONE
    # ==========================================
    def _validate_candidate(self, combo, patterns) -> bool:
        """Verifica che una combo rispetti i pattern richiesti."""
        ssum = sum(combo)
        if not (SUM_MIN <= ssum <= SUM_MAX):
            return False

        # Parità: 4P/2D o 2P/4D (le due config più frequenti con 8 estratti)
        n_pari = sum(1 for x in combo if x % 2 == 0)
        n_dispari = 6 - n_pari
        if not ((n_pari == 4 and n_dispari == 2) or
                (n_pari == 2 and n_dispari == 4)):
            return False

        # Almeno una coppia top
        has_top_pair = False
        for p in combinations(combo, 2):
            if p in patterns["top_pairs"]:
                has_top_pair = True
                break
        if not has_top_pair:
            return False

        # Almeno una terzina ricorrente o quadrupla
        has_pattern = False
        for t in combinations(combo, 3):
            if t in patterns["top_triples"]:
                has_pattern = True
                break
        if not has_pattern:
            for q in combinations(combo, 4):
                if q in patterns["top_quads"]:
                    has_pattern = True
                    break
        if not has_pattern:
            return False

        # Minimo numeri caldi
        hot_count = sum(1 for n in combo if n in patterns["hot_numbers"])
        if hot_count < MIN_HOT_IN_SESTINA:
            return False

        return True

    def _score_candidate(self, combo, patterns) -> float:
        """
        Punteggio composito: più alto = meglio rispetta i pattern.
        Usato per ordinare i candidati validi.
        """
        hot_count = sum(1 for n in combo if n in patterns["hot_numbers"])
        n_pairs = sum(1 for p in combinations(combo, 2)
                      if p in patterns["top_pairs"])
        n_triples = sum(1 for t in combinations(combo, 3)
                        if t in patterns["top_triples"])
        n_quads = sum(1 for q in combinations(combo, 4)
                      if q in patterns["top_quads"])

        # Somma più vicina al centro 275 = meglio
        sum_score = 1.0 - abs(sum(combo) - 275) / 100.0

        return (
            hot_count * 1.0 +
            n_pairs * 0.8 +
            n_triples * 1.5 +
            n_quads * 2.0 +
            sum_score * 0.5
        )

    # ==========================================
    # GENERAZIONE
    # ==========================================
    def build_single(self, pool: List[int], verbose: bool = True,
                     seed: int = None, **kwargs) -> List[Dict]:
        """
        Genera UNA sestina che rispetta i pattern.
        """
        if len(pool) < 6:
            return []

        patterns = self._extract_patterns()

        if seed is None:
            seed = int(time.time())
        rng = random.Random(seed)

        if verbose:
            print(f"[*] Pattern estratti:")
            print(f"    Top {TOP_N_HOT} caldi: {sorted(patterns['hot_numbers'])}")
            print(f"    Terzine ricorrenti: {len(patterns['top_triples'])}")
            print(f"    Quadruple ricorrenti: {len(patterns['top_quads'])}")
            print(f"    Coppie top: {len(patterns['top_pairs'])}")

        candidates = []
        attempts = 0
        max_attempts = DEFAULT_SAMPLES * 20

        while len(candidates) < 200 and attempts < max_attempts:
            attempts += 1
            try:
                combo = tuple(sorted(rng.sample(pool, 6)))
            except ValueError:
                break
            if self._validate_candidate(combo, patterns):
                score = self._score_candidate(combo, patterns)
                candidates.append((combo, score))

        if verbose:
            print(f"[*] Candidati validi: {len(candidates)} "
                  f"(in {attempts} tentativi)")

        if not candidates:
            if verbose:
                print("[!] Nessun candidato valido. Fallback a random+sum.")
            return self._fallback_single(pool, rng, verbose)

        # Ordina per score decrescente, prendi dal top 50
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = candidates[:min(50, len(candidates))]

        chosen, chosen_score = rng.choice(top_candidates)

        if verbose:
            hot_count = sum(1 for n in chosen if n in patterns["hot_numbers"])
            print(f"[*] Sestina scelta: {list(chosen)} "
                  f"(somma {sum(chosen)}, caldi {hot_count}/6, "
                  f"score {chosen_score:.2f})")

        return [{
            "profilo": "PATTERN",
            "numeri": list(chosen),
            "score_profilo": round(chosen_score, 2),
        }]

    def _fallback_single(self, pool, rng, verbose=False):
        """Fallback: genera random con solo vincolo somma."""
        for _ in range(50_000):
            try:
                combo = tuple(sorted(rng.sample(pool, 6)))
            except ValueError:
                break
            if SUM_MIN <= sum(combo) <= SUM_MAX:
                if verbose:
                    print(f"[*] Fallback: {list(combo)} (somma {sum(combo)})")
                return [{
                    "profilo": "FALLBACK",
                    "numeri": list(combo),
                    "score_profilo": 0.0,
                }]
        return []

    def build_multiple(self, pool: List[int], n: int,
                       verbose: bool = True,
                       base_seed: int = None, **kwargs) -> List[Dict]:
        """
        Genera N sestine indipendenti con seed = base_seed + i.
        """
        results = []
        for i in range(n):
            seed_i = (base_seed + i) if base_seed else None
            r = self.build_single(pool, verbose=verbose, seed=seed_i)
            if r:
                results.append(r[0])
        return results
