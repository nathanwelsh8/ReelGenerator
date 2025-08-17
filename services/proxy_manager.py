
import requests
from settings import get_settings
from utils import ProxyHttpConstants
from services.logger import get_logger
from logging import Logger

class ProxyHttpClient:
   
    def __init__(self):
        self.settings = get_settings()
        self.logger: Logger = get_logger()

    def get(self, url: str, headers: dict = {}) -> requests.Response:
        """Make a GET request using the proxy settings."""

        headers['Accept'] = ProxyHttpConstants.ACCEPT_HEADER
        headers['User-Agent'] = ProxyHttpConstants.USER_AGENT

        proxy = {
                'http': f'http://{self._get_proxy_config()}',
                'https': f'http://{self._get_proxy_config()}'
            }
        try:
            response = requests.get(url, headers=headers, proxies=proxy, timeout=10)
            response.raise_for_status()  # Raise an error for bad responses
            self.logger.info(f"GET request to {url} succeeded with status code {response.status_code}")
            return response
        except requests.RequestException as e:
            self.logger.error(f"GET request to {url} failed: {e}")
            raise

    def get_proxy_server_uri(self) -> str:
        """Returns the proxy string for the current session."""
        uri = self._get_proxy_config()
        try:
            self.logger.info(f"Proxy IP: {self.get('https://httpbin.org/ip', {}).content.decode('utf-8')}")
        except Exception:
            pass
        return uri

    def _get_proxy_config(self) -> str:

        proxy_region_str = f"-{self.settings.PROXY_REGION}" if self.settings.PROXY_REGION else ""

        return f'{self.settings.PROXY_USERNAME}-zone-resi{proxy_region_str}:{self.settings.PROXY_PASSWORD}@{self.settings.PROXY_HOST}:{self.settings.PROXY_PORT}'

if __name__ == "__main__":
    pm = ProxyHttpClient()
    print(pm.get('https://httpbin.org/ip', {}).content.decode('utf-8'))
