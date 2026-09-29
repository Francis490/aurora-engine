"""
vinci_vita_crowd.py
AURORA ENGINE v3.1 — Modello bayesiano dinamico del crowding.

FIX (2026-09-29):
- expected_share riformulato: stima quanti ALTRI vincitori in media (Poisson)
  e calcola E[1/(1+N)] con N ~ Poisson(k). Prima il clamp a 1 rendeva il
  campo sempre uguale al jackpot totale.

Uso:
    from vinci_vita_crowd import CrowdModel
    model = CrowdModel()
    share = model.expected_share([5, 30, 31, 34, 65, 80])
"""
import math
from datetime import datetime
from typing import List, Dict, Optional


BIRTHDAY_WEIGHTS = {n: (1.0 if 1 <= n <= 31 else 0.5) for n in range(1, 91)}
BIRTHDAY_BASELINE = 0.6722  # media attesa per sestina uniforme da 90

SUPERSTITION_WEIGHTS = {
    3: 1.4, 7: 1.5, 13: 1.3, 17: 1.2,
    22: 1.2, 33: 1.1, 77: 1.1,
}

# Stima giocatori attivi per estrazione (ordine di grandezza)
N_PLAYERS = 50_000_000
# Probabilità che una specifica sestina di 6 numeri su 90 sia giocata da 1 giocatore
BASE_PROB = 1 / 622_614_630


def pattern_penalty(sestina: List[int]) -> float:
    s = sorted(sestina)
    penalty = 1.0
    consec = sum(1 for i in range(len(s) - 1) if s[i + 1] - s[i] == 1)
    if consec >= 2:
        penalty *= 1.5
    elif consec == 1:
        penalty *= 1.1
    decades = set((n - 1) // 10 for n in s)
    if len(decades) <= 2:
        penalty *= 1.4
    if all(n % 5 == 0 for n in s):
        penalty *= 1.3
    if all(n % 10 == 0 for n in s):
        penalty *= 1.5
    extremes = sum(1 for n in s if n in (1, 2, 3, 89, 90))
    if extremes >= 2:
        penalty *= 1.2
    return penalty


def context_multiplier(date_str: Optional[str] = None,
                       jackpot: Optional[float] = None) -> float:
    m = 1.0
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            weekday = dt.weekday()
            if weekday >= 5:
                m *= 1.15
            if weekday == 4:
                m *= 1.10
        except Exception:
            pass
    if jackpot:
        if jackpot > 15_000_000:
            m *= 1.25
        elif jackpot > 12_000_000:
            m *= 1.15
        elif jackpot > 10_000_000:
            m *= 1.05
    return m


class CrowdModel:

    def __init__(self, date_str: Optional[str] = None,
                 jackpot: Optional[float] = None):
        self.date_str = date_str
        self.jackpot = jackpot
        self.m_context = context_multiplier(date_str, jackpot)

    def estimate_crowding(self, sestina: List[int]) -> float:
        if not sestina:
            return 1.0
        birthday_avg = sum(BIRTHDAY_WEIGHTS.get(n, 1.0) for n in sestina) / len(sestina)
        birthday_norm = birthday_avg / BIRTHDAY_BASELINE

        prod = 1.0
        for n in sestina:
            prod *= SUPERSTITION_WEIGHTS.get(n, 1.0)
        superst_geo = prod ** (1.0 / len(sestina))

        pattern = pattern_penalty(sestina)
        crowd = birthday_norm * superst_geo * pattern * self.m_context
        return round(crowd, 4)

    def anti_crowd_score_v3(self, sestina: List[int]) -> float:
        crowd = self.estimate_crowding(sestina)
        if crowd <= 0:
            return 20.0
        return round(max(0.1, 10.0 / crowd), 4)

    def expected_share(self, sestina: List[int],
                       total_jackpot_value: float = 2_729_878) -> float:
        """
        Stima il valore pro capite atteso della rendita SE vinci.

        Modello: il numero di ALTRI vincitori segue approssimativamente
        una Poisson con media k = N_PLAYERS * BASE_PROB * crowd.
        Se tu vinci (condizione), gli altri N sono ~ Poisson(k).
        La quota pro capite è jackpot / (1 + N).
        E[1/(1+N)] con N ~ Poisson(k) = (1 - e^{-k}) / k.
        """
        crowd = self.estimate_crowding(sestina)
        k = N_PLAYERS * BASE_PROB * crowd
        if k <= 1e-9:
            return round(total_jackpot_value, 2)
        factor = (1.0 - math.exp(-k)) / k
        share = total_jackpot_value * factor
        return round(share, 2)

    def report(self, sestina: List[int]) -> Dict:
        return {
            "crowd_index": self.estimate_crowding(sestina),
            "anti_crowd_score": self.anti_crowd_score_v3(sestina),
            "expected_share_eur": self.expected_share(sestina),
            "context_multiplier": round(self.m_context, 4),
            "pattern_penalty": round(pattern_penalty(sestina), 4),
        }


def compare_sestinas(sestinas: List[List[int]],
                     date_str: Optional[str] = None,
                     jackpot: Optional[float] = None):
    print("=" * 70)
    print("CONFRONTO CROWDING — AURORA v3.1")
    print("=" * 70)
    print(f"Contesto: data={date_str}, jackpot={jackpot}")
    print()
    model = CrowdModel(date_str=date_str, jackpot=jackpot)
    rows = [(i, s, model.report(s)) for i, s in enumerate(sestinas, 1)]
    rows.sort(key=lambda x: x[2]["anti_crowd_score"], reverse=True)
    for i, s, r in rows:
        print(f"#{i}: {s}")
        print(f"    Crowd:    {r['crowd_index']:.3f}")
        print(f"    AC v3:    {r['anti_crowd_score']:.3f}")
        print(f"    Share:    €{r['expected_share_eur']:,.0f} (se 6 punti)")
        print()
    print("=" * 70)
    return rows


if __name__ == "__main__":
    test_sestinas = [
        [3, 5, 35, 60, 67, 70],
        [5, 30, 31, 34, 65, 80],
        [20, 33, 56, 59, 61, 67],
        [1, 2, 3, 4, 5, 6],
        [8, 26, 28, 49, 58, 71],
    ]
    compare_sestinas(test_sestinas, date_str="21/09/2026",
                     jackpot=14_070 * 20 * 12)
