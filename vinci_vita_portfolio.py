"""
vinci_vita_portfolio.py
AURORA ENGINE v2 — Ottimizzatore di portfolio multi-sestina.

Problema:
Quando giochi N sestine, la loro RELAZIONE conta più della qualità
individuale. N sestine quasi identiche = rischio concentrato.

Soluzione:
Selezionare N sestine che MASSIMIZZANO:
1. Score individuale (qualità di ogni sestina)
2. Coverage (numeri distinti coperti)
3. Diversità (profili statistici differenti)
E MINIMIZZANO:
4. Correlazione (overlap pairwise)

Approccio:
- Greedy algorithm con look-ahead
- Scoring composito: individual + diversity - correlation

Ispirato alla Modern Portfolio Theory (Markowitz) applicata alle lotterie.

Uso:
    from vinci_vita_portfolio import PortfolioOptimizer
    opt = PortfolioOptimizer(candidates)
    portfolio = opt.optimize(n_sestinas=3)
"""
import itertools
from typing import List, Tuple, Dict, Optional, Callable


# ==========================================
# UTILITY
# ==========================================
def pairwise_overlap(s1: List[int], s2: List[int]) -> int:
    """Numero di elementi in comune tra due sestine."""
    return len(set(s1) & set(s2))


def jaccard_similarity(s1: List[int], s2: List[int]) -> float:
    """Jaccard similarity: |intersezione| / |unione|."""
    inter = len(set(s1) & set(s2))
    union = len(set(s1) | set(s2))
    return inter / union if union > 0 else 0.0


# ==========================================
# PORTFOLIO OPTIMIZER
# ==========================================
class PortfolioOptimizer:
    """
    Ottimizza la selezione di N sestine da un pool di candidati.

    Ogni candidato deve essere una tupla (sestina, score_individuale).
    """

    def __init__(self, candidates: List[Tuple[List[int], float]]):
        """
        :param candidates: lista di (sestina, score) ordinata o meno.
        """
        # Filtra e ordina per score decrescente
        self.candidates = sorted(candidates, key=lambda x: x[1], reverse=True)
        self.n_candidates = len(self.candidates)

        # Pesi della funzione di scoring composito
        self.w_individual = 0.5   # qualità media delle sestine
        self.w_coverage = 0.2     # copertura del campo numerico
        self.w_diversity = 0.2    # diversità dei profili
        self.w_correlation = 0.1  # penalità per correlazione

    # ==========================================
    # METRICHE DI PORTFOLIO
    # ==========================================
    def _coverage(self, sestinas: List[List[int]]) -> float:
        """
        Copertura: frazione di numeri distinti coperti dal portfolio.
        Normalizzata: min 6 (una sestina), max 90 (impossibile con N piccoli).
        """
        if not sestinas:
            return 0.0
        unique = set()
        for s in sestinas:
            unique.update(s)
        # Normalizza per il massimo teorico (6 * n_sestine)
        max_possible = 6 * len(sestinas)
        return len(unique) / max_possible if max_possible > 0 else 0.0

    def _avg_correlation(self, sestinas: List[List[int]]) -> float:
        """
        Correlazione media: Jaccard similarity media tra tutte le coppie.
        Range 0 (nessuna correlazione) - 1 (identiche).
        """
        if len(sestinas) < 2:
            return 0.0
        pairs = list(itertools.combinations(sestinas, 2))
        similarities = [jaccard_similarity(s1, s2) for s1, s2 in pairs]
        return sum(similarities) / len(similarities)

    def _diversity(self, sestinas: List[List[int]]) -> float:
        """
        Diversità dei profili: quanto le sestine differiscono in termini di:
        - Somma
        - Parità
        - Distribuzione decadi
        """
        if len(sestinas) < 2:
            return 1.0

        # Raccogli profili
        profiles = []
        for s in sestinas:
            ss = sorted(s)
            profile = {
                "sum": sum(ss),
                "pari": sum(1 for n in ss if n % 2 == 0),
                "decadi": len(set((n - 1) // 10 for n in ss)),
                "spread": ss[-1] - ss[0],
            }
            profiles.append(profile)

        # Calcola deviazione standard di ciascuna metrica
        def stdev(values):
            if len(values) < 2:
                return 0.0
            m = sum(values) / len(values)
            return (sum((x - m) ** 2 for x in values) / len(values)) ** 0.5

        std_sum = stdev([p["sum"] for p in profiles])
        std_pari = stdev([p["pari"] for p in profiles])
        std_decadi = stdev([p["decadi"] for p in profiles])
        std_spread = stdev([p["spread"] for p in profiles])

        # Normalizza per range plausibile
        norm_sum = min(1.0, std_sum / 50)       # std max atteso ~50
        norm_pari = min(1.0, std_pari / 1.5)    # std max atteso ~1.5
        norm_decadi = min(1.0, std_decadi / 2)  # std max atteso ~2
        norm_spread = min(1.0, std_spread / 30) # std max atteso ~30

        return (norm_sum + norm_pari + norm_decadi + norm_spread) / 4

    # ==========================================
    # SCORE DI PORTFOLIO
    # ==========================================
    def score_portfolio(self, sestinas: List[List[int]]) -> Dict:
        """
        Score composito di un portfolio.
        Ritorna dict con sub-score e composite.
        """
        if not sestinas:
            return {"composite": 0.0}

        # Score individuale medio
        # Matcha le sestine ai candidati per trovare lo score originale
        candidate_scores = {}
        for s, sc in self.candidates:
            key = tuple(sorted(s))
            candidate_scores[key] = sc

        individual_scores = []
        for s in sestinas:
            key = tuple(sorted(s))
            individual_scores.append(candidate_scores.get(key, 0.0))

        avg_individual = sum(individual_scores) / len(individual_scores)

        # Altri score
        coverage = self._coverage(sestinas)
        correlation = self._avg_correlation(sestinas)
        diversity = self._diversity(sestinas)

        # Composite
        composite = (
            self.w_individual * avg_individual
            + self.w_coverage * coverage
            + self.w_diversity * diversity
            - self.w_correlation * correlation
        )

        return {
            "composite": round(composite, 4),
            "individual": round(avg_individual, 4),
            "coverage": round(coverage, 4),
            "correlation": round(correlation, 4),
            "diversity": round(diversity, 4),
            "n_sestine": len(sestinas),
        }

    # ==========================================
    # OTTIMIZZAZIONE GREEDY
    # ==========================================
    def optimize(self, n_sestinas: int = 2,
                 max_candidates: int = 500,
                 verbose: bool = True) -> List[Tuple[List[int], float]]:
        """
        Seleziona N sestine massimizzando lo score di portfolio.

        Algoritmo greedy:
        1. Considera solo i top max_candidates (per efficienza)
        2. Scegli la prima sestina: score individuale massimo
        3. Per ogni sestina successiva: massimizza score_portfolio incrementale
        4. Ritorna il portfolio finale

        :return: lista di (sestina, score_individuale)
        """
        if n_sestinas <= 0:
            return []
        if not self.candidates:
            return []

        # Limita il pool
        pool = self.candidates[:max_candidates]

        if n_sestinas == 1:
            best = pool[0]
            return [best]

        # Greedy: primo elemento = score individuale massimo
        selected = [pool[0]]
        remaining = pool[1:]

        if verbose:
            print(f"[*] Portfolio: 1/{n_sestinas} = {selected[0][0]} "
                  f"(score {selected[0][1]:.4f})")

        # Iterativamente aggiungi la sestina che migliora di più il portfolio
        while len(selected) < n_sestinas and remaining:
            best_score = -float("inf")
            best_idx = -1
            best_metrics = None

            for idx, candidate in enumerate(remaining):
                trial_portfolio = selected + [candidate]
                trial_sestinas = [s for s, _ in trial_portfolio]
                metrics = self.score_portfolio(trial_sestinas)

                if metrics["composite"] > best_score:
                    best_score = metrics["composite"]
                    best_idx = idx
                    best_metrics = metrics

            if best_idx < 0:
                break

            selected.append(remaining[best_idx])
            remaining.pop(best_idx)

            if verbose:
                print(f"[*] Portfolio: {len(selected)}/{n_sestinas} = "
                      f"{selected[-1][0]} "
                      f"(composite {best_metrics['composite']:.4f}, "
                      f"corr {best_metrics['correlation']:.3f})")

        return selected

    # ==========================================
    # REPORT
    # ==========================================
    def report(self, portfolio: List[Tuple[List[int], float]]) -> str:
        """Genera report leggibile del portfolio."""
        if not portfolio:
            return "Portfolio vuoto."

        sestinas = [s for s, _ in portfolio]
        metrics = self.score_portfolio(sestinas)

        lines = []
        lines.append("=" * 65)
        lines.append("PORTFOLIO — ANALISI")
        lines.append("=" * 65)
        lines.append("")
        for i, (s, sc) in enumerate(portfolio, 1):
            lines.append(f"  {i}. {s} | score {sc:.4f} | somma {sum(s)}")
        lines.append("")
        lines.append(f"Metriche portfolio:")
        lines.append(f"  • Score individuale medio: {metrics['individual']:.4f}")
        lines.append(f"  • Coverage:                 {metrics['coverage']:.4f}")
        lines.append(f"  • Diversity:                {metrics['diversity']:.4f}")
        lines.append(f"  • Correlation (↓ meglio):   {metrics['correlation']:.4f}")
        lines.append(f"  • Composite:                {metrics['composite']:.4f}")
        lines.append("=" * 65)
        return "\n".join(lines)


# ==========================================
# TEST
# ==========================================
if __name__ == "__main__":
    # Portfolio di test: 3 sestine
    test_candidates = [
        ([5, 30, 31, 34, 65, 80], 0.95),
        ([5, 30, 31, 34, 65, 81], 0.94),  # quasi identica
        ([2, 18, 42, 55, 71, 89], 0.90),  # molto diversa
        ([12, 27, 44, 58, 76, 88], 0.88),  # diversa
        ([5, 12, 33, 44, 66, 77], 0.85),
        ([3, 19, 43, 56, 70, 88], 0.82),
    ]

    opt = PortfolioOptimizer(test_candidates)
    portfolio = opt.optimize(n_sestinas=3, verbose=True)
    print()
    print(opt.report(portfolio))

    print()
    print("Confronto: top 3 per score individuale (senza ottimizzazione):")
    naive = test_candidates[:3]
    for s, sc in naive:
        print(f"  {s} (score {sc})")
    print()
    print("Metriche del portfolio naive:")
    print(f"  {opt.score_portfolio([s for s, _ in naive])}")
