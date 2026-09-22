"""
fetch_vinci_draw.py
AURORA ENGINE — Raccolta estrazioni Super Win for Life da Sisal.

FIX (2026-09-22):
- Usa curl_cffi per impersonificare il fingerprint TLS di Chrome e bypassare Cloudflare.
- Rimuove completamente AGIMEG come fonte.
- Parser ottimizzato per la pagina di Sisal.

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

from curl_cffi import requests
from curl_cffi.requests.errors import RequestsError


HISTORY_FILE = "vinci_history.json"

# URL di Sisal da provare in cascata
SISAL_URLS = [
    "https://www.sisal.it/estrazioni/super-win-for-life",
    "https://www.sisal.it/super-win-for-life/estrazioni",
    "https://www.sisal.it/",
]

# Header "browser-like" (curl_cffi aggiunge il fingerprint TLS corretto)
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

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


def clean_html(html):
    """Rimuove tag HTML, script e style per ottenere solo il testo."""
    # Rimuovi script e style
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Rimuovi tag
    text = re.sub(r"<[^>]+>", " ", html)
    # Decodifica entità
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    text = re.sub(r"&#\d+;", " ", text)
    # Normalizza spazi
    return re.sub(r"\s+", " ", text)


# ==========================================
# FETCH CON CURL_CFFI
# ==========================================
def fetch_url(url, timeout=30):
    """Fetch URL con curl_cffi (impersona Chrome)."""
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            impersonate="chrome124",  # Fingerprint TLS di Chrome 124
            timeout=timeout,
        )
        r.raise_for_status()
        return r.text
    except RequestsError as e:
        print(f"    ✗ errore curl_cffi: {e}")
        return None
    except Exception as e:
        print(f"    ✗ errore: {e}")
        return None


# ==========================================
# PARSING UNIVERSALE
# ==========================================
def parse_extraction_from_text(text, target_date=None):
    """
    Cerca un'estrazione nel testo con 4 strategie a cascata.
    """
    text_clean = re.sub(r"\s+", " ", text)
    result = {}

    # --- CONCORSO ---
    m = re.search(r"concorso\s*n[°.]?\s*(\d{1,4})", text_clean, re.IGNORECASE)
    if m:
        result["concorso"] = int(m.group(1))

    # --- DATA ---
    if target_date:
        result["data"] = target_date.strftime("%d/%m/%Y")
    else:
        m = re.search(
            r"(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})",
            text_clean, re.IGNORECASE
        )
        if m:
            giorno = int(m.group(1))
            mese = MESI_IT[m.group(2).lower()]
            anno = int(m.group(3))
            result["data"] = f"{giorno:02d}/{mese:02d}/{anno}"

    # --- NUMERI (4 strategie) ---
    numbers = None

    # S1: "è: 5 – 8 – 17..." o "vincente: 5, 8, ..."
    if not numbers:
        m = re.search(
            r"(?:è|sono|vincente|estratti|combinazione)[\s:]*((?:\d{1,2}\s*[–\-·,]\s*){7}\d{1,2})",
            text_clean, re.IGNORECASE
        )
        if m:
            nums = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            unique = list(dict.fromkeys(nums))
            if len(unique) >= 8:
                numbers = unique[:8]
                print(f"    [S1] numeri trovati con contesto")

    # S2: sequenza di 8+ numeri con separatore – o -
    if not numbers:
        m = re.search(r"((?:\d{1,2}\s*[–\-]\s*){7,}\d{1,2})", text_clean)
        if m:
            nums = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            unique = list(dict.fromkeys(nums))
            if len(unique) >= 8:
                numbers = unique[:8]
                print(f"    [S2] numeri trovati con separatore")

    # S3: blocco di 20+ numeri 1-90 consecutivi
    if not numbers:
        for m in re.finditer(r"((?:\b\d{1,2}\b[\s,·]+){15,}\b\d{1,2}\b)", text_clean):
            nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            unique = list(dict.fromkeys(nums))
            if len(unique) >= 8:
                numbers = unique[:8]
                print(f"    [S3] numeri trovati in blocco ampio")
                break

    # S4: keyword "numeri" + prendi 8 dopo
    if not numbers:
        m = re.search(r"numeri.{0,200}", text_clean, re.IGNORECASE)
        if m:
            chunk = m.group(0)
            nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", chunk)]
            nums = [n for n in nums if 1 <= n <= 90]
            unique = list(dict.fromkeys(nums))
            if len(unique) >= 8:
                numbers = unique[:8]
                print(f"    [S4] numeri trovati dopo keyword")

    if numbers:
        result["numeri"] = numbers
        return result

    return None


# ==========================================
# FETCH SISAL
# ==========================================
def fetch_extraction(target_date):
    """
    Prova a recuperare l'estrazione da Sisal.
    """
    print(f"\n{'=' * 60}")
    print(f"[*] Recupero estrazione del {target_date.strftime('%d/%m/%Y')}")
    print(f"{'=' * 60}")

    for url in SISAL_URLS:
        print(f"[*] URL: {url}")
        html = fetch_url(url)
        if not html:
            continue

        text = clean_html(html)
        parsed = parse_extraction_from_text(text, target_date)

        if parsed and parsed.get("numeri"):
            parsed["url"] = url
            print(f"    ✓ Estrazione trovata su Sisal: concorso {parsed.get('concorso')}")
            return parsed

        print("    ✗ Numeri non trovati nella pagina.")
        time.sleep(2)

    print("[!] Sisal non raggiungibile o dati non trovati.")
    return None


# ==========================================
# MERGE
# ==========================================
def merge_history(existing, fetched):
    existing_ids = {e.get("concorso") for e in existing
                    if isinstance(e.get("concorso"), int)}

    new_items = []
    for e in fetched:
        if e.get("concorso") not in existing_ids:
            new_items.append(e)

    return existing + new_items, len(new_items)


def sort_chronological(history):
    def sort_key(x):
        try:
            dt = datetime.strptime(x.get("data", ""), "%d/%m/%Y")
            return (dt.year, dt.month, dt.day)
        except Exception:
            return (0, 0, 0)
    return sorted(history, key=sort_key)


# ==========================================
# MAIN
# ==========================================
def main():
    print("=== AURORA ENGINE — FETCH VINCI DRAW (SISAL) ===")

    backfill_days = 0
    if len(sys.argv) > 2 and sys.argv[1] == "--backfill":
        try:
            backfill_days = int(sys.argv[2])
        except ValueError:
            print("[!] --backfill richiede un numero.")
            sys.exit(1)

    history = load_history()
    print(f"[*] Storico attuale: {len(history)} estrazioni")

    fetched = []
    today = datetime.now()

    if backfill_days > 0:
        print(f"[*] Backfill: ultimi {backfill_days} giorni")
        for i in range(backfill_days):
            data = today - timedelta(days=i)
            extracted = fetch_extraction(data)
            if extracted:
                fetched.append(extracted)
                print(f"    ✓ Concorso {extracted.get('concorso')}: "
                      f"{extracted['numeri']}")
            time.sleep(2)
    else:
        extracted = fetch_extraction(today)
        if extracted:
            fetched.append(extracted)
            print(f"    ✓ Concorso {extracted.get('concorso')}: "
                  f"{extracted['numeri']}")

    if not fetched:
        print("[!] Nessuna estrazione recuperata.")
        return

    print(f"\n[*] Recuperate {len(fetched)} estrazioni")

    merged, added = merge_history(history, fetched)
    if added > 0:
        merged = sort_chronological(merged)
        save_history(merged)
        print(f"[+] Aggiunte {added} nuove. Totale: {len(merged)}")
    else:
        print("[*] Nessuna nuova estrazione.")


if __name__ == "__main__":
    main()
