"""
vinci_vita_engine.py
AURORA ENGINE v5.0 — Orchestratore con schema database unificato.

FIX (2026-09-29):
- Schema di output unificato: compatibile al 100% con index.html
- Integrato CrowdModel (anti_crowd_score, expected_share_eur)
- Integrato BankrollManager (bankroll_state)
- Aggiunto portfolio_coverage
- Versione database allineata a "5.0"
"""
import json
import os
from datetime import datetime, timedelta

from vinci_vita_math import (
    calcola_ev, soglie_budget, valore_attuale_rendita,
    RENDITA_ATTUALE_MENSILE, COSTO_GIOCATA_EUR,
)
from vinci_vita_generator import extract_fingerprints

try:
    from vinci_vita_fingerprints import AuroraFingerprintEngine
    FP_ADV = True
except ImportError:
    FP_ADV = False

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
    from vinci_vita_crowd import CrowdModel
    CROWD_OK = True
except ImportError:
    CROWD_OK = False

try:
    from vinci_vita_bankroll import BankrollManager
    BANKROLL_OK = True
except ImportError:
    BANKROLL_OK = False


HISTORY_FILE = "vinci_history.json"
DATABASE_FILE = "vinci_database.json"

DATABASE_VERSION = "5.0"


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


def _portfolio_coverage(sestinas):
    if not sestinas:
        return 0.0
    all_nums = set()
    for s in sestinas:
        all_nums.update(s["numeri"])
    unique_ratio = len(all_nums) / (6 * len(sestinas))
    decades = set((n - 1) // 10 for n in all_nums)
    decade_ratio = len(decades) / 9.0
    return round(0.6 * unique_ratio + 0.4 * decade_ratio, 4)


def run_engine(rendita=RENDITA_ATTUALE_MENSILE):
    print("=" * 70)
    print(f"AURORA ENGINE v{DATABASE_VERSION} — UNIFIED SCHEMA")
    print("=" * 70)

    history = load_history()
    print(f"[*] Storico: {len(history)} estrazioni")

    # --- Bias ---
    bias_result = None
    if BIAS_OK:
        print(f"\n[*] Analisi bias...")
        bias_result = quick_bias_check(history, verbose=True)
        print(f"[*] {bias_result['health']}")

    # --- Regime ---
    regime = None
    if REGIME and len(history) >= 20:
        try:
            rd = RegimeDetector(history,
                                recent_window=min(30, max(5, len(history) // 3)))
            health = rd.overall_health()
            print(f"[*] Regime: {health}")
            regime = {"health": health, "n": len(history)}
        except Exception as e:
            print(f"[!] Regime errore: {e}")

    # --- Math ---
    ev = calcola_ev(rendita)
    budget = soglie_budget(rendita)
    print(f"[*] EV: €{ev['ev_netto']:+.4f} ({ev['ev_percentuale']:+.2f}%)")

    # --- Fingerprint ---
    pool = list(range(1, 91))
    fp = extract_fingerprints(history)
    print(f"[*] Fingerprint: {fp['n_draws']} estrazioni")

    fp_eng = None
    if FP_ADV:
        try:
            fp_eng = AuroraFingerprintEngine(history)
        except Exception as e:
            print(f"[!] Fingerprint engine errore: {e}")

    if not PORTF_V3:
        print("[!] Portfolio V3 non disponibile.")
        return None

    # --- Portfolio ---
    print(f"\n[*] Costruzione sestina...")
    p3 = AuroraPortfolioV3(history)
    portfolio_raw = p3.build_single(pool, fp_engine=fp_eng, verbose=True)

    if not portfolio_raw:
        print("[!] Portfolio vuoto.")
        return None

    # --- Crowd ---
    crowd_model = CrowdModel() if CROWD_OK else None

    sdata = []
    for i, item in enumerate(portfolio_raw, 1):
        s = item["numeri"]
        ssum = sum(s)
        ac_score = None
        exp_share = None
        if crowd_model:
            try:
                ac_score = crowd_model.anti_crowd_score_v3(s)
                exp_share = crowd_model.expected_share(s)
            except Exception:
                pass
        sdata.append({
            "id": i,
            "profilo": item["profilo"],
            "numeri": s,
            "somma": ssum,
            "score_profilo": item["score_profilo"],
            "anti_crowd_score": ac_score,
            "expected_share_eur": exp_share,
        })
        print(f"  {i}. [{item['profilo']}] {s} | somma {ssum}")

    # --- Bankroll ---
    bankroll_state = None
    if BANKROLL_OK:
        try:
            bm = BankrollManager()
            bankroll_state = bm.get_state()
        except Exception as e:
            print(f"[!] Bankroll errore: {e}")

    # --- Coverage ---
    coverage = _portfolio_coverage(sdata)

    payload = build_payload(history, sdata, budget, rendita, ev, fp, regime,
                            bias_result, bankroll_state, coverage)
    save_json(DATABASE_FILE, payload)
    return payload


def build_payload(history, sdata, budget, rendita, ev, fp, regime,
                  bias_result, bankroll_state, coverage):
    now = datetime.now()
    lc, ldate, ln, nc, nd = _next_draw_info(history)

    payload = {
        "version": DATABASE_VERSION,
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "rendita_mensile": rendita,
        "valore_attuale_rendita": round(valore_attuale_rendita(rendita), 2),
        "budget_mode": budget,
        "n_sestinas": len(sdata),
        "costo_totale": round(len(sdata) * COSTO_GIOCATA_EUR, 2),
        "sestinas": sdata,
        "portfolio_coverage": coverage,
        "bankroll_state": bankroll_state,
        "bias_analysis": {
            "health": bias_result.get("health"),
            "chi2": bias_result.get("chi2"),
            "is_uniform": bias_result.get("is_uniform"),
            "has_hot_bias": bias_result.get("has_hot_bias"),
            "has_cold_bias": bias_result.get("has_cold_bias"),
            "has_autocorr": bias_result.get("has_autocorr"),
            "hot_numbers": bias_result.get("hot_numbers", [])[:5],
            "cold_numbers": bias_result.get("cold_numbers", [])[:5],
            "profile_weights": bias_result.get("profile_weights"),
        } if bias_result else None,
        "regime_report": regime,
        "ev": {
            "ev_netto": round(ev["ev_netto"], 4),
            "ev_percentuale": round(ev["ev_percentuale"], 2),
        } if ev else None,
        "last_draw": {"concorso": lc, "data": ldate, "numeri": ln},
        "next_draw": {"concorso": nc, "data": nd, "ora": "20:00"},
        "fingerprint_base": {
            "n_draws": fp["n_draws"] if fp else 0,
            "sum_mean": fp["sum_mean"] if fp else None,
        } if fp else None,
    }
    return payload


def format_report(payload):
    if not payload:
        return "❌ Nessun payload."
    lines = [
        f"🌅 AURORA ENGINE v{DATABASE_VERSION} — REPORT",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💎 Rendita: € {payload['rendita_mensile']:,}/mese",
        f"   Valore attuale: € {payload['valore_attuale_rendita']:,.0f}",
        "",
    ]
    if payload.get("bias_analysis"):
        ba = payload["bias_analysis"]
        lines.append(f"🧪 {ba.get('health', 'N/A')}")
        lines.append("")
    if payload.get("regime_report"):
        lines.append(f"🔬 {payload['regime_report']['health']}")
        lines.append("")
    nd = payload["next_draw"]
    lines.append(f"🎯 PROSSIMA: Concorso N° {nd['concorso']} · {nd['data']}")
    lines.append("")
    ld = payload["last_draw"]
    if ld["numeri"]:
        ns = " · ".join(str(n).zfill(2) for n in ld["numeri"])
        lines.append(f"📊 ULTIMA (N° {ld['concorso']}): {ns}")
        lines.append("")
    if payload["sestinas"]:
        lines.append(f"🎲 SESTINA (€{payload['costo_totale']:.2f})")
        for s in payload["sestinas"]:
            ns = " · ".join(str(n).zfill(2) for n in s["numeri"])
            lines.append(f"   <code>[{ns}]</code>")
            lines.append(f"   Somma {s['somma']}")
        lines.append("")
    lines.append(f"🌅 Aurora Engine v{DATABASE_VERSION} — Super Win for Life")
    return "\n".join(lines)


if __name__ == "__main__":
    payload = run_engine()
    if payload:
        print("\n" + "=" * 70)
        print(format_report(payload))
        print("=" * 70)
