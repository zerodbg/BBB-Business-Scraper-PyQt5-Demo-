# 🔎 BBB Business Scraper — Demo (PyQt5 + SeleniumBase + BeautifulSoup)

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python%203-blue?style=for-the-badge" alt="Python"/>
  <img src="https://img.shields.io/badge/UI-PyQt5-green?style=for-the-badge" alt="PyQt5"/>
  <img src="https://img.shields.io/badge/Scraping-SeleniumBase-orange?style=for-the-badge" alt="SeleniumBase"/>
  <img src="https://img.shields.io/badge/License-MIT-lightgrey?style=for-the-badge" alt="License"/>
</p>

> **Demo project** showing how to extract business owner info, address, start year and to follow-up with people search results by combining **SeleniumBase** + **BeautifulSoup** + a small GUI powered by **PyQt5**.  
> Not complete — intended as an example and starting point for practical web data extraction workflows.

---

## 🔥 What this project does (summary)

- Crawls BBB (Better Business Bureau) search results to collect business pages.
- Fetches a BBB business page using SeleniumBase (headless browser).
- Extracts owner/principal contact lines from “Additional Contact Information”.
- Extracts address, business name, and business start year.
- Uses a people-search API (via `scrape.do` endpoint) to attempt to locate owner profiles.
- Demonstrates streaming LLM usage to extract owner/title from page text (local LLM endpoint in the example).
- Saves results to `people.csv` (demo limits to first 3 businesses for speed).

**Keywords:** BBB scraper, business contact extraction, web scraping example, PyQt5 GUI, SeleniumBase, BeautifulSoup, scrape.do, truepeoplesearch.

---

## 📂 Files & structure

```
.
├── scraper_demo.py          # Main script (the code you provided)
├── UI/
│   └── app.ui               # Qt Designer UI file used by PyQt5 (expected)
├── assets/
│   └── Ui.png       # optional background used by UI
└── README.md                # this file
```

---

## ⚙️ Requirements

Install the Python packages used in the demo:

```bash
pip install PyQt5 seleniumbase beautifulsoup4 requests pandas lxml
```

> Note: `seleniumbase` has additional driver and browser dependencies. See SeleniumBase docs if you need to support multiple browsers. The script sets environment variables to control driver locations.

---

## 🧭 Quick start (run demo)

1. Clone the repo and open the folder:

```bash
git clone https://github.com/zerodbg/BBB-Business-Scraper-PyQt5-Demo-.git
cd bbb-scraper-demo
```

2. Install required packages (see above).

3. Ensure UI resources exist:
- `UI/app.ui` must be present (Qt Designer .ui file the code loads).
- Optional: `assets/background.png` and `icon.ico` for a nicer UI look.

4. Configure keys/endpoints inside the script if needed:
- `SCRAPEDO_API_KEY` variable (example key is used in code — replace with your own).
- Local LLM endpoint used for `get_owner_by_llm`: `http://localhost:11434/api/chat`. Adjust if you use a different model/service.

5. Run the demo:

```bash
python scraper_demo.py
```

The PyQt5 window will appear. Enter search keywords and a state (e.g., `Plumbing` and `Las Vegas`), then click `Run`. The demo collects a small number of businesses and shows found people in the text box and writes `people.csv`.

---

## 🔍 How it works (important functions)

- `get_urls(search_keywords, state)` — Uses SeleniumBase to perform a BBB search and collects business page links by paginating results.
- `crawl_bbb_business(url)` — Fetches BBB page HTML (via `fetch_bbb_page`) and extracts:
  - `parse_owner_title_from_html(html)` — Finds owner/principal contact lines from the "Additional Contact Information" block.
  - `get_address`, `get_business_name`, `get_start_year` — Simple extractors that use BeautifulSoup.
- `run_demo(bbb_url, scrapedo_key)` — Tries BBB page extraction; if no owner found, sends page text to local LLM endpoint to extract owner/title; then queries `scrape.do`/`truepeoplesearch` to find people profiles and their details.
- `get_person_details(person_id, token, bname, start_date, position)` — Uses scrape.do to fetch person profile page and extracts name, age, phones, emails, address, etc.

---

## ⚠️ Legal & ethical notice (READ THIS)

This repository is a **technical example**. **Do not** use it to collect, store, or process personal data in ways that violate privacy laws (GDPR, CCPA, etc.) or website Terms of Service.

- Respect robots.txt and site scraping policies.
- Do not harvest PII or re-use personal contact details for spam or abusive activities.
- Many websites (including consumer people-search providers) restrict scraping; use APIs where available and obtain permission.
- This code includes examples of scraping `bbb.org` and `truepeoplesearch` — use responsibly and only for lawful, permitted use-cases (e.g., research, compliance checks, permitted aggregation).

---

## 🛠 Tips & notes

- **SeleniumBase**: By default this demo uses `SB(uc=True, headless=True)` for `fetch_bbb_page`. On some pages heavy JS or bot protections may require non-headless mode or proper browser profiles.
- **Driver paths**: The script sets `SELENIUMBASE_DRIVER_PATH` and `SELENIUMBASE_DRIVER_DIR`. Keep these or configure your own to avoid repeated driver downloads.
- **Rate limits**: If you run many queries, add `time.sleep()` between requests and implement retries/backoff.
- **Local LLM**: `get_owner_by_llm()` expects a streaming API at `http://localhost:11434/api/chat` returning JSON lines — adjust to your LLM/server config or remove if not used.
- **Scrape.do**: This project uses the `scrape.do` wrapper in examples — replace with your own proxy/API provider or direct requests if you have permission.
- **PyInstaller**: `resource_path()` helper is included so you can package the app with PyInstaller and still load bundled images/UI assets. Example build:

```bash
pyinstaller --onefile --add-data "UI/app.ui;UI" --add-data "assets/background.png;assets" scraper_demo.py
```

---

## ✅ Example output (sample CSV columns)

`people.csv` will contain rows similar to:

```
Name,Age,Position,Address,City,State,Business Name,Business Start Date,Phone 0,Email 0,...
```

---

## 🧭 Roadmap (ideas / TODOs)

- ✅ Make example GUI & threaded scraping worker (done).
- ⬜ Add robust error handling & logging to file.
- ⬜ Make configurable rate limits and retry/backoff strategies.
- ⬜ Add unit tests for parsing functions.
- ⬜ Support optional proxy pool & residential IPs for tougher targets.
- ⬜ Replace scrape.do demo calls with pluggable provider interface.
- ⬜ Add sample fixtures and `.env` support for keys.

---

## ❤️ Contributing

This repo is a demo — feel free to fork and send PRs. If you improve parsing rules, error handling, or privacy-preserving features, please submit a PR with tests and a description.

---

## Contact / Credits

Made as a scraping & GUI demo. If you want me to:
- add a **recorded demo GIF** for the README,
- create a polished **packaged exe** with PyInstaller, or
- harden the parsing for specific BBB layouts,

tell me which one and I’ll draft it.

---
