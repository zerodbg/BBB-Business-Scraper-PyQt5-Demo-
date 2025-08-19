import sys
from PyQt5.QtGui import QPixmap, QPalette, QBrush, QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QProgressBar
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5 import uic
import requests
import re
import pandas as pd
import json
import asyncio
import time

from seleniumbase import SB
from bs4 import BeautifulSoup
import os, tempfile
# Optional: force a known location for drivers
os.environ["SELENIUMBASE_DRIVER_PATH"] = os.path.join(os.path.expanduser("~"), ".seleniumbase", "drivers")

os.environ["SELENIUMBASE_DRIVER_DIR"] = os.path.join(tempfile.gettempdir(), "seleniumbase_drivers")

#https://stackoverflow.com/questions/31836104/pyinstaller-and-onefile-how-to-include-an-image-in-the-exe-file
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS # pylint: disable=no-member
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

POSSIBLE_TITLES = ["owner", "president", "ceo", "founder"]


def fetch_bbb_page(url):
    with SB(uc=True, headless=True) as sb:
        sb.open(url)
        sb.wait_for_ready_state_complete(30)
        content = sb.get_page_source()
        return content


def parse_owner_title_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    # Search for label elements containing possible titles
    owner_info = []

    # Find the section with heading 'Additional Contact Information'
    sections = soup.find_all("div", class_="bpr-details-section stack")

    for section in sections:
        heading = section.find("h3", class_="bds-body bpr-details-section-heading")
        if heading and "Additional Contact Information" in heading.text:
            # In this section, find all <dt> and corresponding <dd> pairs
            dl = section.find("dl", class_="bpr-details-dl stack")
            if not dl:
                continue
            for div_data in dl.find_all("div", class_="bpr-details-dl-data"):
                dt = div_data.find("dt")
                if not dt:
                    continue
                label = dt.text.strip()
                # We are interested in Principal Contacts or Customer Contacts
                if label in ["Principal Contacts", "Customer Contacts"]:
                    # There can be multiple <dd> under this div
                    dds = div_data.find_all("dd")
                    for dd in dds:
                        text = dd.get_text(separator=" ", strip=True)
                        # text example: "Roderick Mays, Owner"
                        owner_info.append(text)
    if owner_info:
        return {f"owner{idx}": owner for idx, owner in enumerate(owner_info)}
    return None


def get_address(html):
    soup = BeautifulSoup(html, "html.parser")
    address = soup.find('div', class_='bpr-overview-address').text
    return address


def get_business_name(html):
    soup = BeautifulSoup(html, "html.parser")
    bname = soup.find('span', {"id": 'businessName'}).text
    return bname


def get_start_year(html):
    start_date = None
    soup = BeautifulSoup(html, "html.parser")
    raw_divs = soup.find_all('div', {"class": 'bpr-details-dl-data'})
    for div in raw_divs:
        if "Business Started:" in div.text:
            start_date = div.find('dd').text
    return start_date


async def crawl_bbb_business(url):
    html = fetch_bbb_page(url)
    result = parse_owner_title_from_html(html)
    address = get_address(html)
    bname = get_business_name(html)
    start_date = get_start_year(html)
    return html, result, address, bname, start_date


class ScrapingWorker(QThread):
    """Worker thread for scraping operations"""
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    result_updated = pyqtSignal(str)
    business_count_updated = pyqtSignal(int)
    finished_scraping = pyqtSignal(list)

    def __init__(self, search_keywords, state, scrapedo_key, parent_app):
        super().__init__()
        self.search_keywords = search_keywords
        self.state = state
        self.scrapedo_key = scrapedo_key
        self.parent_app = parent_app

    def run(self):
        persons = []

        try:
            # Step 1: Get business URLs
            self.status_updated.emit("Getting business URLs...")
            self.progress_updated.emit(10)

            business_urls = self.parent_app.get_urls(
                search_keywords=self.search_keywords,
                state=self.state
            )

            self.status_updated.emit(f"Found {len(business_urls)} business URLs")
            self.business_count_updated.emit(len(business_urls))
            self.progress_updated.emit(20)

            if not business_urls:
                self.status_updated.emit("No business URLs found")
                self.finished_scraping.emit([])
                return

            # Step 2: Process each business (limit to first 3 for demo)
            urls_to_process = business_urls[:3]
            total_urls = len(urls_to_process)

            for i, url in enumerate(urls_to_process):
                try:
                    self.status_updated.emit(f"Processing business {i + 1}/{total_urls}...")

                    people = asyncio.run(self.parent_app.run_demo(url, self.scrapedo_key))

                    if people:
                        self.status_updated.emit(f"Found {len(people)} people from business {i + 1}")
                        for p in people:
                            self.result_updated.emit(str(p))
                        persons.extend(people)
                    else:
                        self.status_updated.emit(f"No people found for business {i + 1}")

                    # Update progress (20% for URL collection, 80% for processing)
                    progress = 20 + int((i + 1) / total_urls * 80)
                    self.progress_updated.emit(progress)

                except Exception as e:
                    self.status_updated.emit(f"Error processing business {i + 1}: {str(e)}")
                    continue

            # Step 3: Save results
            if persons:
                self.status_updated.emit("Saving results to CSV...")
                pd.DataFrame(persons).drop_duplicates().to_csv('people.csv', index=False)
                self.status_updated.emit(f"Completed! Saved {len(persons)} records to people.csv")
            else:
                self.status_updated.emit("No data to save")

            self.progress_updated.emit(100)
            self.finished_scraping.emit(persons)

        except Exception as e:
            self.status_updated.emit(f"Error: {str(e)}")
            self.finished_scraping.emit([])


class AppDemo(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi(resource_path('UI\\app.ui'), self)

        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        # Existing UI elements
        self.line1 = self.lineEdit_search_keywords
        self.line3 = self.lineEdit_state
        self.text_area = self.textEdit_results
        self.text_area.setStyleSheet("""
            background-color: rgba(0, 0, 0, 200);
            color: grey;   /* Set text color to contrast with background */
            border: 1px solid white; /* optional */
        """)
        self.business_count_text = self.textEdit_count
        self.business_count_text.setStyleSheet("""
                    background-color: rgba(0, 0, 0, 200);
                    color: grey;   /* Set text color to contrast with background */
                    border: 1px solid white; /* optional */
                """)
        self.pushButton_run.clicked.connect(self.run_all)
        self.pushButton_run.setDisabled(True)
        self.line1.textChanged.connect(self.check_input)
        self.line3.textChanged.connect(self.check_input)
        self.setWindowTitle("BBB.org Business Scraper")

        # Try to load background image, with fallback if file doesn't exist
        try:
            oImage = QPixmap(resource_path("assets\\background.png"))
            if not oImage.isNull():
                sImage = oImage.scaled(self.size())  # Scale to window size
                palette = QPalette()
                palette.setBrush(QPalette.Window, QBrush(sImage))
                self.setPalette(palette)
        except Exception as e:
            print(f"Could not load background image: {e}")

        # Add progress bar from UI file
        self.progress_bar = self.progressBar
        self.progress_bar.setVisible(False)  # Hidden by default

        # Style the progress bar
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                background-color: rgba(255, 255, 255, 100);
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)

        self.SCRAPEDO_API_KEY = "token"

        # Worker thread
        self.worker = None

    def printValue(self):
        print(self.lineEdit_country.text())

    def check_input(self):
        text1, text2 = self.line1.text().strip(), self.line3.text().strip()
        if text1 and text2:
            self.pushButton_run.setDisabled(False)
        else:
            self.pushButton_run.setDisabled(True)

    def run_all(self):
        search_keywords = self.line1.text().strip()
        state = self.line3.text().strip()

        if not all([search_keywords, state]):
            return

        # Disable the run button and show progress bar
        self.pushButton_run.setDisabled(True)
        self.pushButton_run.setText("Running...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Clear previous results
        self.text_area.clear()
        self.business_count_text.clear()

        # Create and start worker thread
        self.worker = ScrapingWorker(search_keywords, state, self.SCRAPEDO_API_KEY, self)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.status_updated.connect(self.update_status)
        self.worker.result_updated.connect(self.add_result)
        self.worker.business_count_updated.connect(self.update_business_count)
        self.worker.finished_scraping.connect(self.on_scraping_finished)

        self.worker.start()

    def update_progress(self, value):
        """Update progress bar value"""
        self.progress_bar.setValue(value)

    def update_status(self, message):
        """Update status (you can display this in a label or the text area)"""
        print(f"Status: {message}")
        # You could also show this in the UI if you have a status label
        # self.status_label.setText(message) if you have one

    def add_result(self, result):
        """Add result to text area"""
        self.text_area.append(f'<span style="color: green;">{result}</span>')

    def update_business_count(self, count):
        """Update business count display"""
        self.business_count_text.append(f'<span style="color: green;">Found {count} businesses</span>')

    def on_scraping_finished(self, persons):
        """Called when scraping is complete"""
        # Re-enable the run button and hide progress bar
        self.pushButton_run.setDisabled(False)
        self.pushButton_run.setText("Run")

        # Hide progress bar after a short delay to show 100% completion
        QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

        # Show completion message
        completion_message = f"Scraping completed! Found {len(persons)} total records."
        print(completion_message)
        self.text_area.append(f'<span style="color: blue; font-weight: bold;">{completion_message}</span>')

    def clean_text(self, text_to_clean):
        # Remove honorifics & extra whitespace
        text = re.sub(r"\b(Mr|Ms|Mrs|Dr|Prof)\.?\s+", "", text_to_clean, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def extract_emails(self, soup):
        # Get all text from the page
        text = soup.get_text(separator=" ")

        # Email regex
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

        # Find all unique matches
        emails = set(re.findall(email_pattern, text))
        return list(emails)

    def get_business_urls(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        raw_urls = soup.find_all('a', class_='text-blue-medium')
        if raw_urls:
            urls = ["https://www.bbb.org" + url.get('href') for url in raw_urls]
            return urls
        return []

    def get_urls(self, search_keywords: str, state: str = "Las Vegas"):
        urls = []
        with SB(uc=True, headless=False) as sb:
            keywords = '+'.join(search_keywords.split())
            state_keyword = '%20'.join(state.split())
            sb.open(
                f"https://www.bbb.org/search?find_country=USA&find_latlng=36.142467%2C-115.204160&find_loc={state_keyword}&find_text={keywords}&page=1&touched=1")
            sb.wait_for_ready_state_complete(30)
            raw_pag = sb.get_text("//h1[@class='search-results-heading font-normal text-black']")
            pagination = int(raw_pag.split()[1]) // 15 + 2
            urls.extend(self.get_business_urls(sb.get_page_source()))
            for pag in range(2, pagination):
                sb.open(
                    f"https://www.bbb.org/search?find_country=USA&find_latlng=36.142467%2C-115.204160&find_loc={state_keyword}&find_text={keywords}&page={pag}&touched=1")
                sb.wait_for_ready_state_complete(30)
                urls.extend(self.get_business_urls(sb.get_page_source()))
            time.sleep(1)
        return urls

    def get_people_urls(self, fullname: str, zipcode: str, token: str):
        fullname = '-'.join(fullname.split()).lower()

        # Scrape.do API endpoint - enabling "super=true" and "geoCode=us" for US-based residential proxies
        api_url = f"http://api.scrape.do?url=https%3A%2F%2Fwww.truepeoplesearch.com%2Fresults%3Fname%3D{fullname}%26citystatezip%3D{zipcode}&token={token}&super=true&geoCode=us"
        # Send the request and parse HTML
        response = requests.get(api_url)
        soup = BeautifulSoup(response.text, "html.parser")

        raw_urls = soup.find_all('a', {"aria-label": "View All Details"})
        urls = list(set(["https://www.truepeoplesearch.com" + url.get('href') for url in raw_urls]))

        return urls

    def get_person_details(self, person_id: str, token: str, bname: str, start_date, position: str):
        try:
            url_to_get = f"http://api.scrape.do?url=https://www.truepeoplesearch.com/find/person/{person_id}&token={token}&super=true&geoCode=us"
            response = requests.get(url_to_get)
            soup = BeautifulSoup(response.text, "html.parser")
            person = soup.find("div", id="personDetails")
            # name = f"{person['data-fn']} {person['data-ln']}"
            name = soup.find('h1', class_='oh1').text
            age = person["data-age"]
            addr = soup.find("a", {"data-link-to-more": "address"})
            address = addr.find("span", {"itemprop": "streetAddress"}).text.strip()
            city = addr.find("span", {"itemprop": "addressLocality"}).text.strip()
            state = addr.find("span", {"itemprop": "addressRegion"}).text.strip()

            # Extract phone number
            phone = soup.find("a", {"data-link-to-more": "phone"}).find_all("span", itemprop="telephone")
            phones = [phon.text.strip() for phon in phone]
            phones_dict = {f'Phone {i}': p for i, p in enumerate(phones)}
            emails = self.extract_emails(soup)
            if "support@truepeoplesearch.com" in emails:
                emails.remove("support@truepeoplesearch.com")
            emails_dict = {f'Email {i}': p for i, p in enumerate(emails)}

            new_row = {
                'Name': name,
                'Age': age,
                'Position': position,
                'Address': address,
                'City': city,
                'State': state,
                'Business Name': bname,
                'Business Start Date': start_date
            }
            new_row.update(phones_dict)
            new_row.update(emails_dict)
        except:
            return {}

        return new_row

    def get_owner_by_llm(self, profile_text):
        prompt = f"""
        Extract the business owner's name and title from the following text.
        Remove any honorifics (Mr, Ms, Mrs, Dr, etc.).
        Respond ONLY in this strict JSON format:
        {{
          "owner": "string",
          "title": "string"
        }}

        Profile:
        {profile_text}
        """

        payload = {
            "model": "mistral",
            "messages": [{"role": "user", "content": prompt}]
        }

        response = requests.post("http://localhost:11434/api/chat", json=payload, stream=True)

        if response.status_code != 200:
            return {"owner0": "", "title": ""}

        collected_content = ""

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                json_data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "message" in json_data and "content" in json_data["message"]:
                collected_content += json_data["message"]["content"]

            if json_data.get("done", False):
                break

        # Extract only the JSON object from the collected content
        match = re.search(r"\{\s*\"owner\".*\}", collected_content, re.DOTALL)
        if not match:
            return {"owner0": "", "title": ""}

        try:
            result = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"owner0": "", "title": ""}

        # Enforce strict format (in case model omits a field)
        return {
            "owner0": result.get("owner", ""),
            "title": result.get("title", "")
        }

    async def run_demo(self, bbb_url, scrapedo_key):
        try:
            # Step 1: Crawl BBB business page
            html, owner_title, address, bname, start_date = await crawl_bbb_business(bbb_url)
            zip_code = address.split()[-1].split('-')[0]
            if not owner_title:
                soup = BeautifulSoup(html, 'html.parser')
                page_text_content = soup.get_text(separator='\n', strip=True)
                owner_title = self.get_owner_by_llm(page_text_content)

            people_urls = {}
            if owner_title:
                for i in range(len(owner_title.keys())):
                    try:
                        full_owner_info = owner_title.get(f'owner{i}', "")
                        owner = self.clean_text(full_owner_info.split(',')[0])
                        if full_owner_info not in people_urls:
                            people_urls[full_owner_info] = self.get_people_urls(owner, zip_code, scrapedo_key)
                    except:
                        continue

            persons = []

            for person, urls in people_urls.items():
                for url in urls:
                    try:
                        pid = url.split('/')[-1]
                        position = person.split(',')[-1].strip() if len(person.split(',')) >= 2 else None
                        result = self.get_person_details(pid, scrapedo_key, bname, start_date, position)
                        if result:
                            persons.append(result)
                    except:
                        continue
            return persons
        except Exception as e:
            print(e)
            print("no available information")
            return []


if __name__ == '__main__':
    app = QApplication(sys.argv)
    demo = AppDemo()
    demo.show()

    try:
        sys.exit(app.exec_())
    except:
        print('Closing Window')
