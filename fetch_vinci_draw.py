"""
fetch_vinci_draw.py
AURORA ENGINE — Raccolta estrazioni Super Win for Life da AGIMEG.

APPROCCIO v5 (2026-10-01) — DEFINITIVO:
- FONTE: WordPress REST API di AGIMEG
- Endpoint: /wp-json/wp/v2/posts?categories=1031 (Win for Life)
- Ritorna JSON strutturato: date ISO, link, titolo, contenuto HTML
- Zero parsing fragile di href/URL

FIX (2026-10-05):
- load_history e save_history ora usano core_io.py (modulo condiviso).
- save_debug continua a usare json.dump diretto (file di debug temporanei,
  non vogliamo .bak e .tmp nella cartella debug_agimeg/).

Uso:
    python fetch_vinci_draw.py              # recupera oggi
    python fetch_vinci_draw.py --backfill 30
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests

from core_io import load_json, save_json


HISTORY_FILE = "vinci_history.json"
DEBUG_DIR = "debug_agimeg"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json,text/html,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.agimeg.it"
WIN_FOR_LIFE_CATEGORY_ID = 1031


def ensure_debug_dir():
    os.makedirs(DEBUG_DIR, exist_ok=True)


def save_debug(name, content):
    """
    Salva un file di debug nella cartella debug_agimeg/.
    Nota: usa json.dump diretto (non core_io) perché questi file
    non vanno backuppati e non hanno bisogno di atomic write.
    """
    ensure_debug_dir()
    path = os.path.join(DEBUG_DIR, name)
    try:
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(content, str):
                f.write(content)
            else:
                json.dump(content, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"    [debug] errore salvataggio {path}: {e}")


def load_history():
    data = load_json(HISTORY_FILE, [])
    return data if isinstance(data, list) else []


def save_history(data):
    save_json(HISTORY_FILE, data)
    print(f"[+] Salvato {HISTORY_FILE} ({len(data)} estrazioni)")


def fetch_posts(page=1, per_page=20):
    """Scarica posts di AGIMEG dalla categoria Win for Life via REST API."""
    url = (
        f"{BASE_URL}/wp-json/wp/v2/posts"
        f"?categories={WIN_FOR_LIFE_CATEGORY_ID}"
        f"&per_page={per_page}"
        f"&page={page}"
        f"&orderby=date"
        f"&order=desc"
    )
    print(f"  [api] GET pagina {page}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        print(f"        status={r.status_code} len={len(r.text)}")
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [api] ✗ errore: {e}")
        return None


def strip_html(html):
    """Rimuove tag HTML e normalizza spazi."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&#8217;", "'", text)
    text = re.sub(r"&#8230;", "...", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_numbers_from_text(text):
    """Cerca 8 numeri 1-90 nel testo. Strategia a cascata."""

    # S1: contesto "estratti/vincenti/combinazione/numeri" + numeri
    m = re.search(
        r"(?:estratti|vincenti|combinazione|numeri)[\s:]*"
        r"((?:\d{1,2}\s*[–\-·,]\s*){7}\d{1,2})",
        text, re.IGNORECASE
    )
    if m:
        nums = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
        nums = [n for n in nums if 1 <= n <= 90]
        unique = list(dict.fromkeys(nums))
        if len(unique) >= 8:
            return unique[:8]

    # S2: sequenza con separatori – o -
    m = re.search(r"((?:\d{1,2}\s*[–\-]\s*){7,}\d{1,2})", text)
    if m:
        nums = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
        nums = [n for n in nums if 1 <= n <= 90]
        unique = list(dict.fromkeys(nums))
        if len(unique) >= 8:
            return unique[:8]

    # S3: blocco con molti numeri
    for m in re.finditer(r"((?:\b\d{1,2}\b[\s,·]+){15,}\b\d{1,2}\b)", text):
        nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", m.group(1))]
        nums = [n for n in nums if 1 <= n <= 90]
        unique = list(dict.fromkeys(nums))
        if len(unique) >= 8:
            return unique[:8]

    return None


def extract_concorso(text):
    m = re.search(r"concorso\s*n(?:\.|umero)?\s*(\d{1,4})", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def post_to_extraction(post):
    """Converte un post REST API in dict estrazione. None se numeri non estraibili."""
    title = strip_html(post.get("title", {}).get("rendered", ""))
    content_html = post.get("content", {}).get("rendered", "")
    content_text = strip_html(content_html)
    link = post.get("link", "")
    date_iso = post.get("date", "")

    data_str = None
    if date_iso:
        try:
            dt = datetime.fromisoformat(date_iso)
            data_str = dt.strftime("%d/%m/%Y")
        except Exception:
            pass

    numbers = extract_numbers_from_text(content_text)
    if not numbers:
        numbers = extract_numbers_from_text(title)

    if not numbers:
        return None

    concorso = extract_concorso(content_text)

    return {
        "concorso": concorso,
        "data": data_str,
        "numeri": numbers,
        "url": link,
        "title": title,
    }


def fetch_all_recent(max_pages=3):
    """Scarica tutti i post recenti dalla categoria Win for Life."""
    all_posts = []
    for page in range(1, max_pages + 1):
        posts = fetch_posts(page=page, per_page=20)
        if not posts:
            break
        if len(posts) == 0:
            print(f"  [api] pagina vuota, stop")
            break
        print(f"  [api] {len(posts)} post ricevuti")
        all_posts.extend(posts)
        if len(posts) < 20:
            print(f"  [api] ultima pagina")
            break
        time.sleep(1)
    return all_posts


def find_extraction_for_date(posts, data):
    """Trova l'estrazione del Win for Life per una data specifica."""
    target_date_iso = data.strftime("%Y-%m-%d")
    for post in posts:
        date_iso = post.get("date", "")
        if date_iso.startswith(target_date_iso):
            return post_to_extraction(post)
    return None


def merge_history(existing, fetched):
    existing_ids = {e.get("concorso") for e in existing
                    if isinstance(e.get("concorso"), int)}
    new_items = [e for e in fetched
                 if isinstance(e.get("concorso"), int)
                 and e.get("concorso") not in existing_ids]
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
    print("=== AURORA ENGINE — FETCH VINCI DRAW (v5 - REST API) ===\n")

    backfill_days = 0
    if len(sys.argv) > 2 and sys.argv[1] == "--backfill":
        try:
            backfill_days = int(sys.argv[2])
        except ValueError:
            print("[!] --backfill richiede un numero.")
            sys.exit(1)

    history = load_history()
    print(f"[*] Storico attuale: {len(history)} estrazioni\n")

    pages = 5 if backfill_days > 0 else 2
    posts = fetch_all_recent(max_pages=pages)
    print(f"\n[*] Totale post scaricati: {len(posts)}")

    if not posts:
        print("[!] Nessun post scaricato. Interrompo.")
        return

    save_debug("api_posts.json", posts)

    print(f"\n[*] Ultimi 10 post (data · titolo):")
    for p in posts[:10]:
        d = p.get("date", "?")
        t = strip_html(p.get("title", {}).get("rendered", ""))[:80]
        print(f"  • {d} · {t}")

    fetched = []
    today = datetime.now()

    if backfill_days > 0:
        print(f"\n[*] Backfill: ultimi {backfill_days} giorni")
        for i in range(backfill_days):
            data = today - timedelta(days=i)
            print(f"\n--- Giorno {i+1}/{backfill_days}: {data.strftime('%d/%m/%Y')} ---")
            ext = find_extraction_for_date(posts, data)
            if ext:
                fetched.append(ext)
                print(f"    ✓ concorso {ext.get('concorso')} · {ext['numeri']}")
            else:
                print(f"    ✗ nessun post per questa data")
    else:
        print(f"\n[*] Recupero oggi: {today.strftime('%d/%m/%Y')}")
        ext = find_extraction_for_date(posts, today)
        if ext:
            fetched.append(ext)
            print(f"    ✓ concorso {ext.get('concorso')} · {ext['numeri']}")
        else:
            print(f"    ✗ nessun post per oggi")

    print(f"\n=== RIEPILOGO ===")
    print(f"[*] Recuperate {len(fetched)} estrazioni")

    if not fetched:
        print("[!] Nessuna estrazione.")
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
