
import os
import tempfile
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from logging import Logger
from selenium_stealth import stealth

class SeleniumDriverFactory:
    """
    Factory for creating Selenium WebDriver instances, supporting authenticated proxies via Chrome extension.
    """
    def __init__(self, logger: Logger, proxy_manager=None):
        self.logger = logger
        self.proxy_manager = proxy_manager

    def get_driver(self, user_data_dir=None) -> "WebDriver":
        """Create and return a configured Selenium WebDriver instance. Uses a proxy, randomizes browser fingerprint, and clears cookies. Accepts optional user_data_dir for browser profile isolation."""
        import random
        try:
            options = Options()
            options.add_argument("--headless")
            # Advanced: randomize window size
            width = random.choice([1920, 1600, 1366, 1280, 1536, 1440])
            height = random.choice([1080, 900, 768, 800, 864, 1024])
            options.add_argument(f"--window-size={width},{height}")
            if user_data_dir is None:
                user_data_dir = tempfile.mkdtemp(prefix="chrome-user-data-")
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument("--no-sandbox")
            options.binary_location = "/usr/bin/chromium"

            # --- Browser fingerprint randomization ---
            user_agents = [
                # Chrome, Firefox, Edge, Safari, random versions
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/18.18363 Safari/537.36",
            ]
            ua = random.choice(user_agents)
            options.add_argument(f'--user-agent={ua}')

            # Randomize language, timezone, and platform
            languages = ["en-US,en;q=0.9", "en-GB,en;q=0.8", "fr-FR,fr;q=0.7", "de-DE,de;q=0.7"]
            lang = random.choice(languages)
            options.add_argument(f'--lang={lang}')
            timezones = ["America/New_York", "Europe/London", "Europe/Berlin", "Asia/Tokyo", "Australia/Sydney"]
            tz = random.choice(timezones)
            options.add_argument(f'--timezone={tz}')

            # Always fetch a new proxy URI for every driver instantiation
            if not self.proxy_manager:
                raise RuntimeError("Proxy manager is required and must be set.")
            proxy_uri = self.proxy_manager.get_proxy_server_uri()
            if proxy_uri and isinstance(proxy_uri, str) and proxy_uri.strip():
                if self._proxy_has_auth(proxy_uri):
                    ext_dir = self._create_proxy_auth_extension(proxy_uri)
                    options.add_argument(f'--load-extension={ext_dir}')
                    self.logger.info(f"Using authenticated proxy via extension.")
                else:
                    if not proxy_uri.startswith("http://") and not proxy_uri.startswith("https://"):
                        proxy_uri = f"https://{proxy_uri}"
                    options.add_argument(f'--proxy-server={proxy_uri}')
                    self.logger.info(f"Using proxy: {proxy_uri}")
            else:
                raise RuntimeError("A valid proxy URI must always be provided.")

            driver = webdriver.Chrome(options=options)
            self.logger.info("WebDriver initialized successfully.")

            # --- Selenium Stealth integration ---
            stealth(
                driver,
                languages=[lang.split(',')[0], "en"],
                vendor="Google Inc.",
                platform=driver.execute_script("return navigator.platform") or "Win32",
                webgl_vendor="NVIDIA Corporation",
                renderer="GeForce GTX 1050/PCIe/SSE2",
                fix_hairline=True,
            )

            # --- Cookie clearing ---
            driver.delete_all_cookies()
  
            return driver
        except Exception as e:
            self.logger.error(f"Error initializing WebDriver: {e}", exc_info=True)
            raise

    def _proxy_has_auth(self, proxy_uri):
        """Return True if the proxy URI contains username and password."""
        pattern = re.compile(r'^(https?://)?(?P<user>[^:@]+)?(?::(?P<pass>[^@]+))?@?(?P<host>[^:/]+)(?::(?P<port>\d+))?')
        match = pattern.match(proxy_uri.replace('https://','').replace('http://',''))
        return bool(match and match.group('user') and match.group('pass'))

    def _create_proxy_auth_extension(self, proxy_uri):
        """Create a Chrome extension for proxy authentication and return its directory path."""
        pattern = re.compile(r'^(https?://)?(?P<user>[^:@]+)?(?::(?P<pass>[^@]+))?@?(?P<host>[^:/]+)(?::(?P<port>\d+))?')
        match = pattern.match(proxy_uri.replace('https://','').replace('http://',''))
        username = match.group('user')
        password = match.group('pass')
        host = match.group('host')
        port = match.group('port') or '443'
        manifest_json = {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version": "22.0.0"
        }
        background_js = f'''
var config = {{
    mode: "fixed_servers",
    rules: {{
      singleProxy: {{
        scheme: "https",
        host: "{host}",
        port: parseInt({port})
      }},
      bypassList: ["localhost"]
    }}
}};
chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
chrome.webRequest.onAuthRequired.addListener(
  function(details) {{
    return {{authCredentials: {{username: "{username}", password: "{password}"}}}};
  }},
  {{urls: ["<all_urls>"]}},
  ['blocking']
);
'''
        ext_dir = tempfile.mkdtemp(prefix="chrome-proxy-ext-")
        manifest_path = os.path.join(ext_dir, 'manifest.json')
        background_path = os.path.join(ext_dir, 'background.js')
        with open(manifest_path, 'w') as f:
            json.dump(manifest_json, f)
        with open(background_path, 'w') as f:
            f.write(background_js)
        return ext_dir
