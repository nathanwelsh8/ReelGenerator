import os
import warnings
import random
warnings.filterwarnings("ignore")
os.environ["IMAGEMAGICK_BINARY"] = "/usr/bin/convert"
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
)
import requests
import os
from utils import DialougeStatus

# Monkey-patch PIL.Image.ANTIALIAS for Pillow>=10 compatibility
try:
    from PIL import Image as PILImage
    if not hasattr(PILImage, 'ANTIALIAS'):
        PILImage.ANTIALIAS = PILImage.Resampling.LANCZOS
except Exception:
    pass


from moviepy.config_defaults import IMAGEMAGICK_BINARY
#IMAGEMAGICK_BINARY = r"/usr/bin/convert"   chnage this path to  your  imagemagick file path

class DynamicVideoEditor:
    def __init__(self, video_path, output_path, dialogue_data=None, db_handler=None):
        self.video_path = video_path
        self.output_path = output_path
        self.audio_clips = []
        self.image_clips = []
        self.subtitle_clips = []
        self.current_start = 0


        # Always fetch dialogue data from the database if db_handler is provided
        if db_handler is not None:
            self.dialogue_data = db_handler.get_ready_assets() or []
        else:
            self.dialogue_data = dialogue_data or []


        # Check that all audio assets are marked as COMPLETE
        incomplete = [item for item in self.dialogue_data if item.get('status') != DialougeStatus.COMPLETED]
        if incomplete:
            raise ValueError(f"The following dialogue items do not have COMPLETE audio assets: {[item.get('id', item) for item in incomplete]}")

        # Calculate total audio duration
        from moviepy.editor import AudioFileClip, concatenate_audioclips
        total_audio_duration = 0
        for item in self.dialogue_data:
            audio_path = item.get('audio')
            if audio_path and os.path.exists(audio_path):
                try:
                    total_audio_duration += AudioFileClip(audio_path).duration
                except Exception as e:
                    print(f"Warning: Could not read duration for {audio_path}: {e}")
        # Add 15 seconds buffer
        video_duration = total_audio_duration + 15

        # Load the background video and trim or loop to match the required duration
        video_clip = VideoFileClip(video_path)

        # If the video is more than twice the required duration, start at a random point
        if video_clip.duration > 2 * video_duration:
            max_start_time = video_clip.duration - video_duration
            start_time = random.uniform(15, max_start_time)
            video_clip = video_clip.subclip(start_time, start_time + video_duration)
        elif video_clip.duration >= video_duration:
            video_clip = video_clip.subclip(15, video_duration)
        else:
            # Loop the video to match the required duration
            n_loops = int(video_duration // video_clip.duration) + 1
            clips = [video_clip] * n_loops
            from moviepy.editor import concatenate_videoclips
            looped = concatenate_videoclips(clips)
            video_clip = looped.subclip(0, video_duration)

        # --- Ensure 9:16 aspect ratio (portrait) ---
        target_w, target_h = 1080, 1920  # 9:16 standard for reels
        # Resize to fit height, then crop or pad width
        video_clip = video_clip.resize(height=target_h)
        # If too wide, crop center; if too narrow, add black bars
        if video_clip.w > target_w:
            x_center = video_clip.w // 2
            x1 = x_center - target_w // 2
            x2 = x1 + target_w
            video_clip = video_clip.crop(x1=x1, y1=0, x2=x2, y2=target_h)
        elif video_clip.w < target_w:
            # Add black bars left/right
            from moviepy.video.fx.all import margin
            pad = (target_w - video_clip.w) // 2
            video_clip = margin(video_clip, left=pad, right=pad, color=(0,0,0))
            # If odd difference, crop to exact width
            if video_clip.w > target_w:
                x_center = video_clip.w // 2
                x1 = x_center - target_w // 2
                x2 = x1 + target_w
                video_clip = video_clip.crop(x1=x1, y1=0, x2=x2, y2=target_h)
        # else: already correct width

        self.video = video_clip

    def search_image(self, term):
        from services.image_downloader import ImageDownloader
        downloader = ImageDownloader(max_images=1, download_folder="downloaded_images")
        images = downloader.search_images(term)
        if images:
            return images[0]
        return None

    def create_title_clip(self, text, duration):
        return (
            TextClip(text, fontsize=60, color='white', font='Arial-Bold', bg_color='black')
            .set_duration(duration)
            .set_position(("center", 80))
        )

    def create_end_title_clip(self, text, duration=3):
        return (
            TextClip(text, fontsize=50, color='white', font='Arial-Bold', bg_color='black',method="caption")
            .set_duration(duration)
            .set_position(("center", "center"))
        )

    def add_word_by_word_subtitles(self, text, start_time, duration):
        words = text.split()
        word_duration = duration / len(words)
        word_clips = []

        current_time = start_time
        for word in words:
            clip = (
                TextClip(word, fontsize=95, color='yellow', font='DejaVu-Sans-Bold', stroke_color="black", stroke_width=0.3)
                .set_start(current_time)
                .set_duration(word_duration)
                .set_position(("center", "center"))
                .fadein(0.1)
                .fadeout(0.1)
            )
            word_clips.append(clip)
            current_time += word_duration
        return word_clips

    def edit(self):
        #title_clip = self.create_title_clip(self.title, duration=self.video.duration)

        if not self.dialogue_data:
            raise ValueError("No dialogue data provided to the video editor. Cannot generate video without dialogue.")

        for item in self.dialogue_data:
            # Use the actual audio path from the DB
            audio_path = item.get('audio')
            image_path = f"image_assests/{item['image']}"

            subtitle_text = item["sentence"]
            search_term = item.get("image_search", "")

            # Load and position audio
            audio = AudioFileClip(audio_path).set_start(self.current_start)
            self.audio_clips.append(audio)

            # Position character image
            char_position = "left" if "peter" in image_path.lower() else "right"
            if image_path:
                char_image = (
                    ImageClip(image_path)
                    .set_start(self.current_start)
                    .set_duration(audio.duration)
                    .resize(height=500)
                    
                )

                y_position = max(0, self.video.h - 500 - 50)

 
                x_position = 50 if char_position == "left" else max(0, self.video.w - char_image.w - 50)

  
                char_image = char_image.set_position((x_position, y_position))
                self.image_clips.append(char_image)

            # Subtitle
            subtitle_clips = self.add_word_by_word_subtitles(subtitle_text, self.current_start, audio.duration)
            self.subtitle_clips.extend(subtitle_clips)

            # Optional: Related image search
            try:
                relevant_image = self.search_image(search_term)
                if relevant_image:
                    searched_image = (
                        ImageClip(relevant_image)
                        .set_start(self.current_start)
                        .set_duration(audio.duration)
                        .resize(height=350)
                        .set_position(("center", 300))
                    )
                    self.image_clips.append(searched_image)
            except Exception as e:
                print(f"Image search failed: {e}")

            self.current_start += audio.duration + 0.5

        # end_clip = self.create_end_title_clip("Like, Share, thanks for watching.")
        # self.image_clips.append(end_clip)

        final_audio = CompositeAudioClip(self.audio_clips)
        final_video = CompositeVideoClip(
            [self.video] + self.image_clips + self.subtitle_clips
        ).set_audio(final_audio)

        final_video.write_videofile(self.output_path, codec="libx264", audio_codec="aac", fps=self.video.fps)


# === Usage Example ===
# if __name__ == "__main__":
#     from db_handler import DBOperation
#     db=DBOperation()
#     dialogue_data=db.get_ready_assets()
#     print(dialogue_data)
    
#     editor = DynamicVideoEditor(
#         video_path=r"/home/ubuntu/mainrepo/stewie_v1/video_assests/video_without_audio.webm",
#         output_path="output_final_video.mp4",
#         dialogue_data=dialogue_data
#     )
#     editor.edit()
