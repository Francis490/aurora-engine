"""
manual_add_draw.py
Aggiunge/aggiorna un'estrazione manuale in vinci_history.json.
Se il concorso esiste già, lo sovrascrive con i dati nuovi.
"""
import json
import os
import re
import sys
from datetime import datetime


HISTORY_FILE = "vinci_history.json"


def main():
    if len(sys.argv) < 4:
        print("[!] Uso: manual_add_draw.py <concorso> <data> <numeri>")
        sys.exit(1)

    concorso = int(sys.argv[1])
    data = sys.argv[2]

    rest = " ".join(sys.argv[3:])
    tokens = [t for t in re.split(r"[,\s]+", rest.strip()) if t]
    numeri = [int(t) for t in tokens]

    if len(numeri) != 8 or not all(1 <= n <= 90 for n in numeri):
        print(f"[!] Servono 8 numeri 1-90. Ricevuti: {numeri}")
        sys.exit(1)

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

    # Rimuovi eventuale entry vecchia con lo stesso concorso
    before = len(history)
    history = [h for h in history if h.get("concorso") != concorso]
    removed = before - len(history)
    if removed:
        print(f"[*] Rimossa {removed} entry vecchia per concorso {concorso}")

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

    print(f"[+] Concorso {concorso} ({data}): {numeri}")
    print(f"[+] History: {len(history)} estrazioni (max concorso = "
          f"{max((h.get('concorso', 0) for h in history), default=0)})")


if __name__ == "__main__":
    main()
