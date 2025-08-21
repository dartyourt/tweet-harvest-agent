"""
Twitter Scraper Agent - Main Launcher
"""
import os
import sys
import tkinter as tk
from gui import TwitterScraperApp

def main():
    """Main function to launch the application"""
    # Create root window
    root = tk.Tk()
    
    # Set window title and icon
    root.title("Twitter Scraper Agent")
    
    # Create application
    app = TwitterScraperApp(root)
    
    # Start main loop
    root.mainloop()

if __name__ == "__main__":
    main()
