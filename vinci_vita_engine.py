"""
vinci_vita_engine.py
AURORA ENGINE v5.4 — Orchestratore con build_multiple (N sestine, overlap <= 2).

FIX (2026-10-01):
- Passa seed = 1000 + next_concorso a build_multiple.
- RIMOSSO completamente anti-crowd (import, calcolo, campi output).
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
    from vinci_vita_bankroll import BankrollManager
    BANKROLL_OK = True
except ImportError:
    BANKROLL_OK = False


HISTORY_FILE = "vinci_history.json"
DATABASE_FILE = "vinci_database.json"

DATABASE_VERSION = "5.4"
N_SESTINE_DEFAULT = 2


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


def run_engine(rendita=RENDITA_ATTUALE_MENSILE, n_sestine=N_SESTINE_DEFAULT):
    print("=" * 70)
    print(f"AURORA ENGINE v{DATABASE_VERSION} — MULTI-SESTINA")
    print("=" * 70)

    history = load_history()
    print(f"[*] Storico: {len(history)} estrazioni")

    bias_result = None
    if BIAS_OK:
        print(f"\n[*] Analisi bias...")
        bias_result = quick_bias_check(history, verbose=True)
        print(f"[*] {bias_result['health']}")

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

    ev = calcola_ev(rendita)
    budget = soglie_budget(rendita)
    print(f"[*] EV: €{ev['ev_netto']:+.4f} ({ev['ev_percentuale']:+.2f}%)")
    print(f"[*] Budget mode: {budget['mode']} ({budget['n_sestine']} sestine)")

    if budget["mode"] == "SKIP":
        print("[*] SKIP mode attivo. Nessuna sestina generata.")
        n_sestine = 0

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

    # Seed derivato dal concorso target
    lc_for_seed, _, _, nc_for_seed, _ = _next_draw_info(history)
    try:
        seed_for_portfolio = 1000 + int(nc_for_seed)
    except (ValueError, TypeError):
        seed_for_portfolio = 1000

    if n_sestine > 0:
        print(f"\n[*] Costruzione {n_sestine} sestine con overlap <= 2...")
        print(f"[*] Seed portfolio: {seed_for_portfolio} (concorso {nc_for_seed})")
        p3 = AuroraPortfolioV3(history)
        portfolio_raw = p3.build_multiple(
            pool, n_sestine, fp_engine=fp_eng, verbose=True,
            base_seed=seed_for_portfolio
        )
    else:
        portfolio_raw = []

    # Costruzione sdata SENZA anti-crowd
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
        print(f"  {i}. [{item['profilo']}] {s} | somma {ssum}")

    bankroll_state = None
    if BANKROLL_OK:
        try:
            bm = BankrollManager()
            bankroll_state = bm.get_state()
        except Exception as e:
            print(f"[!] Bankroll errore: {e}")

    coverage = _portfolio_coverage(sdata)

    payload = build_payload(history, sdata, budget, rendita, ev, fp, regime,
                            bias_result, bankroll_state, coverage)
    save_json(DATABASE_FILE, payload)
    return payload


def build_payload(history, sdata, budget, rendita, ev, fp, regime,
                  bias_result, bankroll_state, coverage):
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
        n = len(payload["sestinas"])
        lines.append(f"🎲 {n} SESTINE (€{payload['costo_totale']:.2f})")
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
