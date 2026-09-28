"""
vinci_vita_backtest.py
AURORA ENGINE v2 — Backtest walk-forward.

FIX (2026-09-29):
- Import corretto: AuroraPortfolioV3 (era PortfolioOptimizer, non esistente)
- bot_portfolio() ora usa realmente il generatore del bot

Uso:
    python vinci_vita_backtest.py
    python vinci_vita_backtest.py --min-history 20 --test-size 10
"""
import json
import os
import sys
import random
import argparse
from math import comb
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


HISTORY_FILE = "vinci_history.json"

DEFAULT_MIN_HISTORY = 20
DEFAULT_TEST_SIZE = 10
DEFAULT_N_SESTINAS = 2
DEFAULT_SEED = 42
DEFAULT_N_RANDOM_TRIALS = 100


def load_history(filepath: str = HISTORY_FILE) -> List[dict]:
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [d for d in data
                if isinstance(d.get("numeri"), list)
                and len(d["numeri"]) == 8
                and all(isinstance(n, int) and 1 <= n <= 90 for n in d["numeri"])]
    except Exception as e:
        print(f"[!] Errore lettura {filepath}: {e}")
        return []


def count_hits(sestina: List[int], estratti: List[int]) -> int:
    return len(set(sestina) & set(estratti))


def random_sestina(rng: random.Random) -> List[int]:
    return sorted(rng.sample(range(1, 91), 6))


def random_portfolio(rng: random.Random, n: int) -> List[List[int]]:
    return [random_sestina(rng) for _ in range(n)]


def top_hot_sestina(history: List[dict]) -> List[int]:
    freq = defaultdict(int)
    for d in history:
        for n in d["numeri"]:
            freq[n] += 1
    top6 = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:6]
    return sorted([n for n, _ in top6])


def top_cold_sestina(history: List[dict]) -> List[int]:
    freq = defaultdict(int)
    for d in history:
        for n in d["numeri"]:
            freq[n] += 1
    eligible = [(n, f) for n, f in freq.items() if f > 0]
    if len(eligible) < 6:
        eligible = list(freq.items())
    cold6 = sorted(eligible, key=lambda x: x[1])[:6]
    return sorted([n for n, _ in cold6])


# ==========================================
# BOT STRATEGY
# ==========================================
def bot_portfolio(history: List[dict], n_sestinas: int,
                  verbose: bool = False) -> List[List[int]]:
    """
    Genera N sestine con AuroraPortfolioV3 + fingerprint engine.
    """
    try:
        from vinci_vita_portfolio_v3 import AuroraPortfolioV3
        from vinci_vita_fingerprints import AuroraFingerprintEngine

        if not history:
            return []

        p3 = AuroraPortfolioV3(history)
        try:
            fp_eng = AuroraFingerprintEngine(history)
        except Exception:
            fp_eng = None

        pool = list(range(1, 91))
        results = []
        for i in range(n_sestinas):
            r = p3.build_single(pool, fp_engine=fp_eng, verbose=False,
                                seed=DEFAULT_SEED + i)
            if r:
                results.append(r[0]["numeri"])

        if not results:
            if verbose:
                print("  [!] Bot: nessuna sestina generata, fallback random")
            rng = random.Random(DEFAULT_SEED)
            return random_portfolio(rng, n_sestinas)

        return results

    except ImportError as e:
        if verbose:
            print(f"  [!] Moduli v2 non disponibili ({e}), fallback random")
        rng = random.Random(DEFAULT_SEED)
        return random_portfolio(rng, n_sestinas)


# ==========================================
# BACKTEST WALK-FORWARD
# ==========================================
def backtest_walk_forward(history: List[dict],
                          min_history: int = DEFAULT_MIN_HISTORY,
                          test_size: int = DEFAULT_TEST_SIZE,
                          n_sestinas: int = DEFAULT_N_SESTINAS,
                          seed: int = DEFAULT_SEED,
                          verbose: bool = True) -> Dict:
    if len(history) < min_history + test_size:
        print(f"[!] Storico insufficiente: {len(history)} "
              f"(servono almeno {min_history + test_size})")
        return {}

    test_start = len(history) - test_size
    test_end = len(history)

    if verbose:
        print(f"=== BACKTEST WALK-FORWARD ===")
        print(f"[*] Storico totale: {len(history)}")
        print(f"[*] Training minimo: {min_history}")
        print(f"[*] Estrazioni di test: {test_size}")
        print(f"[*] Sestine per test: {n_sestinas}")
        print(f"[*] Seed: {seed}")
        print()

    strategies = {"bot": [], "random": [], "hot": [], "cold": [],
                  "baseline_theoretical": []}
    rng = random.Random(seed)

    for i in range(test_start, test_end):
        train = history[:i]
        test_draw = history[i]
        estratti = test_draw["numeri"]
        concorso = test_draw.get("concorso", i + 1)

        # BOT
        bot_sestinas = bot_portfolio(train, n_sestinas, verbose=False)
        bot_hits = [count_hits(s, estratti) for s in bot_sestinas]
        bot_best = max(bot_hits) if bot_hits else 0
        strategies["bot"].append(bot_best)

        # RANDOM
        random_bests = []
        for _ in range(DEFAULT_N_RANDOM_TRIALS):
            r_sestinas = random_portfolio(rng, n_sestinas)
            r_hits = [count_hits(s, estratti) for s in r_sestinas]
            random_bests.append(max(r_hits) if r_hits else 0)
        strategies["random"].append(sum(random_bests) / len(random_bests))

        # HOT
        strategies["hot"].append(count_hits(top_hot_sestina(train), estratti))

        # COLD
        strategies["cold"].append(count_hits(top_cold_sestina(train), estratti))

        # Baseline teorica
        strategies["baseline_theoretical"].append(6 * 8 / 90)

        if verbose:
            print(f"[{i - test_start + 1}/{test_size}] "
                  f"Concorso {concorso}: "
                  f"bot={bot_best} random={strategies['random'][-1]:.2f} "
                  f"hot={strategies['hot'][-1]} cold={strategies['cold'][-1]}")

    return {
        "strategies": strategies,
        "test_size": test_size,
        "n_sestinas": n_sestinas,
        "min_history": min_history,
        "seed": seed,
    }


def analyze_results(results: Dict) -> Dict:
    if not results:
        return {}
    strategies = results["strategies"]
    analysis = {}
    for name, hits in strategies.items():
        if not hits:
            continue
        dist = defaultdict(int)
        for h in hits:
            dist[int(round(h))] += 1
        total = sum(hits)
        mean = total / len(hits)
        hit_2plus = sum(1 for h in hits if h >= 2)
        hit_3plus = sum(1 for h in hits if h >= 3)
        hit_4plus = sum(1 for h in hits if h >= 4)
        analysis[name] = {
            "n": len(hits),
            "mean_hits": round(mean, 4),
            "distribution": dict(dist),
            "hit_2plus": hit_2plus,
            "hit_2plus_rate": round(hit_2plus / len(hits) * 100, 2),
            "hit_3plus": hit_3plus,
            "hit_3plus_rate": round(hit_3plus / len(hits) * 100, 2),
            "hit_4plus": hit_4plus,
            "hit_4plus_rate": round(hit_4plus / len(hits) * 100, 2),
        }
    return analysis


def binomial_test(k: int, n: int, p: float) -> float:
    if n == 0:
        return 1.0
    p_less = sum(comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k + 1))
    p_value = 2 * min(p_less, 1 - p_less + comb(n, k) * (p ** k) * ((1 - p) ** (n - k)))
    return min(1.0, p_value)


def format_backtest_report(results: Dict, analysis: Dict) -> str:
    if not results or not analysis:
        return "❌ Backtest non eseguito."
    lines = []
    lines.append("=" * 70)
    lines.append("AURORA ENGINE v2 — BACKTEST WALK-FORWARD")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Estrazioni di test:   {results['test_size']}")
    lines.append(f"Sestine per test:     {results['n_sestinas']}")
    lines.append(f"Training minimo:      {results['min_history']}")
    lines.append(f"Seed:                 {results['seed']}")
    lines.append("")
    lines.append("PERFORMANCE COMPARATA")
    lines.append("-" * 70)
    lines.append(f"{'Strategia':<25} {'Media':>8} {'2+%':>8} {'3+%':>8} {'4+%':>8}")
    lines.append("-" * 70)
    order = ["bot", "random", "hot", "cold", "baseline_theoretical"]
    for name in order:
        if name not in analysis:
            continue
        a = analysis[name]
        label = {"bot": "Bot (Aurora v2)", "random": "Random (baseline)",
                 "hot": "Hot (top freq)", "cold": "Cold (top rari)",
                 "baseline_theoretical": "Teorica (ipergeom.)"}.get(name, name)
        lines.append(f"{label:<25} {a['mean_hits']:>8.4f} "
                     f"{a['hit_2plus_rate']:>7.2f}% "
                     f"{a['hit_3plus_rate']:>7.2f}% "
                     f"{a['hit_4plus_rate']:>7.2f}%")
    lines.append("")
    if "bot" in analysis and "random" in analysis:
        bot = analysis["bot"]
        rand = analysis["random"]
        lines.append("CONFRONTO BOT vs RANDOM")
        lines.append("-" * 70)
        delta = bot["mean_hits"] - rand["mean_hits"]
        delta_pct = (delta / rand["mean_hits"] * 100) if rand["mean_hits"] > 0 else 0
        lines.append(f"Delta media hits:  {delta:+.4f} ({delta_pct:+.2f}%)")
        lines.append("")
        if delta > 0:
            lines.append("✅ Il bot batte la baseline random")
        elif delta < 0:
            lines.append("⚠️  Il bot è sotto la baseline random")
        else:
            lines.append("⚪ Bot e random sono equivalenti")
        lines.append("")
    lines.append("INTERPRETAZIONE")
    lines.append("-" * 70)
    lines.append("Nota: con campioni piccoli (< 100 test), le differenze")
    lines.append("potrebbero non essere statisticamente significative.")
    lines.append("")
    if "bot" in analysis and "baseline_theoretical" in analysis:
        bot_mean = analysis["bot"]["mean_hits"]
        theo_mean = analysis["baseline_theoretical"]["mean_hits"]
        if bot_mean > theo_mean * 1.05:
            lines.append("✅ Bot sopra la media teorica (+5%): segnale positivo")
        elif bot_mean > theo_mean:
            lines.append("⚪ Bot leggermente sopra la media teorica: marginale")
        else:
            lines.append("⚠️  Bot sotto la media teorica")
    lines.append("")
    lines.append("=" * 70)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-history", type=int, default=DEFAULT_MIN_HISTORY)
    parser.add_argument("--test-size", type=int, default=DEFAULT_TEST_SIZE)
    parser.add_argument("--n-sestinas", type=int, default=DEFAULT_N_SESTINAS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    history = load_history()
    print(f"[*] Caricate {len(history)} estrazioni da {HISTORY_FILE}")

    if not history:
        print("[!] Storico vuoto. Esegui prima fetch_vinci_draw.py")
        sys.exit(1)

    results = backtest_walk_forward(
        history, min_history=args.min_history, test_size=args.test_size,
        n_sestinas=args.n_sestinas, seed=args.seed, verbose=not args.quiet,
    )
    if not results:
        print("[!] Backtest non eseguito.")
        sys.exit(1)

    analysis = analyze_results(results)
    report = format_backtest_report(results, analysis)
    print()
    print(report)

    try:
        with open("backtest_report.txt", "w", encoding="utf-8") as f:
            f.write(report)
        print("[+] Report salvato in backtest_report.txt")
        with open("backtest_results.json", "w", encoding="utf-8") as f:
            json.dump({"results": results, "analysis": analysis}, f,
                      indent=2, ensure_ascii=False)
        print("[+] Risultati salvati in backtest_results.json")
    except Exception as e:
        print(f"[!] Errore salvataggio: {e}")


if __name__ == "__main__":
    main()
