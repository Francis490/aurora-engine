"""
fetch_vinci_draw.py
AURORA ENGINE — Raccolta estrazioni Super Win for Life da Sisal.

FIX (2026-09-22 v2):
- Aggiunti argomenti anti-detection (--disable-blink-features=AutomationControlled)
- Forzato HTTP/1.1 (--disable-http2) per bypassare Cloudflare
- Init script per nascondere navigator.webdriver
- Cambio wait_until: da "networkidle" a "domcontentloaded" + attesa
- User-agent + headers realistici

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
# USER-AGENT E HEADERS REALISTICI
# ==========================================
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

EXTRA_HEADERS = {
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}

# Script iniettato PRIMA del caricamento pagina:
# nasconde navigator.webdriver (rileva automation)
INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['it-IT', 'it', 'en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
"""


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
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    text = re.sub(r"&#\d+;", " ", text)
    return re.sub(r"\s+", " ", text)


# ==========================================
# PARSING
# ==========================================
def parse_extraction_from_text(text, target_date=None):
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
# FETCH CON PLAYWRIGHT + ANTI-DETECTION
# ==========================================
def fetch_extraction(target_date):
    print(f"\n{'=' * 60}")
    print(f"[*] Recupero estrazione del {target_date.strftime('%d/%m/%Y')}")
    print(f"{'=' * 60}")

    with sync_playwright() as p:
        # Argomenti anti-detection + forza HTTP/1.1
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-http2",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--window-size=1920,1080",
            ],
        )

        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="it-IT",
            timezone_id="Europe/Rome",
            extra_http_headers=EXTRA_HEADERS,
        )

        # Nasconde navigator.webdriver prima del caricamento pagina
        context.add_init_script(INIT_SCRIPT)

        page = context.new_page()

        for url in SISAL_URLS:
            print(f"[*] URL: {url}")
            try:
                # "domcontentloaded" invece di "networkidle" (Cloudflare non chiude mai la rete)
                page.goto(url, wait_until="domcontentloaded", timeout=45000)

                # Attesa extra per JS dinamico (pallini numeri)
                page.wait_for_timeout(5000)

                # Scrolla per triggerare lazy-loading
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)

                html = page.content()
                print(f"    [debug] HTML scaricato: {len(html)} byte")

                text = clean_html(html)
                parsed = parse_extraction_from_text(text, target_date)

                if parsed and parsed.get("numeri"):
                    parsed["url"] = url
                    print(f"    ✓ Estrazione trovata: concorso {parsed.get('concorso')}")
                    browser.close()
                    return parsed

                print("    ✗ Numeri non trovati nella pagina.")
                # Debug: mostra un estratto del testo
                if len(text) > 300:
                    print(f"    [debug] Estratto: {text[:300]}...")

            except Exception as e:
                print(f"    ✗ Errore Playwright: {str(e)[:150]}")

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
    print("=== AURORA ENGINE — FETCH VINCI DRAW (SISAL + PLAYWRIGHT v2) ===")

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
