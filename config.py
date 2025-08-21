
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.absolute()
ENV_FILE = BASE_DIR / '.env'

def setup_logging(log_level=logging.INFO):
    log_dir = BASE_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / f'twitter_agent_{os.getpid()}.log')
        ]
    )
    
    return logging.getLogger('TwitterAgent')

def load_config():
    if not ENV_FILE.exists():
        if (BASE_DIR / '.env.example').exists():
            with open(BASE_DIR / '.env.example', 'r') as example_file:
                with open(ENV_FILE, 'w') as env_file:
                    env_file.write(example_file.read())
            print(f"Created .env file. Please edit {ENV_FILE} with your settings.")
        else:
            print("Warning: .env.example file not found.")
    
    load_dotenv(ENV_FILE)
    
    config = {
        'auth_token': os.getenv('AUTH_TOKEN', ''),
        'output_dir': os.getenv('OUTPUT_DIR', str(BASE_DIR / 'scraped_tweets')),
        'default_lang': os.getenv('DEFAULT_LANG', 'id'),
        'default_tab': os.getenv('DEFAULT_TAB', 'LATEST'),
        'default_limit': int(os.getenv('DEFAULT_LIMIT', '100')),
    }
    
    Path(config['output_dir']).mkdir(parents=True, exist_ok=True)
    
    return config

config = load_config()
logger = setup_logging()

def update_auth_token(new_token):
    if not ENV_FILE.exists():
        with open(ENV_FILE, 'w') as env_file:
            env_file.write(f"AUTH_TOKEN={new_token}\n")
            env_file.write(f"OUTPUT_DIR={config['output_dir']}\n")
            env_file.write(f"DEFAULT_LANG={config['default_lang']}\n")
            env_file.write(f"DEFAULT_TAB={config['default_tab']}\n")
            env_file.write(f"DEFAULT_LIMIT={config['default_limit']}\n")
        logger.info("Created new .env file with auth token")
    else:
        with open(ENV_FILE, 'r') as env_file:
            lines = env_file.readlines()
        
        token_updated = False
        for i, line in enumerate(lines):
            if line.startswith('AUTH_TOKEN='):
                lines[i] = f"AUTH_TOKEN={new_token}\n"
                token_updated = True
                break
        
        if not token_updated:
            lines.append(f"AUTH_TOKEN={new_token}\n")
        
        with open(ENV_FILE, 'w') as env_file:
            env_file.writelines(lines)
        
        config['auth_token'] = new_token
        logger.info("Updated auth token in .env file")
        
    return True
