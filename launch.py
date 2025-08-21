
import os
import sys
import tkinter as tk
from gui import TwitterScraperApp

def main():
    root = tk.Tk()
    root.title("Twitter Scraper Agent")
    app = TwitterScraperApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
