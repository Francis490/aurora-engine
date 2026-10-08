"""
vinci_vita_math.py
AURORA ENGINE — Modulo matematico Super Win for Life (Vinci per la Vita)

FIX (2026-09-29 v2):
- EV corretto per condivisione del 6 punti (share factor 0.94)
- Tabella premi caricata dinamicamente da vinci_premi.json (fallback su default)
- Report con nota epistemologica e decimali ridotti
- Il 6 punti non vale più il jackpot intero, ma la quota attesa pro capite

Matematica del gioco:
- Probabilità ipergeometriche (8 estratti da 90, 6 giocati)
- Valore attuale della rendita (annuity, tasso 2%)
- EV per categoria, corretto per condivisione
- Kelly criterion
"""
from math import comb
from typing import Dict, Optional
import json
import os


# ==========================================
# COSTANTI DI GIOCO
# ==========================================
TOTALE_NUMERI = 90
NUMERI_ESTRATTI = 8
NUMERI_GIOCATI = 6
COSTO_GIOCATA_EUR = 2.00
PAYOUT_RATIO_DICHIARATO = 0.65

# Rendita
RENDITA_ATTUALE_MENSILE = 14_390
DURATA_RENDITA_ANNI = 20
MESI_PER_ANNO = 12
TASSO_SCONTO_ANNUO = 0.02
RENDITA_MINIMA_TOTALE = 2_429_875

# Stima del fattore di condivisione del 6 punti.
# Con ~50M sestine giocate e P(6)=1/622M, il numero medio di ALTRI
# vincitori quando TU vinci è k ≈ 0.08.
# E[1/(1+N)] con N ~ Poisson(0.08) ≈ 0.96. Arrotondato a 0.94 (prudenza).
SHARE_FACTOR_6PUNTI = 0.94

# File opzionale con premi reali (se presente)
PREMI_FILE = "vinci_premi.json"


# ==========================================
# TABELLA PREMI (default, sovrascrivibile da vinci_premi.json)
# ==========================================
TABELLA_PREMI_DEFAULT = {
    6: None,       # calcolato dinamicamente
    5: 15_000.0,
    4: 178.59,
    3: 22.06,
    2: 5.00,
    1: 0.0,
    0: 0.0,
}


def _load_premi_table() -> Dict:
    """
    Carica la tabella premi da vinci_premi.json se esiste.
    Struttura attesa:
        {"medie": {"5": 15000, "4": 178.59, "3": 22.06, "2": 5.00}}
    """
    if os.path.exists(PREMI_FILE):
        try:
            with open(PREMI_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            medie = data.get("medie", {})
            table = dict(TABELLA_PREMI_DEFAULT)
            for k, v in medie.items():
                try:
                    table[int(k)] = float(v)
                except (ValueError, TypeError):
                    continue
            return table
        except Exception as e:
            print(f"[!] Errore lettura {PREMI_FILE}: {e}")
    return dict(TABELLA_PREMI_DEFAULT)


# ==========================================
# 1. PROBABILITÀ IPERGEOMETRICHE
# ==========================================
def ipergeometrica(k, n_estratti=NUMERI_ESTRATTI,
                   n_giocati=NUMERI_GIOCATI,
                   n_totali=TOTALE_NUMERI) -> float:
    if k < 0 or k > n_giocati or k > n_estratti:
        return 0.0
    den = comb(n_totali, n_giocati)
    if den == 0:
        return 0.0
    return (comb(n_estratti, k) *
            comb(n_totali - n_estratti, n_giocati - k)) / den


def probabilita_tutte_categorie() -> Dict[int, float]:
    return {k: ipergeometrica(k) for k in range(NUMERI_GIOCATI + 1)}


def probabilita_1_su_n(k) -> Optional[float]:
    p = ipergeometrica(k)
    return 1 / p if p > 0 else None


# ==========================================
# 2. VALORE ATTUALE RENDITA
# ==========================================
def valore_attuale_rendita(rendita_mensile,
                           anni=DURATA_RENDITA_ANNI,
                           tasso_annuo=TASSO_SCONTO_ANNUO) -> float:
    n_mesi = anni * MESI_PER_ANNO
    r_mensile = tasso_annuo / MESI_PER_ANNO
    if r_mensile == 0:
        return rendita_mensile * n_mesi
    return rendita_mensile * (1 - (1 + r_mensile) ** (-n_mesi)) / r_mensile


def valore_nominale_rendita(rendita_mensile, anni=DURATA_RENDITA_ANNI) -> float:
    return rendita_mensile * anni * MESI_PER_ANNO


# ==========================================
# 3. PREMIO STIMATO (con correzione condivisione)
# ==========================================
def premio_stimato(k, rendita_mensile=RENDITA_ATTUALE_MENSILE) -> float:
    """
    Premio atteso per categoria.
    Per il 6 punti applica SHARE_FACTOR_6PUNTI (condivisione realistica).
    """
    if k == 6:
        return valore_attuale_rendita(rendita_mensile) * SHARE_FACTOR_6PUNTI
    table = _load_premi_table()
    return table.get(k, 0.0) or 0.0


# ==========================================
# 4. EV
# ==========================================
def calcola_ev(rendita_mensile=RENDITA_ATTUALE_MENSILE,
               costo=COSTO_GIOCATA_EUR) -> Dict:
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
        "share_factor_6": SHARE_FACTOR_6PUNTI,
        "payout_effettivo": ev_lordo / costo,
        "contributi": contributi,
        "profittevole": ev_netto > 0,
        "e_stima": True,
    }


# ==========================================
# 5. KELLY
# ==========================================
def kelly_fraction(prob_win, payoff_odds, prob_loss=None) -> float:
    if prob_loss is None:
        prob_loss = 1 - prob_win
    if payoff_odds <= 0:
        return 0.0
    return (payoff_odds * prob_win - prob_loss) / payoff_odds


def kelly_analysis(rendita_mensile=RENDITA_ATTUALE_MENSILE) -> Dict:
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
# 6. SOGLIE BUDGET
# ==========================================
def soglie_budget(rendita_mensile=RENDITA_ATTUALE_MENSILE) -> Dict:
    ev_data = calcola_ev(rendita_mensile)
    ev = ev_data["ev_netto"]

    if ev < -1.50:
        return {"mode": "SKIP", "emoji": "🚫", "n_sestine": 0, "costo": 0.0,
                "msg": "⚠️ EV anomalo. Verifica dati. Nessuna sestina."}
    elif ev < -1.20:
        return {"mode": "MINIMO", "emoji": "🟢", "n_sestine": 1, "costo": 2.0,
                "msg": "EV molto negativo. 1 sestina (2€)."}
    elif ev < -1.00:
        return {"mode": "MINIMO", "emoji": "🟢", "n_sestine": 1, "costo": 2.0,
                "msg": "EV negativo. 1 sestina (2€)."}
    elif ev < -0.80:
        return {"mode": "NORMALE", "emoji": "🟡", "n_sestine": 2, "costo": 4.0,
                "msg": "EV nella media del gioco. 2 sestine (4€)."}
    elif ev < -0.60:
        return {"mode": "ATTACK", "emoji": "🟠", "n_sestine": 3, "costo": 6.0,
                "msg": "EV meno negativo del solito. 3 sestine (6€)."}
    else:
        return {"mode": "ALL-IN", "emoji": "🔥", "n_sestine": 5, "costo": 10.0,
                "msg": "EV quasi neutro! 5 sestine (10€)."}


# ==========================================
# 7. REPORT
# ==========================================
def report_matematico(rendita_mensile=RENDITA_ATTUALE_MENSILE) -> str:
    ev = calcola_ev(rendita_mensile)
    budget = soglie_budget(rendita_mensile)

    lines = []
    lines.append("=" * 65)
    lines.append("AURORA ENGINE — REPORT MATEMATICO")
    lines.append("Super Win for Life")
    lines.append("=" * 65)
    lines.append("")
    lines.append(f"Rendita mensile:        € {rendita_mensile:,}/mese")
    lines.append(f"Valore attuale (2%):    € {valore_attuale_rendita(rendita_mensile):,.0f}")
    lines.append(f"Fattore condivisione 6: {SHARE_FACTOR_6PUNTI}")
    lines.append("")
    lines.append("DISTRIBUZIONE PROBABILITÀ:")
    for k in range(6, -1, -1):
        c = ev["contributi"][k]
        p_1su = c["probabilita_1su"]
        prob_str = f"1 su {p_1su:,.0f}" if p_1su and p_1su < 1e12 else "—"
        lines.append(f"  {k} punti: {c['probabilita']:.10f}  ({prob_str})")
    lines.append("")
    lines.append(f"EV netto:               € {ev['ev_netto']:.2f}  [STIMA]")
    lines.append(f"EV percentuale:         {ev['ev_percentuale']:+.1f}%")
    lines.append("")
    lines.append("⚠️  Nota epistemologica:")
    lines.append("   L'EV è una STIMA basata su:")
    lines.append("   - Probabilità ipergeometriche (esatte)")
    lines.append("   - Tabella premi (media storica, variabile)")
    lines.append("   - Fattore di condivisione del 6 punti (stima)")
    lines.append("   Il vero EV varia di ±0,20€ per concorso.")
    lines.append("   Usa l'EV per DECIDERE quante sestine giocare,")
    lines.append("   non per prevedere quanto vincerai.")
    lines.append("")
    lines.append("SOGLIE BUDGET:")
    lines.append(f"  Modo: {budget['mode']} {budget.get('emoji', '')}")
    lines.append(f"  Sestine: {budget['n_sestine']}")
    lines.append(f"  Costo: € {budget['costo']:.2f}")
    lines.append("=" * 65)
    return "\n".join(lines)


if __name__ == "__main__":
    print(report_matematico())
