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
                
                detailsSection = soup.find('div', class_='details-section')
                if not detailsSection:
                    self.logProgress(f"No details section found for mod {modId}")
                    return None
                
                game = detailsSection.find('dd', class_='game')
                if game:
                    modData['game'] = utils.cleanText(game.get_text())
                
                manufacturer = detailsSection.find('dd', class_='manufacturer')
                if manufacturer:
                    modData['manufacturer'] = utils.cleanText(manufacturer.get_text())
                
                category = detailsSection.find('dd', class_='category')
                if category:
                    modData['category'] = utils.cleanText(category.get_text())
                
                version = detailsSection.find('dd', class_='version')
                if version:
                    modData['version'] = utils.cleanText(version.get_text())
                
                released = detailsSection.find('dd', class_='released')
                if released:
                    modData['released'] = utils.cleanText(released.get_text())
                
                descSection = soup.find('div', class_='description-section')
                if descSection:
                    modData['description'] = utils.cleanText(descSection.get_text())
                
                downloadLink = soup.find('a', class_='download-link')
                if downloadLink and downloadLink.get('href'):
                    modData['download_link'] = downloadLink['href']
                
                screenshots = []
                screenshotDivs = soup.find_all('div', class_='screenshot')
                for div in screenshotDivs:
                    img = div.find('img')
                    if img and img.get('src'):
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
            for pageNum in range(1, maxPages + 1):
                pageUrl = f"{config.BASE_URL}?page={pageNum}"
                self.logProgress(f"Scraping page {pageNum}...")
                
                self.page.goto(pageUrl, wait_until="networkidle")
                time.sleep(config.PAGE_DELAY)
                
                html = self.page.content()
                soup = BeautifulSoup(html, 'html.parser')
                
                modLinks = soup.find_all('a', class_='mod-item')
                if not modLinks:
                    self.logProgress(f"No mods found on page {pageNum}, stopping")
                    break
                
                for link in modLinks:
                    modUrl = link.get('href')
                    if not modUrl:
                        continue
                    
                    if not modUrl.startswith('http'):
                        modUrl = f"https://www.farming-simulator.com{modUrl}"
                    
                    modId = self.extractModId(modUrl)
                    if not modId:
                        continue
                    
                    if utils.modExists(modId):
                        existingMod = utils.loadModFromJson(modId)
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