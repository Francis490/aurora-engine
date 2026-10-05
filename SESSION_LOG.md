# SESSION_LOG — Aurora Engine

> Diario di bordo versionato. Aggiornare a ogni sessione significativa.
> Ultimo aggiornamento: 2026-10-05

### Stato attuale
- Versione progetto: **v5.5.1** (fix critici 2026-10-05)
- Dataset: **125 concorsi** (dal 03/06/2026 al 04/10/2026)
- Ultimo concorso registrato: **124** (04/10/2026)
- Prossimo concorso: **125** (05/10/2026)
- Bankroll: **70€** (100 iniziale - 40 speso + 10 vinto)
- ROI: **-75%** (dato reale, non stimato)
- Bot Telegram: `@FrancisauroravinciBot` (operativo)
- Generatore: **random sampling** con filtro somma 240-310 (onesto, senza filtri finti)
- SKIP mode: **se EV < -0.55, nessuna sestina** (severo)

### Workflow GitHub attivi
- **Aurora Manual Update** (workflow_dispatch, con input sestine opzionale)
- **Aurora Planner** (workflow_dispatch, cron disattivato)
- **Aurora Engine — Backfill History** (workflow_dispatch, con input days)
- **Generate PWA Icons** (workflow_dispatch, auto-commit icone)
- Tutti condividono lo stesso **concurrency group** `aurora-write-${{ github.ref }}` → nessuna race condition

### Lavoro in sospeso
- ~~Fase 0: fetch_vinci_draw.py~~ ✅
- ~~Fase 1: vinci_vita_math.py~~ ✅
- ~~Fase 2: vinci_vita_generator.py~~ ✅
- ~~Fase 3: vinci_vita_engine.py~~ ✅
- ~~Fase 4: vinci_vita_telegram.py~~ ✅
- ~~Fase 5: workflow + PWA~~ ✅
- ~~14 fix critici 2026-10-05~~ ✅
- Monitoraggio concorsi 125+

### Problemi noti
- Nessuno bloccante.
- `fetch_vinci_draw.py` funziona ma il formato HTML di AGIMEG può cambiare (retry con backoff attivo).

---

## 2026-10-05 — Fix critici (14 fix in un giorno)

**Obiettivo:** sistemare 14 bug critici accumulati dalla fondazione del progetto.

**Fatto:**
- **#0** Stop cron + concurrency group unificato per tutti i workflow
- **#1** `vinci_vita_check.py` fix order in `vinci_vita_check` (dopo #9 in realtà)
- **#2** Riscrittura `fetch_latest_draw.py` (proxy unico + retry + fail esplicito)
- **#3** `venus_utils.get_year_from_concorso` parametrico via `YEAR_RANGES`
- **#4** `analysis.html` sort cronologico per `(anno, concorso)`
- **#5** Rimozione `true_mimic_generator.py` (OOM bomb)
- **#6** Consolidamento jackpot su `venus_manual_override.json`
- **#7** EV onesto: rimosso `anti_crowd_factor=2.5`
- **#8** `backtest_e2e.py` rimosso
- **#9** `UPDATE_HERE.md` auto-generato in `manual_update.yml`
- **#10** Concurrency unificato
- **#11** `esito_verificato` in `venus_played.json`
- **#12** Backfill `sestina` concorso 159
- **#13** Check-time (cron spento)
- **#14** Doc stale (parziale)

**Personal stats (ricostruite):**
- Speso: €40
- Vinto: €10
- Bilancio: **-€30**
- ROI: **-75%**
- Concorsi completati: 15 (+1 in attesa = 125)

**Track record:**
- Concorsi tracciati: 15 (con 0 punti per la maggior parte)
- Hit rate 3+: 0% (atteso: ~1 ogni 100 concorsi)

**Decisioni:**
- Generatore dichiarato onesto (random + somma 240-310)
- Bias analysis e regime detection **descrittivi**, non influenzano la generazione
- Bankroll ricostruito da `vinci_played.json` (niente più dati inventati)
- SKIP mode severo: EV < -0.55 → nessuna sestina

**Prossimo:**
- Monitorare concorsi 125+
- Eventuale Fase 6 (core condiviso Aurora + Venus)

---

## 2026-09-29 — Estrazione Win for Life concorso 119

**Fatto:**
- Estrazione 29/09/2026 (Concorso 119): `[9, 26, 35, 42, 54, 57, 70, 72]`
- Rendita in palio: €14.110/anno per 20 anni

**Nota:** Il concorso 119 era stato inserito con un typo (36 invece di 35), corretto il 2026-10-05.

---

## 2026-09-20 — Prima vincita documentata

- Estrazione 19/09/2026 (Concorso 109): `[5, 8, 17, 34, 48, 65, 80, 89]`
- Sestina giocata: `[5, 30, 31, 34, 65, 80]`
- **Punti: 4** (5, 34, 65, 80 centrati)
- **Vincita: €178,59**
- **ROI: +8.830%** sulla singola giocata

Sestina originata da Venus Vortex (firma `VX-2026-151-938394`) e giocata manualmente.

---

## 2026-09-20 — Nascita del progetto

**Obiettivo:** Bot Telegram + sistema di analisi quantitativa per Super Win for Life.

**Fatto:**
- Creato repo `aurora-engine` su GitHub
- Attivato GitHub Pages
- Configurati GitHub Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Creato bot Telegram: `@FrancisauroravinciBot`
- Definite 5 fasi di sviluppo

**Decisioni:**
- Repo separato da Venus Vortex
- Fonte dati: AGIMEG (non Sisal)
- Estrazioni giornaliere → serve cron giornaliero (attualmente disattivato, gestito manualmente)
