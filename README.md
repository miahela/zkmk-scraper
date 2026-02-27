# ZK.MK Business Directory Scraper

A Python scraper for [ZK.MK](https://zk.mk/) (Златна Книга / Golden Book), the Macedonian business directory. Extracts company names, contact details, and addresses across 2,197 business categories.

A previous full run collected **56,000+ company records** spanning tailors, automotive dealers, pharmacies, tech services, and everything in between.

## Data collected

| Field | Description |
|---|---|
| `name` | Company name |
| `category` | Business category |
| `phone` | Primary phone number |
| `address` | Street address |
| `city` | City |
| `company_url` | Relative URL on zk.mk |
| `zkid` | Internal directory ID |
| `priority` | `HIGH` for retail/trading categories, `REGULAR` otherwise |

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Full run — priority categories first, then all 2,197
python scraper.py

# Scrape only high-priority retail/trading categories
python scraper.py --mode priority

# Quick smoke test — first 3 categories only
python scraper.py --mode test

# Custom request delay (in seconds)
python scraper.py --delay 1.5 3.0
```

## Output

Results are written to `zkmk_companies.csv` as they are scraped. High-priority companies are also written to `priority_companies.csv`.

Each run starts with a fresh output file.

## Categories

Input categories are read from `zlatna-kniga-categories.csv` (2,197 categories). The file was collected from [zk.mk/page/activities](https://zk.mk/page/activities).

Categories are split into two groups:

- **High-priority** — retail and trading businesses (automotive, electronics, fashion, food, health, etc.) — processed first
- **Regular** — all remaining categories

## Sample output

```
name,category,phone,address,city,company_url
Емили фешн,абаџии,078 321493,Сутјеска лок.73,Штип,/emili-feshn?choice=0
Ирена ексклузив,абаџии,077 921191,Ванчо Прке 121/3,Штип,/irena-ekskluziv?choice=0
Крис-Кире,абаџии,070 594042,Сремски Фронт б.б,Штип,/kris-kire?choice=0
Аљма,абаџии,070 439867,Охридска 9,Тетово,/aljma?choice=0
Анаталија,абаџии,078 224971,Петар поп Арсов б.б.,Велес,/anatalija?choice=0
```

## Requirements

- Python 3.7+
- `requests`
- `beautifulsoup4`
