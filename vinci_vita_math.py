"""
vinci_vita_math.py
AURORA ENGINE — Modulo matematico Super Win for Life (Vinci per la Vita)

Matematica ESATTA del gioco:
- Probabilità ipergeometriche (8 estratti da 90, 6 giocati)
- Valore attuale della rendita (annuity, tasso 2%)
- EV per categoria
- Kelly criterion
- Soglie budget ricalibrate (costo 2€)

Riferimenti:
- Regolamento Super Win for Life (Sisal): rendita CONDIVISA
- Rendita attuale: 13.810 €/mese per 20 anni
- Rendita minima garantita: 2.429.875 € totali
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
RENDITA_ATTUALE_MENSILE = 13_810
RENDITA_MINIMA_TOTALE = 2_429_875  # garantita dal regolamento
DURATA_RENDITA_ANNI = 20
MESI_PER_ANNO = 12

# Tasso di sconto per valore attuale
TASSO_SCONTO_ANNUO = 0.02


# ==========================================
# 1. PROBABILITÀ IPERGEOMETRICHE ESATTE
# ==========================================
def ipergeometrica(k: int, n_estratti: int = NUMERI_ESTRATTI,
                   n_giocati: int = NUMERI_GIOCATI,
                   n_totali: int = TOTALE_NUMERI) -> float:
    """
    P(k match tra i numeri giocati e gli estratti).
    P(k) = C(n_estratti, k) * C(n_totali - n_estratti, n_giocati - k)
           / C(n_totali, n_giocati)
    """
    if k < 0 or k > n_giocati or k > n_estratti:
        return 0.0
    denominatore = comb(n_totali, n_giocati)
    if denominatore == 0:
        return 0.0
    return (comb(n_estratti, k) *
            comb(n_totali - n_estratti, n_giocati - k)) / denominatore


def probabilita_tutte_categorie() -> Dict[int, float]:
    return {k: ipergeometrica(k) for k in range(NUMERI_GIOCATI + 1)}


def probabilita_1_su_n(k: int) -> Optional[float]:
    p = ipergeometrica(k)
    return 1 / p if p > 0 else None


# ==========================================
# 2. VALORE ATTUALE DELLA RENDITA
# ==========================================
def valore_attuale_rendita(rendita_mensile: float,
                           anni: int = DURATA_RENDITA_ANNI,
                           tasso_annuo: float = TASSO_SCONTO_ANNUO) -> float:
    """
    VA di una rendita mensile costante.
    VA = R * [(1 - (1 + r_m)^(-n)) / r_m]
    """
    n_mesi = anni * MESI_PER_ANNO
    r_mensile = tasso_annuo / MESI_PER_ANNO
    if r_mensile == 0:
        return rendita_mensile * n_mesi
    return rendita_mensile * (1 - (1 + r_mensile) ** (-n_mesi)) / r_mensile


def valore_nominale_rendita(rendita_mensile: float,
                            anni: int = DURATA_RENDITA_ANNI) -> float:
    return rendita_mensile * anni * MESI_PER_ANNO


# ==========================================
# 3. TABELLA PREMI (STIME EMPIRICHE)
# ==========================================
# Nota: i premi per 3/4/5 punti sono VARIABILI (dipendono dalla raccolta).
# Queste sono medie osservate da estrazioni recenti.
TABELLA_PREMI_MEDIA = {
    6: None,       # rendita condivisa (gestita separatamente)
    5: 15_000.0,   # stima da osservazioni
    4: 170.66,     # osservato 18/09/2026
    3: 22.06,      # osservato 18/09/2026
    2: 5.00,       # FISSO garantito dal regolamento
    1: 0.0,
    0: 0.0,
}


def premio_stimato(k: int, rendita_mensile: float = RENDITA_ATTUALE_MENSILE) -> float:
    """Ritorna il premio stimato per k punti. k=6 → VA rendita."""
    if k == 6:
        return valore_attuale_rendita(rendita_mensile)
    return TABELLA_PREMI_MEDIA.get(k, 0.0) or 0.0


# ==========================================
# 4. EV (EXPECTED VALUE)
# ==========================================
def calcola_ev(rendita_mensile: float = RENDITA_ATTUALE_MENSILE,
               costo: float = COSTO_GIOCATA_EUR) -> Dict:
    """
    EV ESATTO di una singola giocata (assumendo rendita NON condivisa).
    Per rendita CONDIVISA, l'EV reale è più basso (dipende dal crowding).
    """
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
        "nota": "EV calcolato assumendo rendita non condivisa. "
                "In realtà è condivisa → EV reale più basso.",
    }


# ==========================================
# 5. KELLY CRITERION
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
# 6. SOGLIE BUDGET (ricalibrate per costo 2€)
# ==========================================
def soglie_budget(rendita_mensile: float = RENDITA_ATTUALE_MENSILE) -> Dict:
    ev_data = calcola_ev(rendita_mensile)
    ev = ev_data["ev_netto"]

    if ev < -1.10:
        return {"mode": "SKIP", "n_sestine": 0, "costo": 0.0,
                "msg": "EV molto negativo. Non giocare."}
    elif ev < -0.90:
        return {"mode": "MINIMO", "n_sestine": 1, "costo": 2.0,
                "msg": "EV negativo strutturale. 1 sestina (2,00 €)."}
    elif ev < -0.70:
        return {"mode": "NORMALE", "n_sestine": 2, "costo": 4.0,
                "msg": "EV nella norma del gioco. 2 sestine (4,00 €)."}
    elif ev < -0.50:
        return {"mode": "ATTACK", "n_sestine": 3, "costo": 6.0,
                "msg": "EV meno negativo del solito. 3 sestine (6,00 €)."}
    else:
        return {"mode": "ALL-IN", "n_sestine": 5, "costo": 10.0,
                "msg": "EV quasi neutro! 5 sestine (10,00 €)."}


# ==========================================
# 7. REPORT TECNICO
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
    lines.append(f"Durata rendita:         {DURATA_RENDITA_ANNI} anni")
    lines.append(f"Valore nominale:        € {valore_nominale_rendita(rendita_mensile):,.0f}")
    lines.append(f"Valore attuale (2%):    € {valore_attuale_rendita(rendita_mensile):,.0f}")
    lines.append(f"Rendita minima garantita: € {RENDITA_MINIMA_TOTALE:,}")
    lines.append("")
    lines.append("DISTRIBUZIONE PROBABILITÀ (ipergeometrica esatta):")
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
    lines.append(f"Payout effettivo:       {ev['payout_effettivo']*100:.2f}%")
    lines.append("")
    lines.append("KELLY CRITERION:")
    for k, data in kelly.items():
        lines.append(f"  {k} punti: f* = {data['kelly_fraction']:+.6f} "
                     f"→ {data['kelly_interpretazione']}")
    lines.append("")
    lines.append("SOGLIE BUDGET:")
    lines.append(f"  Modo: {budget['mode']}")
    lines.append(f"  Sestine: {budget['n_sestine']}")
    lines.append(f"  Costo: € {budget['costo']:.2f}")
    lines.append(f"  Msg: {budget['msg']}")
    lines.append("")
    lines.append("=" * 65)
    return "\n".join(lines)


if __name__ == "__main__":
    print(report_matematico())
