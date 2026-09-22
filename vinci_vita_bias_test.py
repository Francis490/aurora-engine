"""
vinci_vita_bias_test.py
AURORA ENGINE — Analisi bias statistici.

Rileva:
- Uniformità frequenze (chi²)
- Hot numbers (z-score > 2)
- Cold numbers (z-score < -2)
- Autocorrelazione somme
- Pesi suggeriti per profili A/B/C

Uso:
    from vinci_vita_bias_test import quick_bias_check
    bias = quick_bias_check(history)
"""
import math
from collections import defaultdict
from typing import Dict, List


CHI2_CRIT_05_89 = 113.0


def quick_bias_check(history: List[dict], verbose: bool = False) -> Dict:
    n = len(history)
    if n < 20:
        return {
            "status": "insufficient_data",
            "n": n,
            "health": "🟡 Dati insufficienti (<20 estrazioni)",
            "profile_weights": {"A_trend": 1.0, "B_contrarian": 1.0, "C_coverage": 1.0},
        }

    freq = defaultdict(int)
    for d in history:
        for num in d.get("numeri", []):
            freq[num] += 1

    expected = n * 8 / 90
    chi2 = sum((freq.get(k, 0) - expected) ** 2 / expected for k in range(1, 91))
    is_uniform = chi2 < CHI2_CRIT_05_89

    std_dev = math.sqrt(n * (8/90) * (1 - 8/90))
    hot = []
    cold = []
    for num in range(1, 91):
        obs = freq.get(num, 0)
        z = (obs - expected) / max(0.001, std_dev)
        if z > 2.0:
            hot.append((num, round(z, 2)))
        if z < -2.0:
            cold.append((num, round(z, 2)))

    hot.sort(key=lambda x: x[1], reverse=True)
    cold.sort(key=lambda x: x[1])

    has_hot_bias = len(hot) > 5
    has_cold_bias = len(cold) > 5

    sums = [sum(d.get("numeri", [])) for d in history]
    mean = sum(sums) / n
    cov = sum((sums[i] - mean) * (sums[i+1] - mean) for i in range(n-1)) / (n-1)
    var = sum((s - mean) ** 2 for s in sums) / n
    r1 = cov / var if var > 0 else 0
    has_autocorr = abs(r1) > 2 / math.sqrt(n)

    weights = {"A_trend": 1.0, "B_contrarian": 1.0, "C_coverage": 1.0}
    if has_hot_bias:
        weights["A_trend"] = 1.0 + min(1.0, len(hot) / 10.0)
    if has_cold_bias:
        weights["B_contrarian"] = 1.0 + min(1.0, len(cold) / 10.0)
    if has_autocorr:
        weights["C_coverage"] = 0.7

    issues = []
    if not is_uniform:
        issues.append("uniformità deviata")
    if has_hot_bias:
        issues.append(f"{len(hot)} hot anomali")
    if has_cold_bias:
        issues.append(f"{len(cold)} cold anomali")
    if has_autocorr:
        issues.append(f"autocorr r1={r1:.3f}")

    if not issues:
        health = "🟢 GIOCO EQUO — Nessun bias sfruttabile"
    elif len(issues) <= 1:
        health = f"🟡 Bias lieve: {', '.join(issues)}"
    else:
        health = f"🔴 Bias multipli: {', '.join(issues)}"

    if verbose:
        print(f"[*] Bias: chi²={chi2:.2f}, hot={len(hot)}, cold={len(cold)}, r1={r1:.3f}")
        print(f"    {health}")

    return {
        "status": "analyzed",
        "n": n,
        "chi2": round(chi2, 2),
        "is_uniform": is_uniform,
        "has_hot_bias": has_hot_bias,
        "has_cold_bias": has_cold_bias,
        "has_autocorr": has_autocorr,
        "hot_numbers": [n for n, _ in hot[:10]],
        "cold_numbers": [n for n, _ in cold[:10]],
        "r1": round(r1, 4),
        "profile_weights": weights,
        "health": health,
    }


if __name__ == "__main__":
    import json, os
    if os.path.exists("vinci_history.json"):
        with open("vinci_history.json", "r", encoding="utf-8") as f:
            history = json.load(f)
        result = quick_bias_check(history, verbose=True)
        print()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("[!] vinci_history.json non trovato")
