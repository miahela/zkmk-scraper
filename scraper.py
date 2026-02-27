#!/usr/bin/env python3
"""
ZK.MK Business Directory Scraper

Scrapes company listings from https://zk.mk/ (the Macedonian Golden Book directory).
Reads categories from a CSV file and writes scraped companies to CSV output.
"""

import argparse
import csv
import os
import random
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Fix Windows console encoding for Macedonian (Cyrillic) text
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


CSV_FIELDS = [
    'name', 'category', 'phone', 'phone2', 'fax', 'address',
    'city', 'activities', 'working_hours', 'website', 'company_url', 'zkid', 'priority',
]


@dataclass
class Company:
    name: str
    category: str
    phone: str = ''
    phone2: str = ''
    fax: str = ''
    address: str = ''
    city: str = ''
    activities: str = ''
    working_hours: str = ''
    website: str = ''
    company_url: str = ''
    zkid: str = ''

    def to_dict(self) -> Dict:
        return asdict(self)

    def is_valid(self) -> bool:
        return bool(self.name.strip())


class CategoryManager:
    """Loads categories from CSV and splits them into priority and regular groups."""

    # High-priority retail/trading categories (processed first in full mode)
    PRIORITY_KEYWORDS = [
        # Automotive
        'автомобили', 'автосалони', 'автомобилски куќи',
        'автомобилски резервни делови - трговија',
        'моторцикли', 'скутери - трговија', 'гуми', 'пневматици',
        # Electronics
        'компјутери', 'компјутерска опрема', 'мобилни телефони',
        'бела техника - продавници', 'апарати за домаќинство - продавници',
        'електроопрема - трговија', 'аудио-видео опрема - трговија',
        # Fashion
        'облека - продавници', 'обувки - продавници', 'бутици',
        'спортска опрема - продавници', 'накит - трговија',
        # Home & Construction
        'мебел - продавници', 'мебел - салони', 'градежни материјали',
        'алати - трговија', 'бои и лакови - трговија', 'керамика',
        # Health
        'аптеки', 'медицински препарати', 'медицински апарати и опрема',
        # Food
        'супермаркети', 'маркети', 'колонијали',
        'месо и сувомеснати производи', 'млеко и млечни производи',
        # Books & Office
        'книжарници', 'канцелариски материјали', 'биротехника',
        # Digital services
        'веб дизајн', 'програмирање', 'софтвер', 'рекламни агенции',
        'печатарски услуги', 'маркетинг', 'графички дизајн',
    ]

    def __init__(self, csv_file: str):
        self.categories: List[Dict] = []
        self.priority_categories: List[Dict] = []
        self.regular_categories: List[Dict] = []
        self._load(csv_file)
        self._split_priority()

    def _load(self, csv_file: str):
        seen: set = set()
        with open(csv_file, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                name = row.get('categories', '').strip()
                url = row.get('categories-href', '').strip()
                if name and url and (name, url) not in seen:
                    seen.add((name, url))
                    self.categories.append({'name': name, 'url': url})
        print(f'Loaded {len(self.categories)} unique categories')

    def _split_priority(self):
        for cat in self.categories:
            name_lower = cat['name'].lower()
            cat['priority'] = any(kw.lower() in name_lower for kw in self.PRIORITY_KEYWORDS)
            if cat['priority']:
                self.priority_categories.append(cat)
            else:
                self.regular_categories.append(cat)
        print(f'  {len(self.priority_categories)} high-priority, {len(self.regular_categories)} regular')


class CompanyExtractor:
    """Parses an HTML page and returns a list of Company records."""

    @staticmethod
    def from_html(html: str, category_name: str) -> List[Company]:
        soup = BeautifulSoup(html, 'html.parser')
        companies = []
        for div in soup.find_all('div', {'itemtype': 'http://schema.org/LocalBusiness'}):
            try:
                company = CompanyExtractor._parse(div, category_name)
                if company and company.is_valid():
                    companies.append(company)
            except Exception:
                continue
        return companies

    @staticmethod
    def _parse(div, category_name: str) -> Optional[Company]:
        name_link = div.find('a', class_='companyname') or div.find('a', href=True)
        if not name_link:
            return None

        name_span = name_link.find('span', {'itemprop': 'name'})
        name = (name_span or name_link).get_text(strip=True)
        if not name:
            return None

        phones = div.find_all('span', {'itemprop': 'telephone'})
        phone = phones[0].get_text(strip=True).replace('\u00a0', ' ') if phones else ''

        addr = div.find('span', {'itemprop': 'streetAddress'})
        city = div.find('span', {'itemprop': 'addressLocality'})

        return Company(
            name=name,
            category=category_name,
            phone=phone,
            address=addr.get_text(strip=True) if addr else '',
            city=city.get_text(strip=True) if city else '',
            company_url=name_link.get('href', ''),
            zkid=div.get('zkid', '') or div.get('id', ''),
        )

    @staticmethod
    def next_page_url(html: str) -> Optional[str]:
        """Return the next-page URL from the pagination block, or None."""
        soup = BeautifulSoup(html, 'html.parser')
        pagination = soup.find('div', class_='pagination')
        if not pagination:
            return None
        link = (
            pagination.find('a', string=re.compile(r'Следна'))
            or pagination.find('a', rel='next')
        )
        return link.get('href') if link and link.get('href') else None


class ZKMKScraper:
    """Orchestrates scraping of the ZK.MK directory."""

    BASE_URL = 'https://zk.mk'
    OUTPUT_CSV = 'zkmk_companies.csv'
    PRIORITY_CSV = 'priority_companies.csv'

    def __init__(self, categories_csv: str, delay: Tuple[float, float] = (1.0, 2.0)):
        self.categories = CategoryManager(categories_csv)
        self.delay = delay
        self._written: set = set()  # tracks which CSV files have had a header written
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'mk,mk-MK;q=0.9,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

    def _get(self, url: str, retries: int = 3) -> Optional[str]:
        if not url.startswith('http'):
            url = urljoin(self.BASE_URL, url)
        for attempt in range(retries):
            try:
                r = self.session.get(url, timeout=15)
                r.raise_for_status()
                r.encoding = 'utf-8'
                time.sleep(random.uniform(*self.delay))
                return r.text
            except requests.exceptions.RequestException:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        return None

    def _scrape_category(self, category: Dict) -> List[Company]:
        companies = []
        url = category['url']
        for _ in range(50):  # hard page limit per category
            html = self._get(url)
            if not html:
                break
            companies.extend(CompanyExtractor.from_html(html, category['name']))
            url = CompanyExtractor.next_page_url(html)
            if not url:
                break
            if not url.startswith('http'):
                url = urljoin(self.BASE_URL, url)
        return companies

    def _append_csv(self, path: str, companies: List[Company], priority_label: str):
        first_write = path not in self._written
        self._written.add(path)
        with open(path, 'w' if first_write else 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if first_write:
                writer.writeheader()
            for c in companies:
                row = c.to_dict()
                row['priority'] = priority_label
                writer.writerow(row)

    def _run_phase(self, cats: List[Dict], is_priority: bool) -> int:
        label = 'HIGH' if is_priority else 'REGULAR'
        total = 0
        start = datetime.now()
        for i, cat in enumerate(cats, 1):
            print(f'  [{i}/{len(cats)}] {cat["name"]}', end='', flush=True)
            companies = self._scrape_category(cat)
            if companies:
                self._append_csv(self.OUTPUT_CSV, companies, label)
                if is_priority:
                    self._append_csv(self.PRIORITY_CSV, companies, label)
                total += len(companies)
                print(f' -> {len(companies)} companies')
            else:
                print(' -> none found')

            if i % 10 == 0:
                elapsed = (datetime.now() - start).total_seconds()
                eta_h = (len(cats) - i) * (elapsed / i) / 3600
                print(f'  Progress: {i}/{len(cats)} | {total} companies | ~{eta_h:.1f}h remaining')

        return total

    def run(self, mode: str = 'full'):
        """
        mode='test'     : first 3 categories (smoke test)
        mode='priority' : high-priority retail/trading categories only
        mode='full'     : priority first, then all remaining (default)
        """
        if mode == 'test':
            cats = self.categories.categories[:3]
            print(f'TEST MODE — {len(cats)} categories\n')
            total = self._run_phase(cats, is_priority=False)
            print(f'\nDone. {total} companies -> {self.OUTPUT_CSV}')

        elif mode == 'priority':
            cats = self.categories.priority_categories
            print(f'PRIORITY MODE — {len(cats)} categories\n')
            total = self._run_phase(cats, is_priority=True)
            print(f'\nDone. {total} companies -> {self.OUTPUT_CSV}, {self.PRIORITY_CSV}')

        else:  # full
            cats_p = self.categories.priority_categories
            cats_r = self.categories.regular_categories

            print(f'PHASE 1 — {len(cats_p)} high-priority categories\n')
            p_total = self._run_phase(cats_p, is_priority=True)
            print(f'\nPhase 1 done. {p_total} companies -> {self.PRIORITY_CSV}\n')

            ans = input('Continue with remaining categories? [y/N]: ').strip().lower()
            if ans != 'y':
                print('Stopped.')
                return

            print(f'\nPHASE 2 — {len(cats_r)} remaining categories\n')
            r_total = self._run_phase(cats_r, is_priority=False)
            print(f'\nDone. {p_total + r_total} total companies -> {self.OUTPUT_CSV}')


def main():
    parser = argparse.ArgumentParser(
        description='Scrape company listings from the ZK.MK Macedonian business directory.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='\n'.join([
            'modes:',
            '  full      priority categories first, then all (default)',
            '  priority  high-priority retail/trading categories only',
            '  test      first 3 categories (quick smoke test)',
        ]),
    )
    parser.add_argument('--mode', choices=['full', 'priority', 'test'], default='full')
    parser.add_argument(
        '--categories', default='zlatna-kniga-categories.csv',
        help='path to the categories CSV (default: zlatna-kniga-categories.csv)',
    )
    parser.add_argument(
        '--delay', nargs=2, type=float, metavar=('MIN', 'MAX'), default=[1.0, 2.0],
        help='request delay range in seconds (default: 1.0 2.0)',
    )
    args = parser.parse_args()

    if not os.path.exists(args.categories):
        print(f"Error: '{args.categories}' not found.")
        sys.exit(1)

    print(f'ZK.MK Scraper | mode={args.mode} | delay={args.delay[0]}-{args.delay[1]}s\n')
    scraper = ZKMKScraper(args.categories, delay=tuple(args.delay))
    try:
        scraper.run(mode=args.mode)
    except KeyboardInterrupt:
        print('\nInterrupted.')


if __name__ == '__main__':
    main()
