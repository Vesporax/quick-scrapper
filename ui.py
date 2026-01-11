import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
from scraper import ModhubScraper
import config


class ScraperUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Modhub Scraper")
        self.window.geometry("600x450")
        self.window.resizable(False, False)
        
        self.scraper = None
        self.scraperThread = None
        self.isRunning = False
        
        self.setupUI()
    
    def setupUI(self):
        mainFrame = ttk.Frame(self.window, padding="10")
        mainFrame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(mainFrame, text="Max Pages:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.maxPagesVar = tk.StringVar(value=str(config.MAX_PAGES_PER_RUN))
        self.maxPagesEntry = ttk.Entry(mainFrame, textvariable=self.maxPagesVar, width=10)
        self.maxPagesEntry.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        buttonFrame = ttk.Frame(mainFrame)
        buttonFrame.grid(row=1, column=0, columnspan=2, pady=10)
        
        self.startButton = ttk.Button(buttonFrame, text="Start Scraping", command=self.startScraping)
        self.startButton.grid(row=0, column=0, padx=5)
        
        self.stopButton = ttk.Button(buttonFrame, text="Stop", command=self.stopScraping, state=tk.DISABLED)
        self.stopButton.grid(row=0, column=1, padx=5)
        
        ttk.Label(mainFrame, text="Progress:").grid(row=2, column=0, sticky=tk.W, pady=5)
        
        self.progressText = scrolledtext.ScrolledText(mainFrame, width=70, height=20, state=tk.DISABLED)
        self.progressText.grid(row=3, column=0, columnspan=2, pady=5)
        
        self.statusLabel = ttk.Label(mainFrame, text="Ready", relief=tk.SUNKEN)
        self.statusLabel.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
    
    def logMessage(self, message):
        self.progressText.config(state=tk.NORMAL)
        self.progressText.insert(tk.END, message + "\n")
        self.progressText.see(tk.END)
        self.progressText.config(state=tk.DISABLED)
    
    def updateStatus(self, status):
        self.statusLabel.config(text=status)
    
    def startScraping(self):
        try:
            maxPages = int(self.maxPagesVar.get())
            if maxPages <= 0:
                self.logMessage("Error: Max pages must be positive")
                return
        except ValueError:
            self.logMessage("Error: Invalid max pages value")
            return
        
        self.isRunning = True
        self.startButton.config(state=tk.DISABLED)
        self.stopButton.config(state=tk.NORMAL)
        self.maxPagesEntry.config(state=tk.DISABLED)
        self.updateStatus("Scraping...")
        
        self.scraperThread = threading.Thread(target=self.runScraper, args=(maxPages,), daemon=True)
        self.scraperThread.start()
    
    def runScraper(self, maxPages):
        try:
            self.scraper = ModhubScraper(progressCallback=self.logMessage)
            self.scraper.scrapeModList(maxPages)
            self.updateStatus("Completed")
        except Exception as e:
            self.logMessage(f"Error: {str(e)}")
            self.updateStatus("Error")
        finally:
            self.isRunning = False
            self.startButton.config(state=tk.NORMAL)
            self.stopButton.config(state=tk.DISABLED)
            self.maxPagesEntry.config(state=tk.NORMAL)
    
    def stopScraping(self):
        if self.scraper:
            self.logMessage("Stopping scraper...")
            self.scraper.shouldStop = True
            self.updateStatus("Stopping...")
            self.startButton.config(state=tk.NORMAL)
            self.stopButton.config(state=tk.DISABLED)
            self.maxPagesEntry.config(state=tk.NORMAL)
    
    def run(self):
        self.window.mainloop()


def launchUI():
    app = ScraperUI()
    app.run()