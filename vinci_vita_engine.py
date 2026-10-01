"""
vinci_vita_engine.py
AURORA ENGINE v5.5 — Orchestratore semplificato.

FIX (2026-10-01):
- N_SESTINE_DEFAULT = 1 (una sola sestina per concorso).
- Rimosso ogni accoppiamento con filtri/scoring complessi.
- Rimosso fingerprint engine dai passaggi.
- Rimosso anti-crowd.
"""
import json
import os
from datetime import datetime, timedelta

from vinci_vita_math import (
    calcola_ev, soglie_budget, valore_attuale_rendita,
    RENDITA_ATTUALE_MENSILE, COSTO_GIOCATA_EUR,
)

try:
    from vinci_vita_portfolio_v3 import AuroraPortfolioV3
    PORTF_V3 = True
except ImportError:
    PORTF_V3 = False
    print("[!] vinci_vita_portfolio_v3 non disponibile")

try:
    from vinci_vita_bias_test import quick_bias_check
    BIAS_OK = True
except ImportError:
    BIAS_OK = False

try:
    from vinci_vita_regime import RegimeDetector
    REGIME = True
except ImportError:
    REGIME = False

try:
    from vinci_vita_bankroll import BankrollManager
    BANKROLL_OK = True
except ImportError:
    BANKROLL_OK = False


HISTORY_FILE = "vinci_history.json"
DATABASE_FILE = "vinci_database.json"

DATABASE_VERSION = "5.5"
N_SESTINE_DEFAULT = 1


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Errore lettura: {e}")
    return []


def save_json(fp, data):
    try:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[+] Salvato: {fp}")
    except Exception as e:
        print(f"[!] Errore salvataggio: {e}")


def _next_draw_info(history):
    now = datetime.now()
    ld = history[-1] if history else {}
    lc = ld.get("concorso", "N/A")
    ldate = ld.get("data", "N/A")
    try:
        nc = int(lc) + 1
    except (ValueError, TypeError):
        nc = 1
    if ldate != "N/A":
        try:
            dt = datetime.strptime(ldate, "%d/%m/%Y")
            nd = (dt + timedelta(days=1)).strftime("%d/%m/%Y")
        except Exception:
            nd = (now + timedelta(days=1)).strftime("%d/%m/%Y")
    else:
        nd = (now + timedelta(days=1)).strftime("%d/%m/%Y")
    return lc, ldate, ld.get("numeri", []), nc, nd


def run_engine(rendita=RENDITA_ATTUALE_MENSILE, n_sestine=N_SESTINE_DEFAULT):
    print("=" * 70)
    print(f"AURORA ENGINE v{DATABASE_VERSION}")
    print("=" * 70)

    history = load_history()
    print(f"[*] Storico: {len(history)} estrazioni")

    bias_result = None
    if BIAS_OK:
        try:
            bias_result = quick_bias_check(history, verbose=False)
        except Exception as e:
            print(f"[!] Bias errore: {e}")

    regime = None
    if REGIME and len(history) >= 20:
        try:
            rd = RegimeDetector(history,
                                recent_window=min(30, max(5, len(history) // 3)))
            health = rd.overall_health()
            regime = {"health": health, "n": len(history)}
        except Exception as e:
            print(f"[!] Regime errore: {e}")

    ev = calcola_ev(rendita)
    budget = soglie_budget(rendita)
    print(f"[*] EV: €{ev['ev_netto']:+.4f} ({ev['ev_percentuale']:+.2f}%)")
    print(f"[*] Budget mode: {budget['mode']}")

    if budget["mode"] == "SKIP":
        print("[*] SKIP mode: nessuna sestina.")
        n_sestine = 0

    if not PORTF_V3:
        print("[!] Portfolio V3 non disponibile.")
        return None

    pool = list(range(1, 91))
    _, _, _, nc_for_seed, _ = _next_draw_info(history)
    try:
        seed_for_portfolio = 1000 + int(nc_for_seed)
    except (ValueError, TypeError):
        seed_for_portfolio = 1000

    if n_sestine > 0:
        print(f"\n[*] Generazione {n_sestine} sestina...")
        print(f"[*] Seed: {seed_for_portfolio}")
        p3 = AuroraPortfolioV3(history)
        portfolio_raw = p3.build_multiple(
            pool, n_sestine, verbose=True,
            base_seed=seed_for_portfolio
        )
    else:
        portfolio_raw = []

    sdata = []
    for i, item in enumerate(portfolio_raw, 1):
        s = item["numeri"]
        ssum = sum(s)
        sdata.append({
            "id": i,
            "profilo": item["profilo"],
            "numeri": s,
            "somma": ssum,
            "score_profilo": item["score_profilo"],
        })
        print(f"  {i}. {s} | somma {ssum}")

    bankroll_state = None
    if BANKROLL_OK:
        try:
            bm = BankrollManager()
            bankroll_state = bm.get_state()
        except Exception as e:
            print(f"[!] Bankroll errore: {e}")

    payload = build_payload(history, sdata, budget, rendita, ev,
                            regime, bias_result, bankroll_state)
    save_json(DATABASE_FILE, payload)
    return payload


def build_payload(history, sdata, budget, rendita, ev,
                  regime, bias_result, bankroll_state):
    now = datetime.now()
    lc, ldate, ln, nc, nd = _next_draw_info(history)

    return {
        "version": DATABASE_VERSION,
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "rendita_mensile": rendita,
        "valore_attuale_rendita": round(valore_attuale_rendita(rendita), 2),
        "budget_mode": budget,
        "n_sestinas": len(sdata),
        "costo_totale": round(len(sdata) * COSTO_GIOCATA_EUR, 2),
        "sestinas": sdata,
        "bankroll_state": bankroll_state,
        "bias_analysis": {
            "health": bias_result.get("health"),
            "chi2": bias_result.get("chi2"),
            "hot_numbers": bias_result.get("hot_numbers", [])[:5],
            "cold_numbers": bias_result.get("cold_numbers", [])[:5],
        } if bias_result else None,
        "regime_report": regime,
        "ev": {
            "ev_netto": round(ev["ev_netto"], 4),
            "ev_percentuale": round(ev["ev_percentuale"], 2),
        } if ev else None,
        "last_draw": {"concorso": lc, "data": ldate, "numeri": ln},
        "next_draw": {"concorso": nc, "data": nd, "ora": "20:00"},
    }


if __name__ == "__main__":
    payload = run_engine()
    if payload:
        print("\n" + "=" * 70)
        s = payload['sestinas'][0]['numeri'] if payload['sestinas'] else '—'
        print(f"Sestina: {s}")
        print("=" * 70)
