"""
vinci_vita_portfolio_v3.py
AURORA ENGINE v5.8 — Generatore pattern-based con filtro SEVERO.

Cambio di strategia (2026-10-05 v3):
- Il generatore ORA rispetta severamente:
  * Terzina ricorrente del report (una delle top del report)
  * Coppia top 10 del report (una delle 10 visibili)
  * Parità 4P/2D o 2P/4D
  * Somma 240-310
  * Almeno 4 numeri dal top 15 caldi
- Quadrupla ricorrente: BONUS (non obbligatorio)

Approccio costruttivo: parte da una terzina, aggiunge una coppia top,
riempie con numeri caldi. Tempo di esecuzione <1s.

Se il filtro severo non trova candidati, rilassa progressivamente
(ma logga il livello di severità raggiunto).

NOTA: matematicamente non aumenta P(6). Il generatore resta onesto.
"""
import random
import time
from collections import Counter
from itertools import combinations
from typing import List, Dict


SUM_MIN = 240
SUM_MAX = 310

# Configurazione
TOP_N_HOT = 15
MIN_HOT_STRICT = 4
MIN_TRIPLE_FREQ = 2
MIN_QUAD_FREQ = 2
PAIR_FREQ_THRESHOLD = 4
TOP_PAIRS_TO_USE = 10
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
        all_pairs = [p for p, c in pair_counter.items()
                     if c >= PAIR_FREQ_THRESHOLD]
        if len(all_pairs) < 10:
            all_pairs = [p for p, _ in pair_counter.most_common(10)]
        all_pairs.sort(key=lambda p: pair_counter[p], reverse=True)
        top_pairs_10 = all_pairs[:TOP_PAIRS_TO_USE]

        self._patterns = {
            "freq": dict(freq),
            "hot_numbers": hot_numbers,
            "hot_set": hot_set,
            "top_triples": top_triples,
            "top_quads": top_quads,
            "top_pairs_10": top_pairs_10,
            "triple_set": set(top_triples),
            "quad_set": set(top_quads),
            "pair_set_10": set(top_pairs_10),
        }
        return self._patterns

    # ==========================================
    # VALIDAZIONE SEVERA
    # ==========================================
    def _validate_strict(self, combo, patterns):
        """
        Filtro SEVERO. Ritorna dict con esito + dettagli.
        """
        result = {
            "valid": False,
            "has_triple": False,
            "has_pair_top10": False,
            "has_quad": False,
            "n_hot": 0,
            "sum": sum(combo),
            "n_pari": 0,
        }

        if len(set(combo)) != 6:
            return result
        if not all(1 <= n <= 90 for n in combo):
            return result

        if not (SUM_MIN <= result["sum"] <= SUM_MAX):
            return result

        n_pari = sum(1 for x in combo if x % 2 == 0)
        result["n_pari"] = n_pari
        if (n_pari, 6 - n_pari) not in TARGET_PARITY:
            return result

        # Terzina ricorrente (obbligatoria)
        has_triple = any(t in patterns["triple_set"]
                         for t in combinations(combo, 3))
        result["has_triple"] = has_triple
        if not has_triple:
            return result

        # Coppia top 10 (obbligatoria)
        has_pair = any(p in patterns["pair_set_10"]
                       for p in combinations(combo, 2))
        result["has_pair_top10"] = has_pair
        if not has_pair:
            return result

        # Min caldi
        n_hot = sum(1 for n in combo if n in patterns["hot_set"])
        result["n_hot"] = n_hot
        if n_hot < MIN_HOT_STRICT:
            return result

        # Quadrupla (bonus, non obbligatoria)
        has_quad = any(q in patterns["quad_set"]
                       for q in combinations(combo, 4))
        result["has_quad"] = has_quad

        result["valid"] = True
        return result

    def _score(self, combo, patterns):
        hot_count = sum(1 for n in combo if n in patterns["hot_set"])
        n_pairs = sum(1 for p in combinations(combo, 2)
                      if p in patterns["pair_set_10"])
        n_triples = sum(1 for t in combinations(combo, 3)
                        if t in patterns["triple_set"])
        n_quads = sum(1 for q in combinations(combo, 4)
                      if q in patterns["quad_set"])
        sum_score = 1.0 - abs(sum(combo) - 275) / 100.0
        return (
            hot_count * 1.5 +
            n_pairs * 1.0 +
            n_triples * 2.0 +
            n_quads * 3.0 +
            sum_score * 0.5
        )

    # ==========================================
    # COSTRUZIONE SEVERA
    # ==========================================
    def _build_candidates_strict(self, patterns, rng, max_candidates=500):
        """
        Costruisce candidati SEVERI:
        - Base: terzina ricorrente
        - + coppia top 10
        - + riempimento con caldi
        """
        candidates = []
        seen = set()

        triples = list(patterns["top_triples"])
        rng.shuffle(triples)

        pairs = list(patterns["top_pairs_10"])
        rng.shuffle(pairs)

        hot = list(patterns["hot_numbers"])

        # 1) Terzina + coppia -> unione, riempi con caldi
        for triple in triples:
            triple_set = set(triple)
            for pair in pairs:
                pair_set = set(pair)
                base = triple_set | pair_set
                if len(base) > 6:
                    continue
                needed = 6 - len(base)
                hot_pool = [h for h in hot if h not in base]
                rng.shuffle(hot_pool)

                if needed == 0:
                    combo = tuple(sorted(base))
                    if combo not in seen:
                        v = self._validate_strict(combo, patterns)
                        if v["valid"]:
                            seen.add(combo)
                            candidates.append(combo)
                            if len(candidates) >= max_candidates:
                                return candidates
                elif needed == 1:
                    for h in hot_pool:
                        combo = tuple(sorted(base | {h}))
                        if combo in seen:
                            continue
                        v = self._validate_strict(combo, patterns)
                        if v["valid"]:
                            seen.add(combo)
                            candidates.append(combo)
                            if len(candidates) >= max_candidates:
                                return candidates
                elif needed == 2:
                    for h1, h2 in combinations(hot_pool, 2):
                        combo = tuple(sorted(base | {h1, h2}))
                        if combo in seen:
                            continue
                        v = self._validate_strict(combo, patterns)
                        if v["valid"]:
                            seen.add(combo)
                            candidates.append(combo)
                            if len(candidates) >= max_candidates:
                                return candidates
                elif needed == 3:
                    # raro: prova con 3 caldi
                    for h1, h2, h3 in combinations(hot_pool, 3):
                        combo = tuple(sorted(base | {h1, h2, h3}))
                        if combo in seen:
                            continue
                        v = self._validate_strict(combo, patterns)
                        if v["valid"]:
                            seen.add(combo)
                            candidates.append(combo)
                            if len(candidates) >= max_candidates:
                                return candidates

        # 2) Prova anche partendo da quadruple + caldi
        quads = list(patterns["top_quads"])
        rng.shuffle(quads)
        for quad in quads:
            quad_set = set(quad)
            hot_pool = [h for h in hot if h not in quad_set]
            rng.shuffle(hot_pool)
            needed = 2
            for h1, h2 in combinations(hot_pool, 2):
                combo = tuple(sorted(quad_set | {h1, h2}))
                if combo in seen:
                    continue
                v = self._validate_strict(combo, patterns)
                if v["valid"]:
                    seen.add(combo)
                    candidates.append(combo)
                    if len(candidates) >= max_candidates:
                        return candidates

        return candidates

    def _build_candidates_relaxed(self, patterns, rng, max_candidates=500):
        """
        Costruzione rilassata: terzina O quadrupla, coppia qualsiasi freq>=4,
        min 3 caldi. Usato come fallback.
        """
        candidates = []
        seen = set()

        triples = list(patterns["top_triples"])
        rng.shuffle(triples)
        hot = list(patterns["hot_numbers"])

        # Base: terzine + riempi con caldi
        for triple in triples:
            base = set(triple)
            hot_pool = [h for h in hot if h not in base]
            rng.shuffle(hot_pool)
            for combo_extra in combinations(hot_pool, 3):
                combo = tuple(sorted(base | set(combo_extra)))
                if combo in seen:
                    continue
                # Filtro rilassato
                ssum = sum(combo)
                if not (SUM_MIN <= ssum <= SUM_MAX):
                    continue
                n_pari = sum(1 for x in combo if x % 2 == 0)
                if (n_pari, 6 - n_pari) not in TARGET_PARITY:
                    continue
                n_hot = sum(1 for n in combo if n in patterns["hot_set"])
                if n_hot < 3:
                    continue
                has_pattern = any(t in patterns["triple_set"]
                                  for t in combinations(combo, 3))
                if not has_pattern:
                    continue
                seen.add(combo)
                candidates.append(combo)
                if len(candidates) >= max_candidates:
                    return candidates

        return candidates

    # ==========================================
    # API PUBBLICA
    # ==========================================
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
            print(f"    Coppie top 10: {patterns['top_pairs_10']}")

        t0 = time.time()

        # Tentativo SEVERO
        candidates = self._build_candidates_strict(patterns, rng, max_candidates=300)
        severity = "STRICT"
        elapsed = time.time() - t0

        if verbose:
            print(f"[*] [STRICT] Candidati validi: {len(candidates)} (in {elapsed:.2f}s)")

        # Fallback rilassato se non trova nulla
        if not candidates:
            if verbose:
                print("[!] [STRICT] Nessun candidato. Provo RELAXED.")
            t1 = time.time()
            candidates = self._build_candidates_relaxed(patterns, rng, max_candidates=300)
            severity = "RELAXED"
            elapsed = time.time() - t1
            if verbose:
                print(f"[*] [RELAXED] Candidati validi: {len(candidates)} (in {elapsed:.2f}s)")

        if not candidates:
            if verbose:
                print("[!] Nessun candidato. Fallback random+sum.")
            return self._fallback_single(pool, rng, verbose)

        # Ordina per score e scegli random dal top 20
        scored = [(c, self._score(c, patterns)) for c in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:min(20, len(scored))]

        chosen, chosen_score = rng.choice(top)

        if verbose:
            v = self._validate_strict(chosen, patterns)
            print(f"[*] Sestina scelta ({severity}): {list(chosen)}")
            print(f"    Somma {sum(chosen)} · {v['n_pari']}P/{6-v['n_pari']}D")
            print(f"    Terzina: {v['has_triple']} · "
                  f"Coppia top10: {v['has_pair_top10']} · "
                  f"Quadrupla: {v['has_quad']}")
            print(f"    Caldi: {v['n_hot']}/6 · Score: {chosen_score:.2f}")

        return [{
            "profilo": f"PATTERN_{severity}",
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
