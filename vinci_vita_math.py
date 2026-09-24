"""
vinci_vita_math.py
AURORA ENGINE — Modulo matematico Super Win for Life (Vinci per la Vita)

FIX (2026-09-20):
- Soglie budget ricalibrate per l'EV strutturale del gioco (payout 65%)
- Il budget "MINIMO" garantisce almeno 1 sestina anche con EV molto negativo
- SKIP riservato solo a casi anomali (EV < -1.5)

Matematica ESATTA del gioco:
- Probabilità ipergeometriche (8 estratti da 90, 6 giocati)
- Valore attuale della rendita (annuity, tasso 2%)
- EV per categoria
- Kelly criterion
"""
from math import comb
from typing import Dict, Optional


# ==========================================
# COSTANTI DI GIOCO
# ==========================================
TOTALE_NUMERI = 90
NUMERI_ESTRATTI = 8
NUMERI_GIOCATI = 6
COSTO_GIOCATA_EUR = 2.00
PAYOUT_RATIO = 0.65

# Rendita
RENDITA_ATTUALE_MENSILE = 13_950
RENDITA_MINIMA_TOTALE = 2_429_875
DURATA_RENDITA_ANNI = 20
MESI_PER_ANNO = 12
TASSO_SCONTO_ANNUO = 0.02


# ==========================================
# 1. PROBABILITÀ IPERGEOMETRICHE
# ==========================================
def ipergeometrica(k: int, n_estratti: int = NUMERI_ESTRATTI,
                   n_giocati: int = NUMERI_GIOCATI,
                   n_totali: int = TOTALE_NUMERI) -> float:
    if k < 0 or k > n_giocati or k > n_estratti:
        return 0.0
    den = comb(n_totali, n_giocati)
    if den == 0:
        return 0.0
    return (comb(n_estratti, k) *
            comb(n_totali - n_estratti, n_giocati - k)) / den


def probabilita_tutte_categorie() -> Dict[int, float]:
    return {k: ipergeometrica(k) for k in range(NUMERI_GIOCATI + 1)}


def probabilita_1_su_n(k: int) -> Optional[float]:
    p = ipergeometrica(k)
    return 1 / p if p > 0 else None


# ==========================================
# 2. VALORE ATTUALE RENDITA
# ==========================================
def valore_attuale_rendita(rendita_mensile: float,
                           anni: int = DURATA_RENDITA_ANNI,
                           tasso_annuo: float = TASSO_SCONTO_ANNUO) -> float:
    n_mesi = anni * MESI_PER_ANNO
    r_mensile = tasso_annuo / MESI_PER_ANNO
    if r_mensile == 0:
        return rendita_mensile * n_mesi
    return rendita_mensile * (1 - (1 + r_mensile) ** (-n_mesi)) / r_mensile


def valore_nominale_rendita(rendita_mensile: float,
                            anni: int = DURATA_RENDITA_ANNI) -> float:
    return rendita_mensile * anni * MESI_PER_ANNO


# ==========================================
# 3. TABELLA PREMI
# ==========================================
TABELLA_PREMI_MEDIA = {
    6: None,
    5: 15_000.0,
    4: 170.66,
    3: 22.06,
    2: 5.00,
    1: 0.0,
    0: 0.0,
}


def premio_stimato(k: int, rendita_mensile: float = RENDITA_ATTUALE_MENSILE) -> float:
    if k == 6:
        return valore_attuale_rendita(rendita_mensile)
    return TABELLA_PREMI_MEDIA.get(k, 0.0) or 0.0


# ==========================================
# 4. EV
# ==========================================
def calcola_ev(rendita_mensile: float = RENDITA_ATTUALE_MENSILE,
               costo: float = COSTO_GIOCATA_EUR) -> Dict:
    prob = probabilita_tutte_categorie()
    contributi = {}
    ev_lordo = 0.0

    for k in range(NUMERI_GIOCATI + 1):
        p = prob[k]
        premio = premio_stimato(k, rendita_mensile)
        contributo = p * premio
        contributi[k] = {
            "probabilita": p,
            "probabilita_1su": 1/p if p > 0 else None,
            "premio_eur": premio,
            "contributo_ev": contributo,
        }
        ev_lordo += contributo

    ev_netto = ev_lordo - costo
    ev_percentuale = ev_netto / costo * 100

    return {
        "costo": costo,
        "ev_lordo": ev_lordo,
        "ev_netto": ev_netto,
        "ev_percentuale": ev_percentuale,
        "rendita_mensile": rendita_mensile,
        "valore_attuale_rendita": valore_attuale_rendita(rendita_mensile),
        "payout_effettivo": ev_lordo / costo,
        "contributi": contributi,
        "profittevole": ev_netto > 0,
    }


# ==========================================
# 5. KELLY
# ==========================================
def kelly_fraction(prob_win: float, payoff_odds: float,
                   prob_loss: float = None) -> float:
    if prob_loss is None:
        prob_loss = 1 - prob_win
    if payoff_odds <= 0:
        return 0.0
    return (payoff_odds * prob_win - prob_loss) / payoff_odds


def kelly_analysis(rendita_mensile: float = RENDITA_ATTUALE_MENSILE) -> Dict:
    risultati = {}
    for k in range(2, 7):
        p = ipergeometrica(k)
        premio = premio_stimato(k, rendita_mensile)
        if premio <= 0 or p <= 0:
            continue
        payoff_odds = (premio - COSTO_GIOCATA_EUR) / COSTO_GIOCATA_EUR
        f_star = kelly_fraction(p, payoff_odds)
        risultati[k] = {
            "probabilita": p,
            "premio_eur": premio,
            "payoff_odds": payoff_odds,
            "kelly_fraction": f_star,
            "kelly_interpretazione": "GIOCA" if f_star > 0 else "NON GIOCARE",
        }
    return risultati


# ==========================================
# 6. SOGLIE BUDGET (RICALIBRATE v2)
# ==========================================
def soglie_budget(rendita_mensile: float = RENDITA_ATTUALE_MENSILE) -> Dict:
    """
    Soglie di budget per Aurora Engine, ricalibrate per l'EV strutturale
    di Super Win for Life.

    FIX (2026-09-20):
    - EV strutturale del gioco è ~-1.13€
    - Le soglie precedenti (SKIP < -1.10) causavano SKIP permanente
    - Ora il budget MINIMO garantisce sempre 1 sestina (2€)
    - SKIP riservato solo a casi anomali (dati corrotti, EV < -1.5)
    """
    ev_data = calcola_ev(rendita_mensile)
    ev = ev_data["ev_netto"]

    if ev < -1.50:
        # Caso anomalo: dati corrotti o rendita crollata
        return {
            "mode": "SKIP",
            "emoji": "🚫",
            "n_sestine": 0,
            "costo": 0.0,
            "msg": "⚠️ EV anomalo. Verifica dati. Nessuna sestina.",
        }
    elif ev < -1.20:
        return {
            "mode": "MINIMO",
            "emoji": "🟢",
            "n_sestine": 1,
            "costo": 2.0,
            "msg": "EV molto negativo (strutturale). 1 sestina (2€).",
        }
    elif ev < -1.00:
        return {
            "mode": "MINIMO",
            "emoji": "🟢",
            "n_sestine": 1,
            "costo": 2.0,
            "msg": "EV negativo (strutturale). 1 sestina (2€).",
        }
    elif ev < -0.80:
        return {
            "mode": "NORMALE",
            "emoji": "🟡",
            "n_sestine": 2,
            "costo": 4.0,
            "msg": "EV nella media del gioco. 2 sestine (4€).",
        }
    elif ev < -0.60:
        return {
            "mode": "ATTACK",
            "emoji": "🟠",
            "n_sestine": 3,
            "costo": 6.0,
            "msg": "EV meno negativo del solito. 3 sestine (6€).",
        }
    else:
        return {
            "mode": "ALL-IN",
            "emoji": "🔥",
            "n_sestine": 5,
            "costo": 10.0,
            "msg": "EV quasi neutro! 5 sestine (10€).",
        }


# ==========================================
# 7. REPORT
# ==========================================
def report_matematico(rendita_mensile: float = RENDITA_ATTUALE_MENSILE) -> str:
    ev = calcola_ev(rendita_mensile)
    kelly = kelly_analysis(rendita_mensile)
    budget = soglie_budget(rendita_mensile)

    lines = []
    lines.append("=" * 65)
    lines.append("AURORA ENGINE — REPORT MATEMATICO")
    lines.append("Super Win for Life")
    lines.append("=" * 65)
    lines.append("")
    lines.append(f"Rendita mensile:        € {rendita_mensile:,}/mese")
    lines.append(f"Valore attuale (2%):    € {valore_attuale_rendita(rendita_mensile):,.0f}")
    lines.append("")
    lines.append("DISTRIBUZIONE PROBABILITÀ:")
    for k in range(6, -1, -1):
        c = ev["contributi"][k]
        p_1su = c["probabilita_1su"]
        prob_str = f"1 su {p_1su:,.0f}" if p_1su and p_1su < 1e12 else "—"
        lines.append(f"  {k} punti: {c['probabilita']:.10f}  ({prob_str})")
    lines.append("")
    lines.append("EV PER CATEGORIA:")
    for k in range(6, 1, -1):
        c = ev["contributi"][k]
        lines.append(f"  {k} punti: premio €{c['premio_eur']:>12,.2f}  "
                     f"× P = €{c['contributo_ev']:.6f}")
    lines.append("")
    lines.append(f"EV lordo:               € {ev['ev_lordo']:.4f}")
    lines.append(f"EV netto:               € {ev['ev_netto']:.4f}")
    lines.append(f"EV percentuale:         {ev['ev_percentuale']:+.2f}%")
    lines.append("")
    lines.append("SOGLIE BUDGET (v2 ricalibrate):")
    lines.append(f"  Modo: {budget['mode']} {budget.get('emoji', '')}")
    lines.append(f"  Sestine: {budget['n_sestine']}")
    lines.append(f"  Costo: € {budget['costo']:.2f}")
    lines.append(f"  Msg: {budget['msg']}")
    lines.append("")
    lines.append("=" * 65)
    return "\n".join(lines)


if __name__ == "__main__":
    print(report_matematico())
