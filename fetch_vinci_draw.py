"""
fetch_vinci_draw.py
AURORA ENGINE — Raccolta estrazioni Super Win for Life da AGIMEG.

VERSIONE DIAGNOSTICA (2026-09-30):
- Log dettagliato di ogni passo
- Salva HTML raw in `debug_agimeg/` su fallimento
- Regex URL allargata + fallback per data
- Stampa gli URL candidati trovati nella pagina di ricerca
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests


HISTORY_FILE = "vinci_history.json"
DEBUG_DIR = "debug_agimeg"

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
MESI_ABBR = {
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
    "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12,
}


def ensure_debug_dir():
    os.makedirs(DEBUG_DIR, exist_ok=True)


def save_debug(name, content):
    ensure_debug_dir()
    path = os.path.join(DEBUG_DIR, name)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"    [debug] salvato {path}")
    except Exception as e:
        print(f"    [debug] errore salvataggio {path}: {e}")


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
    print(f"    → GET {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        print(f"      status={r.status_code} len={len(r.text)}")
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"    ✗ errore fetch: {e}")
        return None


def build_search_url(data):
    giorno = data.day
    mese = MESI_IT_INV[data.month]
    anno = data.year
    url = f"{BASE_URL}/?s=Super+Win+for+Life+{giorno}+{mese}+{anno}"
    return url


def find_article_url_for_date(data):
    """Trova URL articolo AGIMEG. Logga TUTTI i candidati trovati."""
    search_url = build_search_url(data)
    print(f"  [search] {search_url}")
    html = fetch_url(search_url)
    if not html:
        return None

    date_tag = data.strftime("%Y%m%d")
    save_debug(f"search_{date_tag}.html", html)

    pattern = re.compile(
        r'href="(https?://(?:www\.)?agimeg\.it/[^"]*super-win-for-life[^"]*)"',
        re.IGNORECASE
    )
    all_urls = pattern.findall(html)
    print(f"  [search] {len(all_urls)} URL 'super-win-for-life' trovati")

    if not all_urls:
        pattern2 = re.compile(
            r'href="(https?://(?:www\.)?agimeg\.it/[^"]*(?:win-for-life|winforlife)[^"]*)"',
            re.IGNORECASE
        )
        all_urls = pattern2.findall(html)
        print(f"  [search] fallback: {len(all_urls)} URL con 'win...life'")

    for i, u in enumerate(all_urls[:10], 1):
        print(f"    [{i}] {u}")

    giorno = data.day
    mese_num = data.month
    mese_nome = MESI_IT_INV[mese_num]
    anno = data.year
    mese_abbr_list = [k for k, v in MESI_ABBR.items() if v == mese_num]
    mese_abbr = mese_abbr_list[0] if mese_abbr_list else ""

    patterns_data = [
        f"{giorno}-{mese_nome}-{anno}",
        f"{giorno:02d}-{mese_nome}-{anno}",
        f"{giorno}-{mese_abbr}-{anno}",
        f"{giorno:02d}-{mese_abbr}-{anno}",
        f"{giorno:02d}-{mese_num:02d}-{anno}",
        f"{giorno}-{mese_num}-{anno}",
        f"{anno}/{mese_num:02d}/{giorno:02d}",
        f"{anno}-{mese_num:02d}-{giorno:02d}",
    ]

    print(f"  [search] cerco uno di questi pattern nella URL:")
    for p in patterns_data:
        print(f"    • {p}")

    for u in all_urls:
        u_lower = u.lower()
        for p in patterns_data:
            if p.lower() in u_lower:
                print(f"  [search] ✓ match: {u}")
                return u

    print(f"  [search] ✗ nessun match per data {data.strftime('%d/%m/%Y')}")
    return None


def parse_article(html, verbose=True):
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)

    result = {}

    m = re.search(r"concorso\s*n(?:\.|umero)?\s*(\d{1,4})", text, re.IGNORECASE)
    if m:
        result["concorso"] = int(m.group(1))

    m = re.search(
        r"Super Win for Life\s+(\d{1,2})\s+"
        r"(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
        r"settembre|ottobre|novembre|dicembre)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if m:
        giorno = int(m.group(1))
        mese = MESI_IT[m.group(2).lower()]
        anno = int(m.group(3))
        result["data"] = f"{giorno:02d}/{mese:02d}/{anno}"

    numbers = None

    m = re.search(
        r"(?:è|sono|vincente|estratti|combinazione)[\s:]*"
        r"((?:\d{1,2}\s*[–\-·,]\s*){7}\d{1,2})",
        text, re.IGNORECASE
    )
    if m:
        nums = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
        nums = [n for n in nums if 1 <= n <= 90]
        unique = list(dict.fromkeys(nums))
        if len(unique) >= 8:
            numbers = unique[:8]
            if verbose:
                print(f"    [S1] numeri trovati con contesto")

    if not numbers:
        m = re.search(r"((?:\d{1,2}\s*[–\-]\s*){7,}\d{1,2})", text)
        if m:
            nums = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            unique = list(dict.fromkeys(nums))
            if len(unique) >= 8:
                numbers = unique[:8]
                if verbose:
                    print(f"    [S2] numeri trovati con separatore")

    if not numbers:
        for m in re.finditer(r"((?:\b\d{1,2}\b[\s,·]+){15,}\b\d{1,2}\b)", text):
            nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            unique = list(dict.fromkeys(nums))
            if len(unique) >= 8:
                numbers = unique[:8]
                if verbose:
                    print(f"    [S3] numeri trovati in blocco ampio")
                break

    if not numbers:
        m = re.search(r"numeri.{0,200}", text, re.IGNORECASE)
        if m:
            chunk = m.group(0)
            nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", chunk)]
            nums = [n for n in nums if 1 <= n <= 90]
            unique = list(dict.fromkeys(nums))
            if len(unique) >= 8:
                numbers = unique[:8]
                if verbose:
                    print(f"    [S4] numeri trovati dopo keyword")

    if numbers:
        result["numeri"] = numbers

    return result


def fetch_extraction_for_date(data, verbose=True):
    print(f"\n[*] Data target: {data.strftime('%d/%m/%Y')}")
    url = find_article_url_for_date(data)
    if not url:
        print(f"    ✗ Nessun articolo trovato")
        return None

    html = fetch_url(url)
    if not html:
        return None

    date_tag = data.strftime("%Y%m%d")
    save_debug(f"article_{date_tag}.html", html)

    parsed = parse_article(html, verbose=verbose)
    if not parsed.get("numeri"):
        print(f"    ✗ Parsing numeri fallito")
        print(f"    [debug] parsed parziale: {parsed}")
        return None

    parsed["url"] = url
    print(f"    ✓ Risultato: {parsed}")
    return parsed


def merge_history(existing, fetched):
    existing_ids = {e.get("concorso") for e in existing
                    if isinstance(e.get("concorso"), int)}
    new_items = [e for e in fetched if e.get("concorso") not in existing_ids]
    return existing + new_items, len(new_items)


def sort_chronological(history):
    def sort_key(x):
        try:
            dt = datetime.strptime(x.get("data", ""), "%d/%m/%Y")
            return (dt.year, dt.month, dt.day)
        except Exception:
            return (0, 0, 0)
    return sorted(history, key=sort_key)


def main():
    print("=== AURORA ENGINE — FETCH VINCI DRAW (DIAGNOSTIC) ===\n")

    backfill_days = 0
    if len(sys.argv) > 2 and sys.argv[1] == "--backfill":
        try:
            backfill_days = int(sys.argv[2])
        except ValueError:
            print("[!] --backfill richiede un numero.")
            sys.exit(1)

    history = load_history()
    print(f"[*] Storico attuale: {len(history)} estrazioni\n")

    fetched = []
    today = datetime.now()

    if backfill_days > 0:
        print(f"[*] Backfill: ultimi {backfill_days} giorni\n")
        for i in range(backfill_days):
            data = today - timedelta(days=i)
            print(f"--- Giorno {i+1}/{backfill_days} ---")
            extracted = fetch_extraction_for_date(data)
            if extracted:
                fetched.append(extracted)
            time.sleep(2)
    else:
        print(f"[*] Recupero oggi: {today.strftime('%d/%m/%Y')}\n")
        extracted = fetch_extraction_for_date(today)
        if extracted:
            fetched.append(extracted)

    print(f"\n=== RIEPILOGO ===")
    print(f"[*] Recuperate {len(fetched)} estrazioni")

    if not fetched:
        print("[!] Nessuna estrazione. Controlla i file in debug_agimeg/")
        return

    merged, added = merge_history(history, fetched)
    if added > 0:
        merged = sort_chronological(merged)
        save_history(merged)
        print(f"[+] Aggiunte {added} nuove. Totale: {len(merged)}")
    else:
        print("[*] Nessuna nuova estrazione (già presenti).")


if __name__ == "__main__":
    main()
