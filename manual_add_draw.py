"""
manual_add_draw.py
Aggiunge un'estrazione manuale a vinci_history.json.

Uso:
    python manual_add_draw.py <concorso> <data> <n1> <n2> ... <n8>

Es:
    python manual_add_draw.py 121 01/10/2026 3 15 22 33 44 55 66 77
"""
import json
import os
import sys
from datetime import datetime


HISTORY_FILE = "vinci_history.json"


def main():
    if len(sys.argv) != 11:
        print("Uso: python manual_add_draw.py <concorso> <data> <n1..n8>")
        sys.exit(1)

    try:
        concorso = int(sys.argv[1])
    except ValueError:
        print("[!] Concorso non valido.")
        sys.exit(1)

    data = sys.argv[2]

    try:
        numeri = [int(x) for x in sys.argv[3:11]]
    except ValueError:
        print("[!] Numeri non validi.")
        sys.exit(1)

    if len(numeri) != 8 or not all(1 <= n <= 90 for n in numeri):
        print("[!] Servono 8 numeri tra 1 e 90.")
        sys.exit(1)

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception as e:
            print(f"[!] Errore lettura {HISTORY_FILE}: {e}")
            sys.exit(1)

    for item in history:
        if item.get("concorso") == concorso:
            print(f"[*] Concorso {concorso} già presente. Skip.")
            return

    history.append({
        "concorso": concorso,
        "data": data,
        "numeri": numeri,
        "url": "manual-input",
    })

    def sort_key(x):
        try:
            return datetime.strptime(x.get("data", ""), "%d/%m/%Y")
        except Exception:
            return datetime(1900, 1, 1)

    history.sort(key=sort_key)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    print(f"[+] Aggiunto concorso {concorso} ({data}): {numeri}")
    print(f"[+] History: {len(history)} estrazioni")


if __name__ == "__main__":
    main()
