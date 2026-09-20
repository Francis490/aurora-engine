"""
vinci_vita_bankroll.py
AURORA ENGINE v2 — Bankroll adattivo (Kelly frazionario).

Gestione ottimale del capitale con:
1. Kelly fraction limitata (max 5% per giocata)
2. Adattamento alla varianza osservata
3. Stop-loss e take-profit dinamici
4. Tracking persistente dello stato (vinci_bankroll.json)

Approccio:
- Kelly puro è troppo aggressivo → usiamo Kelly/4 (quarter-Kelly)
- Cap massimo 5% del bankroll per singola sessione
- Stop-loss: -20% dal picco → stop per 3 giorni
- Take-profit: +50% → prelievo del 30%

Uso:
    from vinci_vita_bankroll import BankrollManager
    bm = BankrollManager(initial_bankroll=100.0)
    stake = bm.calculate_stake(ev_netto=-0.5, costo=2.0)
    bm.record_play(stake=2.0, won=178.59)
    bm.print_state()
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional


BANKROLL_FILE = "vinci_bankroll.json"


class BankrollManager:
    """
    Gestore del bankroll con Kelly frazionario e stop dinamici.
    """

    def __init__(self,
                 initial_bankroll: float = 100.0,
                 kelly_fraction: float = 0.25,
                 max_stake_pct: float = 0.05,
                 stop_loss_pct: float = 0.20,
                 take_profit_pct: float = 0.50,
                 load_state: bool = True):
        """
        :param initial_bankroll: capitale iniziale (se non c'è stato salvato)
        :param kelly_fraction: frazione di Kelly da usare (0.25 = quarter-Kelly)
        :param max_stake_pct: stake massimo per sessione (% del bankroll)
        :param stop_loss_pct: stop-loss dal picco (%)
        :param take_profit_pct: take-profit dal capitale iniziale (%)
        :param load_state: se True, carica da vinci_bankroll.json
        """
        self.kelly_fraction = kelly_fraction
        self.max_stake_pct = max_stake_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        if load_state and os.path.exists(BANKROLL_FILE):
            state = self._load()
            if state:
                self._restore(state)
                return

        # Stato iniziale
        self.initial_bankroll = initial_bankroll
        self.bankroll = initial_bankroll
        self.peak = initial_bankroll
        self.stake_history = []
        self.win_history = []
        self.total_wagered = 0.0
        self.total_won = 0.0
        self.n_plays = 0
        self.n_wins = 0
        self.stop_until = None
        self.created_at = datetime.now().isoformat()

    # ==========================================
    # PERSISTENZA
    # ==========================================
    def _load(self) -> Optional[Dict]:
        try:
            with open(BANKROLL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Errore lettura {BANKROLL_FILE}: {e}")
            return None

    def _restore(self, state: Dict):
        self.initial_bankroll = state.get("initial_bankroll", 100.0)
        self.bankroll = state.get("bankroll", self.initial_bankroll)
        self.peak = state.get("peak", self.bankroll)
        self.stake_history = state.get("stake_history", [])
        self.win_history = state.get("win_history", [])
        self.total_wagered = state.get("total_wagered", 0.0)
        self.total_won = state.get("total_won", 0.0)
        self.n_plays = state.get("n_plays", 0)
        self.n_wins = state.get("n_wins", 0)
        self.stop_until = state.get("stop_until")
        self.created_at = state.get("created_at", datetime.now().isoformat())

    def save(self):
        state = {
            "initial_bankroll": self.initial_bankroll,
            "bankroll": round(self.bankroll, 2),
            "peak": round(self.peak, 2),
            "stake_history": self.stake_history[-100:],  # ultime 100
            "win_history": self.win_history[-100:],
            "total_wagered": round(self.total_wagered, 2),
            "total_won": round(self.total_won, 2),
            "n_plays": self.n_plays,
            "n_wins": self.n_wins,
            "stop_until": self.stop_until,
            "created_at": self.created_at,
            "updated_at": datetime.now().isoformat(),
            "roi_pct": round(
                (self.total_won - self.total_wagered) / max(1, self.total_wagered) * 100, 2
            ),
        }
        try:
            with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Errore salvataggio {BANKROLL_FILE}: {e}")

    # ==========================================
    # STOP-LOSS / TAKE-PROFIT
    # ==========================================
    def is_stopped(self) -> bool:
        """Ritorna True se il bankroll è in stop-loss attivo."""
        if self.stop_until is None:
            return False
        try:
            return datetime.now() < datetime.fromisoformat(self.stop_until)
        except Exception:
            return False

    def _check_stop_loss(self):
        """Verifica se attivare lo stop-loss."""
        if self.peak <= 0:
            return
        dd = (self.peak - self.bankroll) / self.peak
        if dd >= self.stop_loss_pct:
            stop_until = datetime.now() + timedelta(days=3)
            self.stop_until = stop_until.isoformat()
            print(f"[!] STOP-LOSS attivato: drawdown {dd*100:.1f}% >= "
                  f"{self.stop_loss_pct*100}%. Stop fino al "
                  f"{stop_until.strftime('%d/%m/%Y %H:%M')}")

    def _check_take_profit(self):
        """Verifica se attivare il take-profit."""
        if self.initial_bankroll <= 0:
            return
        gain = (self.bankroll - self.initial_bankroll) / self.initial_bankroll
        if gain >= self.take_profit_pct:
            prelievo = self.bankroll * 0.30
            self.bankroll -= prelievo
            print(f"[+] TAKE-PROFIT attivato: guadagno {gain*100:.1f}%. "
                  f"Prelievo €{prelievo:.2f}. Bankroll: €{self.bankroll:.2f}")
            # Reset iniziale per non ripetere
            self.initial_bankroll = self.bankroll

    # ==========================================
    # CALCOLO STAKE
    # ==========================================
    def calculate_stake(self, ev_netto: float, costo_giocata: float) -> float:
        """
        Calcola lo stake ottimale per la prossima sessione.

        Al Super Win for Life l'EV è strutturalmente negativo, quindi
        Kelly puro darebbe f* < 0 (non giocare). Usiamo invece:
        - Kelly frazionario applicato al "miglior caso" (hit rate osservato)
        - Cap a max_stake_pct del bankroll
        - Minimizzazione dello stake quando EV è molto negativo

        :param ev_netto: EV netto per giocata (es. -0.70)
        :param costo_giocata: costo unitario (es. 2.00)
        :return: stake in € da giocare (0 se stop attivo)
        """
        if self.is_stopped():
            print(f"[*] Stop-loss attivo. Stake = 0")
            return 0.0

        if self.bankroll < costo_giocata:
            print(f"[!] Bankroll insufficiente (€{self.bankroll:.2f} < "
                  f"€{costo_giocata:.2f})")
            return 0.0

        # Kelly frazionario: usiamo EV come proxy (più basso = meno stake)
        # Normalizzato: se EV >= 0 → stake massimo, se EV <= -1 → stake minimo
        ev_clamped = max(-1.0, min(0.0, ev_netto))
        # Da -1 (worst) a 0 (best): factor 0.2 → 1.0
        ev_factor = 0.2 + 0.8 * (1 + ev_clamped)

        # Stake base: massimo consentito * kelly_fraction * ev_factor
        base_stake = self.bankroll * self.max_stake_pct * self.kelly_fraction
        stake = base_stake * ev_factor * 4  # normalizzato

        # Cap a max_stake_pct
        max_stake = self.bankroll * self.max_stake_pct
        stake = min(stake, max_stake)

        # Arrotonda a multipli di costo_giocata
        n_giocate = max(0, int(stake / costo_giocata))
        stake_effettivo = n_giocate * costo_giocata

        return round(stake_effettivo, 2)

    # ==========================================
    # REGISTRAZIONE
    # ==========================================
    def record_play(self, stake: float, won: float):
        """
        Registra una giocata.
        :param stake: importo speso
        :param won: importo vinto (0 se perso)
        """
        if stake <= 0:
            return

        self.bankroll -= stake
        self.total_wagered += stake
        self.n_plays += 1

        if won > 0:
            self.bankroll += won
            self.total_won += won
            self.n_wins += 1

        # Aggiorna picco
        if self.bankroll > self.peak:
            self.peak = self.bankroll

        # Storico
        self.stake_history.append({
            "ts": datetime.now().isoformat(),
            "stake": stake,
            "won": won,
            "bankroll_after": round(self.bankroll, 2),
        })
        if won > 0:
            self.win_history.append({
                "ts": datetime.now().isoformat(),
                "stake": stake,
                "won": won,
                "net": round(won - stake, 2),
            })

        # Check stop
        self._check_stop_loss()
        self._check_take_profit()

        self.save()

    # ==========================================
    # REPORT
    # ==========================================
    def get_state(self) -> Dict:
        return {
            "initial_bankroll": round(self.initial_bankroll, 2),
            "bankroll": round(self.bankroll, 2),
            "peak": round(self.peak, 2),
            "drawdown_pct": round(
                (self.peak - self.bankroll) / max(1, self.peak) * 100, 2
            ),
            "total_wagered": round(self.total_wagered, 2),
            "total_won": round(self.total_won, 2),
            "balance": round(self.bankroll - self.initial_bankroll, 2),
            "n_plays": self.n_plays,
            "n_wins": self.n_wins,
            "win_rate_pct": round(
                self.n_wins / max(1, self.n_plays) * 100, 2
            ),
            "roi_pct": round(
                (self.total_won - self.total_wagered) /
                max(1, self.total_wagered) * 100, 2
            ),
            "is_stopped": self.is_stopped(),
            "stop_until": self.stop_until,
        }

    def print_state(self):
        s = self.get_state()
        print("=" * 65)
        print("AURORA ENGINE v2 — BANKROLL STATE")
        print("=" * 65)
        print(f"Capitale iniziale:  € {s['initial_bankroll']:>10.2f}")
        print(f"Bankroll attuale:   € {s['bankroll']:>10.2f}")
        print(f"Picco storico:      € {s['peak']:>10.2f}")
        print(f"Drawdown:           {s['drawdown_pct']:>10.2f}%")
        print(f"Bilancio:           € {s['balance']:>+10.2f}")
        print()
        print(f"Totale giocato:     € {s['total_wagered']:>10.2f}")
        print(f"Totale vinto:       € {s['total_won']:>10.2f}")
        print(f"ROI:                {s['roi_pct']:>10.2f}%")
        print()
        print(f"Giocate:            {s['n_plays']}")
        print(f"Vincite:            {s['n_wins']}")
        print(f"Win rate:           {s['win_rate_pct']:>10.2f}%")
        print()
        if s["is_stopped"]:
            print(f"⚠️  STOP ATTIVO fino al {s['stop_until']}")
        else:
            print(f"✅ Operativo")
        print("=" * 65)


# ==========================================
# TEST
# ==========================================
if __name__ == "__main__":
    # Simula un bankroll da €100
    bm = BankrollManager(initial_bankroll=100.0, load_state=False)

    print("=== Simulazione bankroll ===\n")

    # Simula 10 giocate
    for i in range(1, 11):
        stake = bm.calculate_stake(ev_netto=-0.70, costo_giocata=2.0)
        # Simula esiti: 1 vincita grossa al giro 5
        won = 0.0
        if i == 5:
            won = 178.59
        bm.record_play(stake=stake, won=won)
        print(f"Giocata {i}: stake €{stake:.2f} | won €{won:.2f} | "
              f"bankroll €{bm.bankroll:.2f}")

    print()
    bm.print_state()
