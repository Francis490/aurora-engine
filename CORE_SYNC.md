# CORE_SYNC — Sincronizzazione tra Aurora Engine e Venus Vortex

> Documento di riferimento per mantenere sincronizzati i file condivisi
> tra i due repository.
> Ultimo aggiornamento: 2026-10-05

---

## 🎯 Scopo

Aurora Engine (`Francis490/aurora-engine`) e Venus Vortex (`Francis490/superenalotto-venus-vortex`) sono **due repo separati** che condividono **alcuni moduli comuni**.

Questo documento spiega:

1. **Quali file** sono duplicati (identici)
2. **Qual è il master** (repo sorgente di verità)
3. **Come sincronizzarli** quando modifichi uno
4. **Come verificare** che siano sincronizzati
5. **Pattern operativi comuni** che entrambi i repo devono seguire

---

## 📋 File duplicati

| File | Aurora | Venus | Master |
|---|---|---|---|
| `core_io.py` | ✅ | ✅ | **Aurora** |

**Regola**: solo `core_io.py` è duplicato. Nessun altro file.

---

## 🏆 Repo master

**`aurora-engine` è il repo master** per i file condivisi.

Motivo: Aurora è stato il primo a ricevere `core_io.py` durante la Fase 6 (2026-10-05), ed è il repo più semplice.

**Conseguenza**: se modifichi `core_io.py`, fallo **prima in Aurora**, poi copia in Venus.

---

## 🔄 Come sincronizzare `core_io.py`

### Scenario: devi modificare `core_io.py`

1. **Modifica in Aurora**:
   - Apri `aurora-engine/core_io.py`
   - Applica la modifica
   - Committa e pusha su Aurora

2. **Copia in Venus**:
   - Apri `superenalotto-venus-vortex/core_io.py`
   - **Seleziona tutto** (Ctrl+A) → **Cancella**
   - **Incolla ESATTAMENTE** il contenuto di `aurora-engine/core_io.py`
   - Committa con messaggio: `chore: sync core_io.py da aurora-engine`

3. **Testa entrambi**:
   - Lancia un workflow su Aurora
   - Lancia un workflow su Venus
   - Verifica che entrambi girino verdi

### Verifica di sincronizzazione

Apri i due file su GitHub e confrontali visivamente. Devono essere **identici carattere per carattere**.

**Metodo rapido in locale** (se hai entrambi i repo clonati):

```bash
diff aurora-engine/core_io.py superenalotto-venus-vortex/core_io.py
