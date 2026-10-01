"""
test_sources.py
Diagnostica multi-sorgente per AGIMEG.
Prova vari endpoint e logga tutto in modo da capire quale funziona.
TEMPORANEO — da cancellare dopo la diagnosi.
"""
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

import requests


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


def try_get(url, label, timeout=20):
    print(f"\n{'='*70}")
    print(f"### {label}")
    print(f"### URL: {url}")
    print('='*70)
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        print(f"STATUS: {r.status_code}")
        print(f"CONTENT-TYPE: {r.headers.get('Content-Type', '?')}")
        print(f"LEN: {len(r.text)}")
        print(f"PRIMI 800 CHAR:")
        print(r.text[:800])
        print(f"\nULTIMI 300 CHAR:")
        print(r.text[-300:])
        return r
    except Exception as e:
        print(f"ERRORE: {type(e).__name__}: {e}")
        return None


def main():
    print("=== DIAGNOSTICA MULTI-SORGENTE AGIMEG ===\n")
    print(f"Data: {datetime.now().isoformat()}\n")

    # 1) Sitemap index
    try_get("https://www.agimeg.it/sitemap_index.xml", "SITEMAP INDEX")

    # 2) Sitemap WordPress moderno
    try_get("https://www.agimeg.it/wp-sitemap.xml", "WP-SITEMAP")

    # 3) API REST WordPress
    try_get(
        "https://www.agimeg.it/wp-json/wp/v2/posts?search=super%20win%20for%20life&per_page=5&orderby=date&order=desc",
        "WP REST API (posts search)"
    )

    # 4) API REST categorie
    try_get(
        "https://www.agimeg.it/wp-json/wp/v2/categories?search=win+for+life",
        "WP REST API (categories search)"
    )

    # 5) Pagina categoria - ANALISI HREF
    print(f"\n{'='*70}")
    print("### ANALISI HREF nella categoria")
    print('='*70)
    try:
        r = requests.get(
            "https://www.agimeg.it/lotterie/win-for-life/",
            headers=HEADERS, timeout=20
        )
        html = r.text
        print(f"LEN: {len(html)}")

        # 5a) Href assoluti https
        pat_abs = re.compile(
            r'href="(https?://(?:www\.)?agimeg\.it/lotterie/win-for-life/[^"]+)"',
            re.IGNORECASE
        )
        abs_urls = pat_abs.findall(html)
        print(f"\n[HREF assoluti /lotterie/win-for-life/...]: {len(abs_urls)}")
        for u in abs_urls[:15]:
            print(f"  • {u}")

        # 5b) Href protocollo-relativi
        pat_rel = re.compile(
            r'href="(//(?:www\.)?agimeg\.it/lotterie/win-for-life/[^"]+)"',
            re.IGNORECASE
        )
        rel_urls = pat_rel.findall(html)
        print(f"\n[HREF protocollo-relativi //...]: {len(rel_urls)}")
        for u in rel_urls[:15]:
            print(f"  • {u}")

        # 5c) Href relativi assoluti path
        pat_path = re.compile(
            r'href="(/lotterie/win-for-life/[^"]+)"',
            re.IGNORECASE
        )
        path_urls = pat_path.findall(html)
        print(f"\n[HREF relativi /lotterie/win-for-life/...]: {len(path_urls)}")
        for u in path_urls[:15]:
            print(f"  • {u}")

        # 5d) Qualsiasi href con win-for-life
        pat_any = re.compile(r'href="([^"]*win-for-life[^"]*)"', re.IGNORECASE)
        any_urls = pat_any.findall(html)
        print(f"\n[HREF qualsiasi contenente 'win-for-life']: {len(any_urls)}")
        seen = set()
        for u in any_urls:
            if u not in seen:
                seen.add(u)
                print(f"  • {u}")
            if len(seen) >= 30:
                break

        # 5e) Cerca link <a> intorno a "Super Win for Life"
        print(f"\n[Ricerca pattern <a> intorno a 'Win for Life']")
        snippet_pat = re.compile(
            r'.{0,200}Win for Life.{0,200}',
            re.DOTALL | re.IGNORECASE
        )
        snippets = snippet_pat.findall(html)
        print(f"  Trovati {len(snippets)} snippet")
        for i, s in enumerate(snippets[:3], 1):
            clean = re.sub(r'\s+', ' ', s)
            print(f"  [{i}] {clean[:400]}")

    except Exception as e:
        print(f"ERRORE: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
