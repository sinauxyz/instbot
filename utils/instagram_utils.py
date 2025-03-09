import os
import json
import random
import time
import requests
from typing import Dict, List, Optional
from instaloader import Instaloader, Profile, QueryReturnedBadRequestException, LoginRequiredException
from dotenv import load_dotenv
from utils.logging_utils import setup_logging

load_dotenv()
logger = setup_logging()

# Load User Agents
def load_user_agents(file_path: str = "user-agents.json") -> List[str]:
    logger.debug(f"Loading user agents from {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            agents = json.load(f)
            return [ua for ua in agents if isinstance(ua, str) and ua.strip()]
    except Exception as e:
        logger.error(f"Error loading user agents: {str(e)}")
        raise RuntimeError(f"Error loading user agents: {str(e)}")

USER_AGENTS = load_user_agents()

# Instagram Setup
class InstagramClient:
    def __init__(self, env_vars: Dict[str, str]):
        self.env_vars = env_vars
        self.username = env_vars['INSTAGRAM_USERNAME']
        self.password = env_vars['INSTAGRAM_PASSWORD']
        self.loader = Instaloader(
            user_agent=random.choice(USER_AGENTS),
            sleep=True,
            quiet=True,
            request_timeout=30,
            dirname_pattern="{target}",
            filename_pattern="{date_utc}_UTC_{profile}",
            download_pictures=True,
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            post_metadata_txt_pattern="",
            storyitem_metadata_txt_pattern="",
            compress_json=False,
            download_comments=False
        )
        self.login()
        self.request_count = 0  # Untuk melacak jumlah permintaan

    def login(self):
        """Login ke Instagram dan simpan sesi untuk penggunaan berikutnya (Saran 4)."""
        logger.debug(f"Attempting to login as {self.username}")
        session_file = f"session_{self.username}.dat"
        try:
            if os.path.exists(session_file):
                logger.info(f"Loading existing session from {session_file}")
                self.loader.load_session_from_file(self.username, session_file)
                if self.validate_session():
                    logger.info("Session loaded and validated successfully")
                else:
                    logger.warning("Loaded session invalid, performing new login")
                    self.loader.login(self.username, self.password)
                    self.loader.save_session_to_file(session_file)
                    logger.info(f"New session saved to {session_file}")
            else:
                self.loader.login(self.username, self.password)
                self.loader.save_session_to_file(session_file)
                logger.info(f"Session saved to {session_file}")
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise RuntimeError(f"Failed to login: {str(e)}")

    def validate_session(self) -> bool:
        """Validasi sesi dengan mencoba mengambil profil pengguna sendiri."""
        logger.debug(f"Validating session for {self.username}")
        try:
            Profile.from_username(self.loader.context, self.username)
            logger.info("Session validated successfully")
            return True
        except (LoginRequiredException, Exception) as e:
            logger.error(f"Session validation failed: {str(e)}")
            return False

    def ensure_valid_session(self):
        """Pastikan sesi valid, login ulang jika perlu (Saran 4)."""
        if not self.validate_session():
            logger.warning("Invalid session detected, attempting to re-login")
            self.login()

    def get_random_headers(self) -> Dict[str, str]:
        """Buat header dinamis untuk meniru browser manusia (Saran 3)."""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice(["en-US,en;q=0.5", "id-ID,id;q=0.9", "fr-FR,fr;q=0.8"]),
            "Connection": "keep-alive",
            "Referer": "https://www.instagram.com/"
        }
        logger.debug(f"Generated random headers")
        return headers

    def simulate_human_behavior(self):
        """Simulasikan perilaku manusia dengan delay acak dan kunjungan dummy (Saran 1 & 5)."""
        self.request_count += 1
        logger.debug(f"Request count: {self.request_count}")

        # Delay variabel acak (Saran 1)
        delay = random.uniform(2, 5)
        logger.debug(f"Applying human-like delay of {delay:.2f} seconds")
        time.sleep(delay)

        # Jeda panjang acak setelah beberapa permintaan (Saran 1)
        if self.request_count % random.randint(5, 10) == 0:
            long_delay = random.uniform(30, 60)
            logger.info(f"Simulating long pause of {long_delay:.2f} seconds")
            time.sleep(long_delay)

        # Simulasi kunjungan dummy ke halaman lain (Saran 5)
        if random.random() < 0.2:  # 20% kemungkinan
            logger.debug("Simulating dummy visit to Instagram homepage")
            requests.get("https://www.instagram.com/", headers=self.get_random_headers())
            time.sleep(random.uniform(1, 3))

    def get_profile(self, username: str) -> Profile:
        """Ambil profil dengan simulasi perilaku manusia (Saran 1, 5)."""
        logger.debug(f"Fetching profile for username: {username}")
        self.ensure_valid_session()
        self.simulate_human_behavior()
        try:
            profile = Profile.from_username(self.loader.context, username)
            logger.info(f"Profile fetched successfully for {username}")
            return profile
        except Exception as e:
            logger.error(f"Failed to fetch profile for {username}: {str(e)}")
            raise

    def get_stories(self, user_ids: List[int]) -> List:
        """Ambil stories dengan simulasi perilaku (Saran 1, 5)."""
        logger.debug(f"Fetching stories for user IDs: {user_ids}")
        self.ensure_valid_session()
        self.simulate_human_behavior()
        try:
            stories = []
            for story in self.loader.get_stories(user_ids):
                stories.extend(story.get_items())
            logger.info(f"Fetched {len(stories)} stories")
            return stories
        except Exception as e:
            logger.error(f"Failed to fetch stories: {str(e)}")
            raise

    def get_highlights(self, profile: Profile) -> List:
        """Ambil highlights dengan simulasi perilaku (Saran 1, 5)."""
        logger.debug(f"Fetching highlights for profile: {profile.username}")
        self.ensure_valid_session()
        self.simulate_human_behavior()
        try:
            highlights = list(self.loader.get_highlights(user=profile))
            logger.info(f"Fetched {len(highlights)} highlights")
            return highlights
        except Exception as e:
            logger.error(f"Failed to fetch highlights: {str(e)}")
            raise

    def download_storyitem(self, item, target: str):
        """Unduh story item dengan simulasi (Saran 1, 5)."""
        logger.debug(f"Downloading story item {item.mediaid} to {target}")
        self.ensure_valid_session()
        self.simulate_human_behavior()
        try:
            self.loader.download_storyitem(item, target)
            logger.info(f"Story item {item.mediaid} downloaded successfully")
        except Exception as e:
            logger.error(f"Failed to download story item {item.mediaid}: {str(e)}")
            raise
