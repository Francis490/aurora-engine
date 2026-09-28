"""
vinci_vita_crowd.py
AURORA ENGINE v3 — Modello bayesiano dinamico del crowding.

FIX (2026-09-29):
- Normalizzazione del crowding (media ~1.0 per sestina random)
- Rimosso clamp superiore a 10 che appiattiva tutti i valori
- Uso della media geometrica per la superstizione (non prodotto)

Uso:
    from vinci_vita_crowd import CrowdModel
    model = CrowdModel()
    crowd = model.estimate_crowding([5, 30, 31, 34, 65, 80])
    score = model.anti_crowd_score_v3([5, 30, 31, 34, 65, 80])
"""
import math
from datetime import datetime
from typing import List, Dict, Optional


# ==========================================
# PESI BASE
# ==========================================
BIRTHDAY_WEIGHTS = {n: (1.0 if 1 <= n <= 31 else 0.5) for n in range(1, 91)}

# Media attesa del peso birthday per una sestina uniforme da 90:
# 31/90 * 1.0 + 59/90 * 0.5 = 0.3444 + 0.3278 = 0.6722
BIRTHDAY_BASELINE = 0.6722

SUPERSTITION_WEIGHTS = {
    3: 1.4, 7: 1.5, 13: 1.3, 17: 1.2,
    22: 1.2, 33: 1.1, 77: 1.1,
}


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


# ==========================================
# MOLTIPLICATORE DI CONTESTO
# ==========================================
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


# ==========================================
# MODELLO CROWDING
# ==========================================
class CrowdModel:
    """Modello bayesiano semplificato del crowding."""

    def __init__(self, date_str: Optional[str] = None,
                 jackpot: Optional[float] = None):
        self.date_str = date_str
        self.jackpot = jackpot
        self.m_context = context_multiplier(date_str, jackpot)

    def estimate_crowding(self, sestina: List[int]) -> float:
        """
        Stima il peso di crowding. 1.0 = sestina media.
        >1.0 = più giocata del solito.
        <1.0 = meno giocata del solito.
        """
        if not sestina:
            return 1.0

        # Media del peso birthday, normalizzata alla baseline
        birthday_avg = sum(BIRTHDAY_WEIGHTS.get(n, 1.0) for n in sestina) / len(sestina)
        birthday_norm = birthday_avg / BIRTHDAY_BASELINE

        # Media geometrica dei pesi superstizione
        s_weights = [SUPERSTITION_WEIGHTS.get(n, 1.0) for n in sestina]
        prod = 1.0
        for w in s_weights:
            prod *= w
        superst_geo = prod ** (1.0 / len(s_weights))

        pattern = pattern_penalty(sestina)
        context = self.m_context

        crowd = birthday_norm * superst_geo * pattern * context
        return round(crowd, 4)

    def anti_crowd_score_v3(self, sestina: List[int]) -> float:
        crowd = self.estimate_crowding(sestina)
        if crowd <= 0:
            return 20.0
        score = 10.0 / crowd
        return round(max(0.1, score), 4)

    def expected_share(self, sestina: List[int],
                       total_jackpot_value: float = 2_729_878) -> float:
        crowd = self.estimate_crowding(sestina)
        N_PLAYERS = 50_000_000
        base_prob = 1 / 622_614_630
        effective_prob = base_prob * crowd
        expected_winners = max(1.0, N_PLAYERS * effective_prob)
        share = total_jackpot_value / expected_winners
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
    print("CONFRONTO CROWDING — AURORA v3")
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
        [11, 16, 48, 59, 67, 68],
        [1, 2, 3, 4, 5, 6],
        [11, 23, 41, 58, 72, 89],
    ]
    compare_sestinas(test_sestinas, date_str="21/09/2026",
                     jackpot=13_810 * 20 * 12)
