"""
vinci_vita_engine.py
AURORA ENGINE v2 — Orchestratore integrato.

Pipeline:
1. Load storico
2. Regime detection
3. Bankroll state
4. EV/Kelly/budget
5. Pool (FIX: esclude < 10) + generator
6. Fingerprint avanzati + portfolio (FIX: filtro AC >= 7.0)
7. Output database + report

FIX (2026-09-20):
- build_pool_from_history: esclude numeri < 10 (troppo popolari)
- run_engine: filtro AC minimo 7.0 sulle sestine candidate
"""
import json
import os
from datetime import datetime, timedelta

from vinci_vita_math import (
    calcola_ev, kelly_analysis, soglie_budget,
    valore_attuale_rendita,
    RENDITA_ATTUALE_MENSILE, COSTO_GIOCATA_EUR,
)
from vinci_vita_generator import (
    generate_aurora_sestinas, extract_fingerprints,
    anti_crowd_score, SUM_HARD_MIN, SUM_HARD_MAX,
)

try:
    from vinci_vita_fingerprints import AuroraFingerprintEngine
    FP_ADV = True
except ImportError:
    FP_ADV = False

try:
    from vinci_vita_portfolio import PortfolioOptimizer
    PORTF = True
except ImportError:
    PORTF = False

try:
    from vinci_vita_bankroll import BankrollManager
    BANK = True
except ImportError:
    BANK = False

try:
    from vinci_vita_regime import RegimeDetector
    REGIME = True
except ImportError:
    REGIME = False


HISTORY_FILE = "vinci_history.json"
DATABASE_FILE = "vinci_database.json"

# FIX: soglia anti-crowd minima
AC_MIN_THRESHOLD = 7.0


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Errore lettura: {e}")
    return []


def save_json(fp, data):
    try:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[+] Salvato: {fp}")
    except Exception as e:
        print(f"[!] Errore salvataggio: {e}")


def build_pool_from_history(history, size=25):
    """
    Costruisce pool di 'size' numeri bilanciando frequenza media + anti-crowd.

    FIX (2026-09-20):
    - Esclude numeri < 10 (troppo popolari in Italia: compleanni, cifre singole)
    - Forza almeno 6 numeri > 60 (anti-crowd forte)
    """
    if not history:
        return [n for n in range(10, 91, 4)][:size]

    freq = {i: 0 for i in range(1, 91)}
    td = 0
    for d in history:
        nums = d.get("numeri", [])
        if len(nums) != 8:
            continue
        td += 1
        for n in nums:
            if 1 <= n <= 90:
                freq[n] += 1

    if td == 0:
        return [n for n in range(10, 91, 4)][:size]

    avg = sum(freq.values()) / 90

    # FIX: escludi numeri < 10
    candidates = list(range(10, 91))

    # Ordina per distanza dalla media
    scored = sorted(candidates, key=lambda n: abs(freq[n] - avg))
    pool = scored[:size]

    # Forza almeno 6 numeri > 60 (anti-crowd forte)
    anti = [n for n in range(61, 91) if n not in pool]
    anti.sort(key=lambda n: abs(freq[n] - avg))
    for n in anti[:6]:
        if len(pool) >= size:
            pool.pop()
        pool.append(n)

    return sorted(set(pool))


def run_engine(rendita=RENDITA_ATTUALE_MENSILE, n_sestinas=None):
    print("=" * 65)
    print("AURORA ENGINE v2 — PIPELINE")
    print("=" * 65)

    history = load_history()
    print(f"[*] Storico: {len(history)} estrazioni")

    # Regime
    regime = None
    if REGIME and len(history) >= 20:
        try:
            rd = RegimeDetector(history, recent_window=min(30, max(5, len(history) // 3)))
            health = rd.overall_health()
            print(f"[*] Regime: {health}")
            regime = {"health": health, "n": len(history)}
        except Exception as e:
            print(f"[!] Regime errore: {e}")

    # Bankroll
    bm = None
    bs = None
    if BANK:
        try:
            bm = BankrollManager(initial_bankroll=100.0)
            bs = bm.get_state()
            print(f"[*] Bankroll: €{bs['bankroll']:.2f} | ROI {bs['roi_pct']:+.2f}%")
        except Exception as e:
            print(f"[!] Bankroll errore: {e}")

    # EV/Kelly/Budget
    ev = calcola_ev(rendita)
    budget = soglie_budget(rendita)
    print(f"[*] EV: €{ev['ev_netto']:+.4f} ({ev['ev_percentuale']:+.2f}%)")
    print(f"[*] Budget: {budget['mode']}")

    if n_sestinas is None:
        n_sestinas = budget["n_sestine"]

    if bm and bm.is_stopped():
        print("[!] Bankroll in stop")
        n_sestinas = 0

    if n_sestinas == 0:
        payload = build_payload(history, [], budget, rendita, ev, None, None, regime, bs)
        save_json(DATABASE_FILE, payload)
        return payload

    # Pool + Generator
    pool = build_pool_from_history(history, 25)
    print(f"[*] Pool: {pool}")
    n_cand = min(50, max(20, n_sestinas * 10))
    cand, fp = generate_aurora_sestinas(history, pool, n_sestinas=n_cand)

    if not cand:
        print("[!] Nessun candidato.")
        payload = build_payload(history, [], budget, rendita, ev, None, None, regime, bs)
        save_json(DATABASE_FILE, payload)
        return payload

    # Fingerprint avanzati
    fp_eng = None
    if FP_ADV:
        try:
            fp_eng = AuroraFingerprintEngine(history)
            print(f"[*] FP avanzati: attivi")
        except Exception as e:
            print(f"[!] FP avanzati errore: {e}")

    # FIX: Score candidati con filtro AC >= 7.0
    scored = []
    rejected = 0
    for s in cand:
        base = anti_crowd_score(s)
        if base < AC_MIN_THRESHOLD:
            rejected += 1
            continue
        adv = 0.5
        if fp_eng:
            try:
                adv = fp_eng.score_sestina(s)["composite"]
            except Exception:
                pass
        comp = 0.5 * (base / 10.0) + 0.5 * adv
        scored.append((s, comp))

    if rejected > 0:
        print(f"[*] Filtro AC: {rejected} sestine scartate (AC < {AC_MIN_THRESHOLD})")

    # Fallback: se il filtro elimina tutto, rilascia
    if not scored:
        print(f"[!] Nessuna sestina con AC >= {AC_MIN_THRESHOLD}. Rilascio filtro.")
        for s in cand:
            base = anti_crowd_score(s)
            adv = 0.5
            if fp_eng:
                try:
                    adv = fp_eng.score_sestina(s)["composite"]
                except Exception:
                    pass
            comp = 0.5 * (base / 10.0) + 0.5 * adv
            scored.append((s, comp))

    print(f"[*] Candidati validi dopo filtro: {len(scored)}")

    # Portfolio
    if PORTF and len(scored) > 0:
        try:
            opt = PortfolioOptimizer(scored)
            portfolio = opt.optimize(n_sestinas=n_sestinas, verbose=False)
            pmetrics = opt.score_portfolio([s for s, _ in portfolio])
            print(f"[*] Portfolio: composite {pmetrics['composite']:.3f}, corr {pmetrics['correlation']:.3f}")
        except Exception as e:
            print(f"[!] Portfolio errore: {e}")
            scored.sort(key=lambda x: x[1], reverse=True)
            portfolio = scored[:n_sestinas]
            pmetrics = None
    else:
        scored.sort(key=lambda x: x[1], reverse=True)
        portfolio = scored[:n_sestinas]
        pmetrics = None

    # Sestine data
    sdata = []
    for i, (s, sc) in enumerate(portfolio, 1):
        ssum = sum(s)
        ac = anti_crowd_score(s)
        fpd = None
        if fp_eng:
            try:
                fpd = fp_eng.score_sestina(s)
            except Exception:
                pass
        sdata.append({
            "id": i, "numeri": s, "somma": ssum,
            "in_range": SUM_HARD_MIN <= ssum <= SUM_HARD_MAX,
            "composite_score": round(sc, 4),
            "anti_crowd_score": round(ac, 2),
            "fingerprint_detail": fpd,
        })
        print(f"  {i}. {s} | somma {ssum} | AC {ac:.2f} | score {sc:.4f}")

    payload = build_payload(history, sdata, budget, rendita, ev, fp,
                            pmetrics, regime, bs)
    save_json(DATABASE_FILE, payload)
    return payload


def build_payload(history, sdata, budget, rendita, ev, fp, pmetrics, regime, bs):
    now = datetime.now()
    ld = history[-1] if history else {}
    lc = ld.get("concorso", "N/A")
    ln = ld.get("numeri", [])
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

    return {
        "version": "2.0",
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "rendita_mensile": rendita,
        "valore_attuale_rendita": round(valore_attuale_rendita(rendita), 2),
        "budget_mode": budget,
        "n_sestinas": len(sdata),
        "costo_totale": round(len(sdata) * COSTO_GIOCATA_EUR, 2),
        "sestinas": sdata,
        "ev": {
            "ev_netto": round(ev["ev_netto"], 4),
            "ev_percentuale": round(ev["ev_percentuale"], 2),
        } if ev else None,
        "last_draw": {"concorso": lc, "data": ldate, "numeri": ln},
        "next_draw": {"concorso": nc, "data": nd, "ora": "20:00"},
        "fingerprint_base": {
            "n_draws": fp["n_draws"] if fp else 0,
            "sum_mean": fp["sum_mean"] if fp else None,
        } if fp else None,
        "portfolio_metrics": pmetrics,
        "regime_report": regime,
        "bankroll_state": bs,
    }


def format_report(payload):
    if not payload:
        return "❌ Nessun payload."
    lines = [
        "🌅 AURORA ENGINE v2 — REPORT",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💎 Rendita: € {payload['rendita_mensile']:,}/mese",
        f"   Valore attuale: € {payload['valore_attuale_rendita']:,.0f}",
        "",
    ]
    if payload.get("regime_report"):
        lines.append(f"🔬 {payload['regime_report']['health']}")
        lines.append("")
    if payload.get("bankroll_state"):
        bs = payload["bankroll_state"]
        lines.append(f"💰 Bankroll: €{bs['bankroll']:.2f} (peak €{bs['peak']:.2f})")
        lines.append(f"   ROI: {bs['roi_pct']:+.2f}%")
        lines.append("")
    nd = payload["next_draw"]
    lines.append(f"🎯 PROSSIMA: Concorso N° {nd['concorso']}")
    lines.append(f"   {nd['data']} · ore {nd['ora']}")
    lines.append("")
    ld = payload["last_draw"]
    if ld["numeri"]:
        ns = " · ".join(str(n).zfill(2) for n in ld["numeri"])
        lines.append(f"📊 ULTIMA (N° {ld['concorso']}): {ns}")
        lines.append("")
    if payload["sestinas"]:
        lines.append(f"🎲 SESTINE ({payload['n_sestinas']} · €{payload['costo_totale']:.2f})")
        em = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
        for i, s in enumerate(payload["sestinas"]):
            e = em[i] if i < len(em) else f"{i+1}."
            ns = " · ".join(str(n).zfill(2) for n in s["numeri"])
            lines.append(f"   {e} [{ns}]")
            lines.append(f"      Somma {s['somma']} · AC {s['anti_crowd_score']:.2f}")
        lines.append("")
    if payload.get("portfolio_metrics"):
        pm = payload["portfolio_metrics"]
        lines.append(f"📊 Portfolio: corr {pm['correlation']:.3f} (↓ meglio)")
        lines.append("")
    lines.append("🌅 Aurora Engine v2 — Super Win for Life")
    return "\n".join(lines)


if __name__ == "__main__":
    payload = run_engine()
    print("\n" + "=" * 65)
    print(format_report(payload))
    print("=" * 65)
