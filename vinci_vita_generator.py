"""
vinci_vita_generator.py
AURORA ENGINE — Generatore sestine Super Win for Life.

Genera sestine statisticamente INDISTINGUIBILI dalle estrazioni reali
di Super Win for Life (8 numeri estratti da 90, 6 giocati).

Non predice. Riproduce la distribuzione reale.
"""
import json
import os
import math
import itertools
from typing import List, Tuple, Dict, Optional


HISTORY_FILE = "vinci_history.json"

# Range hard per la somma
SUM_HARD_MIN = 240
SUM_HARD_MAX = 310

N_ESTRATTI = 8
N_GIOCATI = 6
N_TOTALI = 90


# ==========================================
# FINGERPRINT ANALYSIS
# ==========================================
def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def extract_fingerprints(history: list) -> dict:
    if not history:
        return default_fingerprints()

    all_sestinas = []
    for draw in history:
        nums = draw.get("numeri", [])
        if len(nums) != 8:
            continue
        for combo in itertools.combinations(nums, 6):
            all_sestinas.append(list(combo))

    if not all_sestinas:
        return default_fingerprints()

    n = len(all_sestinas)
    sums = [sum(s) for s in all_sestinas]
    sum_mean = sum(sums) / n
    sum_std = math.sqrt(sum((x - sum_mean) ** 2 for x in sums) / max(1, n - 1))

    parity_counts = {i: 0 for i in range(7)}
    for s in all_sestinas:
        n_pari = sum(1 for x in s if x % 2 == 0)
        parity_counts[n_pari] += 1

    decade_counts = [0] * 9
    for s in all_sestinas:
        for x in s:
            decade_counts[min(8, (x - 1) // 10)] += 1

    firsts = [min(s) for s in all_sestinas]
    lasts = [max(s) for s in all_sestinas]

    all_gaps = []
    for s in all_sestinas:
        ss = sorted(s)
        for i in range(len(ss) - 1):
            all_gaps.append(ss[i + 1] - ss[i])
    max_gap = max(all_gaps) if all_gaps else 40
    avg_gap = sum(all_gaps) / len(all_gaps) if all_gaps else 15

    consec_pairs = []
    for s in all_sestinas:
        ss = sorted(s)
        pairs = sum(1 for i in range(len(ss) - 1) if ss[i + 1] - ss[i] == 1)
        consec_pairs.append(pairs)

    low_counts = [sum(1 for x in s if x < 30) for s in all_sestinas]
    high_counts = [sum(1 for x in s if x > 60) for s in all_sestinas]

    ld_sums = [sum(x % 10 for x in s) for s in all_sestinas]
    ld_mean = sum(ld_sums) / n
    ld_std = math.sqrt(sum((x - ld_mean) ** 2 for x in ld_sums) / max(1, n - 1))

    mod5 = [0] * 5
    for s in all_sestinas:
        for x in s:
            mod5[x % 5] += 1

    spreads = [max(s) - min(s) for s in all_sestinas]

    return {
        "n_samples": n,
        "n_draws": len(history),
        "sum_mean": round(sum_mean, 2),
        "sum_std": round(sum_std, 2),
        "sum_min": min(sums),
        "sum_max": max(sums),
        "parity_distribution": parity_counts,
        "decade_distribution": decade_counts,
        "first_min": min(firsts),
        "first_max": max(firsts),
        "first_mean": round(sum(firsts) / n, 2),
        "last_min": min(lasts),
        "last_max": max(lasts),
        "last_mean": round(sum(lasts) / n, 2),
        "gap_max": max_gap,
        "gap_avg": round(avg_gap, 2),
        "consec_pairs_avg": round(sum(consec_pairs) / n, 2),
        "low_min": min(low_counts),
        "low_max": max(low_counts),
        "high_min": min(high_counts),
        "high_max": max(high_counts),
        "last_digit_mean": round(ld_mean, 2),
        "last_digit_std": round(ld_std, 2),
        "mod5_distribution": mod5,
        "spread_min": min(spreads),
        "spread_max": max(spreads),
    }


def default_fingerprints() -> dict:
    return {
        "n_samples": 0, "n_draws": 0,
        "sum_mean": 273.0, "sum_std": 43.5,
        "sum_min": 144, "sum_max": 405,
        "parity_distribution": {0: 0, 1: 0, 2: 30, 3: 90, 4: 30, 5: 0, 6: 0},
        "decade_distribution": [100] * 9,
        "first_min": 1, "first_max": 25, "first_mean": 10,
        "last_min": 60, "last_max": 90, "last_mean": 78,
        "gap_max": 30, "gap_avg": 15,
        "consec_pairs_avg": 0.5,
        "low_min": 1, "low_max": 4,
        "high_min": 0, "high_max": 4,
        "last_digit_mean": 27, "last_digit_std": 6,
        "mod5_distribution": [200] * 5,
        "spread_min": 40, "spread_max": 88,
    }


# ==========================================
# ANTI-CROWD
# ==========================================
def anti_crowd_weight(number: int) -> float:
    if 1 <= number <= 31:
        return 0.35
    elif 32 <= number <= 45:
        return 0.70
    elif 46 <= number <= 60:
        return 1.20
    elif 61 <= number <= 90:
        return 1.55
    return 1.0


def has_visual_pattern(sestina: list) -> bool:
    s = sorted(sestina)
    consec = sum(1 for i in range(len(s) - 1) if s[i + 1] - s[i] == 1)
    if consec >= 2:
        return True
    decadi = set((n - 1) // 10 for n in s)
    if len(decadi) <= 2:
        return True
    if all(n % 5 == 0 for n in s):
        return True
    if all(n % 10 == 0 for n in s):
        return True
    return False


def anti_crowd_score(sestina: list) -> float:
    weight_sum = sum(anti_crowd_weight(n) for n in sestina)
    pattern_penalty = 0.5 if has_visual_pattern(sestina) else 1.0
    return weight_sum * pattern_penalty


# ==========================================
# VALIDATOR
# ==========================================
def validate_sestina(sestina: list, fp: dict) -> Tuple[bool, float, dict]:
    if len(sestina) != 6:
        return False, 0.0, {}

    s = sorted(sestina)
    checks = {}

    total = sum(s)
    sum_lo = max(SUM_HARD_MIN, fp["sum_mean"] - 1.5 * fp["sum_std"])
    sum_hi = min(SUM_HARD_MAX, fp["sum_mean"] + 1.5 * fp["sum_std"])
    checks["sum"] = sum_lo <= total <= sum_hi

    n_pari = sum(1 for x in s if x % 2 == 0)
    checks["parity"] = 2 <= n_pari <= 4

    decades = [0] * 9
    for x in s:
        decades[min(8, (x - 1) // 10)] += 1
    checks["decades"] = max(decades) <= 2

    checks["first"] = 1 <= s[0] <= 25
    checks["last"] = 55 <= s[-1] <= 90

    max_gap = max(s[i + 1] - s[i] for i in range(5))
    checks["max_gap"] = max_gap <= fp["gap_max"] + 5

    n_consec = sum(1 for i in range(5) if s[i + 1] - s[i] == 1)
    checks["consec"] = n_consec <= 1

    n_low = sum(1 for x in s if x < 30)
    checks["low"] = 1 <= n_low <= 4

    n_high = sum(1 for x in s if x > 60)
    checks["high"] = 0 <= n_high <= 4

    ld_sum = sum(x % 10 for x in s)
    ld_lo = fp["last_digit_mean"] - 2 * fp["last_digit_std"]
    ld_hi = fp["last_digit_mean"] + 2 * fp["last_digit_std"]
    checks["last_digits"] = ld_lo <= ld_sum <= ld_hi

    mods = [x % 5 for x in s]
    checks["mod5"] = len(set(mods)) >= 3

    spread = s[-1] - s[0]
    checks["spread"] = fp["spread_min"] - 5 <= spread <= fp["spread_max"] + 5

    passed = sum(1 for v in checks.values() if v)
    return passed == 12, passed / 12, checks


# ==========================================
# GENERATOR
# ==========================================
def generate_sestinas(pool: list, fp: dict, n_sestinas: int = 2,
                      candidates: int = 5000) -> List[list]:
    if len(pool) < 6:
        return []

    all_combos = list(itertools.combinations(pool, 6))

    valid = []
    for combo in all_combos:
        ok, score, checks = validate_sestina(combo, fp)
        if ok:
            valid.append((combo, score))

    if not valid:
        print(f"[!] Nessuna sestina 12/12. Fallback con somma nel range hard.")
        scored = []
        for combo in all_combos:
            if not (SUM_HARD_MIN <= sum(combo) <= SUM_HARD_MAX):
                continue
            ok, score, _ = validate_sestina(combo, fp)
            scored.append((combo, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        valid = scored[:candidates]
    else:
        print(f"[+] {len(valid)} sestine con 12/12 fingerprint")

    valid.sort(key=lambda x: x[1], reverse=True)

    selected = []
    for combo, score in valid:
        if len(selected) >= n_sestinas:
            break
        combo_set = set(combo)
        max_overlap = 0
        for existing, _ in selected:
            overlap = len(combo_set & set(existing))
            max_overlap = max(max_overlap, overlap)
        if max_overlap <= 2 or not selected:
            selected.append((combo, score))

    return [list(c) for c, _ in selected]


# ==========================================
# API PRINCIPALE
# ==========================================
def generate_aurora_sestinas(history: list, pool: list,
                             n_sestinas: int = 2) -> Tuple[List[list], dict]:
    fp = extract_fingerprints(history)

    print(f"[+] Fingerprint: {fp['n_draws']} estrazioni ({fp['n_samples']} sestine virtuali)")
    print(f"    • Somma: μ={fp['sum_mean']}, σ={fp['sum_std']}")
    print(f"    • Range hard: {SUM_HARD_MIN}-{SUM_HARD_MAX}")

    sestinas = generate_sestinas(pool, fp, n_sestinas)
    return sestinas, fp


if __name__ == "__main__":
    test_history = [
        {"concorso": i, "data": "01/09/2026",
         "numeri": [5, 8, 17, 34, 48, 65, 80, 89]}
        for i in range(1, 21)
    ]
    test_pool = list(range(1, 91))

    sestinas, fp = generate_aurora_sestinas(test_history, test_pool, n_sestinas=3)
    print("\n=== SESTINE GENERATE ===")
    for i, s in enumerate(sestinas, 1):
        print(f"  {i}: {s} (somma {sum(s)})")
