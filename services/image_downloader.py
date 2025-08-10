import os
import logging
from google_images_search import GoogleImagesSearch
from settings import get_settings

class ImageDownloader:
    def __init__(self, max_images=10, download_folder="image_assests"):
        self.max_images = max_images
        self.download_folder = download_folder
        self.settings = get_settings()

        # Create required folders
        os.makedirs(self.download_folder, exist_ok=True)
        self._setup_logging()

    def _setup_logging(self):
        os.makedirs("runtime_logs", exist_ok=True)
        log_path = os.path.join("runtime_logs", "image_downloader.log")

        self.logger = logging.getLogger("ImageDownloader")
        self.logger.setLevel(logging.DEBUG)

        if not self.logger.handlers:
            file_handler = logging.FileHandler(log_path)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        self.logger.info("Logger initialized.")

    def search_images(self, term):

        if term == "":
            self.logger.warning("Search term is empty. Returning empty list.")
            return []

        self.logger.info(f"Starting search for: {term}")
        downloaded_image_paths = []

        # Use API keys from settings.py
        api_key = self.settings.GOOGLE_API_KEY
        cx = self.settings.GOOGLE_SEARCH_ENGINE_CX
        if not api_key or not cx:
            self.logger.critical("Google Custom Search API key or CX not found in settings.py")
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
                    self.logger.warning(f"No local path for image {idx + 1}")
        except Exception as e:
            self.logger.critical(f"Google image search failed: {e}")

        self.logger.info(f"Downloaded {len(downloaded_image_paths)} images successfully.")
        return downloaded_image_paths


# # Example usage
if __name__ == "__main__":
    image_downloader = ImageDownloader(max_images=10)
    downloaded_images = image_downloader.search_images("uk meme")

    print("Downloaded images:")
    for img_path in downloaded_images:
        print(img_path)
