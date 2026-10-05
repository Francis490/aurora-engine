"""
core_io.py
AURORA + VENUS — Core condiviso: I/O JSON.

Versione unificata di load_json/save_json per entrambi i bot.
Questo file è DUPLICATO IDENTICO in due repo:
  - aurora-engine/core_io.py
  - superenalotto-venus-vortex/core_io.py

Se modifichi questo file, copialo IDENTICO nell'altro repo.
Vedi CORE_SYNC.md (in arrivo) per le istruzioni.

API:
  load_json(filepath, default=None)        -> dict/list
  load_json_strict(filepath)               -> dict/list (solleva eccezione)
  save_json(filepath, data, backup=False)  -> bool

Migliorie rispetto alle versioni precedenti:
- save_json ora scrive in modo ATOMICO (file temp + os.replace).
  Evita corruzione del file se il processo muore a metà scrittura.
- save_json supporta backup=True (copia .bak prima di sovrascrivere).
- Logging errori più chiaro (distingue JSON corrotto da errori I/O).
- load_json_strict per i casi dove l'assenza del file è un errore fatale.
"""
import json
import os
import shutil


def load_json(filepath, default=None):
    """
    Carica un file JSON.

    Ritorna `default` se il file non esiste o è corrotto.
    Logga un warning in caso di errore (non solleva eccezioni).
    """
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[!] JSON corrotto in {filepath}: {e}")
        return default
    except Exception as e:
        print(f"[!] Errore lettura {filepath}: {e}")
        return default


def load_json_strict(filepath):
    """
    Carica un file JSON, sollevando eccezione se manca o è corrotto.
    Utile quando l'assenza del file è un errore fatale.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File non trovato: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath, data, backup=False):
    """
    Salva un file JSON in modo atomico.

    - Se backup=True, crea una copia .bak prima di sovrascrivere
    - Scrive su file temporaneo + os.replace (evita corruzione
      se il processo muore a metà scrittura)
    - Ritorna True se successo, False altrimenti
    """
    tmp_path = filepath + ".tmp"

    try:
        if backup and os.path.exists(filepath):
            shutil.copy2(filepath, filepath + ".bak")

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        os.replace(tmp_path, filepath)
        return True

    except Exception as e:
        print(f"[!] Errore salvataggio {filepath}: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return False
