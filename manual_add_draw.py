"""
manual_add_draw.py
Aggiunge un'estrazione manuale a vinci_history.json.
Accetta numeri separati da virgola, spazio, o entrambi.
"""
import json
import os
import re
import sys
from datetime import datetime


HISTORY_FILE = "vinci_history.json"


def main():
    print(f"[debug] argc={len(sys.argv)}")
    print(f"[debug] argv={sys.argv}")

    if len(sys.argv) < 4:
        print("[!] Uso: manual_add_draw.py <concorso> <data> <numeri>")
        sys.exit(1)

    concorso = int(sys.argv[1])
    data = sys.argv[2]

    rest = " ".join(sys.argv[3:])
    print(f"[debug] rest='{rest}'")

    tokens = re.split(r"[,\s]+", rest.strip())
    tokens = [t for t in tokens if t]
    print(f"[debug] tokens={tokens}")

    numeri = [int(t) for t in tokens]

    if len(numeri) != 8 or not all(1 <= n <= 90 for n in numeri):
        print(f"[!] Servono 8 numeri 1-90. Ricevuti: {numeri}")
        sys.exit(1)

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

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
