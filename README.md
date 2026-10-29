# ZK.MK Business Directory Scraper

Turns public ZK.MK category listings into CSV files for business research and spreadsheet workflows. It extracts company names, primary phone numbers, addresses, cities, listing links and directory IDs. Retail and trading categories can be processed first.

## Screenshot

`docs/screenshot.png` is a placeholder. Replace it with a terminal or spreadsheet screenshot from your own run, with contact details hidden.

![Screenshot placeholder](docs/screenshot.png)

## Run locally

Use Python 3.10 or newer. From this folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scraper.py --mode test --max-pages 1
```

The category CSV contains three public category names and URLs from `https://zk.mk/page/activities`, without company contact records. `samples/companies.csv` shows fake output data.

Use `--categories path\to\categories.csv` for another input with columns `categories` and `categories-href`. Use `--mode priority` for priority categories, or `--mode full` to process priority categories and then confirm whether to continue. The sample categories may have no priority matches.

## Configuration and output

`.env.example` documents optional environment variables. The script reads process environment variables; it does not load `.env` files automatically. Set them in PowerShell, for example `$env:ZKMK_OUTPUT = 'demo.csv'`, or use CLI options:

```powershell
.\.venv\Scripts\python.exe scraper.py --mode test --categories zlatna-kniga-categories.csv --output demo.csv --priority-output demo-priority.csv --delay 1 2 --max-pages 1
```

Each run replaces both output files, including when there are no results. Defaults are `zkmk_companies.csv` and `priority_companies.csv`. Output parent folders must already exist. Output paths must differ from each other and from the input CSV. Keep generated contact data out of version control.

The CSV includes `name`, `category`, `phone`, `address`, `city`, `company_url`, `zkid` and `priority`. Reserved columns `phone2`, `fax`, `activities`, `working_hours` and `website` are currently empty. Listing URLs are preserved as supplied by the page.

## Stack

Python, Requests, Beautiful Soup, and standard-library CSV and unittest modules.

## Known limits

For an empty live result, run `python scraper.py --mode test --max-pages 1 --debug`.
Request failures now show their error, and pages without parsed listings show their title.
Debug mode also shows HTTP status, final URL and response size, and saves fetched HTML as
`debug_page_1.html`, etc. These files are ignored by Git and replaced by later debug runs.
They can contain real contact details, so inspect them locally before sharing any excerpt.

- HTML selectors depend on the site's layout. A live check of the three sample categories returned 44 records with no duplicate name and phone pairs. Other categories and pagination still need live verification.
- Test mode uses up to three categories. Set `--max-pages 1` for a short live check; the default is 50 pages per category.
- Requests retry three times. A failed request or changed layout can produce an empty or partial CSV without a failing exit code. Warnings explain request failures or pages with no parsed listings. Inspect the output.
- Repeated pagination URLs stop the category. Companies in multiple categories can still appear more than once.
- Full mode asks for confirmation between phases and is not designed for unattended scheduling.
- There is no browser rendering, login, checkpoint or resume support. Only listing-page fields are extracted.
- Use appropriate delays and check the site's access rules before a larger collection.
