"""
vinci_vita_regime.py
AURORA ENGINE v2 — Regime detection (data drift).

Rileva se la distribuzione statistica del gioco è cambiata nel tempo.
Utile per:
1. Verificare stazionarietà (uniformità delle frequenze)
2. Rilevare drift (confronto finestre temporali)
3. Alertare quando i fingerprint sono obsoleti
4. Validare i dati (individuare bug di scraping)

Test implementati:
- Chi-quadro uniformità (frequenze attese vs osservate)
- Chi-quadro due campioni (finestra recente vs baseline)
- Kolmogorov-Smirnov sulle somme
- Test di autocorrelazione (indipendenza temporale)
- Test di distribuzione parità

Uso:
    from vinci_vita_regime import RegimeDetector
    rd = RegimeDetector(history)
    rd.print_report()
"""
import json
import os
from math import sqrt, log
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


class RegimeDetector:
    """
    Rileva cambi di regime statistico nelle estrazioni.
    """

    def __init__(self, history: List[dict], recent_window: int = 30):
        """
        :param history: lista di dict con "numeri" (8 numeri 1-90)
        :param recent_window: dimensione della finestra "recente" per il drift
        """
        self.history = [d for d in history
                        if isinstance(d.get("numeri"), list)
                        and len(d["numeri"]) == 8]
        self.n = len(self.history)
        self.recent_window = recent_window

    # ==========================================
    # 1. CHI-QUADRO UNIFORMITÀ
    # ==========================================
    def chi_square_uniformity(self) -> Dict:
        """
        Test: le frequenze dei 90 numeri sono compatibili con uniformità?

        H0: ogni numero esce con P = 8/90 per estrazione
        H1: alcune frequenze deviano significativamente

        df = 89 (90-1)
        Chi² critico a 0.05: ~113
        """
        if self.n < 10:
            return {"test": "chi_square_uniformity",
                    "status": "insufficient_data",
                    "n": self.n}

        freq = defaultdict(int)
        for d in self.history:
            for num in d["numeri"]:
                freq[num] += 1

        # Atteso: 8 numeri per estrazione * n estrazioni / 90 numeri
        expected = self.n * 8 / 90

        chi2 = sum(
            (freq.get(num, 0) - expected) ** 2 / expected
            for num in range(1, 91)
        )

        df = 89
        # Chi² critico approssimato a 0.05 per df=89: ~113
        critical_05 = 113
        critical_01 = 128

        if chi2 < critical_05:
            status = "uniforme"
            verdict = "✅ Distribuzione compatibile con uniformità"
        elif chi2 < critical_01:
            status = "borderline"
            verdict = "⚠️  Lieve deviazione (p < 0.05)"
        else:
            status = "deviazione"
            verdict = "🔴 Deviazione significativa (p < 0.01)"

        return {
            "test": "chi_square_uniformity",
            "chi2": round(chi2, 2),
            "df": df,
            "critical_05": critical_05,
            "critical_01": critical_01,
            "status": status,
            "verdict": verdict,
            "n": self.n,
        }

    # ==========================================
    # 2. CHI-QUADRO DUE CAMPIONI (drift)
    # ==========================================
    def chi_square_drift(self) -> Dict:
        """
        Test: la distribuzione recente è compatibile con quella storica?

        Divide lo storico in due finestre:
        - Baseline: tutto tranne gli ultimi recent_window
        - Recente: ultimi recent_window

        Confronta le frequenze osservate.
        """
        if self.n < self.recent_window * 2:
            return {"test": "chi_square_drift",
                    "status": "insufficient_data",
                    "n": self.n,
                    "recent_window": self.recent_window}

        baseline = self.history[:-self.recent_window]
        recent = self.history[-self.recent_window:]

        freq_base = defaultdict(int)
        for d in baseline:
            for num in d["numeri"]:
                freq_base[num] += 1

        freq_recent = defaultdict(int)
        for d in recent:
            for num in d["numeri"]:
                freq_recent[num] += 1

        # Frequenze attese proporzionali
        n_base = len(baseline)
        n_recent = len(recent)

        chi2 = 0.0
        for num in range(1, 91):
            f_b = freq_base.get(num, 0)
            f_r = freq_recent.get(num, 0)

            # Atteso sotto H0 (stessa distribuzione): proporzionale
            total = f_b + f_r
            if total == 0:
                continue
            expected_b = total * n_base / (n_base + n_recent)
            expected_r = total * n_recent / (n_base + n_recent)

            if expected_b > 0:
                chi2 += (f_b - expected_b) ** 2 / expected_b
            if expected_r > 0:
                chi2 += (f_r - expected_r) ** 2 / expected_r

        # df = 89 (approssimazione per indipendenza)
        df = 89
        critical_05 = 113
        critical_01 = 128

        if chi2 < critical_05:
            status = "stabile"
            verdict = "✅ Nessun drift rilevato"
        elif chi2 < critical_01:
            status = "borderline"
            verdict = "⚠️  Drift lieve (possibile rumore)"
        else:
            status = "drift"
            verdict = "🔴 DRIFT RILEVATO: la distribuzione è cambiata"

        # Top 5 numeri più "driftati"
        drifts = []
        for num in range(1, 91):
            f_b = freq_base.get(num, 0)
            f_r = freq_recent.get(num, 0)
            # Differenza normalizzata
            exp_b = n_base * 8 / 90
            exp_r = n_recent * 8 / 90
            drift = abs(f_b - exp_b) + abs(f_r - exp_r)
            drifts.append((num, f_b, f_r, round(drift, 2)))
        drifts.sort(key=lambda x: x[3], reverse=True)

        return {
            "test": "chi_square_drift",
            "chi2": round(chi2, 2),
            "df": df,
            "critical_05": critical_05,
            "critical_01": critical_01,
            "status": status,
            "verdict": verdict,
            "n_baseline": n_base,
            "n_recent": n_recent,
            "top_drift": drifts[:5],
        }

    # ==========================================
    # 3. KOLMOGOROV-SMIRNOV SULLE SOMME
    # ==========================================
    def ks_test_sums(self) -> Dict:
        """
        Test KS: le somme recenti hanno stessa distribuzione delle baseline?
        """
        if self.n < self.recent_window * 2:
            return {"test": "ks_sums",
                    "status": "insufficient_data"}

        baseline = self.history[:-self.recent_window]
        recent = self.history[-self.recent_window:]

        sums_base = sorted([sum(d["numeri"]) for d in baseline])
        sums_recent = sorted([sum(d["numeri"]) for d in recent])

        # KS statistic: max differenza tra CDF empiriche
        def cdf_at(values, x):
            return sum(1 for v in values if v <= x) / len(values)

        all_values = sorted(set(sums_base + sums_recent))
        ks_stat = 0.0
        for x in all_values:
            diff = abs(cdf_at(sums_base, x) - cdf_at(sums_recent, x))
            ks_stat = max(ks_stat, diff)

        # KS critico approssimato (α=0.05) per n₁, n₂ moderate:
        n1, n2 = len(sums_base), len(sums_recent)
        critical_05 = 1.36 * sqrt((n1 + n2) / (n1 * n2))

        if ks_stat < critical_05:
            status = "stabile"
            verdict = "✅ Somme compatibili"
        else:
            status = "drift"
            verdict = "⚠️  Somme distribuite diversamente"

        return {
            "test": "ks_sums",
            "ks_stat": round(ks_stat, 4),
            "critical_05": round(critical_05, 4),
            "status": status,
            "verdict": verdict,
            "mean_base": round(sum(sums_base) / len(sums_base), 2),
            "mean_recent": round(sum(sums_recent) / len(sums_recent), 2),
        }

    # ==========================================
    # 4. AUTOCORRELAZIONE LAG-1
    # ==========================================
    def autocorrelation_lag1(self) -> Dict:
        """
        Test: le somme hanno autocorrelazione lag-1 significativa?
        Se sì, c'è dipendenza temporale (violazione indipendenza).
        """
        if self.n < 10:
            return {"test": "autocorr_lag1", "status": "insufficient_data"}

        sums = [sum(d["numeri"]) for d in self.history]
        n = len(sums)
        mean = sum(sums) / n

        # Covarianza lag-1
        cov = sum((sums[i] - mean) * (sums[i+1] - mean) for i in range(n - 1)) / (n - 1)
        var = sum((s - mean) ** 2 for s in sums) / n

        if var == 0:
            return {"test": "autocorr_lag1",
                    "status": "insufficient_variance"}

        r1 = cov / var

        # Soglia: |r1| > 2/sqrt(n) è significativo
        threshold = 2 / sqrt(n)

        if abs(r1) < threshold:
            status = "indipendente"
            verdict = "✅ Nessuna autocorrelazione significativa"
        else:
            status = "dipendente"
            verdict = "⚠️  Autocorrelazione significativa (possibile pattern)"

        return {
            "test": "autocorr_lag1",
            "r1": round(r1, 4),
            "threshold_2sigma": round(threshold, 4),
            "status": status,
            "verdict": verdict,
            "n": n,
        }

    # ==========================================
    # 5. DISTRIBUZIONE PARITÀ
    # ==========================================
    def parity_distribution(self) -> Dict:
        """
        Test: la distribuzione della parità (numero di pari su 8)
        è compatibile con binomiale B(8, 0.5)?
        """
        if self.n < 20:
            return {"test": "parity_distribution",
                    "status": "insufficient_data"}

        # Conteggio osservato
        observed = defaultdict(int)
        for d in self.history:
            n_pari = sum(1 for x in d["numeri"] if x % 2 == 0)
            observed[n_pari] += 1

        # Atteso: binomiale B(8, 0.5)
        from math import comb
        expected = {}
        for k in range(9):
            expected[k] = self.n * comb(8, k) * (0.5 ** 8)

        # Chi²
        chi2 = 0.0
        for k in range(9):
            exp = expected[k]
            obs = observed.get(k, 0)
            if exp > 0:
                chi2 += (obs - exp) ** 2 / exp

        # df = 8 (9-1)
        critical_05 = 15.51
        critical_01 = 20.09

        if chi2 < critical_05:
            status = "compatibile"
            verdict = "✅ Parità conforme a B(8, 0.5)"
        elif chi2 < critical_01:
            status = "borderline"
            verdict = "⚠️  Lieve deviazione"
        else:
            status = "deviazione"
            verdict = "🔴 Deviazione significativa"

        return {
            "test": "parity_distribution",
            "chi2": round(chi2, 2),
            "df": 8,
            "critical_05": critical_05,
            "critical_01": critical_01,
            "observed": dict(observed),
            "expected_rounded": {k: round(v, 1) for k, v in expected.items()},
            "status": status,
            "verdict": verdict,
        }

    # ==========================================
    # OVERALL STATUS
    # ==========================================
    def run_all(self) -> Dict:
        """Esegue tutti i test e ritorna i risultati aggregati."""
        return {
            "n_history": self.n,
            "recent_window": self.recent_window,
            "tests": {
                "uniformity": self.chi_square_uniformity(),
                "drift": self.chi_square_drift(),
                "ks_sums": self.ks_test_sums(),
                "autocorrelation": self.autocorrelation_lag1(),
                "parity": self.parity_distribution(),
            },
        }

    def overall_health(self) -> str:
        """Ritorna un giudizio sintetico."""
        r = self.run_all()
        tests = r["tests"]

        # Conta problemi
        issues = 0
        for name, t in tests.items():
            if t.get("status") in ("drift", "deviazione", "dipendente"):
                issues += 2
            elif t.get("status") in ("borderline",):
                issues += 1

        if issues == 0:
            return "🟢 SALUTE OTTIMA — Distribuzione stabile, fingerprint affidabili"
        elif issues <= 2:
            return "🟡 SALUTE BUONA — Lieve deviazione, monitorare"
        elif issues <= 4:
            return "🟠 ATTENZIONE — Deviazioni multiple, verificare dati"
        else:
            return "🔴 ALLARME — Drift significativo, fingerprint potenzialmente obsoleti"

    def print_report(self):
        """Stampa un report completo."""
        r = self.run_all()
        print("=" * 70)
        print("AURORA ENGINE v2 — REGIME DETECTION")
        print("=" * 70)
        print(f"Estrazioni analizzate: {r['n_history']}")
        print(f"Finestra recente:      {r['recent_window']}")
        print()

        for name, test in r["tests"].items():
            print(f"### {test['test'].upper()}")
            print(f"  Status: {test.get('status', 'N/A')}")
            print(f"  Verdict: {test.get('verdict', 'N/A')}")

            if test["test"] == "chi_square_uniformity":
                print(f"  Chi²: {test['chi2']} (crit 0.05: {test['critical_05']})")
            elif test["test"] == "chi_square_drift":
                print(f"  Chi²: {test['chi2']} (crit 0.05: {test['critical_05']})")
                if test.get("top_drift"):
                    print(f"  Top 5 drift: {test['top_drift']}")
            elif test["test"] == "ks_sums":
                print(f"  KS: {test['ks_stat']} (crit: {test['critical_05']})")
                print(f"  Media base: {test['mean_base']} | recente: {test['mean_recent']}")
            elif test["test"] == "autocorr_lag1":
                print(f"  r1: {test['r1']} (soglia: ±{test['threshold_2sigma']})")
            elif test["test"] == "parity_distribution":
                print(f"  Chi²: {test['chi2']} (crit 0.05: {test['critical_05']})")
            print()

        print("=" * 70)
        print(f"GIUDIZIO SINTETICO: {self.overall_health()}")
        print("=" * 70)


# ==========================================
# TEST
# ==========================================
if __name__ == "__main__":
    import random

    # Test 1: dati uniformi (dovrebbe essere "uniforme")
    print("### TEST 1: dati uniformi (random)\n")
    rng = random.Random(42)
    history_uniform = [
        {"concorso": i + 1, "numeri": sorted(rng.sample(range(1, 91), 8))}
        for i in range(100)
    ]
    rd1 = RegimeDetector(history_uniform, recent_window=30)
    rd1.print_report()

    # Test 2: dati con drift artificiale
    print("\n\n### TEST 2: dati con drift (numeri alti recenti)\n")
    history_drift = list(history_uniform[:70])
    # Ultime 30 estrazioni: privilegia numeri > 45
    for i in range(30):
        nums = sorted(rng.sample(range(46, 91), 8))
        history_drift.append({"concorso": 71 + i, "numeri": nums})
    rd2 = RegimeDetector(history_drift, recent_window=30)
    rd2.print_report()
