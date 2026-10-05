"""
rebuild_bankroll.py
AURORA ENGINE — Ricostruisce vinci_bankroll.json leggendo vinci_played.json.

Uso:
    python rebuild_bankroll.py

Cosa fa:
1. Legge tutte le giocate da vinci_played.json
2. Calcola speso/vinto reali
3. Rigenera vinci_bankroll.json con dati coerenti
4. Preserva stop_until se presente
"""
import json
import os
from datetime import datetime


PLAYED_FILE = "vinci_played.json"
BANKROLL_FILE = "vinci_bankroll.json"

INITIAL_BANKROLL = 100.0


def load_json(fp, default):
    if os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Errore lettura {fp}: {e}")
    return default


def main():
    print("=" * 65)
    print("AURORA ENGINE — RICOSTRUZIONE BANKROLL")
    print("=" * 65)

    played = load_json(PLAYED_FILE, {"played": []})
    plays = played.get("played", [])

    if not plays:
        print("[!] Nessuna giocata in vinci_played.json. Interrompo.")
        return

    print(f"[*] Trovate {len(plays)} entry in {PLAYED_FILE}")
    print()

    # Preserva eventuale stop_until dal bankroll esistente
    old_state = load_json(BANKROLL_FILE, {})
    stop_until = old_state.get("stop_until")
    created_at = old_state.get("created_at", datetime.now().isoformat())

    bankroll = INITIAL_BANKROLL
    peak = INITIAL_BANKROLL
    stake_history = []
    win_history = []

    total_wagered = 0.0
    total_won = 0.0
    n_plays = 0
    n_wins = 0

    print(f"{'Concorso':<10} {'Costo':>8} {'Premio':>8} {'Bankroll':>10} {'Note':<30}")
    print("-" * 75)

    for play in plays:
        concorso = play.get("concorso", "?")
        costo = float(play.get("costo_eur", 0.0))
        premio = float(play.get("premio_reale", 0.0))
        giocata_il = play.get("giocata_il", play.get("data", ""))
        note = play.get("note", "")

        # Salta entry senza costo (es. falso positivo concorso 120)
        if costo == 0:
            print(f"{concorso:<10} {'—':>8} {'—':>8} {'—':>10} {note[:30]:<30} [SKIP]")
            continue

        bankroll -= costo
        total_wagered += costo
        n_plays += 1

        # Converti data in ISO per ts
        try:
            dt = datetime.strptime(giocata_il, "%d/%m/%Y")
            ts = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            ts = datetime.now().isoformat()

        stake_history.append({
            "ts": ts,
            "stake": round(costo, 2),
            "won": round(premio, 2),
            "bankroll_after": round(bankroll, 2),
        })

        if premio > 0:
            bankroll += premio
            total_won += premio
            n_wins += 1
            if bankroll > peak:
                peak = bankroll
            win_history.append({
                "ts": ts,
                "stake": 0.0,
                "won": round(premio, 2),
                "net": round(premio, 2),
                "note": f"Concorso {concorso}",
            })

        print(f"{concorso:<10} {costo:>8.2f} {premio:>8.2f} {bankroll:>10.2f} {note[:30]:<30}")

    print()
    print("=" * 65)
    print(f"[*] Totale speso:     € {total_wagered:.2f}")
    print(f"[*] Totale vinto:     € {total_won:.2f}")
    print(f"[*] Bankroll finale:  € {bankroll:.2f}")
    print(f"[*] Peak:             € {peak:.2f}")
    print(f"[*] Giocate:          {n_plays}")
    print(f"[*] Vincite:          {n_wins}")
    roi = ((total_won - total_wagered) / max(1, total_wagered)) * 100
    print(f"[*] ROI:              {roi:+.2f}%")
    print("=" * 65)
    print()

    # Costruisci nuovo bankroll.json
    new_state = {
        "initial_bankroll": INITIAL_BANKROLL,
        "bankroll": round(bankroll, 2),
        "peak": round(peak, 2),
        "stake_history": stake_history,
        "win_history": win_history,
        "total_wagered": round(total_wagered, 2),
        "total_won": round(total_won, 2),
        "n_plays": n_plays,
        "n_wins": n_wins,
        "stop_until": stop_until,
        "created_at": created_at,
        "updated_at": datetime.now().isoformat(),
        "roi_pct": round(roi, 2),
    }

    with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
        json.dump(new_state, f, indent=2, ensure_ascii=False)

    print(f"[+] Salvato {BANKROLL_FILE} ricostruito.")
    print()
    print("=== COMPLETATO ===")


if __name__ == "__main__":
    main()
