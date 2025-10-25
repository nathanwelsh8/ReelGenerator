import os
from loguru import logger
from google_images_search import GoogleImagesSearch
from settings import get_settings

class ImageDownloader:
    def __init__(self, max_images=10, download_folder="image_assests"):
        self.max_images = max_images
        self.download_folder = download_folder
        self.settings = get_settings()

        # Create required folders
        os.makedirs(self.download_folder, exist_ok=True)
        # Logging is configured globally via services.config.logging_config
        # Use stdlib logger name "ImageDownloader" via bind for filters
        self._logger = logger.bind(stdlib_logger_name="ImageDownloader")

    def _setup_logging(self):
        # Deprecated: kept for backward compatibility; now a no-op.
        logger.debug("ImageDownloader logger uses global Loguru configuration.")

    def search_images(self, term):
        if term == "":
            self._logger.warning("Search term is empty. Returning empty list.")
            return []

        self._logger.info(f"Starting search for: {term}")
        downloaded_image_paths = []

        # Use API keys from settings.py
        api_key = self.settings.GOOGLE_API_KEY
        cx = self.settings.GOOGLE_SEARCH_ENGINE_CX
        if not api_key or not cx:
            self._logger.critical("Google Custom Search API key or CX not found in settings.py")
            return []

        gis = GoogleImagesSearch(api_key, cx)
        _search_params = {
            'q': term,
            'num': self.max_images,
            'fileType': 'jpg|png',
            'safe': 'high',
        }
        try:
            gis.search(search_params=_search_params, path_to_dir=self.download_folder)
            results = gis.results()
            for idx, image in enumerate(results):
                if hasattr(image, 'path') and image.path:
                    downloaded_image_paths.append(image.path)
                else:
                    self._logger.warning(f"No local path for image {idx + 1}")
        except Exception as e:
            self._logger.critical(f"Google image search failed: {e}")
        
        self._logger.info(f"Downloaded {len(downloaded_image_paths)} images successfully.")
        return downloaded_image_paths


# # Example usage
if __name__ == "__main__":
    image_downloader = ImageDownloader(max_images=10)
    downloaded_images = image_downloader.search_images("uk meme")

    print("Downloaded images:")
    for img_path in downloaded_images:
        print(img_path)
