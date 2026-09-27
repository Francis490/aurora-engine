"""
vinci_vita_planner.py
Genera 2 sestine con la forma esatta delle estrazioni reali.
Invia il report su Telegram e aggiorna vinci_database.json (dashboard).
"""
import json
import os
import sys
import random
import argparse
import itertools
import urllib.request
import urllib.parse
from datetime import datetime, timedelta


HISTORY_FILE = "vinci_history.json"
DATABASE_FILE = "vinci_database.json"
SUM_MIN = 240
SUM_MAX = 310
DEFAULT_N = 2
RENDITA_MENSILE = 14030  # aggiornata manualmente
TASSO_SCONTO = 0.02
DURATA_ANNI = 20


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


def valore_attuale_rendita(rendita, anni=DURATA_ANNI, tasso=TASSO_SCONTO):
    n_mesi = anni * 12
    r_mensile = tasso / 12
    if r_mensile == 0:
        return rendita * n_mesi
    return rendita * (1 - (1 + r_mensile) ** (-n_mesi)) / r_mensile


def send_telegram_message(text, parse_mode="HTML"):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        print("[!] Token/chat_id mancanti.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
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


def extract_real_fingerprint(history):
    all_sestinas = []
    for d in history:
        nums = d.get("numeri", [])
        if len(nums) == 8:
            for combo in itertools.combinations(nums, 6):
                all_sestinas.append(list(combo))

    n = len(all_sestinas)
    if n == 0:
        return None

    sums = [sum(s) for s in all_sestinas]
    sum_mean = sum(sums) / n
    sum_std = (sum((x - sum_mean) ** 2 for x in sums) / max(1, n - 1)) ** 0.5

    gaps = []
    for s in all_sestinas:
        ss = sorted(s)
        for i in range(5):
            gaps.append(ss[i+1] - ss[i])
    gap_mean = sum(gaps) / len(gaps)
    gap_max = max(gaps)

    decades_per = [len(set((x - 1) // 10 for x in s)) for s in all_sestinas]
    decade_mean = sum(decades_per) / n

    parities = [sum(1 for x in s if x % 2 == 0) for s in all_sestinas]
    parity_mean = sum(parities) / n

    highs = [sum(1 for x in s if x > 60) for s in all_sestinas]
    lows = [sum(1 for x in s if x < 30) for s in all_sestinas]

    return {
        "n_samples": n,
        "sum_mean": round(sum_mean, 2),
        "sum_std": round(sum_std, 2),
        "gap_mean": round(gap_mean, 2),
        "gap_max": gap_max,
        "decade_mean": round(decade_mean, 2),
        "parity_mean": round(parity_mean, 2),
        "high_mean": round(sum(highs) / n, 2),
        "low_mean": round(sum(lows) / n, 2),
    }


def score_against_fingerprint(combo, fp):
    s = sorted(combo)
    score = 0.0

    total = sum(s)
    score -= abs(total - fp["sum_mean"]) * 0.5

    gaps = [s[i+1] - s[i] for i in range(5)]
    avg_gap = sum(gaps) / 5.0
    score -= abs(avg_gap - fp["gap_mean"]) * 2.0

    max_gap = max(gaps)
    if max_gap > fp["gap_max"]:
        score -= (max_gap - fp["gap_max"]) * 3.0

    decades = len(set((x - 1) // 10 for x in s))
    score -= abs(decades - fp["decade_mean"]) * 5.0

    pari = sum(1 for x in s if x % 2 == 0)
    score -= abs(pari - fp["parity_mean"]) * 3.0

    high = sum(1 for x in s if x > 60)
    score -= abs(high - fp["high_mean"]) * 2.0

    low = sum(1 for x in s if x < 30)
    score -= abs(low - fp["low_mean"]) * 2.0

    return score


def generate_sestinas(history, fp, n_sestinas=2):
    rng = random.Random(42)
    pool = list(range(1, 91))

    candidates = []
    seen = set()
    target = 500_000
    attempts = 0
    max_attempts = target * 3

    while len(candidates) < target and attempts < max_attempts:
        attempts += 1
        try:
            combo = tuple(sorted(rng.sample(pool, 6)))
        except ValueError:
            break
        if combo in seen:
            continue
        seen.add(combo)
        if SUM_MIN <= sum(combo) <= SUM_MAX:
            candidates.append(combo)

    scored = [(c, score_against_fingerprint(c, fp)) for c in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    selected = []
    selected_sets = []
    for combo, score in scored:
        if len(selected) >= n_sestinas:
            break
        combo_set = set(combo)
        max_overlap = max((len(combo_set & s) for s in selected_sets), default=0)
        if max_overlap <= 2:
            selected.append((combo, score))
            selected_sets.append(combo_set)

    return selected


def build_database(sestinas, history, next_concorso):
    """Genera vinci_database.json nel formato atteso dalla dashboard."""
    now = datetime.now()

    last = history[-1] if history else {}
    last_concorso = last.get("concorso", "N/A")
    last_numeri = last.get("numeri", [])
    last_data = last.get("data", "N/A")

    try:
        dt = datetime.strptime(last_data, "%d/%m/%Y")
        next_date = (dt + timedelta(days=1)).strftime("%d/%m/%Y")
    except Exception:
        next_date = (now + timedelta(days=1)).strftime("%d/%m/%Y")

    va = valore_attuale_rendita(RENDITA_MENSILE)

    # titan_predictions = le sestine generate
    titan_predictions = []
    for i, (combo, score) in enumerate(sestinas, 1):
        s = list(combo)
        ssum = sum(s)
        z = round((ssum - 270.13) / 65.28, 2)  # media e std dal fingerprint
        titan_predictions.append({
            "id": f"SESTINA {i}",
            "numbers": s,
            "sum": ssum,
            "z_score": z,
            "confidence": 20.0,
            "signature": "—",
        })

    payload = {
        "version": "5.0",
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "rendita_mensile": RENDITA_MENSILE,
        "valore_attuale_rendita": round(va, 2),
        "next_contest": {
            "number": next_concorso,
            "date": next_date,
            "jackpot": RENDITA_MENSILE,
        },
        "last_draw": {
            "contest_number": last_concorso,
            "date": last_data,
            "numbers": last_numeri,
            "jolly": "—",
            "superstar": "—",
        },
        "risk": {
            "status": "🟢 SISTEMA ATTIVO",
            "ev": None,
            "level": "PLANNER",
            "advice": f"Gioca {len(sestinas)} sestine",
        },
        "budget_mode": {
            "mode": "PLANNER",
            "emoji": "🎯",
            "n_sestinas": len(sestinas),
            "cost_eur": len(sestinas) * 2.0,
            "message": f"{len(sestinas)} sestine · €{len(sestinas)*2.0:.2f}",
        },
        "sestinas": [
            {"id": i+1, "profilo": "PLANNER", "numeri": list(c), "somma": sum(c)}
            for i, (c, _) in enumerate(sestinas)
        ],
        "titan_predictions": titan_predictions,
        "dodeca_pool": sorted(list(set(n for c, _ in sestinas for n in c))),
        "vortex": {},
    }
    return payload


def build_telegram_report(sestinas, fp, next_concorso):
    lines = []
    lines.append("🌅 <b>AURORA PLANNER</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"🎯 <b>PROSSIMO: Concorso N° {next_concorso}</b>")
    lines.append("")
    lines.append(f"📊 <b>Forma delle {fp['n_samples']} sestine reali:</b>")
    lines.append(f"   • Somma media: {fp['sum_mean']}")
    lines.append(f"   • Gap medio: {fp['gap_mean']}")
    lines.append(f"   • Parità media: {fp['parity_mean']}")
    lines.append("")
    lines.append(f"🎲 <b>{len(sestinas)} SESTINE DA GIOCARE</b>")
    lines.append("")
    for i, (combo, score) in enumerate(sestinas, 1):
        s = list(combo)
        ssum = sum(s)
        ns = " · ".join(str(n).zfill(2) for n in s)
        lines.append(f"   {i}. <code>[{ns}]</code>")
        lines.append(f"      Somma {ssum}")
        lines.append("")
    lines.append("🌅 <i>Aurora Planner — Super Win for Life</i>")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    args = parser.parse_args()

    print("=" * 60)
    print("AURORA PLANNER")
    print("=" * 60)

    history = load_history()
    print(f"[*] Storico: {len(history)} estrazioni")

    if len(history) < 5:
        print("[!] Storico insufficiente.")
        sys.exit(1)

    last = history[-1]
    last_concorso = last.get("concorso", "?")
    next_concorso = last_concorso + 1 if isinstance(last_concorso, int) else "?"

    print(f"[*] Ultima: concorso {last_concorso} del {last.get('data', '?')}")
    print(f"[*] Prossima: concorso {next_concorso}")

    fp = extract_real_fingerprint(history)
    if not fp:
        sys.exit(1)

    print(f"\n[*] Forma delle {fp['n_samples']} sestine reali:")
    print(f"    Somma:  {fp['sum_mean']}")
    print(f"    Gap:    {fp['gap_mean']}")

    print(f"\n[*] Genero {args.n} sestine...")
    sestinas = generate_sestinas(history, fp, n_sestinas=args.n)

    print()
    for i, (combo, score) in enumerate(sestinas, 1):
        s = list(combo)
        ssum = sum(s)
        print(f"  {i}. {s} (somma {ssum})")

    # Salva planner.json
    output = {
        "next_concorso": next_concorso,
        "fingerprint": fp,
        "sestinas": [list(c) for c, _ in sestinas],
    }
    save_json("vinci_planner.json", output)

    # Salva database.json per la dashboard
    db = build_database(sestinas, history, next_concorso)
    save_json(DATABASE_FILE, db)

    # Telegram
    print("\n[*] Invio Telegram...")
    report = build_telegram_report(sestinas, fp, next_concorso)
    send_telegram_message(report)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
