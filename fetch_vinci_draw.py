"""
fetch_vinci_draw.py
AURORA ENGINE — Raccolta estrazioni Super Win for Life da Sisal.

FIX (2026-09-22):
- Usa Playwright per simulare un browser reale e superare Cloudflare.
- Rimuove completamente AGIMEG come fonte.
- Parser ottimizzato per il rendering JavaScript di Sisal.

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

from playwright.sync_api import sync_playwright


HISTORY_FILE = "vinci_history.json"

# URL di Sisal da provare in cascata
SISAL_URLS = [
    "https://www.sisal.it/estrazioni/super-win-for-life",
    "https://www.sisal.it/super-win-for-life/estrazioni",
]

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
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    text = re.sub(r"&#\d+;", " ", text)
    return re.sub(r"\s+", " ", text)


# ==========================================
# PARSING UNIVERSALE
# ==========================================
def parse_extraction_from_text(text, target_date=None):
    """Cerca un'estrazione nel testo con 4 strategie a cascata."""
    text_clean = re.sub(r"\s+", " ", text)
    result = {}

    m = re.search(r"concorso\s*n[°.]?\s*(\d{1,4})", text_clean, re.IGNORECASE)
    if m:
        result["concorso"] = int(m.group(1))

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

    numbers = None

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

    if not numbers:
        m = re.search(r"((?:\d{1,2}\s*[–\-]\s*){7,}\d{1,2})", text_clean)
        if m:
            nums = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            unique = list(dict.fromkeys(nums))
            if len(unique) >= 8:
                numbers = unique[:8]
                print(f"    [S2] numeri trovati con separatore")

    if not numbers:
        for m in re.finditer(r"((?:\b\d{1,2}\b[\s,·]+){15,}\b\d{1,2}\b)", text_clean):
            nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", m.group(1))]
            nums = [n for n in nums if 1 <= n <= 90]
            unique = list(dict.fromkeys(nums))
            if len(unique) >= 8:
                numbers = unique[:8]
                print(f"    [S3] numeri trovati in blocco ampio")
                break

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
# FETCH CON PLAYWRIGHT
# ==========================================
def fetch_extraction(target_date):
    """Recupera l'estrazione da Sisal usando un browser headless."""
    print(f"\n{'=' * 60}")
    print(f"[*] Recupero estrazione del {target_date.strftime('%d/%m/%Y')}")
    print(f"{'=' * 60}")

    with sync_playwright() as p:
        # Avvia Chromium in modalità headless
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        for url in SISAL_URLS:
            print(f"[*] URL: {url}")
            try:
                # Naviga e aspetta che il JavaScript sia eseguito
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(3)  # piccola pausa per sicurezza

                html = page.content()
                text = clean_html(html)
                parsed = parse_extraction_from_text(text, target_date)

                if parsed and parsed.get("numeri"):
                    parsed["url"] = url
                    print(f"    ✓ Estrazione trovata: concorso {parsed.get('concorso')}")
                    browser.close()
                    return parsed

                print("    ✗ Numeri non trovati nella pagina.")
            except Exception as e:
                print(f"    ✗ Errore con Playwright: {e}")

            time.sleep(2)

        browser.close()

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
    print("=== AURORA ENGINE — FETCH VINCI DRAW (SISAL + PLAYWRIGHT) ===")

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
