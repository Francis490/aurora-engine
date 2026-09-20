"""
fetch_vinci_draw.py
AURORA ENGINE — Raccolta estrazioni Super Win for Life da AGIMEG.

Fonte: https://www.agimeg.it
Formato: ogni giorno AGIMEG pubblica un articolo con:
- Numero concorso
- Combinazione vincente (8 numeri)
- Quote complete

FIX (2026-09-20):
- Parser con 4 strategie a cascata per gestire formati diversi
- Fallback su ricerca numerica ampia (blocchi di 8+ numeri)
- Migliore gestione articoli "vincite-super-rendita" vs "estrazione-quote"

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


def fetch_url(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"    ✗ errore fetch: {e}")
        return None


def build_search_url(data: datetime) -> str:
    giorno = data.day
    mese = MESI_IT_INV[data.month]
    anno = data.year
    return f"{BASE_URL}/?s=Super+Win+for+Life+{giorno}+{mese}+{anno}"


# ==========================================
# PARSING — 4 STRATEGIE A CASCATA
# ==========================================
def parse_article(html: str, verbose: bool = True) -> dict:
    """
    Estrae i dati dell'estrazione dal testo dell'articolo AGIMEG.
    Usa 4 strategie a cascata.
    """
    # Pulisci HTML
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)

    result = {}

    # === CONCORSO ===
    m = re.search(r"concorso\s*n(?:\.|umero)?\s*(\d{1,4})", text, re.IGNORECASE)
    if m:
        result["concorso"] = int(m.group(1))

    # === DATA ===
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
        # Fallback: cerca nel titolo "Super Win for Life 19 settembre"
        m = re.search(
            r"(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)",
            text, re.IGNORECASE
        )
        if m:
            giorno = int(m.group(1))
            mese = MESI_IT[m.group(2).lower()]
            # Cerca anno vicino
            anno_m = re.search(r"\b(20\d{2})\b", text)
            anno = int(anno_m.group(1)) if anno_m else datetime.now().year
            result["data"] = f"{giorno:02d}/{mese:02d}/{anno}"

    # === NUMERI — 4 strategie ===
    numbers = None

    # Strategia 1: pattern esplicito "è: 5 – 8 – 17..."
    if not numbers:
        m = re.search(
            r"(?:è|sono|vincente|estratti|combinazione)[\s:]*((?:\d{1,2}\s*[–\-·,]\s*){7}\d{1,2})",
            text, re.IGNORECASE
        )
        if m:
            nums = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            if len(nums) >= 8:
                # Deduplica mantenendo ordine
                seen = set()
                unique = []
                for n in nums:
                    if n not in seen:
                        seen.add(n)
                        unique.append(n)
                if len(unique) >= 8:
                    numbers = unique[:8]
                    if verbose:
                        print(f"    [strategy 1] numeri trovati con contesto 'è/vincente'")

    # Strategia 2: sequenza di 8+ numeri separati da – o -
    if not numbers:
        m = re.search(
            r"((?:\d{1,2}\s*[–\-]\s*){7,}\d{1,2})",
            text
        )
        if m:
            nums = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            if len(nums) >= 8:
                seen = set()
                unique = []
                for n in nums:
                    if n not in seen:
                        seen.add(n)
                        unique.append(n)
                if len(unique) >= 8:
                    numbers = unique[:8]
                    if verbose:
                        print(f"    [strategy 2] numeri trovati con separatore '–'")

    # Strategia 3: blocco numerico esteso (numeri separati da spazi/virgole)
    if not numbers:
        # Cerca blocchi di 20+ numeri consecutivi 1-90
        for m in re.finditer(r"((?:\b\d{1,2}\b[\s,·]+){15,}\b\d{1,2}\b)", text):
            nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            if len(nums) >= 8:
                # Dedup
                seen = set()
                unique = []
                for n in nums:
                    if n not in seen:
                        seen.add(n)
                        unique.append(n)
                # Prendi i primi 8 (spesso sono quelli dell'estrazione)
                if len(unique) >= 8:
                    numbers = unique[:8]
                    if verbose:
                        print(f"    [strategy 3] numeri trovati in blocco ampio")
                    break

    # Strategia 4: cerca la parola "numeri" e prendi i primi 8 numeri dopo
    if not numbers:
        m = re.search(r"numeri.{0,200}", text, re.IGNORECASE)
        if m:
            chunk = m.group(0)
            nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", chunk)]
            nums = [n for n in nums if 1 <= n <= 90 and n != 0]
            # Dedup
            seen = set()
            unique = []
            for n in nums:
                if n not in seen:
                    seen.add(n)
                    unique.append(n)
            if len(unique) >= 8:
                numbers = unique[:8]
                if verbose:
                    print(f"    [strategy 4] numeri trovati dopo keyword 'numeri'")

    if numbers:
        result["numeri"] = numbers

    return result


# ==========================================
# RICERCA ARTICOLO
# ==========================================
def find_article_url_for_date(data: datetime) -> str:
    search_url = build_search_url(data)
    html = fetch_url(search_url)
    if not html:
        return None

    data_str = f"{data.day}-{MESI_IT_INV[data.month]}-{data.year}"
    pattern = re.compile(
        rf'href="(https://www\.agimeg\.it/super-win-for-life-{data_str}[^"]*)"',
        re.IGNORECASE
    )
    matches = pattern.findall(html)
    if matches:
        return matches[0]

    # Fallback
    pattern2 = re.compile(
        r'href="(https://www\.agimeg\.it/super-win-for-life-[^"]*)"',
        re.IGNORECASE
    )
    for url in pattern2.findall(html):
        if data_str in url:
            return url

    return None


def fetch_extraction_for_date(data: datetime, verbose: bool = True) -> dict:
    url = find_article_url_for_date(data)
    if not url:
        print(f"    ✗ Nessun articolo per {data.strftime('%d/%m/%Y')}")
        return None

    if verbose:
        print(f"    → {url}")
    html = fetch_url(url)
    if not html:
        return None

    parsed = parse_article(html, verbose=verbose)
    if not parsed.get("numeri"):
        print(f"    ✗ Parsing numeri fallito (4 strategie esaurite)")
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


def sort_chronological(history):
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

    backfill_days = 0
    if len(sys.argv) > 2 and sys.argv[1] == "--backfill":
        try:
            backfill_days = int(sys.argv[2])
        except ValueError:
            print("[!] --backfill richiede un numero intero.")
            sys.exit(1)

    history = load_history()
    print(f"[*] Storico attuale: {len(history)} estrazioni.")

    fetched = []
    today = datetime.now()

    if backfill_days > 0:
        print(f"[*] Backfill: ultimi {backfill_days} giorni")
        for i in range(backfill_days):
            data = today - timedelta(days=i)
            print(f"[*] Giorno {i+1}/{backfill_days}: {data.strftime('%d/%m/%Y')}")
            extracted = fetch_extraction_for_date(data, verbose=True)
            if extracted:
                fetched.append(extracted)
                print(f"    ✓ Concorso {extracted.get('concorso')} "
                      f"({extracted.get('data')}): {extracted['numeri']}")
            time.sleep(2)
    else:
        print(f"[*] Recupero oggi: {today.strftime('%d/%m/%Y')}")
        extracted = fetch_extraction_for_date(today, verbose=True)
        if extracted:
            fetched.append(extracted)
            print(f"    ✓ Concorso {extracted.get('concorso')} "
                  f"({extracted.get('data')}): {extracted['numeri']}")

    if not fetched:
        print("[!] Nessuna estrazione recuperata.")
        return

    print(f"\n[*] Recuperate {len(fetched)} estrazioni")

    merged, added = merge_history(history, fetched)
    if added > 0:
        merged = sort_chronological(merged)
        save_history(merged)
        print(f"[+] Aggiunte {added} nuove estrazioni. Totale: {len(merged)}")
    else:
        print("[*] Nessuna nuova estrazione. Storico invariato.")

    print("=== COMPLETATO ===")


if __name__ == "__main__":
    main()
