"""
fetch_vinci_draw.py
AURORA ENGINE — Raccolta estrazioni Super Win for Life.

⚠️ NOTA IMPORTANTE:
Le URL delle fonti sono SEGNAPOSTO. Super Win for Life è un gioco recente
e non ho la certezza di quali siti lo pubblichino. Verificheremo insieme
quali URL funzionano e le aggiorneremo.

Struttura dati salvata in vinci_history.json:
[
  {
    "concorso": 1,
    "data": "18/09/2026",
    "ora": "20:00",
    "numeri": [20, 42, 45, 48, 68, 85, 12, 33]  # 8 numeri 1-90
  }
]
"""
import json
import os
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup


HISTORY_FILE = "vinci_history.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

# ⚠️ SEGNAPOSTO — Da verificare insieme
SOURCES = [
    "https://www.sisal.it/",
    "https://www.superenalotto.net/vinci-per-la-vita",
    "https://www.estrazionedelotto.it/vinci-per-la-vita",
]


# ==========================================
# UTILITY
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Errore lettura {HISTORY_FILE}: {e}")
    return []


def save_history(data):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[+] Salvato {HISTORY_FILE} ({len(data)} estrazioni)")
    except Exception as e:
        print(f"[!] Errore salvataggio: {e}")


def normalize_date(raw):
    if not raw:
        return None
    raw = raw.strip()
    m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$", raw)
    if m:
        d, mo, y = m.groups()
        return f"{int(d):02d}/{int(mo):02d}/{y}"
    return None


# ==========================================
# FETCH MULTI-SORGENTE
# ==========================================
def fetch_url(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"    ✗ errore: {e}")
        return None


def parse_extractions_from_text(text):
    """
    Parser generico: cerca pattern di 8 numeri 1-90 con contesto data.
    ⚠️ DA ADATTARE al formato reale del sito scelto.
    """
    results = []
    text_clean = re.sub(r"\s+", " ", text)

    # Pattern: cerca 8 numeri 1-90 in sequenza
    # (adattabile: alcuni siti mostrano le palline come <span>)
    pattern = re.compile(
        r"((?:\b\d{1,2}\b[\s,·-]+){7}\b\d{1,2}\b)"
    )

    for m in pattern.finditer(text_clean):
        nums_str = m.group(1)
        nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", nums_str)]
        nums = [n for n in nums if 1 <= n <= 90]

        # Dedup mantenendo ordine
        seen = set()
        unique = []
        for n in nums:
            if n not in seen:
                seen.add(n)
                unique.append(n)

        if len(unique) == 8:
            # Cerca data vicina
            context = text_clean[max(0, m.start() - 200):m.start()]
            date_match = re.search(r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4})", context)
            data = normalize_date(date_match.group(1)) if date_match else None

            results.append({
                "data": data or "N/A",
                "ora": "20:00",
                "numeri": unique,
            })

    return results


def fetch_all_extractions():
    all_results = []
    for url in SOURCES:
        print(f"[*] Fetch da: {url}")
        content = fetch_url(url)
        if not content:
            continue

        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text(" ", strip=True)

        extractions = parse_extractions_from_text(text)
        print(f"    ✓ {len(extractions)} estrazioni trovate")
        all_results.extend(extractions)
        time.sleep(1)

    # Dedup per (data + numeri)
    seen = set()
    unique_results = []
    for e in all_results:
        key = (e["data"], tuple(e["numeri"]))
        if key not in seen:
            seen.add(key)
            unique_results.append(e)

    return unique_results


# ==========================================
# MERGE
# ==========================================
def merge_history(existing, fetched):
    existing_keys = set()
    for e in existing:
        key = (e.get("data", ""), tuple(e.get("numeri", [])))
        existing_keys.add(key)

    new_items = []
    for e in fetched:
        key = (e["data"], tuple(e["numeri"]))
        if key not in existing_keys:
            new_items.append(e)

    return existing + new_items, len(new_items)


def assign_progressive_concorso(history):
    """Assegna numeri di concorso progressivi (1, 2, 3...) in base all'ordine cronologico."""
    history_sorted = sorted(history, key=lambda x: (
        int(x.get("data", "01/01/1900").split("/")[2] or 0),
        int(x.get("data", "01/01/1900").split("/")[1] or 0),
        int(x.get("data", "01/01/1900").split("/")[0] or 0),
        x.get("ora", "20:00"),
    ))
    for i, e in enumerate(history_sorted, 1):
        e["concorso"] = i
    return history_sorted


# ==========================================
# MAIN
# ==========================================
def main():
    print("=== AURORA ENGINE — FETCH VINCI DRAW ===")

    history = load_history()
    print(f"[*] Storico attuale: {len(history)} estrazioni.")

    fetched = fetch_all_extractions()
    if not fetched:
        print("[!] Nessuna estrazione recuperata.")
        print("[!] Verifica le URL in SOURCES e adatta il parser.")
        sys.exit(1)

    print(f"[*] Trovate {len(fetched)} estrazioni (dopo dedup)")

    merged, added = merge_history(history, fetched)
    if added > 0:
        merged = assign_progressive_concorso(merged)
        save_history(merged)
        print(f"[+] Aggiunte {added} nuove estrazioni. Totale: {len(merged)}")
    else:
        print("[*] Nessuna nuova estrazione. Storico invariato.")


if __name__ == "__main__":
    main()
