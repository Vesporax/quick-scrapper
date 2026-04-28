import time
import re
import os
import json
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

    def downloadScreenshots(self, screenshotUrls, modId, outputDir, modUrl):
        """
        Télécharge les screenshots un par un via le contexte navigateur actif
        (mêmes cookies/session que la page du mod, avec Referer explicite).
        Retourne le nombre de fichiers téléchargés avec succès.
        """
        downloaded = 0
        total = len(screenshotUrls)
        for i, imgUrl in enumerate(screenshotUrls, start=1):
            filename = os.path.join(outputDir, f"{modId}_{i}.png")
            try:
                response = self.page.context.request.get(
                    imgUrl,
                    headers={"Referer": modUrl}
                )
                if response.status == 200:
                    with open(filename, 'wb') as f:
                        f.write(response.body())
                    self.logProgress(f"  [{i}/{total}] ✓ {modId}_{i}.png")
                    downloaded += 1
                elif response.status == 403:
                    self.logProgress(f"  [{i}/{total}] ✗ 403 Forbidden — accès refusé ({imgUrl})")
                else:
                    self.logProgress(f"  [{i}/{total}] ✗ HTTP {response.status} ({imgUrl})")
            except Exception as e:
                self.logProgress(f"  [{i}/{total}] ✗ Erreur : {str(e)}")
        return downloaded

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

    def scrapeOne(self):
        """
        Test unitaire : scrape le premier mod visible, télécharge ses screenshots
        pendant que la page est encore ouverte, puis sauvegarde le tout dans
        output/mod_{id}/ — JSON sans URLs de screenshots + images numérotées.
        """
        self.logProgress("--- Test run: fetching most recent mod only ---")
        self.initBrowser()

        try:
            # 1. Charger la page listing
            pageUrl = f"{config.BASE_URL}?title=fs2025&filter=latest&page=0"
            self.logProgress("Chargement de la page listing...")
            self.page.goto(pageUrl, wait_until="networkidle")
            time.sleep(config.PAGE_DELAY)

            html = self.page.content()
            soup = BeautifulSoup(html, 'html.parser')

            modLinks = soup.find_all('a', href=re.compile(r'mod\.php\?mod_id=\d+'))
            if not modLinks:
                self.logProgress("Aucun mod trouvé sur la page listing.")
                return

            # 2. Première URL valide
            firstUrl = None
            for link in modLinks:
                href = link.get('href')
                if href:
                    if not href.startswith('http'):
                        href = f"https://www.farming-simulator.com/{href}"
                    firstUrl = href
                    break

            if not firstUrl:
                self.logProgress("Impossible de résoudre une URL de mod.")
                return

            modId = self.extractModId(firstUrl)
            self.logProgress(f"Test sur le mod ID {modId} → {firstUrl}")

            # 3. Scraper les données — la page reste ouverte après cet appel
            modData = self.scrapeMod(firstUrl)
            if not modData:
                self.logProgress("Échec du scraping. Vérifier les sélecteurs ou la connectivité.")
                return

            # 4. Extraire les URLs de screenshots (ne seront pas dans le JSON final)
            screenshotUrls = modData.pop('screenshots', [])
            self.logProgress(f"\n{len(screenshotUrls)} screenshot(s) détecté(s).")

            # 5. Créer le dossier de sortie
            modFolder = os.path.join(config.OUTPUT_DIR, f"mod_{modId}")
            os.makedirs(modFolder, exist_ok=True)

            # 6. Télécharger les screenshots PENDANT QUE la page est encore active
            if screenshotUrls:
                self.logProgress("Téléchargement des screenshots (page toujours ouverte)...")
                downloaded = self.downloadScreenshots(screenshotUrls, modId, modFolder, firstUrl)
                self.logProgress(f"→ {downloaded}/{len(screenshotUrls)} screenshot(s) sauvegardé(s).")
            else:
                self.logProgress("Aucun screenshot à télécharger.")

            # 7. Sauvegarder le JSON (sans les URLs de screenshots)
            jsonPath = os.path.join(modFolder, f"mod_{modId}.json")
            with open(jsonPath, 'w', encoding='utf-8') as f:
                json.dump(modData, f, indent=2, ensure_ascii=False)
            self.logProgress(f"JSON sauvegardé → {jsonPath}")

            # 8. Résumé dans le log
            self.logProgress("\n--- Données extraites ---")
            for key, value in modData.items():
                self.logProgress(f"  {key}: {value}")
            self.logProgress(f"\nDossier de sortie : {modFolder}")
            self.logProgress("Test terminé avec succès.")

        finally:
            self.closeBrowser()