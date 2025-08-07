import time
import requests
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium_driver_factory import SeleniumDriverFactory
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from pydub.silence import split_on_silence

from proxy_manager import ProxyHttpClient
from logger import get_logger
from logging import Logger

class VoiceGenerator:
    PETER_URL = "https://www.tryparrotai.com/ai-voice/peter-griffin"
    STEWIE_URL = "https://www.tryparrotai.com/ai-voice/stewie-griffin"

    def __init__(self):
        self.logger: Logger = get_logger()
        self.proxy_manager: ProxyHttpClient = ProxyHttpClient(rotate_every=3)
        self.driver_factory = SeleniumDriverFactory(self.logger, self.proxy_manager)
        self.driver = self.driver_factory.get_driver()
        self.output_dir = "audio_assests"
        os.makedirs(self.output_dir, exist_ok=True)

    def __del__(self):
        """Ensure the WebDriver is closed when the object is destroyed."""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
                self.logger.info("WebDriver quit upon object destruction.")
            except Exception as e:
                self.logger.error(f"Error quitting WebDriver during object destruction: {e}")

    

    # WebDriver setup is now handled by SeleniumDriverFactory

    def download_video(self, url, filename):
        """Download video from the provided URL"""
        try:
            self.logger.info(f"Downloading from: {url}")
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            with open(filename, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    f.write(chunk)
            self.logger.info("Video downloaded successfully!")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error downloading video: {e}", exc_info=True)
            raise

    def convert_video_to_audio(self, video_filename, audio_filename):
        """Convert video file to audio, save in 'audio_assests', and delete the original video."""
        try:
            audio_path = os.path.join(self.output_dir, audio_filename)
            self.logger.info(f"Converting {video_filename} to {audio_path}")

            with VideoFileClip(video_filename) as video_clip:
                video_clip.audio.write_audiofile(audio_path, logger=None)

            # Delete original video file
            if os.path.exists(video_filename):
                os.remove(video_filename)
                self.logger.info(f"Deleted video file: {video_filename}")
            else:
                self.logger.warning(f"Video file not found: {video_filename}")

            self.logger.info(f"Audio saved as {audio_path}")
            return audio_path
        except Exception as e:
            self.logger.error(f"Error converting video to audio: {e}", exc_info=True)
            raise

    def remove_silence(self, audio_file):
        """Remove silence from audio"""
        try:
            audio = AudioSegment.from_mp3(audio_file)

            # Split the audio based on silence
            chunks = split_on_silence(
                audio,
                min_silence_len=500,  # Silence length to consider for splitting
                silence_thresh=-40,   # Silence threshold in dB
                keep_silence=250      # Keep 250ms of silence between chunks
            )

            # Combine the chunks after splitting
            combined_audio = AudioSegment.empty()
            for chunk in chunks:
                combined_audio += chunk

            # Export the combined audio to the same output file (overwrite original)
            combined_audio.export(audio_file, format="mp3")
            self.logger.info(f"Processed audio saved to {audio_file}")
            return audio_file
        except Exception as e:
            self.logger.error(f"Error removing silence from audio: {e}", exc_info=True)
            raise

    def generate_audio_from_sentence(self, sentence, speaker, index):
        """Generate audio from sentence using the specified speaker"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                page_url = self.PETER_URL if speaker.lower() == "peter" else self.STEWIE_URL
                filename_prefix = speaker.lower()

                # Load the page
                self.driver.delete_all_cookies()
                self.logger.info("Cookies cleared.")
                self.driver.get(page_url)

                # Input text
                try:
                    textarea = WebDriverWait(self.driver, 90).until(
                        EC.presence_of_element_located((By.TAG_NAME, "textarea"))
                    )
                except Exception as find_exc:
                    # Log page source and save screenshot for debugging
                    page_source_path = f"debug_page_source_{time.time()}.html"
                    screenshot_path = f"debug_screenshot_{time.time()}.png"
                    with open(page_source_path, "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    self.driver.save_screenshot(screenshot_path)
                    self.logger.error(f"Failed to find textarea. Page source saved to {page_source_path}, screenshot saved to {screenshot_path}")
                    raise find_exc
                textarea.clear()
                textarea.send_keys(sentence)

                # Click generate
                generate_btn = self.driver.find_element(By.XPATH, '//button[contains(text(), "Generate")]')
                generate_btn.click()

                # Wait for video
                video_element = WebDriverWait(self.driver, 90).until(
                    EC.presence_of_element_located((By.TAG_NAME, "video"))
                )

                # Wait for the src attribute to be a valid URL
                video_url = WebDriverWait(self.driver, 90).until(
                    lambda d: video_element.get_attribute("src") if video_element.get_attribute("src") and video_element.get_attribute("src").startswith("https://") else False,
                    "Timeout waiting for video src attribute to become a valid URL."
                )
                if video_url:
                    self.logger.info(f"Video URL: {video_url}")
                    mp4_name = f"{filename_prefix}_voice_{index}.mp4"
                    mp3_name = f"{filename_prefix}_audio_{index}.mp3"
                    self.download_video(video_url, mp4_name)
                    audio_path = self.convert_video_to_audio(mp4_name, mp3_name)
                    # Remove silence from the audio
                    self.remove_silence(audio_path)
                else:
                    self.logger.warning("Video URL not found.")
                return
            except Exception as e:
                error_str = str(e)
                self.logger.error(f"Error during sentence generation (attempt {attempt+1}): {e}", exc_info=True)
                # If the error is a tunnel connection failure, retry with a new proxy
                if "net::ERR_TUNNEL_CONNECTION_FAILED" in error_str and attempt < max_retries - 1:
                    self.driver.quit()
                    self.driver = self.setup_driver(self.proxy_manager.get_proxy_server_uri())
                    continue
                else:
                    raise

    def process_conversation(self, line: str, dialogue_id: int) -> bool:
        """Process a single conversation line to generate an audio file"""
        try:
         
            if ":" not in line:
                self.logger.warning(f"Skipping malformed line: '{line}'")
                return False

            speaker, sentence = map(str.strip, line.split(":", 1))

            if len(sentence) <= 100:
                self.logger.info(f"Generating for: '{sentence}' with ID: {dialogue_id}")
                self.generate_audio_from_sentence(sentence, speaker, dialogue_id)
                return True  # Success
            else:
                self.logger.warning(f"Skipping sentence (too long): '{sentence}'")
                return False  # Sentence too long

        except Exception as e:
            self.logger.error(f"Error processing conversation ID {dialogue_id}: {e}", exc_info=True)
            return False  # Exception occurred

# Example usage:

if __name__ == "__main__":
    conversation_list = [
        "Peter: Time complexity tells you how long your code will take as input grows.",
        "Stewie: So it's not about actual seconds?",
        "Peter: Correct. It measures how the effort scales with more data.",
        "Stewie: And space complexity?",
        "Peter: It measures how much memory your code needs as input grows.",
        "Stewie: So time is speed, space is memory?",
        "Peter: Exactly. Both use Big O to describe growth.",
        "Stewie: O of one means constant time and space?",
        "Peter: Yes. It doesn’t matter how big the input is.",
        "Stewie: Got it. So we aim for efficiency in both time and space."
    ]
    
    voice_generator = VoiceGenerator()
    for idx,line in enumerate(conversation_list):
        voice_generator.process_conversation(line,idx)
