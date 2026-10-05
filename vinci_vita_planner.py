"""
vinci_vita_planner.py
AURORA ENGINE v5.1 — Planner: N sestine con overlap controllato.

FIX (2026-10-05):
- load_history e save_json ora usano core_io.py (modulo condiviso).
- Rimossa la definizione locale di save_json (va in conflitto con core_io).
- Rimosso import json diretto (non più necessario).

FIX (2026-09-29):
- Usa AuroraPortfolioV3.build_multiple (overlap <= 2)
- Calcola bias_analysis e regime_report come l'engine
- Schema di output unificato con vinci_vita_engine.py
"""
import os
import sys
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

from core_io import load_json, save_json

from vinci_vita_math import (
    RENDITA_ATTUALE_MENSILE, valore_attuale_rendita,
    calcola_ev, soglie_budget, COSTO_GIOCATA_EUR,
)
from vinci_vita_generator import extract_fingerprints

try:
    from vinci_vita_portfolio_v3 import AuroraPortfolioV3
    PORTF_V3 = True
except ImportError:
    PORTF_V3 = False

try:
    from vinci_vita_fingerprints import AuroraFingerprintEngine
    FP_ADV = True
except ImportError:
    FP_ADV = False

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

try:
    from vinci_vita_bias_test import quick_bias_check
    BIAS_OK = True
except ImportError:
    BIAS_OK = False

try:
    from vinci_vita_regime import RegimeDetector
    REGIME_OK = True
except ImportError:
    REGIME_OK = False


HISTORY_FILE = "vinci_history.json"
DATABASE_FILE = "vinci_database.json"
DEFAULT_N = 2
DATABASE_VERSION = "5.1"


def load_history():
    data = load_json(HISTORY_FILE, [])
    return data if isinstance(data, list) else []


def send_telegram_message(text, parse_mode="HTML"):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        print("[!] Token/chat_id mancanti.")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    if len(text) > 4000:
        text = text[:3997] + "..."
    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"[+] Telegram: {response.status}")
            return True
    except Exception as e:
        print(f"[!] Errore Telegram: {e}")
        return False


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


def _portfolio_coverage(sestinas_data):
    if not sestinas_data:
        return 0.0
    all_nums = set()
    for s in sestinas_data:
        all_nums.update(s["numeri"])
    unique_ratio = len(all_nums) / (6 * len(sestinas_data))
    decades = set((n - 1) // 10 for n in all_nums)
    decade_ratio = len(decades) / 9.0
    return round(0.6 * unique_ratio + 0.4 * decade_ratio, 4)


def build_database(sestinas_data, history, bias_result, regime_result):
    now = datetime.now()
    lc, ldate, ln, nc, nd = _next_draw_info(history)

    ev = calcola_ev(RENDITA_ATTUALE_MENSILE)
    budget = soglie_budget(RENDITA_ATTUALE_MENSILE)

    bankroll_state = None
    if BANKROLL_OK:
        try:
            bm = BankrollManager()
            bankroll_state = bm.get_state()
        except Exception:
            pass

    coverage = _portfolio_coverage(sestinas_data)

    return {
        "version": DATABASE_VERSION,
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "rendita_mensile": RENDITA_ATTUALE_MENSILE,
        "valore_attuale_rendita": round(valore_attuale_rendita(RENDITA_ATTUALE_MENSILE), 2),
        "budget_mode": budget,
        "n_sestinas": len(sestinas_data),
        "costo_totale": round(len(sestinas_data) * COSTO_GIOCATA_EUR, 2),
        "sestinas": sestinas_data,
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
        "regime_report": regime_result,
        "ev": {
            "ev_netto": round(ev["ev_netto"], 4),
            "ev_percentuale": round(ev["ev_percentuale"], 2),
        },
        "last_draw": {"concorso": lc, "data": ldate, "numeri": ln},
        "next_draw": {"concorso": nc, "data": nd, "ora": "20:00"},
        "fingerprint_base": None,
    }


def build_telegram_report(sestinas_data, fp, next_concorso, next_date,
                          bias_result, regime_result):
    lines = []
    lines.append("🌅 <b>AURORA PLANNER</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"🎯 <b>PROSSIMO: Concorso N° {next_concorso}</b> · {next_date}")
    lines.append("")

    if bias_result:
        lines.append(f"🧪 {bias_result.get('health', 'N/A')}")
        lines.append("")
    if regime_result:
        lines.append(f"🔬 {regime_result.get('health', 'N/A')}")
        lines.append("")

    if fp:
        lines.append(f"📊 <b>Forma ({fp['n_samples']} sestine reali):</b>")
        lines.append(f"   Somma μ={fp['sum_mean']} · gap μ={fp['gap_avg']}")
        lines.append("")

    lines.append(f"🎲 <b>{len(sestinas_data)} SESTINE</b>")
    lines.append("")
    for s in sestinas_data:
        ns = " · ".join(str(n).zfill(2) for n in s["numeri"])
        lines.append(f"   {s['id']}. <code>[{ns}]</code>")
        lines.append(f"      Somma {s['somma']}")
        if s.get("anti_crowd_score") is not None:
            lines.append(f"      ACv3 {s['anti_crowd_score']:.2f}")
        lines.append("")
    lines.append("🌅 <i>Aurora Planner — Super Win for Life</i>")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    args = parser.parse_args()

    print("=" * 60)
    print(f"AURORA PLANNER v{DATABASE_VERSION}")
    print("=" * 60)

    history = load_history()
    print(f"[*] Storico: {len(history)} estrazioni")

    if len(history) < 5:
        print("[!] Storico insufficiente.")
        sys.exit(1)

    if not PORTF_V3:
        print("[!] vinci_vita_portfolio_v3 non disponibile.")
        sys.exit(1)

    # Bias
    bias_result = None
    if BIAS_OK:
        print("\n[*] Analisi bias...")
        bias_result = quick_bias_check(history, verbose=True)
        print(f"[*] {bias_result['health']}")

    # Regime
    regime_result = None
    if REGIME_OK and len(history) >= 20:
        try:
            rd = RegimeDetector(
                history,
                recent_window=min(30, max(5, len(history) // 3)),
            )
            health = rd.overall_health()
            print(f"[*] Regime: {health}")
            regime_result = {"health": health, "n": len(history)}
        except Exception as e:
            print(f"[!] Regime errore: {e}")

    fp = extract_fingerprints(history)
    fp_eng = None
    if FP_ADV:
        try:
            fp_eng = AuroraFingerprintEngine(history)
        except Exception:
            pass

    pool = list(range(1, 91))
    p3 = AuroraPortfolioV3(history)

    print(f"\n[*] Genero {args.n} sestine con overlap controllato...")
    raw = p3.build_multiple(pool, args.n, fp_engine=fp_eng, verbose=True)

    if not raw:
        print("[!] Nessuna sestina generata.")
        sys.exit(1)

    crowd_model = CrowdModel() if CROWD_OK else None
    sestinas_data = []
    for i, item in enumerate(raw, 1):
        s = item["numeri"]
        ac_score = None
        exp_share = None
        if crowd_model:
            try:
                ac_score = crowd_model.anti_crowd_score_v3(s)
                exp_share = crowd_model.expected_share(s)
            except Exception:
                pass
        sestinas_data.append({
            "id": i,
            "profilo": item["profilo"],
            "numeri": s,
            "somma": sum(s),
            "score_profilo": item["score_profilo"],
            "anti_crowd_score": ac_score,
            "expected_share_eur": exp_share,
        })

    print()
    for s in sestinas_data:
        print(f"  {s['id']}. {s['numeri']} (somma {s['somma']})")

    # Legacy planner file
    _, _, _, nc, nd = _next_draw_info(history)
    save_json("vinci_planner.json", {
        "next_concorso": nc,
        "fingerprint": fp,
        "sestinas": [s["numeri"] for s in sestinas_data],
    })

    db = build_database(sestinas_data, history, bias_result, regime_result)
    save_json(DATABASE_FILE, db)

    print("\n[*] Invio Telegram...")
    report = build_telegram_report(sestinas_data, fp, nc, nd,
                                   bias_result, regime_result)
    send_telegram_message(report)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
