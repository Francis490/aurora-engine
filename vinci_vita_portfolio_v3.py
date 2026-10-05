"""
vinci_vita_portfolio_v3.py
AURORA ENGINE v5.7 — Generatore pattern-based (approccio costruttivo).

Cambio di strategia (2026-10-05 v2):
- Il generatore precedente tentava di trovare una sestina random che
  rispettasse tutti i filtri (terzina, coppia, parità, somma, caldi).
  Con filtri stretti questo richiede milioni di tentativi → run lentissimi.
- Ora usa approccio COSTRUTTIVO: parte da una terzina ricorrente,
  aggiunge una coppia top, aggiunge i numeri caldi per arrivare a 6,
  verifica che somma e parità siano ok.
- Se una combinazione non funziona, prova la successiva. Spazio di
  ricerca limitato → risoluzione in meno di 1 secondo.

Interfaccia invariata: build_single / build_multiple.

NOTA: matematicamente non aumenta P(6). Il generatore resta onesto
sul fatto che non predice nulla. Ma produce sestine che rispettano
i pattern reali (caldi + terzine + quadruple + coppie + parità).
"""
import random
import time
from collections import Counter
from itertools import combinations
from typing import List, Dict, Optional


SUM_MIN = 240
SUM_MAX = 310

# Parametri pattern
TOP_N_HOT = 15
MIN_HOT_IN_SESTINA = 3
MIN_TRIPLE_FREQ = 2
MIN_QUAD_FREQ = 2
PAIR_FREQ_THRESHOLD = 4

# Target parità (le due configurazioni più frequenti)
TARGET_PARITY = [(4, 2), (2, 4)]


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
        if self._patterns is not None:
            return self._patterns

        freq = Counter()
        for d in self.history:
            for n in d.get("numeri", []):
                freq[n] += 1

        sorted_hot = sorted(range(1, 91), key=lambda n: freq[n], reverse=True)
        hot_numbers = sorted_hot[:TOP_N_HOT]
        hot_set = set(hot_numbers)

        triple_counter = Counter()
        for d in self.history:
            nums = sorted(d.get("numeri", []))
            for t in combinations(nums, 3):
                triple_counter[t] += 1
        top_triples = [t for t, c in triple_counter.items()
                       if c >= MIN_TRIPLE_FREQ]
        # Ordina per frequenza decrescente
        top_triples.sort(key=lambda t: triple_counter[t], reverse=True)

        quad_counter = Counter()
        for d in self.history:
            nums = sorted(d.get("numeri", []))
            for q in combinations(nums, 4):
                quad_counter[q] += 1
        top_quads = [q for q, c in quad_counter.items()
                     if c >= MIN_QUAD_FREQ]
        top_quads.sort(key=lambda q: quad_counter[q], reverse=True)

        pair_counter = Counter()
        for d in self.history:
            nums = sorted(d.get("numeri", []))
            for p in combinations(nums, 2):
                pair_counter[p] += 1
        top_pairs = [p for p, c in pair_counter.items()
                     if c >= PAIR_FREQ_THRESHOLD]
        if len(top_pairs) < 10:
            top_pairs = [p for p, _ in pair_counter.most_common(10)]
        top_pairs.sort(key=lambda p: pair_counter[p], reverse=True)

        self._patterns = {
            "freq": dict(freq),
            "hot_numbers": hot_numbers,
            "hot_set": hot_set,
            "top_triples": top_triples,
            "top_quads": top_quads,
            "top_pairs": top_pairs,
            "pair_set": set(top_pairs),
            "triple_set": set(top_triples),
            "quad_set": set(top_quads),
        }
        return self._patterns

    # ==========================================
    # VALIDAZIONE
    # ==========================================
    def _validate(self, combo, patterns) -> bool:
        if len(set(combo)) != 6:
            return False
        if not all(1 <= n <= 90 for n in combo):
            return False

        ssum = sum(combo)
        if not (SUM_MIN <= ssum <= SUM_MAX):
            return False

        n_pari = sum(1 for x in combo if x % 2 == 0)
        n_dispari = 6 - n_pari
        if (n_pari, n_dispari) not in TARGET_PARITY:
            return False

        # Almeno 1 coppia top
        has_pair = any(p in patterns["pair_set"]
                       for p in combinations(combo, 2))
        if not has_pair:
            return False

        # Almeno 1 terzina o quadrupla
        has_pattern = any(t in patterns["triple_set"]
                          for t in combinations(combo, 3))
        if not has_pattern:
            has_pattern = any(q in patterns["quad_set"]
                              for q in combinations(combo, 4))
        if not has_pattern:
            return False

        # Minimo caldi
        hot_count = sum(1 for n in combo if n in patterns["hot_set"])
        if hot_count < MIN_HOT_IN_SESTINA:
            return False

        return True

    def _score(self, combo, patterns) -> float:
        hot_count = sum(1 for n in combo if n in patterns["hot_set"])
        n_pairs = sum(1 for p in combinations(combo, 2)
                      if p in patterns["pair_set"])
        n_triples = sum(1 for t in combinations(combo, 3)
                        if t in patterns["triple_set"])
        n_quads = sum(1 for q in combinations(combo, 4)
                      if q in patterns["quad_set"])
        sum_score = 1.0 - abs(sum(combo) - 275) / 100.0
        return (
            hot_count * 1.0 +
            n_pairs * 0.8 +
            n_triples * 1.5 +
            n_quads * 2.0 +
            sum_score * 0.5
        )

    # ==========================================
    # GENERAZIONE COSTRUTTIVA
    # ==========================================
    def _build_candidates(self, patterns, rng, max_candidates=300):
        """
        Costruisce candidati partendo dalle terzine ricorrenti,
        aggiungendo coppie top e caldi.
        """
        candidates = []
        seen = set()

        # Ordine casuale delle terzine (ma deterministico col seed)
        triples = list(patterns["top_triples"])
        rng.shuffle(triples)

        # Anche le quadruple possono essere base
        quads = list(patterns["top_quads"])
        rng.shuffle(quads)

        hot = list(patterns["hot_numbers"])
        pairs = list(patterns["top_pairs"])
        rng.shuffle(pairs)

        # Base: terzine
        for triple in triples:
            base = set(triple)
            # Prova ad aggiungere una coppia top che non sovrapponga
            for pair in pairs:
                pa, pb = pair
                if pa in base or pb in base:
                    # La coppia è già parzialmente nella terzina
                    # Aggiungi solo i mancanti se non supera 6
                    extra = [n for n in pair if n not in base]
                    combined = base | set(extra)
                    if len(combined) > 6:
                        continue
                    # Riempi con caldi
                    for h in hot:
                        if len(combined) >= 6:
                            break
                        combined.add(h)
                    if len(combined) == 6:
                        combo = tuple(sorted(combined))
                        if combo not in seen and self._validate(combo, patterns):
                            seen.add(combo)
                            candidates.append(combo)
                            if len(candidates) >= max_candidates:
                                return candidates
                else:
                    # Coppia esterna: aggiungi entrambi i numeri
                    combined = base | {pa, pb}
                    if len(combined) > 6:
                        continue
                    # Riempi con caldi
                    for h in hot:
                        if len(combined) >= 6:
                            break
                        combined.add(h)
                    if len(combined) == 6:
                        combo = tuple(sorted(combined))
                        if combo not in seen and self._validate(combo, patterns):
                            seen.add(combo)
                            candidates.append(combo)
                            if len(candidates) >= max_candidates:
                                return candidates

        # Base: quadruple (che contengono anche una terzina)
        for quad in quads:
            base = set(quad)
            for h in hot:
                if len(base) >= 6:
                    break
                if h not in base:
                    base.add(h)
            # Prova con 1 o 2 caldi
            for h2 in hot:
                if len(base) >= 6:
                    break
                if h2 not in base:
                    base.add(h2)
                    if len(base) == 6:
                        combo = tuple(sorted(base))
                        if combo not in seen and self._validate(combo, patterns):
                            seen.add(combo)
                            candidates.append(combo)
                            if len(candidates) >= max_candidates:
                                return candidates
                    # Rimuovi per il prossimo tentativo
                    base.discard(h2)

        return candidates

    def build_single(self, pool: List[int], verbose: bool = True,
                     seed: int = None, **kwargs) -> List[Dict]:
        if seed is None:
            seed = int(time.time())
        rng = random.Random(seed)

        patterns = self._extract_patterns()

        if verbose:
            print(f"[*] Pattern estratti:")
            print(f"    Top {TOP_N_HOT} caldi: {patterns['hot_numbers']}")
            print(f"    Terzine ricorrenti: {len(patterns['top_triples'])}")
            print(f"    Quadruple ricorrenti: {len(patterns['top_quads'])}")
            print(f"    Coppie top: {len(patterns['top_pairs'])}")

        t0 = time.time()
        candidates = self._build_candidates(patterns, rng, max_candidates=300)
        elapsed = time.time() - t0

        if verbose:
            print(f"[*] Candidati costruiti: {len(candidates)} "
                  f"(in {elapsed:.2f}s)")

        if not candidates:
            if verbose:
                print("[!] Nessun candidato. Fallback a random+sum.")
            return self._fallback_single(pool, rng, verbose)

        # Ordina per score e scegli random dal top 30
        scored = [(c, self._score(c, patterns)) for c in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:min(30, len(scored))]

        chosen, chosen_score = rng.choice(top)

        if verbose:
            hot_count = sum(1 for n in chosen if n in patterns["hot_set"])
            n_pairs = sum(1 for p in combinations(chosen, 2)
                          if p in patterns["pair_set"])
            n_triples = sum(1 for t in combinations(chosen, 3)
                            if t in patterns["triple_set"])
            n_quads = sum(1 for q in combinations(chosen, 4)
                          if q in patterns["quad_set"])
            n_pari = sum(1 for x in chosen if x % 2 == 0)
            print(f"[*] Sestina scelta: {list(chosen)}")
            print(f"    Somma {sum(chosen)} · {n_pari}P/{6-n_pari}D")
            print(f"    Caldi: {hot_count}/6 · Coppie: {n_pairs} · "
                  f"Terzine: {n_triples} · Quadruple: {n_quads}")
            print(f"    Score: {chosen_score:.2f}")

        return [{
            "profilo": "PATTERN",
            "numeri": list(chosen),
            "score_profilo": round(chosen_score, 2),
        }]

    def _fallback_single(self, pool, rng, verbose=False):
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
        results = []
        for i in range(n):
            seed_i = (base_seed + i) if base_seed else None
            r = self.build_single(pool, verbose=verbose, seed=seed_i)
            if r:
                results.append(r[0])
        return results
