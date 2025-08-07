import os
import tempfile
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from logging import Logger

class SeleniumDriverFactory:
    """
    Factory for creating Selenium WebDriver instances, supporting authenticated proxies via Chrome extension.
    """
    def __init__(self, logger: Logger, proxy_manager=None):
        self.logger = logger
        self.proxy_manager = proxy_manager

    def get_driver(self, proxy=None):
        """Create and return a configured Selenium WebDriver instance."""
        try:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--window-size=1920,1080")
            user_data_dir = tempfile.mkdtemp(prefix="chrome-user-data-")
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument("--no-sandbox")
            options.binary_location = "/usr/bin/chromium"

            proxy_uri = proxy if proxy else (self.proxy_manager.get_proxy_server_uri() if self.proxy_manager else None)
            self.logger.info(f"Proxy candidate: {proxy_uri!r}")
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
                self.logger.info("No proxy will be used for this WebDriver instance.")

            driver = webdriver.Chrome(options=options)
            self.logger.info("WebDriver initialized successfully.")
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
