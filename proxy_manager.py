
import requests
import os
from settings import get_settings
from utils import ProxyHttpConstants
from time import time as get_unix_timestamp  
from logger import get_logger
from logging import Logger

class ProxyHttpClient:
   
    def __init__(self, rotate_every: int = 1):
        self.settings = get_settings()
        self.request_count = 0
        self.rotate_every = rotate_every
        self.logger: Logger = get_logger()

        self.__session_id = None

    def get(self, url: str, headers: dict = {}) -> requests.Response:
        """Make a GET request using the proxy settings."""

        headers['Accept'] = ProxyHttpConstants.ACCEPT_HEADER
        headers['User-Agent'] = ProxyHttpConstants.USER_AGENT

        session_id = self._get_session_id()
        proxy = {
                'http': f'http://{self._get_proxy_config(session_id)}',
                'https': f'http://{self._get_proxy_config(session_id)}'
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
        session_id = self._get_session_id()
        uri = self._get_proxy_config(session_id)
        return uri

    def _get_proxy_config(self, session_id:str) -> str:
        return f'{self.settings.PROXY_USERNAME}-zone-resi-{self.settings.PROXY_REGION}-session-{session_id}:{self.settings.PROXY_PASSWORD}@{self.settings.PROXY_HOST}:{self.settings.PROXY_PORT}'

    def _get_session_id(self) -> str:
        """Gets session ID based on rotation policy."""
        
        if self.__session_id is None or self.request_count % self.rotate_every == 0:
            self.logger.info(f"Rotating proxy session. Count:Rotate={self.request_count}:{self.rotate_every}")
            self.__session_id = get_unix_timestamp()

        self.request_count += 1
        return self.__session_id

if __name__ == "__main__":
    pm = ProxyHttpClient()
    print(pm.get('https://httpbin.org/ip', {}).content.decode('utf-8'))