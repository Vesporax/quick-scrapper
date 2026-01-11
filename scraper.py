import time
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import config
import utils


class ModhubScraper:
    def __init__(self, progressCallback=None):
        self.progressCallback = progressCallback
        self.browser = None
        self.page = None
        self.scrapedCount = 0
        self.skippedCount = 0
        self.errorCount = 0
        self.shouldStop = False
    
    def logProgress(self, message):
        if self.progressCallback:
            self.progressCallback(message)
        else:
            print(message)
    
    def initBrowser(self):
        playwright = sync_playwright().start()
        self.browser = playwright.chromium.launch(headless=config.HEADLESS)
        self.page = self.browser.new_page(user_agent=config.USER_AGENT)
        self.page.set_default_timeout(config.TIMEOUT)
    
    def closeBrowser(self):
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
    
    def extractModId(self, url):
        match = re.search(r'mod_id=(\d+)', url)
        return match.group(1) if match else None
    
    def scrapeMod(self, modUrl):
        for attempt in range(config.MAX_RETRIES):
            try:
                self.page.goto(modUrl, wait_until="networkidle")
                time.sleep(config.REQUEST_DELAY)
                
                html = self.page.content()
                soup = BeautifulSoup(html, 'html.parser')
                
                modId = self.extractModId(modUrl)
                if not modId:
                    self.logProgress(f"Failed to extract mod ID from {modUrl}")
                    return None
                
                modData = {
                    'mod_id': modId,
                    'url': modUrl,
                    'scraped_at': utils.formatTimestamp()
                }
                
                allText = soup.get_text()
                lines = [line.strip() for line in allText.split('\n') if line.strip()]
                
                for i, line in enumerate(lines):
                    if line == 'Game' and i + 1 < len(lines):
                        modData['game'] = utils.cleanText(lines[i + 1])
                    elif line == 'Manufacturer' and i + 1 < len(lines):
                        modData['manufacturer'] = utils.cleanText(lines[i + 1])
                    elif line == 'Category' and i + 1 < len(lines):
                        modData['category'] = utils.cleanText(lines[i + 1])
                    elif line == 'Version' and i + 1 < len(lines):
                        modData['version'] = utils.cleanText(lines[i + 1])
                    elif line == 'Released' and i + 1 < len(lines):
                        modData['released'] = utils.cleanText(lines[i + 1])
                
                descDiv = soup.find('div', class_='top-line')
                if descDiv:
                    modData['description'] = utils.cleanText(descDiv.get_text())
                
                downloadLink = soup.find('a', string='DOWNLOAD')
                if downloadLink and downloadLink.get('href'):
                    modData['download_link'] = downloadLink['href']
                
                screenshots = []
                screenshotImgs = soup.select('img[src*="screenshot"]')
                for img in screenshotImgs:
                    if img.get('src'):
                        screenshots.append(img['src'])
                modData['screenshots'] = screenshots
                
                return modData
                
            except Exception as e:
                self.logProgress(f"Attempt {attempt + 1} failed for {modUrl}: {str(e)}")
                if attempt < config.MAX_RETRIES - 1:
                    time.sleep(config.RETRY_DELAY)
                else:
                    self.errorCount += 1
                    return None
    
    def scrapeModList(self, maxPages=None):
        if maxPages is None:
            maxPages = config.MAX_PAGES_PER_RUN
        
        self.logProgress(f"Starting scrape with max {maxPages} pages")
        self.initBrowser()
        
        try:
            for pageNum in range(maxPages):
                if self.shouldStop:
                    self.logProgress("Stopping scraper...")
                    break
                
                pageUrl = f"{config.BASE_URL}?title=fs2025&filter=latest&page={pageNum}"
                self.logProgress(f"Scraping page {pageNum + 1}...")
                
                self.page.goto(pageUrl, wait_until="networkidle")
                time.sleep(config.PAGE_DELAY)
                
                html = self.page.content()
                soup = BeautifulSoup(html, 'html.parser')
                
                modLinks = soup.find_all('a', href=re.compile(r'mod\.php\?mod_id=\d+'))
                if not modLinks:
                    self.logProgress(f"No mods found on page {pageNum + 1}, stopping")
                    break
                
                self.logProgress(f"Found {len(modLinks)} mods on page {pageNum + 1}")
                
                processedIds = set()
                for link in modLinks:
                    if self.shouldStop:
                        self.logProgress("Stopping scraper...")
                        break
                    
                    modUrl = link.get('href')
                    if not modUrl:
                        continue
                    
                    if not modUrl.startswith('http'):
                        modUrl = f"https://www.farming-simulator.com/{modUrl}"
                    
                    modId = self.extractModId(modUrl)
                    if not modId or modId in processedIds:
                        continue
                    
                    processedIds.add(modId)
                    
                    if utils.modExists(modId):
                        self.logProgress(f"Mod {modId} already exists, skipping")
                        self.skippedCount += 1
                        continue
                    
                    self.logProgress(f"Scraping mod {modId}...")
                    modData = self.scrapeMod(modUrl)
                    
                    if modData:
                        utils.saveModToJson(modData)
                        self.scrapedCount += 1
                        self.logProgress(f"Saved mod {modId}")
        
        finally:
            self.closeBrowser()
            self.logProgress(f"\nScraping complete!")
            self.logProgress(f"Scraped: {self.scrapedCount}")
            self.logProgress(f"Skipped: {self.skippedCount}")
            self.logProgress(f"Errors: {self.errorCount}")