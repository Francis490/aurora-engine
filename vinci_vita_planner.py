"""
vinci_vita_planner.py
AURORA ENGINE v5.0 — Planner: genera 1 sestina con schema unificato.

FIX (2026-09-29):
- Schema di output UNIFICATO con vinci_vita_engine.py
- Rendita importata da vinci_vita_math (single source of truth)
- Rimossi titan_predictions/dodeca_pool fittizi
- Rimosso valore_attuale_rendita duplicato
"""
import json
import os
import sys
import random
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

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


HISTORY_FILE = "vinci_history.json"
DATABASE_FILE = "vinci_database.json"
DEFAULT_N = 2
DATABASE_VERSION = "5.0"


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_json(fp, data):
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[+] Salvato: {fp}")


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
            "chat_id": chat_id,
            "text": text,
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


def build_database(sestinas_data, history):
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
        "bias_analysis": None,
        "regime_report": None,
        "ev": {
            "ev_netto": round(ev["ev_netto"], 4),
            "ev_percentuale": round(ev["ev_percentuale"], 2),
        },
        "last_draw": {"concorso": lc, "data": ldate, "numeri": ln},
        "next_draw": {"concorso": nc, "data": nd, "ora": "20:00"},
        "fingerprint_base": None,
    }


def build_telegram_report(sestinas_data, fp, next_concorso, next_date):
    lines = []
    lines.append("🌅 <b>AURORA PLANNER</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"🎯 <b>PROSSIMO: Concorso N° {next_concorso}</b> · {next_date}")
    lines.append("")
    if fp:
        lines.append(f"📊 <b>Forma delle {fp['n_samples']} sestine reali:</b>")
        lines.append(f"   • Somma media: {fp['sum_mean']}")
        lines.append(f"   • Gap medio: {fp['gap_avg']}")
        lines.append("")
    lines.append(f"🎲 <b>{len(sestinas_data)} SESTINE DA GIOCARE</b>")
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

    fp = extract_fingerprints(history)
    fp_eng = None
    if FP_ADV:
        try:
            fp_eng = AuroraFingerprintEngine(history)
        except Exception:
            pass

    pool = list(range(1, 91))
    p3 = AuroraPortfolioV3(history)

    sestinas_data = []
    crowd_model = CrowdModel() if CROWD_OK else None

    for i in range(args.n):
        # Seed diverso per ogni sestina
        result = p3.build_single(pool, fp_engine=fp_eng, verbose=False,
                                 seed=42 + i)
        if not result:
            continue
        item = result[0]
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
            "id": i + 1,
            "profilo": item["profilo"],
            "numeri": s,
            "somma": sum(s),
            "score_profilo": item["score_profilo"],
            "anti_crowd_score": ac_score,
            "expected_share_eur": exp_share,
        })

    if not sestinas_data:
        print("[!] Nessuna sestina generata.")
        sys.exit(1)

    print()
    for s in sestinas_data:
        print(f"  {s['id']}. {s['numeri']} (somma {s['somma']})")

    # Salva planner (legacy, mantenuto per compat)
    save_json("vinci_planner.json", {
        "next_concorso": _next_draw_info(history)[3],
        "fingerprint": fp,
        "sestinas": [s["numeri"] for s in sestinas_data],
    })

    db = build_database(sestinas_data, history)
    save_json(DATABASE_FILE, db)

    print("\n[*] Invio Telegram...")
    _, _, _, nc, nd = _next_draw_info(history)
    report = build_telegram_report(sestinas_data, fp, nc, nd)
    send_telegram_message(report)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
