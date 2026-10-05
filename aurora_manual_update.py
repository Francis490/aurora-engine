"""
aurora_manual_update.py
AURORA ENGINE — Manual update da GitHub Actions form.

FIX (2026-10-05 v2):
- load_json e save_json ora importati da core_io.py (modulo condiviso
  tra Aurora e Venus). Vedi CORE_SYNC.md.

FIX (2026-09-29):
- Aggiunto controllo unicità degli 8 numeri
- Validazione più severa (data valida, concorso positivo)

Legge input da variabili d'ambiente:
- MANUAL_CONCORSO       numero concorso (es. 112)
- MANUAL_DATA           data DD/MM/YYYY (es. 22/09/2026)
- MANUAL_NUMERI         8 numeri separati da virgola
- MANUAL_SESTINE        (opzionale) sestine giocate, formato:
                        "16,35,46,51,66,68 | 5,22,30,34,65,84"
"""
import json
import os
import sys
import re
from datetime import datetime

from core_io import load_json, save_json


HISTORY_FILE = "vinci_history.json"
PLAYED_FILE = "vinci_played.json"


def parse_numeri(s):
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
    if not s or not s.strip():
        return []
    result = []
    for block in s.split("|"):
        nums = parse_numeri(block)
        if (len(nums) == 6
                and len(set(nums)) == 6
                and all(1 <= n <= 90 for n in nums)):
            result.append(nums)
    return result


def validate_data(data_str):
    if not re.match(r"^\d{2}/\d{2}/\d{4}$", data_str):
        return False
    try:
        datetime.strptime(data_str, "%d/%m/%Y")
        return True
    except ValueError:
        return False


def update_history(concorso, data, numeri):
    history = load_json(HISTORY_FILE, [])

    if len(numeri) != 8:
        print(f"[!] Errore: servono 8 numeri, trovati {len(numeri)}")
        return False
    if len(set(numeri)) != 8:
        print(f"[!] Errore: gli 8 numeri devono essere DISTINTI")
        return False
    if not all(1 <= n <= 90 for n in numeri):
        print(f"[!] Errore: numeri fuori range 1-90")
        return False

    for h in history:
        if h.get("concorso") == concorso:
            print(f"[*] Concorso {concorso} già presente, aggiorno.")
            h["data"] = data
            h["numeri"] = numeri
            save_json(HISTORY_FILE, history)
            return True

    history.append({
        "concorso": concorso,
        "data": data,
        "numeri": numeri,
        "url": "manual-update",
    })

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
    if not sestine:
        print("[*] Nessuna sestina giocata fornita.")
        return True

    played = load_json(PLAYED_FILE, {
        "note": "Registro delle sestine giocate con Aurora Engine.",
        "played": []
    })

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

    errors = []

    try:
        concorso = int(concorso_raw)
        if concorso <= 0:
            errors.append(f"concorso deve essere positivo: {concorso}")
    except ValueError:
        errors.append(f"concorso non valido: '{concorso_raw}'")
        concorso = 0

    if not validate_data(data):
        errors.append(f"data deve essere DD/MM/YYYY valida: '{data}'")

    numeri = parse_numeri(numeri_raw)
    if len(numeri) != 8:
        errors.append(f"numeri: servono 8 valori, trovati {len(numeri)}")
    elif len(set(numeri)) != 8:
        errors.append("numeri: gli 8 valori devono essere DISTINTI")
    elif not all(1 <= n <= 90 for n in numeri):
        errors.append("numeri: fuori range 1-90")

    sestine = parse_sestine(sestine_raw)
    if sestine_raw.strip() and not sestine:
        errors.append("sestine: formato non valido o numeri duplicati")

    if errors:
        print("\n[!] ERRORI DI VALIDAZIONE:")
        for e in errors:
            print(f"    - {e}")
        sys.exit(1)

    print(f"\n[*] Concorso:      {concorso}")
    print(f"[*] Data:          {data}")
    print(f"[*] Numeri:        {numeri}")
    print(f"[*] Sestine:       {sestine if sestine else '(nessuna)'}")
    print()

    ok1 = update_history(concorso, data, numeri)
    ok2 = update_played(concorso, data, sestine)

    if not ok1:
        sys.exit(1)

    print("\n=== COMPLETATO ===")


if __name__ == "__main__":
    main()
