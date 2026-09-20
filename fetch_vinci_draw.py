"""
fetch_vinci_draw.py
AURORA ENGINE — Raccolta estrazioni Super Win for Life da AGIMEG.

Fonte: https://www.agimeg.it
Pattern URL: https://www.agimeg.it/super-win-for-life-{giorno}-{mese}-{anno}-...
Formato: ogni giorno AGIMEG pubblica un articolo con:
- Numero concorso
- Combinazione vincente (8 numeri)
- Quote complete

Strategia:
1. Costruisce l'URL dell'articolo di oggi (o di una data specifica)
2. Estrae i dati con regex dal testo dell'articolo
3. Segue il link all'articolo precedente per recuperare lo storico
4. Salva tutto in vinci_history.json

Uso:
    python fetch_vinci_draw.py              # recupera oggi
    python fetch_vinci_draw.py --backfill 30  # recupera ultimi 30 giorni
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests


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

BASE_URL = "https://www.agimeg.it"

MESI_IT = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}

MESI_IT_INV = {v: k for k, v in MESI_IT.items()}


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


def build_search_url(data: datetime) -> str:
    """
    Costruisce l'URL di ricerca per una data specifica.
    Usa il motore di ricerca interno di AGIMEG.
    """
    giorno = data.day
    mese = MESI_IT_INV[data.month]
    anno = data.year
    return f"{BASE_URL}/?s=Super+Win+for+Life+{giorno}+{mese}+{anno}"


def build_article_url_pattern(data: datetime) -> str:
    """
    Pattern URL tipico: /super-win-for-life-{giorno}-{mese}-{anno}-...
    Non sempre esatto: il suffisso varia. Cerchiamo via search.
    """
    giorno = data.day
    mese = MESI_IT_INV[data.month]
    anno = data.year
    return f"super-win-for-life-{giorno}-{mese}-{anno}"


def fetch_url(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"    ✗ errore fetch {url}: {e}")
        return None


# ==========================================
# PARSING ARTICOLO AGIMEG
# ==========================================
def parse_article(html: str) -> dict:
    """
    Estrae i dati dell'estrazione dal testo dell'articolo AGIMEG.
    Ritorna dict con: concorso, data, numeri, quote (opzionale).
    """
    # Estrai il testo principale (rimuovi tag HTML)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    result = {}

    # 1. Numero concorso: "concorso n. 109" o "concorso numero 109"
    m = re.search(r"concorso\s*n(?:\.|umero)?\s*(\d{1,4})", text, re.IGNORECASE)
    if m:
        result["concorso"] = int(m.group(1))

    # 2. Data: cerca nel titolo "Super Win for Life 19 settembre 2026"
    m = re.search(
        r"Super Win for Life\s+(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if m:
        giorno = int(m.group(1))
        mese = MESI_IT[m.group(2).lower()]
        anno = int(m.group(3))
        result["data"] = f"{giorno:02d}/{mese:02d}/{anno}"
    else:
        # Fallback: cerca "sabato 19 settembre" senza anno
        m = re.search(
            r"(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)",
            text, re.IGNORECASE
        )
        if m:
            giorno = int(m.group(1))
            mese = MESI_IT[m.group(2).lower()]
            anno = datetime.now().year
            result["data"] = f"{giorno:02d}/{mese:02d}/{anno}"

    # 3. Numeri: "è: 5 – 8 – 17 – 34 – 48 – 65 – 80 – 89"
    # Cerca 8 numeri separati da – o -
    m = re.search(
        r"(?:è|sono|vincita)\s*:?\s*((?:\d{1,2}\s*[–\-]\s*){7}\d{1,2})",
        text, re.IGNORECASE
    )
    if m:
        nums_str = m.group(1)
        nums = [int(n) for n in re.findall(r"\d{1,2}", nums_str)]
        nums = [n for n in nums if 1 <= n <= 90]
        if len(nums) == 8:
            result["numeri"] = nums

    # Fallback: cerca sequenza di 8 numeri 1-90
    if "numeri" not in result:
        # Cerca nel testo sequenze di 8 numeri plausibili
        m = re.search(
            r"(\d{1,2}\s*[–\-]\s*\d{1,2}\s*[–\-]\s*\d{1,2}\s*[–\-]\s*\d{1,2}\s*[–\-]\s*\d{1,2}\s*[–\-]\s*\d{1,2}\s*[–\-]\s*\d{1,2}\s*[–\-]\s*\d{1,2})",
            text
        )
        if m:
            nums = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            if len(nums) == 8:
                result["numeri"] = nums

    return result


# ==========================================
# RICERCA ARTICOLO
# ==========================================
def find_article_url_for_date(data: datetime) -> str:
    """
    Trova l'URL dell'articolo AGIMEG per una data specifica.
    Usa la ricerca interna del sito.
    """
    # 1. Prova pattern diretto (a volte funziona)
    pattern = build_article_url_pattern(data)
    # Non possiamo sapere il suffisso, quindi usiamo la ricerca

    # 2. Usa ricerca interna
    search_url = build_search_url(data)
    print(f"[*] Ricerca articolo per {data.strftime('%d/%m/%Y')}...")
    html = fetch_url(search_url)
    if not html:
        return None

    # Cerca link ad articoli "super-win-for-life-{giorno}-{mese}-{anno}"
    pattern_link = re.compile(
        rf'href="(https://www\.agimeg\.it/super-win-for-life-{data.day}-{MESI_IT_INV[data.month]}-{data.year}[^"]*)"',
        re.IGNORECASE
    )
    matches = pattern_link.findall(html)
    if matches:
        return matches[0]

    # Fallback: cerca link generici
    pattern_link2 = re.compile(
        r'href="(https://www\.agimeg\.it/super-win-for-life-[^"]*)"',
        re.IGNORECASE
    )
    matches2 = pattern_link2.findall(html)
    # Filtra per data
    data_str = f"{data.day}-{MESI_IT_INV[data.month]}-{data.year}"
    for url in matches2:
        if data_str in url:
            return url

    return None


def fetch_extraction_for_date(data: datetime) -> dict:
    """Recupera l'estrazione di una data specifica. Ritorna None se non trovata."""
    url = find_article_url_for_date(data)
    if not url:
        print(f"    ✗ Nessun articolo per {data.strftime('%d/%m/%Y')}")
        return None

    print(f"    → {url}")
    html = fetch_url(url)
    if not html:
        return None

    parsed = parse_article(html)
    if not parsed.get("numeri"):
        print(f"    ✗ Parsing numeri fallito")
        return None

    parsed["url"] = url
    return parsed


# ==========================================
# MERGE
# ==========================================
def merge_history(existing, fetched):
    existing_keys = set()
    for e in existing:
        key = (e.get("data", ""), e.get("concorso"))
        existing_keys.add(key)

    new_items = []
    for e in fetched:
        key = (e.get("data", ""), e.get("concorso"))
        if key not in existing_keys:
            new_items.append(e)

    return existing + new_items, len(new_items)


def assign_progressive_concorso(history):
    """Ordina cronologicamente e assegna numeri di concorso se mancanti."""
    def sort_key(x):
        d = x.get("data", "01/01/1900")
        try:
            dt = datetime.strptime(d, "%d/%m/%Y")
            return (dt.year, dt.month, dt.day)
        except Exception:
            return (0, 0, 0)

    return sorted(history, key=sort_key)


# ==========================================
# MAIN
# ==========================================
def main():
    print("=== AURORA ENGINE — FETCH VINCI DRAW (AGIMEG) ===")

    # Controlla argomenti
    backfill_days = 0
    if len(sys.argv) > 2 and sys.argv[1] == "--backfill":
        try:
            backfill_days = int(sys.argv[2])
        except ValueError:
            print("[!] Argomento --backfill deve essere un numero intero.")
            sys.exit(1)

    history = load_history()
    print(f"[*] Storico attuale: {len(history)} estrazioni.")

    fetched = []
    today = datetime.now()

    if backfill_days > 0:
        # Recupera gli ultimi N giorni (oggi incluso)
        print(f"[*] Backfill: ultimi {backfill_days} giorni")
        for i in range(backfill_days):
            data = today - timedelta(days=i)
            print(f"[*] Giorno {i+1}/{backfill_days}: {data.strftime('%d/%m/%Y')}")
            extracted = fetch_extraction_for_date(data)
            if extracted:
                fetched.append(extracted)
                print(f"    ✓ Concorso {extracted.get('concorso')} "
                      f"({extracted.get('data')}): {extracted['numeri']}")
            time.sleep(2)  # rispetta il server
    else:
        # Solo oggi
        print(f"[*] Recupero estrazione di oggi: {today.strftime('%d/%m/%Y')}")
        extracted = fetch_extraction_for_date(today)
        if extracted:
            fetched.append(extracted)
            print(f"    ✓ Concorso {extracted.get('concorso')} "
                  f"({extracted.get('data')}): {extracted['numeri']}")

    if not fetched:
        print("[!] Nessuna estrazione recuperata.")
        # Non è un errore fatale: magari oggi non c'è ancora
        return

    print(f"\n[*] Recuperate {len(fetched)} estrazioni")

    merged, added = merge_history(history, fetched)
    if added > 0:
        merged = assign_progressive_concorso(merged)
        save_history(merged)
        print(f"[+] Aggiunte {added} nuove estrazioni. Totale: {len(merged)}")
    else:
        print("[*] Nessuna nuova estrazione. Storico invariato.")

    print("=== COMPLETATO ===")


if __name__ == "__main__":
    main()
