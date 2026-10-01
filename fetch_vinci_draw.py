"""
fetch_vinci_draw.py
AURORA ENGINE — Raccolta estrazioni Super Win for Life da AGIMEG.

APPROCCIO v4 (2026-10-01):
- FONTE PRIMARIA: feed RSS WordPress
  (https://www.agimeg.it/lotterie/win-for-life/feed/)
  → contiene ultimi ~10-15 articoli con pubDate, title, link
- FONTE SECONDARIA: pagina categoria HTML (fallback, con regex migliorata)

Uso:
    python fetch_vinci_draw.py              # recupera oggi
    python fetch_vinci_draw.py --backfill 30
"""
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

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
CATEGORY_URL = f"{BASE_URL}/lotterie/win-for-life/"
FEED_URL = f"{BASE_URL}/lotterie/win-for-life/feed/"

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


# ==========================================
# RSS PARSER
# ==========================================
def fetch_feed_items():
    """
    Scarica il feed RSS e ritorna lista di dict con:
    {title, link, pubdate_dt, description}
    """
    print(f"\n[*] FONTE 1: feed RSS")
    xml = fetch_url(FEED_URL)
    if not xml:
        return []

    save_debug("feed.xml", xml)

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        print(f"    ✗ Errore parsing XML: {e}")
        return []

    items = []
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")
        desc_el = item.find("description")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        pubdate_str = pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else ""
        desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

        pubdate_dt = None
        if pubdate_str:
            try:
                pubdate_dt = parsedate_to_datetime(pubdate_str)
            except Exception:
                pass

        items.append({
            "title": title,
            "link": link,
            "pubdate_str": pubdate_str,
            "pubdate_dt": pubdate_dt,
            "description": desc,
        })

    print(f"  [feed] {len(items)} item nel feed")
    for i, it in enumerate(items[:15], 1):
        pd = it["pubdate_dt"].strftime("%d/%m/%Y") if it["pubdate_dt"] else "?"
        print(f"    [{i}] {pd} · {it['title'][:80]}")
        print(f"         {it['link']}")

    return items


def find_feed_item_for_date(items, data):
    """Trova l'item del feed la cui pubdate corrisponde alla data target."""
    target = data.date()
    for it in items:
        if it["pubdate_dt"] is None:
            continue
        if it["pubdate_dt"].date() == target:
            return it
    return None


# ==========================================
# HTML PARSER (fallback)
# ==========================================
def extract_article_urls_from_category(html):
    """Regex migliorata: cattura slug di primo livello, esclude feed/page."""
    pattern = re.compile(
        r'href="(https?://(?:www\.)?agimeg\.it/lotterie/win-for-life/[^"]+)"',
        re.IGNORECASE
    )
    urls = pattern.findall(html)
    filtered = []
    for u in urls:
        if '/feed' in u:
            continue
        if '/page/' in u:
            continue
        if u.rstrip("/") == CATEGORY_URL.rstrip("/"):
            continue
        if not u.endswith("/"):
            u = u + "/"
        filtered.append(u)
    # dedup
    seen = set()
    unique = []
    for u in filtered:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def url_matches_date(url, data):
    """Verifica se l'URL contiene la data target in uno dei formati noti."""
    u_lower = url.lower()
    giorno = data.day
    mese_num = data.month
    mese_nome = MESI_IT_INV[mese_num]
    anno = data.year
    mese_abbr_list = [k for k, v in MESI_ABBR.items() if v == mese_num]
    mese_abbr = mese_abbr_list[0] if mese_abbr_list else ""

    patterns = [
        f"{giorno}-{mese_nome}-{anno}",
        f"{giorno:02d}-{mese_nome}-{anno}",
        f"{giorno}-{mese_abbr}-{anno}",
        f"{giorno:02d}-{mese_abbr}-{anno}",
        f"{giorno:02d}-{mese_num:02d}-{anno}",
        f"{giorno}-{mese_num}-{anno}",
        f"{anno}/{mese_num:02d}/{giorno:02d}",
        f"{anno}-{mese_num:02d}-{giorno:02d}",
    ]
    for p in patterns:
        if p in u_lower:
            return True
    return False


def find_article_url_via_category(data):
    """Fallback: naviga la categoria HTML e cerca articolo per data."""
    print(f"\n[*] FONTE 2 (fallback): categoria HTML")
    html = fetch_url(CATEGORY_URL)
    if not html:
        return None

    date_tag = data.strftime("%Y%m%d")
    save_debug(f"category_{date_tag}.html", html)

    urls = extract_article_urls_from_category(html)
    print(f"  [category] {len(urls)} URL articoli trovati")
    for i, u in enumerate(urls[:20], 1):
        print(f"    [{i}] {u}")

    for u in urls:
        if url_matches_date(u, data):
            print(f"  [category] ✓ match: {u}")
            return u

    return None


# ==========================================
# PARSING ARTICOLO
# ==========================================
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
        r"(\d{1,2})\s+"
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


def fetch_extraction_for_date(data):
    """
    Recupera l'estrazione per una data:
    1. Tenta il feed RSS
    2. Fallback: categoria HTML
    """
    print(f"\n[*] Data target: {data.strftime('%d/%m/%Y')}")

    # --- FONTE 1: feed RSS ---
    items = fetch_feed_items()
    item = find_feed_item_for_date(items, data)

    article_url = None
    if item:
        print(f"  [feed] ✓ match: {item['link']}")
        article_url = item["link"]
    else:
        print(f"  [feed] ✗ nessun match nel feed")

    # --- FONTE 2: fallback categoria ---
    if not article_url:
        article_url = find_article_url_via_category(data)

    if not article_url:
        print(f"    ✗ Nessun articolo trovato per {data.strftime('%d/%m/%Y')}")
        return None

    # --- Fetch articolo ---
    html = fetch_url(article_url)
    if not html:
        return None

    date_tag = data.strftime("%Y%m%d")
    save_debug(f"article_{date_tag}.html", html)

    parsed = parse_article(html, verbose=True)
    if not parsed.get("numeri"):
        print(f"    ✗ Parsing numeri fallito")
        print(f"    [debug] parsed parziale: {parsed}")
        return None

    parsed["url"] = article_url
    parsed["data"] = parsed.get("data") or data.strftime("%d/%m/%Y")
    print(f"    ✓ Risultato: concorso={parsed.get('concorso')} "
          f"data={parsed.get('data')} numeri={parsed['numeri']}")
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
    print("=== AURORA ENGINE — FETCH VINCI DRAW (v4) ===\n")

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

    # Per ottimizzare: fetch del feed UNA VOLTA, poi uso per tutti i giorni
    global FEED_CACHE
    if backfill_days > 0:
        print(f"[*] Backfill: ultimi {backfill_days} giorni")
        # Pre-fetch feed una sola volta
        FEED_CACHE = fetch_feed_items()
        for i in range(backfill_days):
            data = today - timedelta(days=i)
            print(f"\n--- Giorno {i+1}/{backfill_days} ---")
            extracted = fetch_extraction_for_date(data)
            if extracted:
                fetched.append(extracted)
            time.sleep(1)
    else:
        print(f"[*] Recupero oggi: {today.strftime('%d/%m/%Y')}")
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


FEED_CACHE = None


if __name__ == "__main__":
    main()
