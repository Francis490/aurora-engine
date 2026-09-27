"""
vinci_vita_planner.py
Genera 2 sestine con la forma esatta delle estrazioni reali.
"""
import json
import os
import sys
import random
import argparse
import itertools


HISTORY_FILE = "vinci_history.json"
SUM_MIN = 240
SUM_MAX = 310
DEFAULT_N = 2


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
    print(f"    Somma:  {fp['sum_mean']} (sigma {fp['sum_std']})")
    print(f"    Gap:    {fp['gap_mean']} (max {fp['gap_max']})")
    print(f"    Decadi: {fp['decade_mean']}")
    print(f"    Parita: {fp['parity_mean']}")
    print(f"    Alti:   {fp['high_mean']}")
    print(f"    Bassi:  {fp['low_mean']}")

    print(f"\n[*] Genero {args.n} sestine...")
    sestinas = generate_sestinas(history, fp, n_sestinas=args.n)

    print()
    for i, (combo, score) in enumerate(sestinas, 1):
        s = list(combo)
        ssum = sum(s)
        gaps = [sorted(s)[j+1] - sorted(s)[j] for j in range(5)]
        avg_gap = sum(gaps) / 5.0
        decades = len(set((x - 1) // 10 for x in s))
        pari = sum(1 for x in s if x % 2 == 0)
        high = sum(1 for x in s if x > 60)
        low = sum(1 for x in s if x < 30)
        print(f"  {i}. {s}")
        print(f"     Somma {ssum} | Gap {avg_gap:.1f} | Decadi {decades} | "
              f"Pari {pari} | Alti {high} | Bassi {low}")

    output = {
        "next_concorso": next_concorso,
        "fingerprint": fp,
        "sestinas": [list(c) for c, _ in sestinas],
    }
    save_json("vinci_planner.json", output)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
