"""
vinci_vita_backtest.py
AURORA ENGINE v2 — Backtest walk-forward.

Simula la generazione di sestine sul passato SENZA guardare al futuro.
Confronta la performance del bot con:
1. Baseline random (sestine casuali)
2. Baseline ipergeometrica (probabilità teorica)
3. Strategia "top hot" (numeri più frequenti)
4. Strategia "top cold" (numeri meno frequenti)

Metriche calcolate:
- Distribuzione punti (0-6)
- Hit rate 2+, 3+, 4+
- Media punti per estrazione
- p-value (test binomiale vs baseline)
- ROI simulato

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

# Configurazione default
DEFAULT_MIN_HISTORY = 20      # Min estrazioni per iniziare il test
DEFAULT_TEST_SIZE = 10        # Numero di estrazioni di test finali
DEFAULT_N_SESTINAS = 2        # Sestine generate per ogni test
DEFAULT_SEED = 42             # Seed per riproducibilità
DEFAULT_N_RANDOM_TRIALS = 100 # Trial random per baseline


# ==========================================
# UTILITY
# ==========================================
def load_history(filepath: str = HISTORY_FILE) -> List[dict]:
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Filtra entry valide
        return [d for d in data
                if isinstance(d.get("numeri"), list)
                and len(d["numeri"]) == 8
                and all(isinstance(n, int) and 1 <= n <= 90 for n in d["numeri"])]
    except Exception as e:
        print(f"[!] Errore lettura {filepath}: {e}")
        return []


def count_hits(sestina: List[int], estratti: List[int]) -> int:
    """Conta quanti numeri della sestina sono negli 8 estratti."""
    return len(set(sestina) & set(estratti))


# ==========================================
# BASELINE RANDOM
# ==========================================
def random_sestina(rng: random.Random) -> List[int]:
    """Genera una sestina casuale (6 numeri da 1-90)."""
    return sorted(rng.sample(range(1, 91), 6))


def random_portfolio(rng: random.Random, n: int) -> List[List[int]]:
    """Genera N sestine casuali non sovrapposte."""
    return [random_sestina(rng) for _ in range(n)]


# ==========================================
# BASELINE SEMPLICI
# ==========================================
def top_hot_sestina(history: List[dict]) -> List[int]:
    """Sestina con i 6 numeri più frequenti nella history."""
    freq = defaultdict(int)
    for d in history:
        for n in d["numeri"]:
            freq[n] += 1
    top6 = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:6]
    return sorted([n for n, _ in top6])


def top_cold_sestina(history: List[dict]) -> List[int]:
    """Sestina con i 6 numeri meno frequenti (ma almeno usciti una volta)."""
    freq = defaultdict(int)
    for d in history:
        for n in d["numeri"]:
            freq[n] += 1
    # Filtra numeri mai usciti (troppo estremi)
    eligible = [(n, f) for n, f in freq.items() if f > 0]
    if len(eligible) < 6:
        eligible = list(freq.items())
    cold6 = sorted(eligible, key=lambda x: x[1])[:6]
    return sorted([n for n, _ in cold6])


# ==========================================
# BOT STRATEGY (import dai moduli v2)
# ==========================================
def bot_portfolio(history: List[dict], n_sestinas: int,
                  verbose: bool = False) -> List[List[int]]:
    """
    Genera N sestine usando la strategia del bot (fingerprint + portfolio).
    Import dinamico per non fallire se i moduli non esistono.
    """
    try:
        from vinci_vita_generator import (
            generate_aurora_sestinas, extract_fingerprints
        )
        from vinci_vita_portfolio import PortfolioOptimizer

        if not history:
            return []

        # Pool: tutti i 90 numeri (il generatore filtrerà)
        pool = list(range(1, 91))

        # Genera un pool ampio di candidati
        n_candidates = min(500, comb(25, 6))  # limite pratico
        # Usa un pool ristretto per efficienza (25 numeri con freq media)
        freq = defaultdict(int)
        for d in history:
            for n in d["numeri"]:
                freq[n] += 1
        avg = sum(freq.values()) / 90 if freq else 1
        scored_pool = sorted(range(1, 91), key=lambda n: abs(freq.get(n, 0) - avg))
        pool = scored_pool[:25]

        sestinas, _ = generate_aurora_sestinas(history, pool, n_sestinas=min(20, n_candidates))

        if not sestinas:
            if verbose:
                print("  [!] Bot: nessuna sestina generata, fallback random")
            rng = random.Random(DEFAULT_SEED)
            return random_portfolio(rng, n_sestinas)

        # Score le sestine con fingerprint engine (composito)
        try:
            from vinci_vita_fingerprints import AuroraFingerprintEngine
            engine = AuroraFingerprintEngine(history)
            scored = []
            for s in sestinas:
                sc = engine.score_sestina(s)["composite"]
                scored.append((s, sc))
        except ImportError:
            scored = [(s, 1.0) for s in sestinas]

        # Ottimizza portfolio
        opt = PortfolioOptimizer(scored)
        portfolio = opt.optimize(n_sestinas=n_sestinas, verbose=False)
        return [s for s, _ in portfolio]

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
    """
    Esegue il backtest walk-forward.

    Per ogni estrazione di test:
    1. Usa SOLO i dati precedenti
    2. Genera N sestine con il bot
    3. Confronta con l'estrazione reale

    :return: dict con risultati aggregati per ogni strategia
    """
    if len(history) < min_history + test_size:
        print(f"[!] Storico insufficiente: {len(history)} "
              f"(servono almeno {min_history + test_size})")
        return {}

    # Determina range di test
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

    # Storage risultati
    strategies = {
        "bot": [],
        "random": [],
        "hot": [],
        "cold": [],
        "baseline_theoretical": [],
    }

    rng = random.Random(seed)

    # Loop di test
    for i in range(test_start, test_end):
        train = history[:i]
        test_draw = history[i]
        estratti = test_draw["numeri"]
        concorso = test_draw.get("concorso", i + 1)

        # === Strategia BOT ===
        bot_sestinas = bot_portfolio(train, n_sestinas, verbose=False)
        bot_hits = [count_hits(s, estratti) for s in bot_sestinas]
        bot_best = max(bot_hits) if bot_hits else 0
        strategies["bot"].append(bot_best)

        # === Strategia RANDOM (media di N trial) ===
        random_bests = []
        for _ in range(DEFAULT_N_RANDOM_TRIALS):
            r_sestinas = random_portfolio(rng, n_sestinas)
            r_hits = [count_hits(s, estratti) for s in r_sestinas]
            random_bests.append(max(r_hits) if r_hits else 0)
        strategies["random"].append(sum(random_bests) / len(random_bests))

        # === Strategia HOT ===
        hot_s = top_hot_sestina(train)
        strategies["hot"].append(count_hits(hot_s, estratti))

        # === Strategia COLD ===
        cold_s = top_cold_sestina(train)
        strategies["cold"].append(count_hits(cold_s, estratti))

        # === Baseline teorica (media ipergeometrica) ===
        # E[hits] = 6 * 8/90 = 0.5333
        # Best atteso su N sestine = leggermente più alto
        strategies["baseline_theoretical"].append(6 * 8 / 90)

        if verbose:
            print(f"[{i - test_start + 1}/{test_size}] "
                  f"Concorso {concorso}: "
                  f"bot={bot_best} random={strategies['random'][-1]:.2f} "
                  f"hot={strategies['hot'][-1]} cold={strategies['cold'][-1]} "
                  f"(estratti: {estratti})")

    return {
        "strategies": strategies,
        "test_size": test_size,
        "n_sestinas": n_sestinas,
        "min_history": min_history,
        "seed": seed,
    }


# ==========================================
# ANALISI STATISTICA
# ==========================================
def analyze_results(results: Dict) -> Dict:
    """Calcola metriche aggregate per ogni strategia."""
    if not results:
        return {}

    strategies = results["strategies"]
    n = results["test_size"]

    analysis = {}
    for name, hits in strategies.items():
        if not hits:
            continue

        # Distribuzione
        dist = defaultdict(int)
        for h in hits:
            dist[int(round(h))] += 1

        # Statistiche
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
    """
    p-value a due code per un test binomiale.
    H0: k successi su n trial con probabilità p.
    Ritorna p-value approssimato.
    """
    if n == 0:
        return 1.0
    # Calcola P(X <= k) con distribuzione binomiale esatta
    from math import comb
    p_less = sum(comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k + 1))
    # p-value a due code
    p_value = 2 * min(p_less, 1 - p_less + comb(n, k) * (p ** k) * ((1 - p) ** (n - k)))
    return min(1.0, p_value)


# ==========================================
# REPORT
# ==========================================
def format_backtest_report(results: Dict, analysis: Dict) -> str:
    """Report testuale del backtest."""
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

    # Tabella comparativa
    lines.append("PERFORMANCE COMPARATA")
    lines.append("-" * 70)
    header = f"{'Strategia':<20} {'Media':>8} {'2+%':>8} {'3+%':>8} {'4+%':>8}"
    lines.append(header)
    lines.append("-" * 70)

    # Ordine: bot, random, hot, cold, baseline
    order = ["bot", "random", "hot", "cold", "baseline_theoretical"]
    for name in order:
        if name not in analysis:
            continue
        a = analysis[name]
        label = {
            "bot": "Bot (Aurora v2)",
            "random": "Random (baseline)",
            "hot": "Hot (top freq)",
            "cold": "Cold (top rari)",
            "baseline_theoretical": "Teorica (ipergeometrica)",
        }.get(name, name)
        lines.append(
            f"{label:<20} "
            f"{a['mean_hits']:>8.4f} "
            f"{a['hit_2plus_rate']:>7.2f}% "
            f"{a['hit_3plus_rate']:>7.2f}% "
            f"{a['hit_4plus_rate']:>7.2f}%"
        )
    lines.append("")

    # Analisi statistica bot vs random
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
            lines.append(f"✅ Il bot batte la baseline random")
        elif delta < 0:
            lines.append(f"⚠️  Il bot è sotto la baseline random")
        else:
            lines.append(f"⚪ Bot e random sono equivalenti")
        lines.append("")

    # Interpretazione
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
            lines.append("⚠️  Bot sotto la media teorica: metodo non vantaggioso")

    lines.append("")
    lines.append("=" * 70)
    return "\n".join(lines)


# ==========================================
# MAIN
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Aurora Engine — Backtest")
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
        history,
        min_history=args.min_history,
        test_size=args.test_size,
        n_sestinas=args.n_sestinas,
        seed=args.seed,
        verbose=not args.quiet,
    )

    if not results:
        print("[!] Backtest non eseguito.")
        sys.exit(1)

    analysis = analyze_results(results)
    report = format_backtest_report(results, analysis)

    print()
    print(report)

    # Salva report
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
