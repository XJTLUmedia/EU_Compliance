import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from datetime import datetime
import json
import logging
from urllib.parse import urljoin, urlparse
import re
from fake_useragent import UserAgent
import random
import feedparser  # new dependency for RSS/Atom parsing

# Configure logging (keeps your logging config)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('regulatory_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EURegulatoryScraper:
    """
    Scrapes EU regulatory websites for the latest regulations.
    This trimmed-down version ONLY scrapes the EUR-Lex daily view by ojDate
    and does not attempt RSS discovery or generic page crawling.
    """
    def __init__(self, config_file='scraper_config.json'):
        """
        Initialize the scraper with configuration
        """
        self.config = self._load_config(config_file)
        self.ua = UserAgent()
        self.data_dir = self.config.get('data_dir', 'regulatory_data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Rate limiting settings
        self.min_delay = self.config.get('min_delay', 2)  # Minimum delay between requests
        self.max_delay = self.config.get('max_delay', 5)  # Maximum delay between requests
        self.max_retries = self.config.get('max_retries', 3)  # Maximum number of retries
        
        # Session for persistent connections
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Only register EUR-Lex as a discovered source (no RSS)
        # Key name kept simple so existing callers can use 'eur-lex' or the netloc key
        self.regulation_sources = {
            'eur-lex': {
                'url': 'https://eur-lex.europa.eu/oj/daily-view/L-series/default.html',
                'base_url': 'https://eur-lex.europa.eu',
                'method': 'eur-lex-daily',
                'note': 'EUR-Lex daily view; supply ojDate to fetch specific date'
            }
        }
        logger.info(f"Configured regulation_sources: {list(self.regulation_sources.keys())}")

    # --- config loader (unchanged) ---
    def _load_config(self, config_file):
        default_config = {
            'min_delay': 2,
            'max_delay': 5,
            'max_retries': 3,
            'data_dir': 'regulatory_data',
            'user_agents': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
            ]
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                logger.error(f"Error loading config file: {str(e)}")
                return default_config
        else:
            try:
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                logger.info(f"Created default config file: {config_file}")
            except Exception as e:
                logger.error(f"Error creating config file: {str(e)}")
            return default_config

    # --- simple delay & request helpers ---
    def _random_delay(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
    
    def _get_random_user_agent(self):
        return random.choice(self.config.get('user_agents', []))
    
    def _make_request(self, url, retry_count=0):
        if retry_count > 0:
            logger.info(f"Retry {retry_count}/{self.max_retries} for URL: {url}")
        try:
            headers = {'User-Agent': self.ua.random}
            response = self.session.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', self.max_delay))
                logger.warning(f"Rate limited. Waiting {retry_after} seconds before retrying.")
                time.sleep(retry_after)
                return self._make_request(url, retry_count + 1)
            else:
                logger.error(f"Request failed with status {response.status_code}: {response.text[:200]}")
                if retry_count < self.max_retries:
                    return self._make_request(url, retry_count + 1)
                else:
                    raise Exception(f"Max retries exceeded for URL: {url}")
        except Exception as e:
            logger.error(f"Request error: {str(e)}")
            if retry_count < self.max_retries:
                return self._make_request(url, retry_count + 1)
            else:
                raise Exception(f"Max retries exceeded for URL: {url}")

    # --- stubbed RSS/feed functions (kept for signature compatibility, but not used) ---
    def _find_rss_feed(self, site_url):
        """RSS discovery disabled in this trimmed implementation."""
        return None

    def _parse_rss_feed(self, feed_url, source_key):
        """RSS parsing disabled — return empty list to preserve return format."""
        return []

    def _scan_page_for_legal_links(self, page_url, source_key, depth=0, max_links=12):
        """Generic page scanning disabled in this trimmed implementation."""
        return []

    # --- ojDate formatter ---
    def _format_ojdate(self, date_input):
        """
        Accepts datetime/date or strings 'YYYY-MM-DD', 'DD-MM-YYYY', 'DDMMYYYY'
        Returns 'DDMMYYYY' string used by eur-lex daily-view ojDate param.
        """
        # Accept both datetime and date objects
        try:
            from datetime import date as _date  # local import to avoid top-level change if needed
        except Exception:
            _date = None

        if isinstance(date_input, (datetime, ) + (( _date, ) if _date else ( ))):
            return date_input.strftime("%d%m%Y")
        if isinstance(date_input, str):
            s = date_input.strip()
            # YYYY-MM-DD
            m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
            if m:
                y, mo, da = m.groups()
                return f"{int(da):02d}{int(mo):02d}{y}"
            # DD-MM-YYYY
            m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", s)
            if m:
                da, mo, y = m.groups()
                return f"{int(da):02d}{int(mo):02d}{y}"
            # DDMMYYYY
            m = re.match(r"^(\d{2})(\d{2})(\d{4})$", s)
            if m:
                return s
        raise ValueError("Unsupported date format for ojDate. Use YYYY-MM-DD, DD-MM-YYYY, DDMMYYYY, or a date object.")

    # --- core EUR-Lex daily scraping (returns same dict structure as RSS/page functions) ---
    def _scrape_eurlex_daily_by_ojdate(self, ojdate_ddmmyyyy):
        """
        Scrape EUR-Lex daily view page for the ojDate in DDMMYYYY format and return updates list.
        Each update has keys: title, date, content, url, source, method
        """
        updates = []
        ojdate_param = ojdate_ddmmyyyy
        daily_url = f"https://eur-lex.europa.eu/oj/daily-view/L-series/default.html?&ojDate={ojdate_param}"
        logger.info(f"Fetching EUR-Lex daily view for ojDate={ojdate_param}")
        try:
            resp = self._make_request(daily_url)
            if not resp:
                return updates
            soup = BeautifulSoup(resp.text, 'html.parser')

            # The daily view has nested panels; legislation rows include 'daily-view-row-spacing'
            rows = soup.find_all("div", class_=lambda c: c and "daily-view-row-spacing" in c)
            logger.info(f"EUR-Lex daily view: found {len(rows)} row containers")

            for row in rows:
                try:
                    # find anchor (title + link) if present
                    anchor = row.find("a", href=True)
                    if anchor:
                        href = anchor['href']
                        full_url = urljoin(daily_url, href)
                        title = anchor.get_text(" ", strip=True)
                    else:
                        # fallback to readable text
                        full_url = None
                        title = row.get_text(" ", strip=True)[:200]

                    # snippet: first <p> within that widget
                    snippet = ""
                    p = row.find("p")
                    if p:
                        snippet = p.get_text(" ", strip=True)[:800]

                    updates.append({
                        'title': title,
                        'date': datetime.strptime(ojdate_param, "%d%m%Y").strftime("%Y-%m-%d"),
                        'content': snippet,
                        'url': full_url,
                        'source': 'eur-lex',
                        'method': 'daily-view'
                    })
                except Exception as e:
                    logger.debug(f"Error parsing eur-lex row: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping eur-lex daily view: {e}")
        return updates

    # --- scrape_regulation_updates (keeps signature) ---
    def scrape_regulation_updates(self, regulation_key):
        """
        Attempt to find updates for a discovered regulation source key.
        In this trimmed implementation, any call will attempt to fetch EUR-Lex daily view
        by date. Date selection order:
          1. If regulation_key contains '::' (e.g. 'eur-lex::2025-09-10'), use that.
          2. Else if self.config contains 'ojDate', use that.
          3. Else default to today.
        Returns list of dicts with keys matching the original format.
        """
        logger.info(f"Scraping updates for requested key: {regulation_key}")

        # parse possible override date from regulation_key
        date_override = None
        base_key = regulation_key
        if "::" in regulation_key:
            parts = regulation_key.split("::", 1)
            base_key = parts[0]
            date_override = parts[1]

        # determine ojDate string (DDMMYYYY)
        ojDate_str = None
        if date_override:
            try:
                ojDate_str = self._format_ojdate(date_override)
            except Exception:
                logger.warning("Date override format invalid; ignoring override.")

        if ojDate_str is None and self.config.get('ojDate'):
            try:
                ojDate_str = self._format_ojdate(self.config.get('ojDate'))
            except Exception:
                logger.warning("self.config['ojDate'] format invalid; ignoring.")

        if ojDate_str is None:
            # default to today
            ojDate_str = datetime.now().strftime("%d%m%Y")

        updates = self._scrape_eurlex_daily_by_ojdate(ojDate_str)
        if updates:
            # Save under the base_key so existing callers that expect files named by the key still work
            self._save_scraped_data(base_key, updates)
            logger.info(f"Scraped {len(updates)} items for ojDate={ojDate_str}")
        else:
            logger.warning(f"No items found for ojDate={ojDate_str}")
        return updates

    # --- keep your save function unchanged ---
    def _save_scraped_data(self, regulation_type, data):
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"{self.data_dir}/{regulation_type}_{timestamp}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(data)} updates to {filename}")
        except Exception as e:
            logger.error(f"Error saving scraped data: {str(e)}")

    # --- keep get_regulation_text and check_for_updates but simplified ---
    def get_regulation_text(self, regulation_type):
        regulation_texts = {
            'gdpr': "...",  # placeholder texts if desired
            'digital_services_act': "...",
            'ai_act': "..."
        }
        return regulation_texts.get(regulation_type, "Regulation text not available")
    
    def check_for_updates(self):
        """
        Check all discovered regulation sources for updates.
        In this trimmed implementation, it will call scrape_regulation_updates on each discovered key.
        """
        logger.info("Checking all discovered regulation sources for updates")
        all_updates = {}
        for key in self.regulation_sources.keys():
            try:
                updates = self.scrape_regulation_updates(key)
                all_updates[key] = updates
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error checking updates for {key}: {str(e)}")
                all_updates[key] = []
        return all_updates
