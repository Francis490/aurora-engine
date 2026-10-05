"""
analyze_history.py
Analisi pattern di vinci_history.json.

Genera:
- pattern_report.json (dati strutturati, committato su repo)
- Messaggio Telegram riassuntivo

Eseguito automaticamente dopo "Aurora Manual Update".

FIX (2026-10-05):
- load_history e save_json ora usano core_io.py (modulo condiviso).
- Rimosso import json diretto (non più necessario).
"""
import os
import urllib.parse
import urllib.request
from collections import Counter
from itertools import combinations
from statistics import mean, stdev

from core_io import load_json, save_json


HISTORY_FILE = "vinci_history.json"
PATTERN_FILE = "pattern_report.json"


def load_history():
    data = load_json(HISTORY_FILE, [])
    return data if isinstance(data, list) else []


def send_telegram(text):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        print("[!] Token mancanti, skip Telegram.")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    if len(text) > 4000:
        text = text[:3997] + "..."
    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"[+] Telegram pattern report: {response.status}")
            return True
    except Exception as e:
        print(f"[!] Errore Telegram: {e}")
        return False


def main():
    history = load_history()
    n_draws = len(history)
    all_nums = []
    for d in history:
        all_nums.extend(d.get("numeri", []))

    # === FREQUENZE ===
    freq = Counter(all_nums)
    expected = len(all_nums) / 90

    # Top 15 caldi e freddi
    sorted_freq = sorted(range(1, 91), key=lambda n: freq[n], reverse=True)
    hot = [(n, freq[n]) for n in sorted_freq[:15]]
    cold = [(n, freq[n]) for n in sorted_freq[-15:]]

    # === COPPIE ===
    pair_counter = Counter()
    for d in history:
        nums = sorted(d.get("numeri", []))
        for pair in combinations(nums, 2):
            pair_counter[pair] += 1
    top_pairs = [(list(p), c) for p, c in pair_counter.most_common(10) if c >= 2]

    # === TERZINE ===
    triple_counter = Counter()
    for d in history:
        nums = sorted(d.get("numeri", []))
        for t in combinations(nums, 3):
            triple_counter[t] += 1
    top_triples = [(list(t), c) for t, c in triple_counter.most_common(10) if c >= 2]

    # === QUADRUPLE ===
    quad_counter = Counter()
    for d in history:
        nums = sorted(d.get("numeri", []))
        for q in combinations(nums, 4):
            quad_counter[q] += 1
    top_quads = [(list(q), c) for q, c in quad_counter.most_common(5) if c >= 2]

    # === SOMME ===
    sums = [sum(d.get("numeri", [])) for d in history if len(d.get("numeri", [])) == 8]
    sum_stats = {
        "mean": round(mean(sums), 1) if sums else 0,
        "std": round(stdev(sums), 1) if len(sums) > 1 else 0,
        "min": min(sums) if sums else 0,
        "max": max(sums) if sums else 0,
    }

    # === PARITÀ ===
    parity = Counter()
    for d in history:
        nums = d.get("numeri", [])
        n_pari = sum(1 for n in nums if n % 2 == 0)
        parity[n_pari] += 1

    # === DECADI ===
    decade_count = Counter()
    for n in all_nums:
        if 1 <= n <= 90:
            decade_count[(n-1)//10] += 1

    # === SALVA REPORT ===
    report = {
        "n_draws": n_draws,
        "n_numbers": len(all_nums),
        "expected_per_number": round(expected, 2),
        "hot_numbers": [{"num": n, "count": c} for n, c in hot],
        "cold_numbers": [{"num": n, "count": c} for n, c in cold],
        "top_pairs": [{"pair": p, "count": c} for p, c in top_pairs],
        "top_triples": [{"triple": t, "count": c} for t, c in top_triples],
        "top_quadruples": [{"quad": q, "count": c} for q, c in top_quads],
        "sum_stats": sum_stats,
        "parity_distribution": {str(k): v for k, v in sorted(parity.items())},
        "decade_distribution": {str(i): decade_count[i] for i in range(9)},
    }

    save_json(PATTERN_FILE, report)

    # === TELEGRAM ===
    lines = []
    lines.append(f"📊 <b>PATTERN ANALYSIS</b>")
    lines.append(f"<i>{n_draws} concorsi · {len(all_nums)} numeri</i>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"🔥 <b>TOP 15 CALDI</b> (atteso {expected:.1f}):")
    for n, c in hot:
        lines.append(f"   {n:2} → {c}x")
    lines.append("")
    lines.append(f"❄️ <b>TOP 15 FREDDI</b>:")
    for n, c in cold:
        lines.append(f"   {n:2} → {c}x")
    lines.append("")

    if top_triples:
        lines.append(f"🎯 <b>TERZINE RICORRENTI</b>:")
        for t, c in top_triples[:5]:
            lines.append(f"   {t[0]:2} · {t[1]:2} · {t[2]:2} → {c}x")
        lines.append("")

    if top_quads:
        lines.append(f"🎲 <b>QUADRUPLE RICORRENTI</b>:")
        for q, c in top_quads[:5]:
            lines.append(f"   {q[0]:2} · {q[1]:2} · {q[2]:2} · {q[3]:2} → {c}x")
        lines.append("")

    if top_pairs:
        lines.append(f"👥 <b>COPPIE TOP 10</b>:")
        for p, c in top_pairs[:10]:
            lines.append(f"   {p[0]:2} + {p[1]:2} → {c}x")
        lines.append("")

    lines.append(f"📈 <b>SOMME</b>:")
    lines.append(f"   Media {sum_stats['mean']} · σ {sum_stats['std']}")
    lines.append(f"   Min {sum_stats['min']} · Max {sum_stats['max']}")
    lines.append("")

    lines.append(f"⚖️ <b>PARITÀ</b> (pari su 8):")
    for k in sorted(parity.keys()):
        pct = parity[k] / n_draws * 100
        lines.append(f"   {k} pari: {parity[k]} ({pct:.1f}%)")

    text = "\n".join(lines)
    send_telegram(text)


if __name__ == "__main__":
    main()
