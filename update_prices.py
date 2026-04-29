#!/usr/bin/env python3
"""
Scraper cen pohonných hmot z mBenzin.cz
Spouští se denně přes GitHub Actions, aktualizuje index.html
"""

import re
import sys
import json
import time
import urllib.request
from datetime import date

# Sítě a jejich URL na mBenzin.cz
NETWORKS = {
    'mol':     'MOL',
    'shell':   'Shell',
    'omv':     'OMV',
    'orlen':   'Orlen',
    'euroil':  'EuroOil',
    'tankono': 'Tank-ONO',
    'avia':    'Avia',
    'globus':  'Globus',
    'papoil':  'Papoil',
    'prim':    'Prim',
    'eurobit': 'Eurobit-Oil',
    'agropod': 'AGROPODNIK',
    'armex':   'ARMEX',
    'f1':      'ERNEKS',
}

BASE_URL = 'https://www.mbenzin.cz/Ceny-benzinu-a-nafty/Retezce/{}'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'cs-CZ,cs;q=0.9',
    'Referer': 'https://www.mbenzin.cz/',
}


def fetch_page(url: str) -> str:
    """Stáhne stránku a vrátí HTML."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='replace')


def parse_prices(html: str) -> dict:
    """
    Extrahuje průměrné ceny benzínu a nafty ze stránky mBenzin.cz.
    Hledá vzor: Benzín XX,XX | Nafta XX,XX v textu stránky.
    """
    # Odstraní HTML tagy
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)

    benzin = None
    nafta = None

    # Hledej "Benzín" nebo "Natural" následované číslem
    m = re.search(r'Benz[íi]n\s+(3[5-9]|4[0-5]),(\d{2})', text)
    if m:
        benzin = f"{m.group(1)},{m.group(2)}"

    # Hledej "Nafta" následovanou číslem
    m = re.search(r'Nafta\s+(3[5-9]|4[0-5]),(\d{2})', text)
    if m:
        nafta = f"{m.group(1)},{m.group(2)}"

    # Fallback: první dvě čísla ve formátu XX,XX v rozsahu cen paliv
    if not benzin or not nafta:
        all_prices = re.findall(r'\b(3[5-9]|4[0-5]),(\d{2})\b', text)
        valid = [f"{a},{b}" for a, b in all_prices]
        if not benzin and len(valid) >= 1:
            benzin = valid[0]
        if not nafta and len(valid) >= 2:
            nafta = valid[1]

    return {'benzin': benzin, 'nafta': nafta}


def scrape_all() -> dict:
    """Stáhne ceny pro všechny sítě."""
    results = {}
    for net_id, mbenzin_name in NETWORKS.items():
        url = BASE_URL.format(mbenzin_name)
        print(f"  Načítám {net_id} ({mbenzin_name})...", end=' ', flush=True)
        try:
            html = fetch_page(url)
            prices = parse_prices(html)
            results[net_id] = prices
            print(f"B={prices['benzin']} N={prices['nafta']}")
        except Exception as e:
            print(f"CHYBA: {e}")
            results[net_id] = {'benzin': None, 'nafta': None}
        time.sleep(1.5)  # Respektuj server
    return results


def update_html(prices: dict, html_path: str = 'index.html'):
    """Aktualizuje ceny v index.html."""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Mapa: net_id -> (pub_b field, pub_n field)
    # Hledáme vzor jako:  pub_b:42.10,  nebo  pub_b:null
    def to_js_num(price_str):
        if not price_str:
            return None
        return float(price_str.replace(',', '.'))

    updated = 0
    for net_id, p in prices.items():
        b = to_js_num(p.get('benzin'))
        n = to_js_num(p.get('nafta'))

        if b:
            # Nahraď pub_b:XX.XX nebo pub_b:null
            new_content = re.sub(
                rf"(id:'{net_id}'[^}}]+?)pub_b:[\d.]+",
                lambda m: m.group(1) + f"pub_b:{b}",
                content
            )
            if new_content != content:
                content = new_content
                updated += 1

        if n:
            new_content = re.sub(
                rf"(id:'{net_id}'[^}}]+?)pub_n:[\d.]+",
                lambda m: m.group(1) + f"pub_n:{n}",
                content
            )
            if new_content != content:
                content = new_content
                updated += 1

    # Aktualizuj datum poslední aktualizace cen v kódu
    today = date.today().strftime('%d. %m. %Y')
    content = re.sub(
        r'PUB: mBenzin\.cz[^<]*',
        f'PUB: mBenzin.cz · aktualizováno {today}',
        content
    )

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n✓ Aktualizováno {updated} hodnot v {html_path}")
    return updated


def main():
    html_path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    print(f"=== Aktualizace cen PHM – {date.today()} ===\n")
    print("Scrapuji mBenzin.cz...")
    prices = scrape_all()

    print("\nVýsledky:")
    for net_id, p in prices.items():
        print(f"  {net_id:10s}: benzin={p['benzin']:>6} | nafta={p['nafta']:>6}")

    print(f"\nAktualizuji {html_path}...")
    update_html(prices, html_path)
    print("\nHotovo!")


if __name__ == '__main__':
    main()
