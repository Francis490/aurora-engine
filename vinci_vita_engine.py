"""
vinci_vita_engine.py
AURORA ENGINE v4.0 — Orchestratore SENZA anti-crowd.

FIX (2026-09-26):
- Rimosso CrowdModel (anti-crowd)
- Rimosso filtro ACv3
- Pool = tutti i 90 numeri (nessuna restrizione)
- Solo fingerprint statistici per la validazione
- Massima varietà tra le sestine
"""
import json
import os
from datetime import datetime, timedelta

from vinci_vita_math import (
    calcola_ev, kelly_analysis, soglie_budget,
    valore_attuale_rendita,
    RENDITA_ATTUALE_MENSILE, COSTO_GIOCATA_EUR,
)
from vinci_vita_generator import (
    extract_fingerprints,
    SUM_HARD_MIN, SUM_HARD_MAX,
)

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


HISTORY_FILE = "vinci_history.json"
DATABASE_FILE = "vinci_database.json"


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


def run_engine(rendita=RENDITA_ATTUALE_MENSILE):
    print("=" * 70)
    print("AURORA ENGINE v4.0 — SESTINA SENZA ANTI-CROWD")
    print("=" * 70)

    history = load_history()
    print(f"[*] Storico: {len(history)} estrazioni")

    # Bias test
    bias_result = None
    if BIAS_OK:
        print(f"\n[*] Analisi bias...")
        bias_result = quick_bias_check(history, verbose=True)
        print(f"[*] {bias_result['health']}")

    # Regime
    regime = None
    if REGIME and len(history) >= 20:
        try:
            rd = RegimeDetector(history, recent_window=min(30, max(5, len(history) // 3)))
            health = rd.overall_health()
            print(f"[*] Regime: {health}")
            regime = {"health": health, "n": len(history)}
        except Exception as e:
            print(f"[!] Regime errore: {e}")

    ev = calcola_ev(rendita)
    budget = soglie_budget(rendita)
    print(f"[*] EV: €{ev['ev_netto']:+.4f} ({ev['ev_percentuale']:+.2f}%)")

    # Pool = TUTTI i 90 numeri (nessuna restrizione)
    pool = list(range(1, 91))
    print(f"[*] Pool: tutti i 90 numeri")

    fp = extract_fingerprints(history)
    print(f"[*] Fingerprint base: {fp['n_draws']} estrazioni")

    fp_eng = None
    if FP_ADV:
        try:
            fp_eng = AuroraFingerprintEngine(history)
        except Exception:
            pass

    if not PORTF_V3:
        print("[!] Portfolio V3 non disponibile.")
        return None

    print(f"\n[*] Costruzione sestina (50% trend + 50% contrarian, no anti-crowd)...")
    p3 = AuroraPortfolioV3(history)
    portfolio_raw = p3.build_single(
        pool,
        fp_engine=fp_eng,
        verbose=True,
    )

    if not portfolio_raw:
        print("[!] Portfolio vuoto.")
        return None

    sdata = []
    for i, item in enumerate(portfolio_raw, 1):
        s = item["numeri"]
        ssum = sum(s)

        fpd = None
        if fp_eng:
            try:
                fpd = fp_eng.score_sestina(s)
            except Exception:
                pass

        sdata.append({
            "id": i,
            "profilo": item["profilo"],
            "numeri": s,
            "somma": ssum,
            "score_profilo": item["score_profilo"],
            "fingerprint_detail": fpd,
        })
        print(f"  {i}. [{item['profilo']}] {s} | somma {ssum}")

    payload = build_payload(history, sdata, budget, rendita, ev, fp, regime, bias_result)
    save_json(DATABASE_FILE, payload)
    return payload


def build_payload(history, sdata, budget, rendita, ev, fp, regime, bias_result):
    now = datetime.now()
    ld = history[-1] if history else {}
    lc = ld.get("concorso", "N/A")
    ln = ld.get("numeri", [])
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

    return {
        "version": "4.0",
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "rendita_mensile": rendita,
        "valore_attuale_rendita": round(valore_attuale_rendita(rendita), 2),
        "budget_mode": budget,
        "n_sestinas": len(sdata),
        "costo_totale": round(len(sdata) * COSTO_GIOCATA_EUR, 2),
        "sestinas": sdata,
        "bias_analysis": {
            "health": bias_result.get("health"),
            "chi2": bias_result.get("chi2"),
            "is_uniform": bias_result.get("is_uniform"),
            "has_hot_bias": bias_result.get("has_hot_bias"),
            "has_cold_bias": bias_result.get("has_cold_bias"),
            "has_autocorr": bias_result.get("has_autocorr"),
            "hot_numbers": bias_result.get("hot_numbers", [])[:5],
            "cold_numbers": bias_result.get("cold_numbers", [])[:5],
        } if bias_result else None,
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
        "regime_report": regime,
    }


def format_report(payload):
    if not payload:
        return "❌ Nessun payload."
    lines = [
        "🌅 AURORA ENGINE v4.0 — REPORT",
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

    lines.append("🌅 Aurora Engine v4.0 — Super Win for Life")
    return "\n".join(lines)


if __name__ == "__main__":
    payload = run_engine()
    if payload:
        print("\n" + "=" * 70)
        print(format_report(payload))
        print("=" * 70)
