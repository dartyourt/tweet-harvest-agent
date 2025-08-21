"""
Twitter Scraper module - core functionality for tweet scraping
"""
import os
import subprocess
import time
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
import calendar
import re

from config import config, logger

class TwitterScraper:
    """Twitter scraper class with advanced functionality"""
    
    def __init__(self, auth_token=None, output_dir=None):
        """Initialize the scraper with token and output directory"""
        self.auth_token = auth_token or config['auth_token']
        self.output_dir = output_dir or config['output_dir']
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Check for valid auth token
        if not self.auth_token or self.auth_token == 'your_auth_token_here':
            logger.warning("No valid auth token provided. Please update it in the settings.")
    
    def setup_output_directory(self):
        """
        Ensure the output directory structure is ready for tweet-harvest tool
        """
        # Create main output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # tweet-harvest sometimes creates a tweets-data subfolder automatically
        # Let's ensure it exists and then handle files afterward
        tweets_data_dir = os.path.join(self.output_dir, 'tweets-data')
        os.makedirs(tweets_data_dir, exist_ok=True)
        
        # Move any existing files from tweets-data to main directory
        try:
            import shutil
            files_moved = 0
            for file in os.listdir(tweets_data_dir):
                if file.endswith('.csv'):
                    source = os.path.join(tweets_data_dir, file)
                    destination = os.path.join(self.output_dir, file)
                    if not os.path.exists(destination):
                        shutil.copy2(source, destination)
                        files_moved += 1
                        try:
                            os.remove(source)
                        except:
                            pass
            
            if files_moved > 0:
                logger.info(f"Moved {files_moved} existing files from tweets-data to main directory")
        except Exception as e:
            logger.warning(f"Error when checking for existing files: {e}")
        
        logger.info(f"Output directory prepared: {self.output_dir}")
        
        return True
    
    def check_node_installation(self):
        """Check if Node.js and npx are installed"""
        try:
            node_result = subprocess.run(['node', '--version'], 
                                       capture_output=True, text=True, timeout=10, shell=True)
            if node_result.returncode == 0:
                node_version = node_result.stdout.strip()
                logger.info(f"Node.js found: {node_version}")
                
                # Check npx
                npx_result = subprocess.run(['cmd', '/c', 'npx', '--version'], 
                                          capture_output=True, text=True, timeout=10)
                if npx_result.returncode == 0:
                    npx_version = npx_result.stdout.strip()
                    logger.info(f"npx found: {npx_version}")
                    return {'success': True, 'node': node_version, 'npx': npx_version}
                else:
                    logger.warning(f"npx check failed. Return code: {npx_result.returncode}")
                    return {'success': False, 'error': 'npx not found or not working'}
            else:
                logger.error("Node.js not found")
                return {'success': False, 'error': 'Node.js not found'}
        except Exception as e:
            logger.error(f"Error checking Node.js installation: {e}")
            return {'success': False, 'error': str(e)}
    
    def scrape_tweets(self, keyword, start_date, end_date, use_quotes=True, 
                     limit=100, lang='id', tab='LATEST'):
        """
        Scrape tweets for a specific keyword and date range
        
        Args:
            keyword: Search keyword (e.g., "gibran", "Universitas Indonesia", "#pilpres2024")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            use_quotes: Whether to wrap keyword in quotes (True for exact phrases)
            limit: Number of tweets to scrape
            lang: Language filter ('id' for Indonesian, 'en' for English, etc.)
            tab: Search tab ('LATEST' or 'TOP')
            
        Returns:
            Dictionary with scraping results
        """
        # Validate auth token
        if not self.auth_token or self.auth_token == 'your_auth_token_here':
            return {'success': False, 'reason': 'No valid auth token provided'}
        
        # Setup output directory structure
        self.setup_output_directory()
        
        # Create safe filename from keyword
        safe_keyword = re.sub(r'[^\w\s]', '_', keyword).strip()
        safe_keyword = re.sub(r'\s+', '_', safe_keyword).lower()
        filename = f'{safe_keyword}_{start_date.replace("-", "_")}_to_{end_date.replace("-", "_")}.csv'
        
        # Create search keyword with or without quotes
        if use_quotes:
            search_keyword = f'"{keyword}" since:{start_date} until:{end_date} lang:{lang}'
        else:
            search_keyword = f'{keyword} since:{start_date} until:{end_date} lang:{lang}'
        
        logger.info(f"Processing: {keyword} ({start_date} to {end_date})")
        logger.info(f"Search query: {search_keyword}")
        logger.info(f"Mode: {'Exact phrase' if use_quotes else 'Flexible search'}")
        
        # Save current directory to return to it later
        original_cwd = os.getcwd()
        
        # Switch to the scraped_tweets directory, not the tweets-data subdirectory
        os.chdir(self.output_dir)
        
        try:
            # Prepare command based on whether we use quotes or not
            full_output_path = os.path.abspath(filename)
            if use_quotes:
                # For quoted keywords, escape the quotes
                escaped_search = search_keyword.replace('"', '\\"')
                cmd_string = f'npx tweet-harvest@2.6.1 -o "{filename}" -s "{escaped_search}" --tab {tab} -l {limit} --token {self.auth_token}'
            else:
                # For unquoted keywords, no need to escape
                cmd_string = f'npx tweet-harvest@2.6.1 -o "{filename}" -s "{search_keyword}" --tab {tab} -l {limit} --token {self.auth_token}'
            
            # Log redacted command (hide token)
            logger.info(f"Running: npx tweet-harvest@2.6.1 -o \"{filename}\" -s \"{search_keyword}\" --tab {tab} -l {limit} --token [REDACTED]")
            
            process = subprocess.Popen(
                cmd_string,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                shell=True
            )
            
            # Stream output in real-time
            output_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Store original output for logging
                    original_output = output.strip()
                    
                    # Detect tweet-harvest output messages and handle appropriately
                    if "Your tweets saved to:" in output:
                        # Extract the actual path from the message
                        save_path = output.strip().split("Your tweets saved to:")[-1].strip()
                        logger.info(f"Tweet harvest save path: {save_path}")
                        
                        # Add our own message about the final destination
                        final_path = os.path.join(self.output_dir, filename)
                        logger.info(f"Final output location: {final_path}")
                    else:
                        # Log normal outputs
                        logger.info(original_output)
                    
                    # Store the output line
                    output_lines.append(original_output)
            
            return_code = process.wait()
            full_output = '\n'.join(output_lines)
            
            # Check for files in all possible locations
            expected_file = filename  # Direct in current directory
            tweets_data_file = os.path.join("tweets-data", filename)  # In tweets-data subfolder
            
            # First, check if file was created in tweets-data subfolder
            if os.path.exists(tweets_data_file):
                logger.info(f"File found in tweets-data subfolder, moving to main directory")
                # Copy file to main directory
                import shutil
                shutil.copy2(tweets_data_file, filename)
                
                try:
                    # Try to remove original after copying
                    os.remove(tweets_data_file)
                    logger.info("Removed file from tweets-data after copying")
                except Exception as e:
                    logger.warning(f"Could not remove file from tweets-data: {e}")
            
            # Check if file exists in main directory (either originally or after copying)
            if os.path.exists(expected_file):
                file_size = os.path.getsize(expected_file)
                if file_size > 0:
                    final_path = os.path.join(self.output_dir, filename)
                    logger.info(f"Success! File size: {file_size} bytes")
                    logger.info(f"File saved at: {final_path}")
                    
                    # Try to count rows in CSV
                    try:
                        df = pd.read_csv(expected_file)
                        num_tweets = len(df)
                        logger.info(f"Retrieved {num_tweets} tweets")
                    except Exception as e:
                        logger.warning(f"Could not read CSV: {e}")
                        num_tweets = None
                    
                    return {
                        'success': True,
                        'filename': filename,
                        'path': os.path.join(self.output_dir, filename),
                        'size': file_size,
                        'tweet_count': num_tweets,
                        'keyword': keyword,
                        'search_query': search_keyword,
                        'start_date': start_date,
                        'end_date': end_date
                    }
                else:
                    logger.warning("File created but empty (0 bytes)")
                    return {'success': False, 'reason': 'Empty file', 'keyword': keyword}
            else:
                # Check also in tweets-data directory as a last resort
                tweets_data_file = os.path.join("tweets-data", filename)
                if os.path.exists(tweets_data_file):
                    logger.info(f"File only found in tweets-data subfolder")
                    try:
                        import shutil
                        shutil.copy2(tweets_data_file, filename)
                        logger.info(f"Successfully copied file from tweets-data to main directory")
                        
                        # Now return success with the copied file
                        file_size = os.path.getsize(filename)
                        return {
                            'success': True,
                            'filename': filename,
                            'path': os.path.join(self.output_dir, filename),
                            'size': file_size,
                            'keyword': keyword,
                            'search_query': search_keyword,
                            'start_date': start_date,
                            'end_date': end_date
                        }
                    except Exception as e:
                        logger.error(f"Error copying file: {e}")
                
                # Check for any CSV files created by this run that might have a different name
                try:
                    for file in os.listdir():
                        if file.endswith('.csv') and file.lower().startswith(safe_keyword.lower()):
                            logger.info(f"Found alternative file: {file}")
                            file_size = os.path.getsize(file)
                            return {
                                'success': True, 
                                'filename': file,
                                'path': os.path.join(self.output_dir, file),
                                'size': file_size,
                                'keyword': keyword,
                                'search_query': search_keyword,
                                'start_date': start_date,
                                'end_date': end_date
                            }
                except Exception as e:
                    logger.error(f"Error checking for alternative files: {e}")
                
                logger.error(f"No valid output file found for {keyword}")
                return {'success': False, 'reason': 'File not created', 'keyword': keyword}
                
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            return {'success': False, 'reason': str(e), 'keyword': keyword}
        
        finally:
            os.chdir(original_cwd)
    
    def generate_date_ranges(self, start_date, end_date, interval='monthly'):
        """
        Generate date ranges between start and end dates based on specified interval
        
        Args:
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            interval: 'monthly', 'quarterly', 'yearly', 'weekly' or 'daily'
            
        Returns:
            List of tuples with (start_date, end_date) for each interval
        """
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        if start > end:
            logger.error("Start date must be before end date")
            return []
        
        date_ranges = []
        
        if interval == 'monthly':
            # Generate monthly ranges
            current = start.replace(day=1)  # Start from the 1st of the month
            
            while current <= end:
                # Get the last day of the current month
                if current.month == 12:
                    last_day = current.replace(day=31)
                else:
                    next_month = current.replace(month=current.month + 1)
                    last_day = next_month - timedelta(days=1)
                
                # Adjust if last_day is beyond end date
                if last_day > end:
                    last_day = end
                
                # Only add if we're not past the start date
                if last_day >= start:
                    # If start is not the 1st of the month, adjust the first range
                    if current.month == start.month and current.year == start.year:
                        date_ranges.append((start.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
                    else:
                        date_ranges.append((current.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
                
                # Move to the 1st of next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
        
        elif interval == 'yearly':
            # Generate yearly ranges
            current = start.replace(month=1, day=1)  # Start from January 1st
            
            while current <= end:
                # Last day of the year
                last_day = current.replace(month=12, day=31)
                
                # Adjust if beyond end date
                if last_day > end:
                    last_day = end
                
                # Adjust if before start date
                if current < start:
                    current = start
                
                if current <= last_day:  # Only add valid ranges
                    date_ranges.append((current.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
                
                # Move to next year
                current = current.replace(year=current.year + 1, month=1, day=1)
        
        elif interval == 'quarterly':
            # Generate quarterly ranges
            quarters = [(1, 3), (4, 6), (7, 9), (10, 12)]
            current_year = start.year
            
            while current_year <= end.year:
                for start_month, end_month in quarters:
                    # Create start and end date for this quarter
                    quarter_start = datetime(current_year, start_month, 1)
                    # Last day of the end month
                    last_day = calendar.monthrange(current_year, end_month)[1]
                    quarter_end = datetime(current_year, end_month, last_day)
                    
                    # Skip if entirely before start date or after end date
                    if quarter_end < start or quarter_start > end:
                        continue
                    
                    # Adjust quarter_start if needed
                    if quarter_start < start:
                        quarter_start = start
                    
                    # Adjust quarter_end if needed
                    if quarter_end > end:
                        quarter_end = end
                    
                    date_ranges.append((quarter_start.strftime('%Y-%m-%d'), quarter_end.strftime('%Y-%m-%d')))
                
                current_year += 1
        
        elif interval == 'weekly':
            # Generate weekly ranges
            current = start
            
            while current <= end:
                # Calculate end of the week (6 days from current)
                week_end = current + timedelta(days=6)
                
                # Adjust if beyond the end date
                if week_end > end:
                    week_end = end
                
                date_ranges.append((current.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
                
                # Move to the next week
                current = week_end + timedelta(days=1)
        
        elif interval == 'daily':
            # Simply create a range for each day
            current = start
            
            while current <= end:
                date_ranges.append((current.strftime('%Y-%m-%d'), current.strftime('%Y-%m-%d')))
                current += timedelta(days=1)
        
        else:
            logger.error(f"Unsupported interval: {interval}")
            return []
        
        return date_ranges
    
    def batch_scrape(self, keywords, start_date, end_date, interval='monthly', 
                    use_quotes=None, limit=100, lang='id', tab='LATEST'):
        """
        Batch scrape tweets for multiple keywords and date ranges
        
        Args:
            keywords: List of keywords to search for
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            interval: 'monthly', 'quarterly', 'yearly', 'weekly', or 'daily'
            use_quotes: List of booleans indicating whether to use quotes for each keyword
                        If None, all keywords use quotes=False
            limit: Number of tweets to scrape per keyword and date range
            lang: Language filter
            tab: Search tab ('LATEST' or 'TOP')
            
        Returns:
            Dictionary with batch scraping results
        """
        # Validate inputs
        if not keywords:
            return {'success': False, 'reason': 'No keywords provided'}
        
        # If use_quotes is None, default to False for all keywords
        if use_quotes is None:
            use_quotes = [False] * len(keywords)
        
        # Ensure use_quotes is a list matching keywords length
        if isinstance(use_quotes, bool):
            use_quotes = [use_quotes] * len(keywords)
        elif len(use_quotes) != len(keywords):
            return {'success': False, 'reason': 'use_quotes list must match keywords list length'}
        
        # Set up the output directory structure
        self.setup_output_directory()
        
        # Generate date ranges
        date_ranges = self.generate_date_ranges(start_date, end_date, interval)
        if not date_ranges:
            return {'success': False, 'reason': 'Could not generate valid date ranges'}
        
        # Record batch start time
        batch_start_time = datetime.now()
        
        # Initialize results
        results = {
            'overall_success': True,
            'start_time': batch_start_time,
            'end_time': None,
            'total_keywords': len(keywords),
            'total_date_ranges': len(date_ranges),
            'total_jobs': len(keywords) * len(date_ranges),
            'completed_jobs': 0,
            'successful_jobs': 0,
            'failed_jobs': 0,
            'files_created': [],
            'errors': [],
            'date_ranges': date_ranges,
            'details': []
        }
        
        logger.info(f"Starting batch scrape with {len(keywords)} keywords and {len(date_ranges)} date ranges")
        logger.info(f"Total jobs: {results['total_jobs']}")
        
        # Loop through keywords and date ranges
        for i, keyword in enumerate(keywords):
            for j, (range_start, range_end) in enumerate(date_ranges):
                job_number = i * len(date_ranges) + j + 1
                logger.info(f"Job {job_number}/{results['total_jobs']}: {keyword} from {range_start} to {range_end}")
                
                # Scrape tweets for this keyword and date range
                job_result = self.scrape_tweets(
                    keyword=keyword,
                    start_date=range_start,
                    end_date=range_end,
                    use_quotes=use_quotes[i],
                    limit=limit,
                    lang=lang,
                    tab=tab
                )
                
                # Update results
                results['completed_jobs'] += 1
                
                if job_result['success']:
                    results['successful_jobs'] += 1
                    results['files_created'].append(job_result['path'])
                else:
                    results['failed_jobs'] += 1
                    results['errors'].append({
                        'keyword': keyword,
                        'start_date': range_start,
                        'end_date': range_end,
                        'reason': job_result.get('reason', 'Unknown error')
                    })
                    logger.error(f"Job {job_number} failed: {job_result.get('reason', 'Unknown error')}")
                
                # Add detailed result
                results['details'].append({
                    'job_number': job_number,
                    'keyword': keyword,
                    'use_quotes': use_quotes[i],
                    'start_date': range_start,
                    'end_date': range_end,
                    'success': job_result['success'],
                    'result': job_result
                })
                
                # Short pause between requests to avoid rate limits
                time.sleep(2)
        
        # Record batch end time
        batch_end_time = datetime.now()
        results['end_time'] = batch_end_time
        results['total_duration'] = (batch_end_time - batch_start_time).total_seconds()
        
        # Set overall success flag
        if results['failed_jobs'] == results['total_jobs']:
            results['overall_success'] = False
        
        logger.info(f"Batch scrape completed. Success: {results['successful_jobs']}/{results['total_jobs']}")
        logger.info(f"Total duration: {results['total_duration']} seconds")
        
        return results
