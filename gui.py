
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
import time
from datetime import datetime, timedelta
import calendar
import pandas as pd
import webbrowser
from pathlib import Path
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config, logger, update_auth_token
from twitter_scraper import TwitterScraper

class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.bind("<Enter>", self._bind_mousewheel)
        self.bind("<Leave>", self._unbind_mousewheel)
    
    def _bind_mousewheel(self, event):
        if sys.platform.startswith('win'):
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        elif sys.platform.startswith('darwin'):
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
            self.canvas.bind_all("<Button-4>", self._on_mousewheel)
            self.canvas.bind_all("<Button-5>", self._on_mousewheel)
        else:
            self.canvas.bind_all("<Button-4>", self._on_mousewheel)
            self.canvas.bind_all("<Button-5>", self._on_mousewheel)
    
    def _unbind_mousewheel(self, event):
        if sys.platform.startswith('win'):
            self.canvas.unbind_all("<MouseWheel>")
        elif sys.platform.startswith('darwin'):
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        else:
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
    
    def _on_mousewheel(self, event):
        if sys.platform.startswith('win'):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        elif sys.platform.startswith('darwin'):
            self.canvas.yview_scroll(int(-1*(event.delta)), "units")
        else:
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")

class TwitterScraperApp:
    
    def __init__(self, root):
        self.root = root
        self.root.title("Tweet Harvest Agent - Advanced Twitter Scraping Tool")
        self.root.geometry("1024x768") 
        self.root.minsize(1024, 768)
        self.root.resizable(True, True)
        
        self.scraper = TwitterScraper()
        self.setup_variables()
        self.create_ui()
        self.check_node_install()
        self.check_auth_token()
    
    def setup_variables(self):
        self.auth_token_var = tk.StringVar(value=config['auth_token'])
        
        current_year = datetime.now().year
        current_month = datetime.now().month
        current_day = datetime.now().day
        
        self.start_year_var = tk.StringVar(value=str(current_year-1))
        self.start_month_var = tk.StringVar(value="01")
        self.start_day_var = tk.StringVar(value="01")
        
        self.end_year_var = tk.StringVar(value=str(current_year))
        self.end_month_var = tk.StringVar(value=f"{current_month:02d}")
        self.end_day_var = tk.StringVar(value=f"{current_day:02d}")
        
        self.start_date = datetime(current_year-1, 1, 1)
        self.end_date = datetime(current_year, current_month, current_day)
        
        self.interval_var = tk.StringVar(value="monthly")
        
        self.keywords_text = scrolledtext.ScrolledText(self.root, height=5)
        self.use_quotes_vars = []
        
        self.limit_var = tk.StringVar(value=str(config['default_limit']))
        self.lang_var = tk.StringVar(value=config['default_lang'])
        self.tab_var = tk.StringVar(value=config['default_tab'])
        
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0.0)
        
        self.output_dir_var = tk.StringVar(value=config['output_dir'])
        
        self.current_batch = None
        self.stop_requested = False
    
    def create_ui(self):
        self.style = ttk.Style()
        
        self.style.configure('TNotebook.Tab', padding=[20, 10], font=('Segoe UI', 11))
        self.style.configure('Custom.TButton', font=('Segoe UI', 11, 'bold'), padding=[10, 5])
        self.style.configure('TLabelframe.Label', font=('Segoe UI', 11, 'bold'))
        self.style.configure('TLabel', font=('Segoe UI', 10))
        self.style.configure('TButton', font=('Segoe UI', 10), padding=[8, 4])
        self.style.configure('KeywordHeader.TFrame', background='#E8F0F8')
        self.style.configure('Emphasis.TLabelframe', borderwidth=2, relief='groove')
        self.style.configure('Emphasis.TLabelframe.Label', 
                            font=('Segoe UI', 12, 'bold'), 
                            foreground='#004080')
        self.style.configure('TScrollbar', gripcount=0, background='#D0D0D0', 
                          troughcolor='#F0F0F0', borderwidth=1, arrowsize=13)
        self.style.configure('Selected.TButton', background='#0078D7', foreground='white')
        self.style.map('Custom.TButton',
                     foreground=[('active', '#000000'), ('!disabled', '#000000')],
                     background=[('active', '#e1e1e1'), ('!disabled', '#f0f0f0')],
                     relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
        
        container = ttk.Frame(self.root)
        container.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.main_tab = ttk.Frame(self.notebook)
        self.results_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.help_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.main_tab, text='  Scraper  ')
        self.notebook.add(self.results_tab, text='  Results  ')
        self.notebook.add(self.settings_tab, text='  Settings  ')
        self.notebook.add(self.help_tab, text='  Help  ')
        def on_tab_changed(event):
            tab_id = self.notebook.select()
            tab_name = self.notebook.tab(tab_id, "text").strip()
            if sys.platform.startswith('win'):
                self.root.unbind_all("<MouseWheel>")
            elif sys.platform.startswith('darwin'):
                self.root.unbind_all("<MouseWheel>")
                self.root.unbind_all("<Button-4>")
                self.root.unbind_all("<Button-5>")
            else:
                self.root.unbind_all("<Button-4>")
                self.root.unbind_all("<Button-5>")
                
            if tab_name == "Scraper" and hasattr(self, 'scrollable_main_frame'):
                pass
        
        self.notebook.bind("<<NotebookTabChanged>>", on_tab_changed)
        
        self.setup_main_tab()
        self.setup_results_tab()
        self.setup_settings_tab()
        self.setup_help_tab()

        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        self.progress_bar = ttk.Progressbar(
            status_frame, 
            orient='horizontal',
            mode='determinate', 
            variable=self.progress_var
        )
        self.progress_bar.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        status_label = ttk.Label(status_frame, textvariable=self.status_var)
        status_label.pack(side='right')
    
    def setup_main_tab(self):
        main_frame = ttk.Frame(self.main_tab)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(
            header_frame, 
            text="Twitter Tweet Scraper", 
            font=('Segoe UI', 16, 'bold')
        ).pack(side='left')
        ttk.Button(
            header_frame,
            text="Need Help?",
            command=lambda: self.notebook.select(self.help_tab),
            style='Custom.TButton'
        ).pack(side='right')

        keywords_frame = ttk.LabelFrame(main_frame, text="")
        keywords_frame.pack(fill='x', pady=(0, 15), ipady=10)
        keyword_header = ttk.Frame(keywords_frame, style='KeywordHeader.TFrame')
        keyword_header.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(
            keyword_header, 
            text="ENTER YOUR KEYWORDS BELOW 👇",
            font=('Segoe UI', 12, 'bold'),
            foreground='#004080'
        ).pack(anchor='center')
        
        ttk.Label(
            keywords_frame, 
            text="Input one keyword per line in the box below:",
            font=('Segoe UI', 10)
        ).pack(anchor='w', padx=10, pady=(5, 0))
        
        keyword_entry_frame = ttk.Frame(keywords_frame, padding=5)
        keyword_entry_frame.pack(fill='x', padx=10, pady=5)
        
        self.keywords_text = scrolledtext.ScrolledText(
            keyword_entry_frame, 
            height=6, 
            font=('Segoe UI', 10),
            borderwidth=2,
            relief="groove"
        )
        self.keywords_text.pack(fill='x', expand=True)
        
        if not hasattr(self, 'keywords_initialized'):
            placeholder = "#pilpres2024\ngibran\n\"Universitas Indonesia\""
            self.keywords_text.insert('1.0', placeholder)
            self.keywords_initialized = True
        
        keyword_info_frame = ttk.Frame(keywords_frame)
        keyword_info_frame.pack(fill='x', padx=10, pady=(0, 5))
        
        ttk.Label(
            keyword_info_frame, 
            text="✓ Use quotes (\"\") around keywords for exact phrase matching  ✓",
            font=('Segoe UI', 9, 'italic')
        ).pack(side='left')
        
        ttk.Button(
            keyword_info_frame, 
            text="Add Example Keywords ▼", 
            command=self.add_keyword_examples,
            style='Custom.TButton'
        ).pack(side='right')
        
        date_frame = ttk.LabelFrame(main_frame, text="Time Range", style='Emphasis.TLabelframe')
        date_frame.pack(fill='x', pady=(0, 15), ipady=5)
        
        start_date_frame = ttk.LabelFrame(date_frame, text="Start Date")
        start_date_frame.pack(side='left', fill='x', expand=True, padx=10, pady=5)

        start_date_inner = ttk.Frame(start_date_frame)
        start_date_inner.pack(padx=5, pady=5, fill='x')
        
        ttk.Label(start_date_inner, text="Year:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        start_year_entry = ttk.Combobox(start_date_inner, textvariable=self.start_year_var, 
                                        values=[str(y) for y in range(2010, datetime.now().year+2)],  # Include next year
                                        width=6)
        start_year_entry.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        
        ttk.Label(start_date_inner, text="Month:").grid(row=0, column=2, padx=5, pady=5, sticky='w')
        start_month_combobox = ttk.Combobox(start_date_inner, textvariable=self.start_month_var, 
                                          values=['01', '02', '03', '04', '05', '06', 
                                                  '07', '08', '09', '10', '11', '12'],
                                          width=4)
        start_month_combobox.grid(row=0, column=3, padx=5, pady=5, sticky='w')
        
        ttk.Label(start_date_inner, text="Day:").grid(row=0, column=4, padx=5, pady=5, sticky='w')
        start_day_combobox = ttk.Combobox(start_date_inner, textvariable=self.start_day_var,
                                       width=4)
        start_day_combobox.grid(row=0, column=5, padx=5, pady=5, sticky='w')
    
        ttk.Button(start_date_inner, text="📅", width=3,
                 command=lambda: self.show_calendar(
                     self.start_year_var, 
                     self.start_month_var, 
                     self.start_day_var
                 )).grid(row=0, column=6, padx=5, pady=5, sticky='w')
        
        def update_start_days(*args):
            self.update_day_options(
                self.start_year_var, 
                self.start_month_var, 
                self.start_day_var, 
                start_day_combobox
            )
        
        self.start_year_var.trace('w', update_start_days)
        self.start_month_var.trace('w', update_start_days)
        
        self.update_day_options(
            self.start_year_var, 
            self.start_month_var, 
            self.start_day_var, 
            start_day_combobox
        )
        
        end_date_frame = ttk.LabelFrame(date_frame, text="End Date")
        end_date_frame.pack(side='right', fill='x', expand=True, padx=10, pady=5)
 
        end_date_inner = ttk.Frame(end_date_frame)
        end_date_inner.pack(padx=5, pady=5, fill='x')

        ttk.Label(end_date_inner, text="Year:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        end_year_entry = ttk.Combobox(end_date_inner, textvariable=self.end_year_var,
                                     values=[str(y) for y in range(2010, datetime.now().year+2)],  # Include next year
                                     width=6)
        end_year_entry.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        

        ttk.Label(end_date_inner, text="Month:").grid(row=0, column=2, padx=5, pady=5, sticky='w')
        end_month_combobox = ttk.Combobox(end_date_inner, textvariable=self.end_month_var, 
                                        values=['01', '02', '03', '04', '05', '06', 
                                                '07', '08', '09', '10', '11', '12'],
                                        width=4)
        end_month_combobox.grid(row=0, column=3, padx=5, pady=5, sticky='w')

        ttk.Label(end_date_inner, text="Day:").grid(row=0, column=4, padx=5, pady=5, sticky='w')
        end_day_combobox = ttk.Combobox(end_date_inner, textvariable=self.end_day_var,
                                     width=4)
        end_day_combobox.grid(row=0, column=5, padx=5, pady=5, sticky='w')
        
        ttk.Button(end_date_inner, text="📅", width=3,
                 command=lambda: self.show_calendar(
                     self.end_year_var, 
                     self.end_month_var, 
                     self.end_day_var
                 )).grid(row=0, column=6, padx=5, pady=5, sticky='w')
        def update_end_days(*args):
            self.update_day_options(
                self.end_year_var, 
                self.end_month_var, 
                self.end_day_var, 
                end_day_combobox
            )
        
        self.end_year_var.trace('w', update_end_days)
        self.end_month_var.trace('w', update_end_days)
        

        self.update_day_options(
            self.end_year_var, 
            self.end_month_var, 
            self.end_day_var, 
            end_day_combobox
        )
        
        interval_frame = ttk.Frame(date_frame)
        interval_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(interval_frame, text="Split date range by:", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 10))
        interval_combobox = ttk.Combobox(interval_frame, textvariable=self.interval_var,
                                        values=["yearly", "quarterly", "monthly", "weekly", "daily"],
                                        width=10)
        interval_combobox.pack(side='left')
        
        ttk.Button(interval_frame, text="Preview Date Ranges", command=self.preview_date_ranges).pack(
            side='right', padx=10)

        options_frame = ttk.LabelFrame(main_frame, text="Scraping Options", style='Emphasis.TLabelframe')
        options_frame.pack(fill='x', pady=(0, 15), ipady=5)
 
        options_grid = ttk.Frame(options_frame)
        options_grid.pack(fill='x', padx=10, pady=5)
   
        ttk.Label(options_grid, text="Tweets per request:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
        limit_entry = ttk.Entry(options_grid, textvariable=self.limit_var, width=10)
        limit_entry.grid(row=0, column=1, padx=10, pady=5, sticky='w')
        
        ttk.Label(options_grid, text="Language:").grid(row=0, column=2, padx=10, pady=5, sticky='w')
        lang_combobox = ttk.Combobox(options_grid, textvariable=self.lang_var, 
                                    values=["id", "en", "es", "fr", "ar", "ja", "ko", "de"], width=10)
        lang_combobox.grid(row=0, column=3, padx=10, pady=5, sticky='w')
        
        ttk.Label(options_grid, text="Tab:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
        tab_combobox = ttk.Combobox(options_grid, textvariable=self.tab_var, 
                                   values=["LATEST", "TOP"], width=10)
        tab_combobox.grid(row=1, column=1, padx=10, pady=5, sticky='w')
        
        ttk.Label(options_grid, text="Output Directory:").grid(row=1, column=2, padx=10, pady=5, sticky='w')
        output_frame = ttk.Frame(options_grid)
        output_frame.grid(row=1, column=3, padx=10, pady=5, sticky='w')

        display_path = self.output_dir_var.get()
        if "/tweets-data" in display_path:
            display_path = display_path.replace("/tweets-data", "")
            self.output_dir_var.set(display_path)
        
        output_entry = ttk.Entry(output_frame, textvariable=self.output_dir_var, width=20)
        output_entry.pack(side='left')
        
        ttk.Button(output_frame, text="...", width=3, command=self.browse_output_dir).pack(side='left')

        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill='x', pady=15)

        ttk.Separator(main_frame).pack(fill='x', pady=5)

        button_frame = ttk.Frame(action_frame)
        button_frame.pack(fill='x', expand=True)
        
        ttk.Button(button_frame, text="✅ Start Scraping", command=self.start_scraping, 
                  style='Custom.TButton', width=20).pack(side='left', padx=10)
        
        self.stop_button = ttk.Button(button_frame, text="⛔ Stop", command=self.stop_scraping, 
                                     state='disabled', style='Custom.TButton', width=10)
        self.stop_button.pack(side='left', padx=10)
        
        self.style.configure('Clear.TButton', 
                           font=('Segoe UI', 11, 'bold'),
                           padding=[10, 5],
                           background='#ffeeee')
        
        self.style.map('Clear.TButton',
                     foreground=[('active', '#000000'), ('!disabled', '#000000')],
                     background=[('active', '#ffe0e0'), ('!disabled', '#ffeeee')])
                     
        clear_button = ttk.Button(button_frame, text="🗑️ Clear Form", command=self.clear_form, 
                               style='Clear.TButton', width=15)
        clear_button.pack(side='right', padx=20)
        
        ttk.Separator(main_frame).pack(fill='x', pady=5)
        
        log_frame = ttk.LabelFrame(main_frame, text="Log", style='Emphasis.TLabelframe')
        log_frame.pack(fill='x', pady=(0, 10), ipady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD)
        self.log_text.pack(fill='both', padx=10, pady=5)
        self.log_text.config(state='disabled')

        ttk.Frame(main_frame, height=20).pack(fill='x')
    
    def setup_results_tab(self):
        results_frame = ttk.Frame(self.results_tab)
        results_frame.pack(fill='both', expand=True, padx=20, pady=20)
 
        header_frame = ttk.Frame(results_frame)
        header_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(header_frame, text="Scraping Results", font=('Segoe UI', 12, 'bold')).pack(side='left')
        
        self.refresh_button = ttk.Button(header_frame, text="Refresh", command=self.refresh_results)
        self.refresh_button.pack(side='right')

        paned_window = ttk.PanedWindow(results_frame, orient=tk.VERTICAL)
        paned_window.pack(fill='both', expand=True)

        summary_frame = ttk.LabelFrame(paned_window, text="Summary")
        paned_window.add(summary_frame, weight=1)
        
        self.summary_text = scrolledtext.ScrolledText(summary_frame, height=5, wrap=tk.WORD)
        self.summary_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.summary_text.config(state='disabled')
    
        files_frame = ttk.LabelFrame(paned_window, text="Files")
        paned_window.add(files_frame, weight=2)
  
        columns = ('filename', 'date_range', 'keyword', 'size', 'tweets')
        self.files_tree = ttk.Treeview(files_frame, columns=columns, show='headings')
        
        self.files_tree.heading('filename', text='Filename')
        self.files_tree.heading('date_range', text='Date Range')
        self.files_tree.heading('keyword', text='Keyword')
        self.files_tree.heading('size', text='Size')
        self.files_tree.heading('tweets', text='Tweets')
        
        self.files_tree.column('filename', width=200)
        self.files_tree.column('date_range', width=150)
        self.files_tree.column('keyword', width=150)
        self.files_tree.column('size', width=80)
        self.files_tree.column('tweets', width=80)
        
        scrollbar = ttk.Scrollbar(files_frame, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscroll=scrollbar.set)
        
        self.files_tree_menu = tk.Menu(self.files_tree, tearoff=0)
        self.files_tree_menu.add_command(label="Open File", command=self.open_selected_file)
        self.files_tree_menu.add_command(label="Open Folder", command=self.open_containing_folder)
        
        self.files_tree.bind("<Button-3>", self.show_files_tree_menu)
        self.files_tree.bind("<Double-1>", lambda e: self.open_selected_file())
        
        scrollbar.pack(side='right', fill='y')
        self.files_tree.pack(side='left', fill='both', expand=True)
        
        action_frame = ttk.Frame(results_frame)
        action_frame.pack(fill='x', pady=10)
        
        ttk.Button(action_frame, text="Open Output Folder", 
                  command=self.open_output_folder).pack(side='left', padx=5)
        
        ttk.Button(action_frame, text="Export Results Summary", 
                  command=self.export_results_summary).pack(side='left', padx=5)
    
    def setup_settings_tab(self):
        settings_frame = ttk.Frame(self.settings_tab)
        settings_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        auth_frame = ttk.LabelFrame(settings_frame, text="Authentication")
        auth_frame.pack(fill='x', pady=(0, 15), ipady=5)
        
        ttk.Label(auth_frame, text="Auth Token:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        
        token_frame = ttk.Frame(auth_frame)
        token_frame.grid(row=0, column=1, padx=10, pady=10, sticky='w')
        
        self.auth_token_entry = ttk.Entry(token_frame, textvariable=self.auth_token_var, width=40, show="*")
        self.auth_token_entry.pack(side='left')
        
        self.show_token_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(token_frame, text="Show", variable=self.show_token_var, 
                       command=self.toggle_token_visibility).pack(side='left', padx=5)
        
        ttk.Button(auth_frame, text="Save Token", command=self.save_auth_token).grid(
            row=0, column=2, padx=10, pady=10, sticky='w')
        
        ttk.Label(auth_frame, text="How to get your token:").grid(
            row=1, column=0, padx=10, pady=(0, 10), sticky='w')
        
        token_instructions = ttk.Label(
            auth_frame, 
            text="1. Log in to Twitter (x.com) in your browser\n" +
                 "2. Press F12 to open developer tools\n" +
                 "3. Go to the Application tab (you may need to click >> to see it)\n" +
                 "4. Under Storage, expand Cookies and click on x.com\n" +
                 "5. In the cookies list, search for 'auth_token'\n" +
                 "6. Copy the value of the auth_token cookie"
        )
        token_instructions.grid(row=1, column=1, columnspan=2, padx=10, pady=(0, 10), sticky='w')
        
        output_frame = ttk.LabelFrame(settings_frame, text="Output Settings")
        output_frame.pack(fill='x', pady=(0, 15), ipady=5)
        
        ttk.Label(output_frame, text="Files will be saved directly in this folder:").grid(
            row=0, column=0, columnspan=3, padx=10, pady=(10, 0), sticky='w')
        
        ttk.Label(output_frame, text="Default Output Directory:").grid(
            row=1, column=0, padx=10, pady=10, sticky='w')
        
        display_path = self.output_dir_var.get()
        if "/tweets-data" in display_path:
            display_path = display_path.replace("/tweets-data", "")
            self.output_dir_var.set(display_path)
        
        dir_frame = ttk.Frame(output_frame)
        dir_frame.grid(row=1, column=1, padx=10, pady=10, sticky='w')
        
        ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=40).pack(side='left')
        
        ttk.Button(dir_frame, text="...", width=3, command=self.browse_output_dir).pack(side='left')
        
        ttk.Button(output_frame, text="Save", command=self.save_output_dir).grid(
            row=1, column=2, padx=10, pady=10, sticky='w')
        
        node_frame = ttk.LabelFrame(settings_frame, text="System Requirements")
        node_frame.pack(fill='x', pady=(0, 15), ipady=5)
        
        self.node_status_var = tk.StringVar(value="Checking Node.js installation...")
        node_status_label = ttk.Label(node_frame, textvariable=self.node_status_var)
        node_status_label.pack(anchor='w', padx=10, pady=10)
        
        ttk.Button(node_frame, text="Check Again", command=self.check_node_install).pack(
            anchor='w', padx=10, pady=(0, 10))
    
    def setup_help_tab(self):
        help_frame = ttk.Frame(self.help_tab)
        help_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        help_notebook = ttk.Notebook(help_frame)
        help_notebook.pack(fill='both', expand=True)
        
        getting_started = ttk.Frame(help_notebook)
        help_notebook.add(getting_started, text='Getting Started')
        
        getting_started_text = scrolledtext.ScrolledText(getting_started, wrap=tk.WORD)
        getting_started_text.pack(fill='both', expand=True, padx=10, pady=10)
        getting_started_text.insert(tk.END, """# Twitter Scraper Agent - Getting Started

## Quick Start
1. Check that Node.js is installed (see System Requirements in Settings tab)
2. Set your Twitter auth token in the Settings tab
3. Enter one or more keywords in the Scraper tab
4. Set your desired date range and interval
5. Click "Start Scraping"

## Date Ranges
- Choose a start and end year
- Select how to split the date range (yearly, quarterly, monthly, weekly, daily)
- Use "Preview Date Ranges" to see how your date range will be split

## Keywords
- Enter one keyword per line
- Use quotes around phrases for exact matching (e.g., "Universitas Indonesia")
- Without quotes, words will match in any order
""")
        getting_started_text.config(state='disabled')
        
        keywords_help = ttk.Frame(help_notebook)
        help_notebook.add(keywords_help, text='Keywords')
        
        keywords_help_text = scrolledtext.ScrolledText(keywords_help, wrap=tk.WORD)
        keywords_help_text.pack(fill='both', expand=True, padx=10, pady=10)
        keywords_help_text.insert(tk.END, """# Keyword Tips

## Without Quotes (Flexible Search)
- Single words: gibran, jokowi, prabowo
- Hashtags: #pilpres2024, #debatcapres
- Multiple keywords: gibran rakabuming (finds tweets with both words)
- Better for: broad searches, variations, typos

## With Quotes (Exact Phrase)
- Exact phrases: "Gibran Rakabuming Raka"
- Institution names: "Universitas Indonesia"
- Specific terms: "Presiden Jokowi"
- Better for: precise searches, official names

## Advanced Tips
- Use hashtags without quotes: #pilpres2024
- Mix and match: Use both quoted and unquoted keywords for different searches
- For popular topics, consider using smaller date ranges (weekly or daily)
""")
        keywords_help_text.config(state='disabled')
        
        troubleshooting = ttk.Frame(help_notebook)
        help_notebook.add(troubleshooting, text='Troubleshooting')
        
        troubleshooting_text = scrolledtext.ScrolledText(troubleshooting, wrap=tk.WORD)
        troubleshooting_text.pack(fill='both', expand=True, padx=10, pady=10)
        troubleshooting_text.insert(tk.END, """# Troubleshooting

## Common Issues

### No Results or Empty Files
- Check that your auth token is valid and up-to-date
- Try a different date range or more common keywords
- Make sure your quotes are properly formatted (use straight quotes: "keyword")
- Try without quotes for broader matching

### Node.js Not Found
- Install Node.js from https://nodejs.org/
- Restart the application after installation
- Make sure Node.js is in your system PATH

### Authentication Issues
- Twitter auth tokens expire periodically
- Update your token in the Settings tab
- Follow the instructions to get a new token

### Rate Limiting
- If you're getting rate limit errors, wait a while before trying again
- Consider using longer intervals between requests
- Split your scraping into smaller batches
""")
        troubleshooting_text.config(state='disabled')
        
        about = ttk.Frame(help_notebook)
        help_notebook.add(about, text='About')
        
        about_text = scrolledtext.ScrolledText(about, wrap=tk.WORD)
        about_text.pack(fill='both', expand=True, padx=10, pady=10)
        about_text.insert(tk.END, """# About Twitter Scraper Agent

## Overview
Twitter Scraper Agent is a tool for automatically scraping tweets based on keywords and date ranges. It provides a user-friendly interface for configuring and running tweet scraping jobs.

## Features
- Scrape tweets for multiple keywords
- Configure date ranges and intervals
- Support for exact phrase matching
- Batch processing with detailed results
- CSV output for easy analysis

## Credits
This tool uses tweet-harvest for the actual scraping functionality.

## Version
1.0.0 - August 2025
""")
        about_text.config(state='disabled')
    
    def unbind_all_mousewheel(self):
        if sys.platform.startswith('win'):
            self.root.unbind_all("<MouseWheel>")
        elif sys.platform.startswith('darwin'):
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Button-4>")
            self.root.unbind_all("<Button-5>")
        else:
            self.root.unbind_all("<Button-4>")
            self.root.unbind_all("<Button-5>")
            
    def get_days_in_month(self, year, month):
        return calendar.monthrange(int(year), int(month))[1]
    
    def update_day_options(self, year_var, month_var, day_var, day_combobox):
        try:
            year = int(year_var.get())
            month = int(month_var.get())
            
            current_day = day_var.get()
            
            max_days = self.get_days_in_month(year, month)
            
            days = [f"{d:02d}" for d in range(1, max_days + 1)]
            
            day_combobox['values'] = days
            
            if int(current_day) > max_days:
                day_var.set(f"{max_days:02d}")
        except ValueError:
            pass
    
    def change_month_year(self, year_label, month_label, delta):
        current_year = int(year_label.cget("text"))
        month_names = list(calendar.month_name)
        current_month_idx = month_names.index(month_label.cget("text"))
        
        new_month_idx = current_month_idx + delta
        new_year = current_year
        
        if new_month_idx < 1:
            new_month_idx = 12
            new_year -= 1
        elif new_month_idx > 12:
            new_month_idx = 1
            new_year += 1
            
        month_label.config(text=calendar.month_name[new_month_idx])
        year_label.config(text=str(new_year))
        
        return new_year, new_month_idx
    
    def change_year(self, year_label, delta):
        current_year = int(year_label.cget("text"))
        new_year = current_year + delta
        year_label.config(text=str(new_year))
        return new_year
    
    def show_calendar(self, year_var, month_var, day_var):
        cal_win = tk.Toplevel(self.root)
        cal_win.title("Select Date")
        cal_win.transient(self.root)
        cal_win.grab_set()
        
        try:
            year = int(year_var.get())
            month = int(month_var.get())
            day = int(day_var.get())
        except ValueError:
            today = datetime.now()
            year = today.year
            month = today.month
            day = today.day
        
        cal_frame = ttk.Frame(cal_win, padding=10)
        cal_frame.pack(fill='both', expand=True)
        
        header_frame = ttk.Frame(cal_frame)
        header_frame.pack(fill='x', pady=(0, 10))
        
        cal_year = year
        cal_month = month
        
        prev_month = ttk.Button(header_frame, text="<", width=2)
        prev_month.pack(side='left')
        
        month_label = ttk.Label(header_frame, text=calendar.month_name[month], width=10, anchor='center')
        month_label.pack(side='left', padx=5)
        
        next_month = ttk.Button(header_frame, text=">", width=2)
        next_month.pack(side='left')
        
        prev_year = ttk.Button(header_frame, text="<<", width=2)
        prev_year.pack(side='left', padx=(20, 0))
        
        year_label = ttk.Label(header_frame, text=str(year), width=6, anchor='center')
        year_label.pack(side='left', padx=5)
        
        next_year = ttk.Button(header_frame, text=">>", width=2)
        next_year.pack(side='left')
        
        days_frame = ttk.Frame(cal_frame)
        days_frame.pack(fill='both')
        
        for i, day_name in enumerate(calendar.day_abbr):
            ttk.Label(days_frame, text=day_name, width=4, anchor='center').grid(row=0, column=i, padx=2, pady=2)
        
        day_buttons = []
        
        def create_calendar(year, month):
            nonlocal cal_year, cal_month
            cal_year = year
            cal_month = month
            
            for btn in day_buttons:
                btn.grid_forget()
            day_buttons.clear()
            
            cal = calendar.monthcalendar(year, month)
            
            for week_num, week in enumerate(cal, 1):
                for day_idx, day_num in enumerate(week):
                    if day_num != 0:
                        btn = ttk.Button(days_frame, text=str(day_num), width=4,
                                       command=lambda d=day_num: select_date(year, month, d))
                        btn.grid(row=week_num, column=day_idx, padx=2, pady=2)
                        if day_num == day and month == int(month_var.get()) and year == int(year_var.get()):
                            btn.configure(style='Selected.TButton')
                        day_buttons.append(btn)
        
        def select_date(year, month, day):
            year_var.set(str(year))
            month_var.set(f"{month:02d}")
            day_var.set(f"{day:02d}")
            cal_win.destroy()
        
        def prev_month_clicked():
            nonlocal cal_year, cal_month
            if cal_month == 1:
                cal_month = 12
                cal_year -= 1
            else:
                cal_month -= 1
            month_label.config(text=calendar.month_name[cal_month])
            year_label.config(text=str(cal_year))
            create_calendar(cal_year, cal_month)
        
        def next_month_clicked():
            nonlocal cal_year, cal_month
            if cal_month == 12:
                cal_month = 1
                cal_year += 1
            else:
                cal_month += 1
            month_label.config(text=calendar.month_name[cal_month])
            year_label.config(text=str(cal_year))
            create_calendar(cal_year, cal_month)
        
        def prev_year_clicked():
            nonlocal cal_year
            cal_year -= 1
            year_label.config(text=str(cal_year))
            create_calendar(cal_year, cal_month)
        
        def next_year_clicked():
            nonlocal cal_year
            cal_year += 1
            year_label.config(text=str(cal_year))
            create_calendar(cal_year, cal_month)
        
        prev_month.config(command=prev_month_clicked)
        next_month.config(command=next_month_clicked)
        prev_year.config(command=prev_year_clicked)
        next_year.config(command=next_year_clicked)
        
        create_calendar(year, month)
        
        today = datetime.now()
        ttk.Button(cal_frame, text="Today",
                 command=lambda: select_date(today.year, today.month, today.day)).pack(pady=10)
        
        cal_win.update_idletasks()
        width = cal_win.winfo_width()
        height = cal_win.winfo_height()
        x = (cal_win.winfo_screenwidth() // 2) - (width // 2)
        y = (cal_win.winfo_screenheight() // 2) - (height // 2)
        cal_win.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    
    def log(self, message):
        self.log_text.config(state='normal')
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        logger.info(message)
    
    def check_node_install(self):
        self.log("Checking Node.js installation...")
        self.node_status_var.set("Checking Node.js installation...")
        
        def check_thread():
            result = self.scraper.check_node_installation()
            if result['success']:
                self.node_status_var.set(
                    f"✅ Node.js {result['node']} and npx {result['npx']} found and working properly."
                )
                self.log(f"Node.js {result['node']} and npx {result['npx']} found.")
            else:
                self.node_status_var.set(
                    f"❌ Node.js installation issue: {result['error']}\n" +
                    "Please install Node.js from https://nodejs.org/"
                )
                self.log(f"Node.js issue: {result['error']}")
        
        threading.Thread(target=check_thread).start()
    
    def check_auth_token(self):
        if not self.auth_token_var.get() or self.auth_token_var.get() == 'your_auth_token_here':
            messagebox.showwarning(
                "Auth Token Required",
                "Please set your Twitter auth token in the Settings tab before scraping."
            )
            self.notebook.select(self.settings_tab)
    
    def toggle_token_visibility(self):
        if self.show_token_var.get():
            self.auth_token_entry.config(show="")
        else:
            self.auth_token_entry.config(show="*")
    
    def save_auth_token(self):
        token = self.auth_token_var.get().strip()
        if not token:
            messagebox.showerror("Error", "Auth token cannot be empty")
            return
        
        update_auth_token(token)
        self.scraper.auth_token = token
        messagebox.showinfo("Success", "Auth token saved successfully!")
        self.log("Auth token updated")
    
    def save_output_dir(self):
        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showerror("Error", "Output directory cannot be empty")
            return
        
        os.makedirs(output_dir, exist_ok=True)
        self.scraper.output_dir = output_dir
        try:
            from pathlib import Path
            env_file = Path(__file__).parent / '.env'
            
            if env_file.exists():
                with open(env_file, 'r') as f:
                    lines = f.readlines()
                
                updated = False
                for i, line in enumerate(lines):
                    if line.startswith('OUTPUT_DIR='):
                        lines[i] = f"OUTPUT_DIR={output_dir}\n"
                        updated = True
                        break
                
                if not updated:
                    lines.append(f"OUTPUT_DIR={output_dir}\n")
                
                with open(env_file, 'w') as f:
                    f.writelines(lines)
                
                self.log(f"Updated OUTPUT_DIR in .env file to: {output_dir}")
        except Exception as e:
            self.log(f"Warning: Could not update .env file: {e}")
        
        messagebox.showinfo("Success", "Output directory saved successfully!")
        self.log(f"Output directory updated to: {output_dir}")
    
    def browse_output_dir(self):
        current_dir = self.output_dir_var.get()
        new_dir = filedialog.askdirectory(initialdir=current_dir)
        if new_dir:
            self.output_dir_var.set(new_dir)
            self.scraper.output_dir = new_dir
    
    def preview_date_ranges(self):
        try:
            start_year = int(self.start_year_var.get())
            start_month = int(self.start_month_var.get())
            start_day = int(self.start_day_var.get())
            
            end_year = int(self.end_year_var.get())
            end_month = int(self.end_month_var.get())
            end_day = int(self.end_day_var.get())
            
            start_date = f"{start_year}-{start_month:02d}-{start_day:02d}"
            end_date = f"{end_year}-{end_month:02d}-{end_day:02d}"
            
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error", "Invalid date. Please check year, month, and day values.")
                return
            
            if datetime.strptime(start_date, '%Y-%m-%d') > datetime.strptime(end_date, '%Y-%m-%d'):
                messagebox.showerror("Error", "Start date must be before or equal to end date")
                return
            
            interval = self.interval_var.get()
            date_ranges = self.scraper.generate_date_ranges(start_date, end_date, interval)
            
            if not date_ranges:
                messagebox.showerror("Error", "Could not generate date ranges")
                return
            
            preview_window = tk.Toplevel(self.root)
            preview_window.title("Date Ranges Preview")
            preview_window.geometry("500x400")
            preview_window.transient(self.root)
            preview_window.grab_set()
            scrollable = ScrollableFrame(preview_window)
            scrollable.pack(fill='both', expand=True, padx=10, pady=10)
            
            ttk.Label(
                scrollable.scrollable_frame, 
                text=f"Date Ranges ({len(date_ranges)} total):",
                font=('Segoe UI', 10, 'bold')
            ).pack(anchor='w', pady=(0, 10))
            
            for i, (start, end) in enumerate(date_ranges, 1):
                ttk.Label(
                    scrollable.scrollable_frame,
                    text=f"{i}. {start} to {end}"
                ).pack(anchor='w', pady=2)
            
            ttk.Button(
                preview_window, 
                text="Close", 
                command=preview_window.destroy
            ).pack(pady=10)
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid date format: {str(e)}")
    
    def add_keyword_examples(self):
        examples = [
            "gibran",
            "\"Gibran Rakabuming Raka\"",
            "#pilpres2024",
            "\"Universitas Indonesia\"",
            "jokowi president",
            "\"Menteri Pendidikan\""
        ]
        
        example_window = tk.Toplevel(self.root)
        example_window.title("Keyword Examples")
        example_window.geometry("500x400")
        example_window.transient(self.root)
        example_window.grab_set()
        
        frame = ttk.Frame(example_window, padding=10)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(
            frame, 
            text="Keyword Examples:",
            font=('Segoe UI', 12, 'bold')
        ).pack(anchor='w', pady=(0, 10))
        
        ttk.Label(
            frame,
            text="Click on examples to add them to your keywords:",
            font=('Segoe UI', 10)
        ).pack(anchor='w', pady=(0, 10))
        ttk.Label(
            frame,
            text="Without quotes (flexible search):",
            font=('Segoe UI', 10, 'bold')
        ).pack(anchor='w', pady=(10, 5))
        
        simple_frame = ttk.Frame(frame)
        simple_frame.pack(fill='x', pady=5)
        
        for ex in ["gibran", "#pilpres2024", "jokowi president"]:
            btn = ttk.Button(
                simple_frame,
                text=ex,
                command=lambda kw=ex: self.add_keyword_to_text(kw)
            )
            btn.pack(side='left', padx=5, pady=5)
        
        ttk.Label(
            frame,
            text="With quotes (exact phrase):",
            font=('Segoe UI', 10, 'bold')
        ).pack(anchor='w', pady=(10, 5))
        
        quoted_frame = ttk.Frame(frame)
        quoted_frame.pack(fill='x', pady=5)
        
        for ex in ["\"Gibran Rakabuming Raka\"", "\"Universitas Indonesia\"", "\"Menteri Pendidikan\""]:
            btn = ttk.Button(
                quoted_frame,
                text=ex.replace('\"', ''),
                command=lambda kw=ex: self.add_keyword_to_text(kw)
            )
            btn.pack(side='left', padx=5, pady=5)
        
        explanation = ttk.LabelFrame(frame, text="How Keywords Work")
        explanation.pack(fill='x', pady=10)
        
        explanation_text = scrolledtext.ScrolledText(explanation, wrap=tk.WORD, height=8)
        explanation_text.pack(fill='both', expand=True, padx=5, pady=5)
        explanation_text.insert(tk.END, 
            "WITHOUT QUOTES (Flexible Search):\n" +
            "• Single words: gibran, jokowi, prabowo\n" +
            "• Hashtags: #pilpres2024, #debatcapres\n" +
            "• Multiple keywords: gibran rakabuming (finds tweets with both words in any order)\n" +
            "• Better for: broad searches, variations, typos\n\n" +
            "WITH QUOTES (Exact Phrase):\n" +
            "• Exact phrases: \"Gibran Rakabuming Raka\"\n" +
            "• Institution names: \"Universitas Indonesia\"\n" +
            "• Specific terms: \"Presiden Jokowi\"\n" +
            "• Better for: precise searches, official names"
        )
        explanation_text.config(state='disabled')
        
        ttk.Button(
            example_window, 
            text="Close", 
            command=example_window.destroy
        ).pack(pady=10)
    
    def add_keyword_to_text(self, keyword):
        current_text = self.keywords_text.get('1.0', tk.END).strip()
        if current_text:
            self.keywords_text.insert(tk.END, f"\n{keyword}")
        else:
            self.keywords_text.insert(tk.END, keyword)
        
        self.log(f"Added keyword: {keyword}")
    
    def parse_keywords_with_quotes(self, keywords_text):
        lines = keywords_text.strip().split('\n')
        keywords = []
        use_quotes = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            quoted_match = re.match(r'^"(.+)"$', line)
            if quoted_match:
                keywords.append(quoted_match.group(1))
                use_quotes.append(True)
            else:
                keywords.append(line)
                use_quotes.append(False)
        
        return keywords, use_quotes
    
    def start_scraping(self):
        if not self.auth_token_var.get() or self.auth_token_var.get() == 'your_auth_token_here':
            messagebox.showwarning(
                "Auth Token Required",
                "Please set your Twitter auth token in the Settings tab before scraping."
            )
            self.notebook.select(self.settings_tab)
            return
        
        try:
            start_year = int(self.start_year_var.get())
            start_month = int(self.start_month_var.get())
            start_day = int(self.start_day_var.get())
            
            end_year = int(self.end_year_var.get())
            end_month = int(self.end_month_var.get())
            end_day = int(self.end_day_var.get())
            
            start_max_days = self.get_days_in_month(start_year, start_month)
            end_max_days = self.get_days_in_month(end_year, end_month)
            
            if start_day > start_max_days:
                messagebox.showerror(
                    "Error", 
                    f"Invalid start day: {start_day}. {calendar.month_name[start_month]} {start_year} has only {start_max_days} days."
                )
                return
                
            if end_day > end_max_days:
                messagebox.showerror(
                    "Error", 
                    f"Invalid end day: {end_day}. {calendar.month_name[end_month]} {end_year} has only {end_max_days} days."
                )
                return
            
            start_date = f"{start_year}-{start_month:02d}-{start_day:02d}"
            end_date = f"{end_year}-{end_month:02d}-{end_day:02d}"
            
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                self.start_date = start_date_obj
                self.end_date = end_date_obj
            except ValueError:
                messagebox.showerror("Error", "Invalid date. Please check year, month, and day values.")
                return
                
            if start_date_obj > end_date_obj:
                messagebox.showerror("Error", "Start date must be before end date")
                return
            
            interval = self.interval_var.get()
            limit = int(self.limit_var.get())
            lang = self.lang_var.get()
            tab = self.tab_var.get()
            keywords_text = self.keywords_text.get('1.0', tk.END)
            keywords, use_quotes = self.parse_keywords_with_quotes(keywords_text)
            
            if not keywords:
                messagebox.showerror("Error", "Please enter at least one keyword")
                return
            
            output_dir = self.output_dir_var.get()
            self.scraper.output_dir = output_dir
            self.stop_requested = False
            self.stop_button.config(state='normal')
            self.status_var.set("Scraping in progress...")
            self.progress_var.set(0)
            
            self.log(f"Starting batch scrape with {len(keywords)} keywords")
            self.log(f"Date range: {start_date} to {end_date}, split by {interval}")
            self.log(f"Output directory: {output_dir}")
            
            for i, kw in enumerate(keywords):
                self.log(f"Keyword {i+1}: {kw} ({'with' if use_quotes[i] else 'without'} quotes)")
            
            import threading
            import time
            threading.Thread(
                target=self.run_scraping_job,
                args=(keywords, use_quotes, start_date, end_date, interval, limit, lang, tab)
            ).start()
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {str(e)}")
    
    def run_scraping_job(self, keywords, use_quotes, start_date, end_date, interval, limit, lang, tab):
        import time
        
        try:
            self.current_batch = self.scraper.batch_scrape(
                keywords=keywords,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                use_quotes=use_quotes,
                limit=limit,
                lang=lang,
                tab=tab
            )
            
            total_jobs = self.current_batch['total_jobs']
            
            while self.current_batch['completed_jobs'] < total_jobs and not self.stop_requested:
                progress = (self.current_batch['completed_jobs'] / total_jobs) * 100
                self.progress_var.set(progress)
                self.status_var.set(f"Scraping: {self.current_batch['completed_jobs']}/{total_jobs} jobs")
                time.sleep(0.5)
            
            if self.stop_requested:
                self.log("Scraping stopped by user")
                self.status_var.set("Scraping stopped")
            else:
                self.progress_var.set(100)
                self.status_var.set(f"Completed: {self.current_batch['successful_jobs']}/{total_jobs} successful")
                self.log(f"Scraping completed. {self.current_batch['successful_jobs']}/{total_jobs} jobs successful")
            
            self.refresh_results()
            
            if not self.stop_requested:
                messagebox.showinfo(
                    "Scraping Complete",
                    f"Completed {self.current_batch['successful_jobs']}/{total_jobs} jobs successfully.\n\n" +
                    f"Files saved to: {self.scraper.output_dir}"
                )
                self.notebook.select(self.results_tab)
            
        except Exception as e:
            self.log(f"Error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred during scraping: {str(e)}")
        
        finally:
            self.stop_button.config(state='disabled')
    
    def stop_scraping(self):
        if messagebox.askyesno("Stop Scraping", "Are you sure you want to stop the scraping process?"):
            self.stop_requested = True
            self.log("Requesting to stop scraping...")
            self.status_var.set("Stopping...")
    
    def clear_form(self):
        if messagebox.askyesno("Clear Form", "Are you sure you want to clear all inputs?"):
            original_bg = self.main_tab.cget("background")
            self.main_tab.configure(background="#f0f0f0")
            self.root.update_idletasks()
            self.root.after(100)
            self.main_tab.configure(background=original_bg)
            
            current_year = datetime.now().year
            current_month = datetime.now().month
            current_day = datetime.now().day
            
            self.start_year_var.set(str(current_year-1))
            self.start_month_var.set("01")
            self.start_day_var.set("01")
            
            self.end_year_var.set(str(current_year))
            self.end_month_var.set(f"{current_month:02d}")
            self.end_day_var.set(f"{current_day:02d}")
            
            self.start_date = datetime(current_year-1, 1, 1)
            self.end_date = datetime(current_year, current_month, current_day)
            
            self.interval_var.set("monthly")
        
            self.keywords_text.delete('1.0', tk.END)
            self.limit_var.set(str(config['default_limit']))
            self.lang_var.set(config['default_lang'])
            self.tab_var.set(config['default_tab'])
            
            self.log_text.config(state='normal')
            self.log_text.delete('1.0', tk.END)
            self.log_text.config(state='disabled')
            
            default_keywords = "#pilpres2024\ngibran\n\"Universitas Indonesia\""
            self.keywords_text.insert('1.0', default_keywords)
            
            self.log("Form cleared - all inputs have been reset to defaults")
            self.status_var.set("Form cleared successfully")
            
            self.progress_var.set(100)
            self.root.update_idletasks()
            self.root.after(500)
            self.progress_var.set(0)
    
    def refresh_results(self):
        # Clear existing tree items
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)
        self.summary_text.config(state='normal')
        self.summary_text.delete('1.0', tk.END)
        
        output_dir = Path(self.scraper.output_dir)
        
        if self.current_batch:
            self.summary_text.insert(tk.END, "BATCH SCRAPING SUMMARY\n\n")
            
            self.summary_text.insert(tk.END, f"Total Jobs: {self.current_batch['total_jobs']}\n")
            self.summary_text.insert(tk.END, f"Successful: {self.current_batch['successful_jobs']}\n")
            self.summary_text.insert(tk.END, f"Failed: {self.current_batch['failed_jobs']}\n\n")
            
            start_time = self.current_batch['start_time'].strftime('%Y-%m-%d %H:%M:%S')
            self.summary_text.insert(tk.END, f"Start Time: {start_time}\n")
            
            if self.current_batch['end_time']:
                end_time = self.current_batch['end_time'].strftime('%Y-%m-%d %H:%M:%S')
                duration_sec = self.current_batch['total_duration']
                
                if duration_sec < 60:
                    duration = f"{duration_sec:.1f} seconds"
                elif duration_sec < 3600:
                    duration = f"{duration_sec/60:.1f} minutes"
                else:
                    duration = f"{duration_sec/3600:.1f} hours"
                
                self.summary_text.insert(tk.END, f"End Time: {end_time}\n")
                self.summary_text.insert(tk.END, f"Total Duration: {duration}\n")
            
        else:
            self.summary_text.insert(tk.END, "No batch scraping results available.\n\n")
        
        self.summary_text.insert(tk.END, "\nOUTPUT DIRECTORY SUMMARY\n\n")
        
        if output_dir.exists():
            csv_files = list(output_dir.glob("*.csv"))
            
            tweets_data_dir = output_dir / 'tweets-data'
            if tweets_data_dir.exists():
                nested_csv_files = list(tweets_data_dir.glob("*.csv"))
                if nested_csv_files:
                    self.summary_text.insert(tk.END, "Note: Found legacy CSV files in nested tweets-data folder.\n")
                    self.summary_text.insert(tk.END, "Moving them to the main directory...\n")
                    
                    moved_count = 0
                    import shutil
                    for nested_file in nested_csv_files:
                        target_file = output_dir / nested_file.name
                        try:
                            if not target_file.exists():
                                shutil.copy2(nested_file, target_file)
                                try:
                                    os.remove(nested_file)
                                    moved_count += 1
                                except Exception:
                                    self.summary_text.insert(tk.END, f"Copied: {nested_file.name} to main directory (but couldn't delete source)\n")
                            else:
                                self.summary_text.insert(tk.END, f"Skipped: {nested_file.name} already exists in main directory\n")
                        except Exception as e:
                            self.summary_text.insert(tk.END, f"Error moving {nested_file.name}: {e}\n")
                    
                    if moved_count > 0:
                        self.summary_text.insert(tk.END, f"Successfully moved {moved_count} files to main directory\n\n")
                    
                    csv_files = list(output_dir.glob("*.csv"))
                    
                    try:
                        remaining_files = list(tweets_data_dir.glob("*"))
                        if not remaining_files:
                            import shutil
                            shutil.rmtree(tweets_data_dir)
                            self.summary_text.insert(tk.END, "Removed empty tweets-data directory\n\n")
                    except Exception as e:
                        self.summary_text.insert(tk.END, f"Note: Could not remove tweets-data directory: {e}\n\n")
            
            self.summary_text.insert(tk.END, f"Output Directory: {output_dir}\n")
            self.summary_text.insert(tk.END, f"Total CSV Files: {len(csv_files)}\n")
            
            total_size = sum(f.stat().st_size for f in csv_files)
            
            if total_size < 1024:
                size_str = f"{total_size} bytes"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size/1024:.1f} KB"
            else:
                size_str = f"{total_size/(1024*1024):.1f} MB"
            
            self.summary_text.insert(tk.END, f"Total Size: {size_str}\n")
            
            for csv_file in csv_files:
                filename = csv_file.name
                
                try:
                    parts = filename.replace('.csv', '').split('_')
                    
                    date_indices = []
                    for i, part in enumerate(parts):
                        if re.match(r'^(\d{4})$', part):  # Year
                            date_indices.append(i)
                    
                    if len(date_indices) >= 2:
                        keyword = ' '.join(parts[:date_indices[0]])
                        date_str = ' to '.join([
                            '-'.join(parts[date_indices[0]:date_indices[0]+3]),
                            '-'.join(parts[date_indices[1]:date_indices[1]+3])
                        ])
                    else:
                        keyword = ' '.join(parts[:-3] if len(parts) > 3 else parts)
                        date_str = '-'.join(parts[-3:]) if len(parts) > 3 else "Unknown"
                    
                    size = csv_file.stat().st_size
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size/1024:.1f} KB"
                    else:
                        size_str = f"{size/(1024*1024):.1f} MB"
                    
                    try:
                        df = pd.read_csv(csv_file)
                        tweet_count = len(df)
                    except:
                        tweet_count = "N/A"
                    
                    self.files_tree.insert(
                        '', 'end', values=(filename, date_str, keyword, size_str, tweet_count),
                        tags=(str(csv_file),)
                    )
                    
                except Exception as e:
                    self.files_tree.insert(
                        '', 'end', values=(filename, "Unknown", "Unknown", "Unknown", "Unknown"),
                        tags=(str(csv_file),)
                    )
        else:
            self.summary_text.insert(tk.END, f"Output directory {output_dir} does not exist.")
        
        self.summary_text.config(state='disabled')
    
    def show_files_tree_menu(self, event):
        iid = self.files_tree.identify_row(event.y)
        if iid:
            self.files_tree.selection_set(iid)
            self.files_tree_menu.post(event.x_root, event.y_root)
    
    def open_selected_file(self):
        selection = self.files_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        file_path = self.files_tree.item(item, "tags")[0]
        
        try:
            if os.name == 'nt':  
                os.startfile(file_path)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {str(e)}")
    
    def open_containing_folder(self):
        """Open the folder containing the selected file"""
        selection = self.files_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        file_path = self.files_tree.item(item, "tags")[0]
        folder_path = os.path.dirname(file_path)
        
        try:
            if os.name == 'nt':  
                os.startfile(folder_path)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', folder_path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {str(e)}")
    
    def open_output_folder(self):
        output_dir = self.output_dir_var.get()
        if not os.path.exists(output_dir):
            messagebox.showerror("Error", f"Output directory {output_dir} does not exist")
            return
        
        try:
            if os.name == 'nt':  
                os.startfile(output_dir)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', output_dir])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {str(e)}")
    
    def export_results_summary(self):
        if not self.current_batch:
            messagebox.showwarning("Warning", "No batch results available to export")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=self.output_dir_var.get(),
            initialfile=f"scraping_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        if not file_path:
            return
        
        try:
            export_data = self.current_batch.copy()
            export_data['start_time'] = self.current_batch['start_time'].strftime('%Y-%m-%d %H:%M:%S')
            
            if self.current_batch['end_time']:
                export_data['end_time'] = self.current_batch['end_time'].strftime('%Y-%m-%d %H:%M:%S')
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
            
            messagebox.showinfo("Success", f"Results summary exported to {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not export results: {str(e)}")

def main():
    root = tk.Tk()
    app = TwitterScraperApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
