"""
vinci_vita_crowd.py
AURORA ENGINE v3 — Modello bayesiano dinamico del crowding.

Formula implementata (semplificata):
    C(s) = Σ_n w_birth(n) · w_superst(n) · w_pattern(n) · M_context

dove:
    w_birth   = probabilità che n sia una data di nascita (1-31: alta)
    w_superst = peso superstizione (3, 7, 13, 17, 22, 33)
    w_pattern = penalità pattern visivi (consecutivi, decadi, ecc.)
    M_context = moltiplicatore di contesto (giorno, jackpot)

Il crowding stimato viene combinato con l'anti-crowd statico
per produrre uno score finale "atteso valore condizionato alla vincita".

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
# Peso "data di nascita": numeri 1-31 sono i più giocati
BIRTHDAY_WEIGHTS = {
    n: 1.0 if 1 <= n <= 31 else 0.5
    for n in range(1, 91)
}

# Numeri superstiziosi in Italia (peso extra)
SUPERSTITION_WEIGHTS = {
    3: 1.4, 7: 1.5, 13: 1.3, 17: 1.2,
    22: 1.2, 33: 1.1, 77: 1.1,
}

# Peso pattern
def pattern_penalty(sestina: List[int]) -> float:
    """Penalità se la sestina ha pattern visivamente popolari."""
    s = sorted(sestina)
    penalty = 1.0

    # Consecutivi
    consec = sum(1 for i in range(len(s) - 1) if s[i + 1] - s[i] == 1)
    if consec >= 2:
        penalty *= 1.5
    elif consec == 1:
        penalty *= 1.1

    # Decadi concentrate
    decades = set((n - 1) // 10 for n in s)
    if len(decades) <= 2:
        penalty *= 1.4

    # Multipli di 5 o 10
    if all(n % 5 == 0 for n in s):
        penalty *= 1.3
    if all(n % 10 == 0 for n in s):
        penalty *= 1.5

    # Estremi popolari (1, 2, 3, 89, 90)
    extremes = sum(1 for n in s if n in (1, 2, 3, 89, 90))
    if extremes >= 2:
        penalty *= 1.2

    return penalty


# ==========================================
# MOLTIPLICATORE DI CONTESTO
# ==========================================
def context_multiplier(date_str: Optional[str] = None,
                       jackpot: Optional[float] = None) -> float:
    """
    Stima quanti più giocatori del solito ci sono in un certo contesto.
    Valori > 1.0 = più crowding = meno vincita pro capite.
    """
    m = 1.0

    # Giorno della settimana
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            weekday = dt.weekday()  # 0=lun, 6=dom
            # Weekend = più giocate
            if weekday >= 5:
                m *= 1.15
            # Venerdì sera = picco
            if weekday == 4:
                m *= 1.10
        except Exception:
            pass

    # Jackpot alto = più giocate
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
        Stima il "peso di crowding" della sestina.
        Valori più alti = più giocata = vincita pro capite più bassa.
        """
        if not sestina:
            return 1.0

        # Base: somma dei pesi birthday
        birthday_score = sum(BIRTHDAY_WEIGHTS.get(n, 1.0) for n in sestina)

        # Moltiplicatore superstizione
        superst_score = 1.0
        for n in sestina:
            if n in SUPERSTITION_WEIGHTS:
                superst_score *= SUPERSTITION_WEIGHTS[n]

        # Moltiplicatore pattern
        pattern_score = pattern_penalty(sestina)

        # Moltiplicatore contesto
        context_score = self.m_context

        # Crowding complessivo (normalizzato: media = 1.0)
        crowd = (birthday_score / 6.0) * superst_score * pattern_score * context_score

        return round(crowd, 4)

    def anti_crowd_score_v3(self, sestina: List[int]) -> float:
        """
        Anti-crowd score v3: inverso del crowding.
        Range: 0.1 (popolarissima) - 10+ (rarissima).
        """
        crowd = self.estimate_crowding(sestina)
        if crowd <= 0:
            return 10.0
        score = 10.0 / crowd
        return round(max(0.1, min(10.0, score)), 4)

    def expected_share(self, sestina: List[int],
                       total_jackpot_value: float = 2_729_878) -> float:
        """
        Stima il valore atteso pro capite della rendita in caso di 6 punti.

        Assunzione: N giocatori totali stimati ~ 50.000.000
        Frazione che gioca la sestina ~ crowd / 90^6 * costante

        Questo è il pezzo che risponde alla tua domanda:
        "Se vinco, quanto prendo?"
        """
        # Approssimazione: ogni sestina ha P = 1/622M di essere giocata
        # Il crowding relativo modula questa probabilità
        crowd = self.estimate_crowding(sestina)

        # Giocatori italiani (stima)
        N_PLAYERS = 50_000_000

        # Frazione che gioca questa sestina
        base_prob = 1 / 622_614_630
        effective_prob = base_prob * crowd

        # Vincitori attesi
        expected_winners = max(1.0, N_PLAYERS * effective_prob)

        # Rendita pro capite
        share = total_jackpot_value / expected_winners

        return round(share, 2)

    def report(self, sestina: List[int]) -> Dict:
        """Report completo del crowding per una sestina."""
        return {
            "crowd_index": self.estimate_crowding(sestina),
            "anti_crowd_score": self.anti_crowd_score_v3(sestina),
            "expected_share_eur": self.expected_share(sestina),
            "context_multiplier": round(self.m_context, 4),
            "pattern_penalty": round(pattern_penalty(sestina), 4),
        }


# ==========================================
# CONFRONTO
# ==========================================
def compare_sestinas(sestinas: List[List[int]],
                     date_str: Optional[str] = None,
                     jackpot: Optional[float] = None):
    """Confronta il crowding di più sestine."""
    print("=" * 70)
    print("CONFRONTO CROWDING — AURORA v3")
    print("=" * 70)
    print(f"Contesto: data={date_str}, jackpot={jackpot}")
    print()

    model = CrowdModel(date_str=date_str, jackpot=jackpot)

    rows = []
    for i, s in enumerate(sestinas, 1):
        r = model.report(s)
        rows.append((i, s, r))

    # Ordina per anti_crowd_score decrescente
    rows.sort(key=lambda x: x[2]["anti_crowd_score"], reverse=True)

    for i, s, r in rows:
        print(f"#{i}: {s}")
        print(f"    Crowd:    {r['crowd_index']:.3f}")
        print(f"    AC v3:    {r['anti_crowd_score']:.3f}")
        print(f"    Share:    €{r['expected_share_eur']:,.0f} (se 6 punti)")
        print()

    print("=" * 70)
    return rows


# ==========================================
# TEST
# ==========================================
if __name__ == "__main__":
    test_sestinas = [
        [3, 5, 35, 60, 67, 70],       # popolare (3, 5, 35 consecutivi)
        [5, 30, 31, 34, 65, 80],      # media
        [20, 33, 56, 59, 61, 67],     # anti-crowd
        [11, 16, 48, 59, 67, 68],     # anti-crowd v2
        [1, 2, 3, 4, 5, 6],           # MOLTO popolare
        [11, 23, 41, 58, 72, 89],     # generata, mix
    ]

    compare_sestinas(
        test_sestinas,
        date_str="21/09/2026",
        jackpot=13_810 * 20 * 12,  # valore attuale rendita
    )
