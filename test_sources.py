"""
test_sources.py
Verifica che l'API di AGIMEG trovi gli articoli per numero concorso.
TEMPORANEO.
"""
import json
import re
import requests
from datetime import datetime


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.agimeg.it"


def search_concorso(n):
    """Cerca articoli che menzionano il concorso N."""
    url = (
        f"{BASE_URL}/wp-json/wp/v2/posts"
        f"?search=Super%20Win%20for%20Life%20concorso%20{n}"
        f"&per_page=10"
        f"&orderby=date"
        f"&order=desc"
    )
    print(f"\n{'='*70}")
    print(f"### SEARCH: concorso {n}")
    print(f"### URL: {url}")
    print('='*70)
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        print(f"STATUS: {r.status_code}")
        print(f"LEN: {len(r.text)}")
        posts = r.json()
        print(f"RISULTATI: {len(posts)}")
        for i, p in enumerate(posts, 1):
            title = re.sub(r"<[^>]+>", " ", p.get("title", {}).get("rendered", ""))
            title = re.sub(r"\s+", " ", title).strip()
            date = p.get("date", "?")
            link = p.get("link", "?")
            print(f"  [{i}] {date}")
            print(f"      {title[:100]}")
            print(f"      {link}")

            # Analizza contenuto
            content_html = p.get("content", {}).get("rendered", "")
            content_text = re.sub(r"<[^>]+>", " ", content_html)
            content_text = re.sub(r"\s+", " ", content_text)

            # Cerca pattern "concorso N"
            concorso_match = re.search(
                rf"concorso\s*n?\.?\s*{n}\b",
                content_text, re.IGNORECASE
            )
            print(f"      → 'concorso {n}' nel contenuto: {'SÌ' if concorso_match else 'no'}")

            # Cerca 8 numeri consecutivi
            seq = re.search(r"((?:\d{1,2}\s*[–\-·,]\s*){7}\d{1,2})", content_text)
            if seq:
                nums = [int(x) for x in re.findall(r"\d{1,2}", seq.group(1))]
                nums = [x for x in nums if 1 <= x <= 90]
                unique = list(dict.fromkeys(nums))
                print(f"      → sequenza 8 numeri: {unique[:8]}")
            else:
                print(f"      → nessuna sequenza di 8 numeri trovata")
        return posts
    except Exception as e:
        print(f"ERRORE: {type(e).__name__}: {e}")
        return []


def main():
    print("=== TEST SEARCH PER CONCORSO ===")
    print(f"Data: {datetime.now().isoformat()}")

    # I concorsi che ci interessano (dal 115 al 120)
    for n in [120, 119, 118, 117, 116, 115]:
        search_concorso(n)


if __name__ == "__main__":
    main()
