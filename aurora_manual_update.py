"""
aurora_manual_update.py
AURORA ENGINE — Manual update da GitHub Actions form.

Legge input da variabili d'ambiente:
- MANUAL_CONCORSO       numero concorso (es. 112)
- MANUAL_DATA           data DD/MM/YYYY (es. 22/09/2026)
- MANUAL_NUMERI         8 numeri separati da virgola
- MANUAL_SESTINE        (opzionale) sestine giocate, formato:
                        "16,35,46,51,66,68 | 5,22,30,34,65,84"
                        (sestine separate da |)

Aggiorna:
- vinci_history.json    (aggiunge estrazione)
- vinci_played.json     (aggiunge giocate, se fornite)
"""
import json
import os
import sys
import re
from datetime import datetime


HISTORY_FILE = "vinci_history.json"
PLAYED_FILE = "vinci_played.json"


def load_json(fp, default):
    if os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Errore lettura {fp}: {e}")
    return default


def save_json(fp, data):
    try:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[+] Salvato: {fp}")
    except Exception as e:
        print(f"[!] Errore salvataggio {fp}: {e}")


def parse_numeri(s):
    """'23,42,47,...' -> [23, 42, 47, ...]"""
    if not s:
        return []
    nums = []
    for part in re.split(r"[,\s;]+", s.strip()):
        try:
            nums.append(int(part))
        except ValueError:
            continue
    return nums


def parse_sestine(s):
    """'16,35,46,51,66,68 | 5,22,30,34,65,84' -> [[...], [...]]"""
    if not s or not s.strip():
        return []
    result = []
    for block in s.split("|"):
        nums = parse_numeri(block)
        if len(nums) == 6 and all(1 <= n <= 90 for n in nums):
            result.append(nums)
    return result


def validate_data(data_str):
    """Verifica formato DD/MM/YYYY."""
    return bool(re.match(r"^\d{2}/\d{2}/\d{4}$", data_str))


def update_history(concorso, data, numeri):
    """Aggiunge/aggiorna estrazione in vinci_history.json."""
    history = load_json(HISTORY_FILE, [])

    if len(numeri) != 8:
        print(f"[!] Errore: servono 8 numeri, trovati {len(numeri)}")
        return False
    if not all(1 <= n <= 90 for n in numeri):
        print(f"[!] Errore: numeri fuori range 1-90")
        return False

    # Verifica duplicati
    for h in history:
        if h.get("concorso") == concorso:
            print(f"[*] Concorso {concorso} già presente, aggiorno.")
            h["data"] = data
            h["numeri"] = numeri
            save_json(HISTORY_FILE, history)
            return True

    # Aggiungi in fondo
    history.append({
        "concorso": concorso,
        "data": data,
        "numeri": numeri,
        "url": "manual-update"
    })

    # Ordina cronologicamente
    def sort_key(x):
        try:
            dt = datetime.strptime(x.get("data", ""), "%d/%m/%Y")
            return (dt.year, dt.month, dt.day)
        except Exception:
            return (0, 0, 0)

    history.sort(key=sort_key)
    save_json(HISTORY_FILE, history)
    print(f"[+] Concorso {concorso} aggiunto a {HISTORY_FILE}")
    return True


def update_played(concorso, data, sestine):
    """Aggiunge giocate in vinci_played.json."""
    if not sestine:
        print("[*] Nessuna sestina giocata fornita.")
        return True

    played = load_json(PLAYED_FILE, {
        "note": "Registro delle sestine giocate con Aurora Engine.",
        "played": []
    })

    # Verifica duplicati
    for p in played["played"]:
        if p.get("concorso") == concorso:
            print(f"[*] Giocata concorso {concorso} già presente, aggiorno.")
            p["sestine"] = sestine
            p["costo_eur"] = len(sestine) * 2.00
            p["data"] = data
            save_json(PLAYED_FILE, played)
            return True

    played["played"].append({
        "concorso": concorso,
        "data": data,
        "giocata_il": datetime.now().strftime("%d/%m/%Y"),
        "costo_eur": len(sestine) * 2.00,
        "sestine": sestine,
        "note": f"Manual update — {len(sestine)} sestine"
    })

    played["played"].sort(key=lambda x: x.get("concorso", 0))
    save_json(PLAYED_FILE, played)
    print(f"[+] {len(sestine)} sestine aggiunte a {PLAYED_FILE}")
    return True


def main():
    print("=" * 65)
    print("AURORA ENGINE — MANUAL UPDATE")
    print("=" * 65)

    concorso_raw = os.environ.get("MANUAL_CONCORSO", "").strip()
    data = os.environ.get("MANUAL_DATA", "").strip()
    numeri_raw = os.environ.get("MANUAL_NUMERI", "").strip()
    sestine_raw = os.environ.get("MANUAL_SESTINE", "").strip()

    # Validazione
    errors = []

    try:
        concorso = int(concorso_raw)
        if concorso <= 0:
            errors.append(f"concorso deve essere positivo: {concorso}")
    except ValueError:
        errors.append(f"concorso non valido: '{concorso_raw}'")
        concorso = 0

    if not validate_data(data):
        errors.append(f"data deve essere DD/MM/YYYY: '{data}'")

    numeri = parse_numeri(numeri_raw)
    if len(numeri) != 8:
        errors.append(f"numeri: servono 8 valori, trovati {len(numeri)}")

    sestine = parse_sestine(sestine_raw)

    if errors:
        print("\n[!] ERRORI DI VALIDAZIONE:")
        for e in errors:
            print(f"    - {e}")
        sys.exit(1)

    # Info
    print(f"\n[*] Concorso:      {concorso}")
    print(f"[*] Data:          {data}")
    print(f"[*] Numeri:        {numeri}")
    print(f"[*] Sestine:       {sestine if sestine else '(nessuna)'}")
    print()

    # Aggiorna
    ok1 = update_history(concorso, data, numeri)
    ok2 = update_played(concorso, data, sestine)

    if not ok1:
        sys.exit(1)

    print("\n=== COMPLETATO ===")


if __name__ == "__main__":
    main()
