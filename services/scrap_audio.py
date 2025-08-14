import time
import requests
import os
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.selenium_driver_factory import SeleniumDriverFactory
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from pydub.silence import split_on_silence

from services.proxy_manager import ProxyHttpClient
from services.logger import get_logger
from logging import Logger
import shutil

class VoiceGenerator:
    PETER_URL = "https://www.tryparrotai.com/ai-voice/peter-griffin"
    STEWIE_URL = "https://www.tryparrotai.com/ai-voice/stewie-griffin"

    def __init__(self):
        self.logger: Logger = get_logger()
        self.proxy_manager: ProxyHttpClient = ProxyHttpClient()
        self.driver_factory = SeleniumDriverFactory(self.logger, self.proxy_manager)
        self.output_dir = "audio_assests"
        os.makedirs(self.output_dir, exist_ok=True)

        self.max_retries = 3

    def __del__(self):
        pass  # No persistent driver to clean up


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

    def generate_audio_from_sentence(self, sentence, speaker, index, db_handler=None, dialogue_id=None):
        # Clean debug/ directory at the start of each run
        debug_dir = "debug"
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir, exist_ok=True)
        else:
            for f in os.listdir(debug_dir):
                fp = os.path.join(debug_dir, f)
                try:
                    if os.path.isfile(fp):
                        os.remove(fp)
                except Exception as e:
                    self.logger.warning(f"Failed to delete debug file {fp}: {e}")
        """Generate audio from sentence using the specified speaker. Uses a new proxied Selenium driver for each call. Retries up to 3 times on error, waits 5 minutes between retries.
        If db_handler and dialogue_id are provided, update DB to COMPLETED after audio is saved."""
        audio_path = None
        for attempt in range(self.max_retries):
            # Rotate browser user data directory for each session
            user_data_dir = f"/tmp/selenium_profile_{time.time()}_{random.randint(0,10000)}"
            if os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir)
            driver = self.driver_factory.get_driver(user_data_dir=user_data_dir) if hasattr(self.driver_factory, 'get_driver') and 'user_data_dir' in self.driver_factory.get_driver.__code__.co_varnames else self.driver_factory.get_driver()
            try:
                page_url = self.PETER_URL if speaker.lower() == "peter" else self.STEWIE_URL
                filename_prefix = speaker.lower()


                # --- Advanced browser fingerprint randomization and storage clearing ---
                # 1. Randomize user agent
                user_agents = [
                    # Chrome, Firefox, Edge, Safari, mobile, etc.
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
                    "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Mobile Safari/537.36",
                ]
                ua = random.choice(user_agents)
                try:
                    driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": ua})
                    self.logger.info(f"User-Agent randomized: {ua}")
                except Exception as e:
                    self.logger.warning(f"Failed to set user agent: {e}")

                # 2. Randomize viewport size
                width = random.randint(900, 1920)
                height = random.randint(700, 1200)
                try:
                    driver.set_window_size(width, height)
                    self.logger.info(f"Viewport randomized: {width}x{height}")
                except Exception as e:
                    self.logger.warning(f"Failed to set window size: {e}")

                # 3. Clear all browser storage (cookies, localStorage, sessionStorage, indexedDB) will be done after loading the page

                # 4. Randomize timezone and languages (stealth)
                try:
                    tz = random.choice(["America/New_York", "Europe/London", "Asia/Tokyo", "Europe/Berlin", "America/Los_Angeles"])
                    lang = random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.8", "de-DE,de;q=0.9", "fr-FR,fr;q=0.9"])
                    driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {"timezoneId": tz})
                    driver.execute_cdp_cmd('Emulation.setLocaleOverride', {"locale": lang.split(",")[0]})
                    self.logger.info(f"Timezone set: {tz}, Language set: {lang}")
                except Exception as e:
                    self.logger.warning(f"Failed to set timezone/language: {e}")

                # 5. Randomize platform
                try:
                    platform = random.choice(["Win32", "Linux x86_64", "MacIntel", "iPhone"])
                    driver.execute_script(f"Object.defineProperty(navigator, 'platform', {{get: () => '{platform}'}});")
                    self.logger.info(f"Platform randomized: {platform}")
                except Exception as e:
                    self.logger.warning(f"Failed to set platform: {e}")

                # --- End advanced fingerprinting ---


                self.logger.info(f"Browser fingerprint randomized. Attempt {attempt+1} of {self.max_retries}")

                # Now load the page
                driver.get(page_url)

                # Now clear all browser storage (cookies, localStorage, sessionStorage, indexedDB) on the actual site
                try:
                    driver.delete_all_cookies()
                    driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
                    # IndexedDB clearing (best effort)
                    driver.execute_script('''
                        indexedDB.databases().then(dbs => {
                            dbs.forEach(db => indexedDB.deleteDatabase(db.name));
                        });
                    ''')
                    self.logger.info("All browser storage cleared on site.")
                except Exception as e:
                    self.logger.warning(f"Failed to clear browser storage on site: {e}")

                # --- Human-like actions: mouse movement, scrolling, random waits ---
                import selenium.webdriver.common.action_chains as ac
                import selenium.webdriver.common.keys as keys
                # Move mouse in random pattern
                try:
                    actions = ac.ActionChains(driver)
                    body = driver.find_element(By.TAG_NAME, "body")
                    for _ in range(random.randint(2, 5)):
                        x_offset = random.randint(0, 300)
                        y_offset = random.randint(0, 300)
                        actions.move_to_element_with_offset(body, x_offset, y_offset)
                        if random.random() > 0.5:
                            actions.click()
                    actions.perform()
                    self.logger.info("Simulated mouse movement and clicks.")
                except Exception as e:
                    self.logger.warning(f"Failed to simulate mouse movement: {e}")
                # Scroll randomly
                try:
                    for _ in range(random.randint(1, 3)):
                        scroll_y = random.randint(100, 800)
                        driver.execute_script(f"window.scrollBy(0, {scroll_y});")
                        time.sleep(random.uniform(0.2, 0.7))
                    self.logger.info("Simulated random scrolling.")
                except Exception as e:
                    self.logger.warning(f"Failed to simulate scrolling: {e}")
                # Random wait before interacting
                wait_time = random.uniform(1.5, 4.0)
                self.logger.info(f"Waiting {wait_time:.2f}s to simulate human pause.")
                time.sleep(wait_time)

                # Input text
                try:
                    textarea = WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.TAG_NAME, "textarea"))
                    )
                except Exception as find_exc:
                    # Log page source and save screenshot for debugging
                    screenshot_path = f"debug/debug_screenshot_{time.time()}.png"
                    page_source_path = f"debug/debug_html_{time.time()}.html"
                    driver.save_screenshot(screenshot_path)
                    try:
                        with open(page_source_path, "w", encoding="utf-8") as f:
                            f.write(driver.page_source)
                    except Exception as e:
                        self.logger.warning(f"Failed to save page source: {e}")
                    self.logger.error(f"Failed to find textarea. Page source saved to {page_source_path}, screenshot saved to {screenshot_path}")
                    raise find_exc
                textarea.clear()
                textarea.send_keys(sentence)

                # Click generate
                generate_btn = driver.find_element(By.XPATH, '//button[contains(text(), "Generate")]')
                generate_btn.click()

                # Wait for video
                try:
                    video_element = WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.TAG_NAME, "video"))
                    )
                except Exception as video_exc:
                    # Save screenshot and page source for video timeout
                    screenshot_path = f"debug/debug_video_screenshot_{time.time()}.png"
                    driver.save_screenshot(screenshot_path)
                    self.logger.error(f"Failed to find video element. Screenshot saved to {screenshot_path}")
                    raise video_exc

                # Wait for the src attribute to be a valid URL
                video_url = WebDriverWait(driver, 30).until(
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
                    # If db_handler and dialogue_id are provided, update DB
                    if db_handler is not None and dialogue_id is not None and audio_path is not None:
                        try:
                            db_handler.update_audio_path(dialogue_id, audio_path)
                            from utils import DialougeStatus
                            db_handler.update_status(dialogue_id, DialougeStatus.COMPLETED)
                        except Exception as db_e:
                            # Non-fatal; main flow will reconcile
                            self.logger.warning(f"DB update failed for dialogue {dialogue_id}: {db_e}")
                else:
                    self.logger.warning("Video URL not found.")
                driver.quit()
                return audio_path
            except Exception as e:
                self.logger.error(f"Error during sentence generation (attempt {attempt+1}/{self.max_retries})")
                driver.quit()
                if attempt < self.max_retries - 1:
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
        "Peter: Yes. It doesn1t matter how big the input is.",
        "Stewie: Got it. So we aim for efficiency in both time and space."
    ]
    
    voice_generator = VoiceGenerator()
    for idx,line in enumerate(conversation_list):
        voice_generator.process_conversation(line,idx)
