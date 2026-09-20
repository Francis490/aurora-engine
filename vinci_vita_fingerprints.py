"""
vinci_vita_fingerprints.py
AURORA ENGINE v2 — Fingerprint avanzati.

Analisi multi-livello dei dati reali:
1. Matrice di transizione Markov (P(j | i))
2. Matrice di co-occorrenza (conteggio coppie)
3. Gap analysis (pattern dei ritardi)
4. Hot/cold weighting (frequenza pesata temporalmente)

⚠️ Nota epistemologica:
Queste analisi DESCRIVONO i dati storici. NON predicono nulla.
Servono a generare sestine statisticamente compatibili con le
distribuzioni reali, non a indovinare i numeri futuri.

Uso:
    from vinci_vita_fingerprints import AuroraFingerprintEngine
    engine = AuroraFingerprintEngine(history)
    engine.print_summary()
    score = engine.score_sestina([5, 30, 31, 34, 65, 80])
"""
from math import log, exp
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


# Costanti di gioco
N_TOTALI = 90
N_ESTRATTI = 8
N_GIOCATI = 6


class AuroraFingerprintEngine:
    """
    Motore di analisi avanzata delle estrazioni reali.
    Costruisce 4 modelli statistici e li combina in uno score composito.
    """

    def __init__(self, history: List[dict], halflife: int = 10):
        """
        :param history: lista di dict con chiave "numeri" (8 numeri 1-90)
        :param halflife: emivita per il weighting hot/cold (in numero di estrazioni)
        """
        self.history = self._filter_valid(history)
        self.n_draws = len(self.history)
        self.halflife = halflife

        # Modelli (costruiti lazily)
        self._transition_matrix = None
        self._cooccurrence = None
        self._gaps = None
        self._hot_cold = None

        # Statistiche descrittive
        self._stats = None

    # ==========================================
    # FILTRAGGIO INPUT
    # ==========================================
    @staticmethod
    def _filter_valid(history: List[dict]) -> List[dict]:
        """Filtra entry con 8 numeri validi 1-90."""
        valid = []
        for d in history:
            nums = d.get("numeri", [])
            if (isinstance(nums, list) and len(nums) == 8
                    and all(isinstance(n, int) and 1 <= n <= 90 for n in nums)):
                valid.append(d)
        return valid

    # ==========================================
    # 1. MATRICE DI TRANSIZIONE MARKOV
    # ==========================================
    def _build_transition_matrix(self) -> Dict[Tuple[int, int], float]:
        """
        P(j appare in t+1 | i appare in t) per ogni coppia (i, j).

        Ritorna dict {(i, j): prob}. Se i non è mai apparso, ritorna
        la probabilità a priori P(j) = freq(j) / n_draws.
        """
        # Conteggi
        pair_counts = defaultdict(int)  # (i, j) -> quante volte i in t, j in t+1
        i_counts = defaultdict(int)     # i -> quante volte i in t

        for t in range(self.n_draws - 1):
            nums_t = set(self.history[t]["numeri"])
            nums_next = set(self.history[t + 1]["numeri"])

            for i in nums_t:
                i_counts[i] += 1
                for j in nums_next:
                    pair_counts[(i, j)] += 1

        # Probabilità a priori P(j)
        freq_total = defaultdict(int)
        for d in self.history:
            for n in d["numeri"]:
                freq_total[n] += 1

        prior = {j: freq_total[j] / max(1, self.n_draws) for j in range(1, N_TOTALI + 1)}

        # Costruisci matrice
        matrix = {}
        for i in range(1, N_TOTALI + 1):
            if i_counts[i] == 0:
                # i mai apparso: usa prior
                for j in range(1, N_TOTALI + 1):
                    matrix[(i, j)] = prior[j]
            else:
                for j in range(1, N_TOTALI + 1):
                    count = pair_counts.get((i, j), 0)
                    # Smoothing di Laplace
                    matrix[(i, j)] = (count + 0.5) / (i_counts[i] + 0.5 * N_TOTALI)

        return matrix

    def transition_score(self, sestina: List[int]) -> float:
        """
        Score Markov: P(j appare in t+1 | i appare in t) media
        per tutte le coppie (i, j) della sestina.
        Valori più alti = più compatibile con pattern storici.
        """
        if self._transition_matrix is None:
            self._transition_matrix = self._build_transition_matrix()

        if self.n_draws < 2:
            return 0.5

        # Media delle probabilità pairwise
        scores = []
        s = list(sestina)
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                scores.append(self._transition_matrix[(s[i], s[j])])
                scores.append(self._transition_matrix[(s[j], s[i])])

        if not scores:
            return 0.5

        return sum(scores) / len(scores)

    # ==========================================
    # 2. MATRICE DI CO-OCCORRENZA
    # ==========================================
    def _build_cooccurrence(self) -> Dict[Tuple[int, int], float]:
        """
        Quante volte la coppia (i, j) appare nella stessa estrazione.
        Normalizzato per il numero di estrazioni.
        """
        counts = defaultdict(int)
        for d in self.history:
            nums = sorted(d["numeri"])
            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    a, b = nums[i], nums[j]
                    counts[(min(a, b), max(a, b))] += 1

        n = max(1, self.n_draws)
        return {k: v / n for k, v in counts.items()}

    def cooccurrence_score(self, sestina: List[int]) -> float:
        """
        Score co-occorrenza: media delle co-occorrenze osservate
        tra tutte le coppie della sestina.
        """
        if self._cooccurrence is None:
            self._cooccurrence = self._build_cooccurrence()

        if not self.history:
            return 0.0

        s = sorted(sestina)
        scores = []
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                key = (min(s[i], s[j]), max(s[i], s[j]))
                scores.append(self._cooccurrence.get(key, 0.0))

        if not scores:
            return 0.0

        return sum(scores) / len(scores)

    # ==========================================
    # 3. GAP ANALYSIS
    # ==========================================
    def _compute_gaps(self) -> Dict[int, int]:
        """
        Gap corrente per ogni numero: quante estrazioni dall'ultima apparizione.
        """
        gaps = {n: self.n_draws for n in range(1, N_TOTALI + 1)}
        for idx, d in enumerate(reversed(self.history)):
            for n in d["numeri"]:
                if gaps[n] == self.n_draws:
                    gaps[n] = idx
        return gaps

    def gap_pattern_score(self, sestina: List[int]) -> float:
        """
        Score gap pattern: quanto la distribuzione dei gap della sestina
        è vicina alla distribuzione teorica (media = n_draws / freq_attesa).

        Numeri "in linea con la media" → score alto.
        Numeri troppo caldi o troppo freddi → score basso.
        """
        if self._gaps is None:
            self._gaps = self._compute_gaps()

        if self.n_draws < 5:
            return 0.5

        # Gap atteso per un numero in una lotteria uniforme:
        # P(esce in una data estrazione) = 8/90
        # Gap medio atteso = 90/8 ≈ 11.25
        gap_atteso = N_TOTALI / N_ESTRATTI

        scores = []
        for n in sestina:
            gap = self._gaps.get(n, self.n_draws)
            # Score = exp(-|gap - gap_atteso| / gap_atteso)
            # 1.0 se gap == atteso, decade esponenzialmente
            deviation = abs(gap - gap_atteso) / max(1, gap_atteso)
            scores.append(exp(-deviation))

        return sum(scores) / len(scores)

    # ==========================================
    # 4. HOT/COLD WEIGHTING
    # ==========================================
    def _compute_hot_cold(self) -> Dict[int, float]:
        """
        Frequenza pesata temporalmente: estrazioni recenti contano di più.
        Usa emivita configurabile.
        """
        weights = {n: 0.0 for n in range(1, N_TOTALI + 1)}
        decay = log(2) / max(1, self.halflife)

        for idx, d in enumerate(reversed(self.history)):
            w = exp(-decay * idx)
            for n in d["numeri"]:
                weights[n] += w

        # Normalizza: somma totale dei pesi
        total_weight = sum(exp(-decay * i) for i in range(self.n_draws))
        if total_weight <= 0:
            return weights

        return {n: w / total_weight for n, w in weights.items()}

    def hot_cold_score(self, sestina: List[int]) -> float:
        """
        Score hot/cold: quanto la sestina è "bilanciata" tra caldi e freddi.
        Premia sestine con mix bilanciato (né tutti caldi, né tutti freddi).
        """
        if self._hot_cold is None:
            self._hot_cold = self._compute_hot_cold()

        # Soglia: mediana dei pesi
        weights_values = sorted(self._hot_cold.values())
        median = weights_values[len(weights_values) // 2]

        n_hot = sum(1 for n in sestina if self._hot_cold[n] > median)
        n_cold = len(sestina) - n_hot

        # Mix ideale: 3 hot, 3 cold
        ideal = 3
        deviation = abs(n_hot - ideal) + abs(n_cold - ideal)
        return max(0.0, 1.0 - deviation / N_GIOCATI)

    # ==========================================
    # SCORE COMPOSITO
    # ==========================================
    def score_sestina(self, sestina: List[int],
                      weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """
        Score composito: combina i 4 modelli in un unico valore 0-1.

        :param weights: pesi per ciascun sub-score. Default:
            - transition: 0.25
            - cooccurrence: 0.25
            - gap_pattern: 0.25
            - hot_cold: 0.25
        """
        if weights is None:
            weights = {
                "transition": 0.25,
                "cooccurrence": 0.25,
                "gap_pattern": 0.25,
                "hot_cold": 0.25,
            }

        sub_scores = {
            "transition": self.transition_score(sestina),
            "cooccurrence": self.cooccurrence_score(sestina),
            "gap_pattern": self.gap_pattern_score(sestina),
            "hot_cold": self.hot_cold_score(sestina),
        }

        composite = sum(sub_scores[k] * weights.get(k, 0) for k in sub_scores)

        return {
            "composite": round(composite, 4),
            **{k: round(v, 4) for k, v in sub_scores.items()},
        }

    # ==========================================
    # UTILITY / SUMMARY
    # ==========================================
    def get_stats(self) -> Dict:
        """Ritorna statistiche descrittive dei dati."""
        if self._stats is not None:
            return self._stats

        if not self.history:
            return {"n_draws": 0}

        # Frequenze
        freq = defaultdict(int)
        for d in self.history:
            for n in d["numeri"]:
                freq[n] += 1

        # Gap attuali
        if self._gaps is None:
            self._gaps = self._compute_gaps()

        # Hot/cold
        if self._hot_cold is None:
            self._hot_cold = self._compute_hot_cold()

        self._stats = {
            "n_draws": self.n_draws,
            "n_samples_sestina": self.n_draws * 28,  # C(8,6)=28
            "freq_top5": sorted(freq.items(), key=lambda x: x[1], reverse=True)[:5],
            "freq_bottom5": sorted(freq.items(), key=lambda x: x[1])[:5],
            "gap_mean": sum(self._gaps.values()) / 90,
            "gap_max": max(self._gaps.values()),
            "gap_min": min(self._gaps.values()),
            "hot_top5": sorted(self._hot_cold.items(), key=lambda x: x[1], reverse=True)[:5],
            "cold_top5": sorted(self._hot_cold.items(), key=lambda x: x[1])[:5],
        }
        return self._stats

    def print_summary(self):
        """Stampa un riepilogo leggibile."""
        stats = self.get_stats()
        print("=" * 65)
        print("AURORA ENGINE v2 — FINGERPRINT AVANZATI")
        print("=" * 65)
        print(f"Estrazioni analizzate: {stats['n_draws']}")
        print(f"Sestine virtuali:      {stats.get('n_samples_sestina', 0)}")
        print()
        print(f"TOP 5 frequenze:  {stats['freq_top5']}")
        print(f"BOTTOM 5 freq:    {stats['freq_bottom5']}")
        print()
        print(f"Gap medio: {stats['gap_mean']:.2f} "
              f"(min {stats['gap_min']}, max {stats['gap_max']})")
        print()
        print(f"TOP 5 hot:   {stats['hot_top5']}")
        print(f"TOP 5 cold:  {stats['cold_top5']}")
        print("=" * 65)


# ==========================================
# TEST
# ==========================================
if __name__ == "__main__":
    import json
    import os

    history_file = "vinci_history.json"
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        # Test con dati sintetici
        print("[!] vinci_history.json non trovato. Uso dati sintetici.")
        import random
        random.seed(42)
        history = []
        for i in range(30):
            nums = sorted(random.sample(range(1, 91), 8))
            history.append({"concorso": i + 1, "numeri": nums})

    engine = AuroraFingerprintEngine(history)
    engine.print_summary()

    # Test scoring
    print()
    test_sestina = [5, 30, 31, 34, 65, 80]
    print(f"Test sestina: {test_sestina}")
    print(f"Scores: {engine.score_sestina(test_sestina)}")
