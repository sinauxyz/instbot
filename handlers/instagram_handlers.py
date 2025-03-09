import os
import pytz
import time
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from instaloader import Profile, QueryReturnedBadRequestException
from utils.file_utils import get_latest_file, create_temp_dir, cleanup_temp_dir
from utils.instagram_utils import InstagramClient
from utils.logging_utils import setup_logging, log_errors

logger = setup_logging()

@log_errors(logger)
async def handle_profile_pic(query, username: str, client: InstagramClient, config: dict, lang: str):
    logger.info(f"Handling profile picture request for {username}")
    profile = client.get_profile(username)
    if profile.is_private and not profile.followed_by_viewer:
        logger.warning(f"Profile {username} is private and not followed")
        await query.message.reply_text(config["languages"][lang]["private_profile"])
        return

    hd_url = profile.profile_pic_url.replace("/s150x150/", "/s1080x1080/")
    logger.debug(f"Fetching profile picture from URL: {hd_url}")
    response = requests.get(hd_url, headers=client.get_random_headers(), stream=True)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=True, suffix='.jpg') as temp_file:
        response.raw.decode_content = True
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        temp_file.seek(0)
        logger.info(f"Sending profile picture for {username}")
        await query.message.reply_document(
            document=temp_file,
            filename=f"{username}_profile.jpg",
            caption=f"📸 Foto Profil @{username}"
        )

@log_errors(logger)
async def handle_stories(query, username: str, client: InstagramClient, config: dict, lang: str):
    logger.info(f"Handling stories request for {username}")
    profile = client.get_profile(username)
    if profile.is_private and not profile.followed_by_viewer:
        logger.warning(f"Profile {username} is private and not followed")
        await query.message.reply_text(config["languages"][lang]["private_profile"])
        return

    stories = []
    try:
        stories = client.get_stories([profile.userid])
    except QueryReturnedBadRequestException as e:
        logger.error(f"Instagram API denied access to stories for {username}: {str(e)}")
        await query.message.reply_text(config["languages"][lang]["private_profile"])
        return

    if not stories:
        logger.info(f"No stories available for {username}")
        await query.message.reply_text(config["languages"][lang]["no_stories"])
        return

    stories.sort(key=lambda x: x.date_utc)
    time_zone = pytz.timezone(config["timezone"])
    temp_dir = create_temp_dir(f"temp_{username}_")
    sent_count = 0

    try:
        for story_item in stories:
            client.download_storyitem(story_item, temp_dir)
            latest_file = get_latest_file(temp_dir)
            if not latest_file:
                logger.warning(f"No valid file downloaded for story item {story_item.mediaid}")
                continue

            file_size = os.path.getsize(latest_file)
            if file_size > config["max_file_size_mb"] * 1024 * 1024:
                logger.warning(f"File {latest_file} exceeds size limit: {file_size} bytes")
                await query.message.reply_text("⚠️ File melebihi batas ukuran")
                os.remove(latest_file)
                continue

            local_time = story_item.date_utc.replace(tzinfo=pytz.utc).astimezone(time_zone)
            caption = f"{'📹' if story_item.is_video else '📸'} {local_time.strftime('%d-%m-%Y %H:%M')}"
            with open(latest_file, "rb") as f:
                logger.info(f"Sending story item {story_item.mediaid} for {username}")
                if story_item.is_video:
                    await query.message.reply_video(video=f, caption=caption, read_timeout=60, write_timeout=60)
                else:
                    await query.message.reply_photo(photo=f, caption=caption, read_timeout=60)
            sent_count += 1
            os.remove(latest_file)

        logger.info(f"Sent {sent_count} stories for {username}")
        await query.message.reply_text(f"📤 Total {sent_count} story berhasil dikirim")
    finally:
        cleanup_temp_dir(temp_dir)

@log_errors(logger)
async def handle_highlights(query, username: str, client: InstagramClient, config: dict, lang: str, page: int = 0):
    logger.info(f"Handling highlights request for {username}, page {page}")
    profile = client.get_profile(username)
    highlights = client.get_highlights(profile)

    if not highlights:
        logger.info(f"No highlights available for {username}")
        await query.message.reply_text("🌟 Tidak ada highlights yang tersedia")
        return

    items_per_page = config["items_per_page"]
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_highlights = highlights[start_idx:end_idx]
    logger.debug(f"Displaying highlights {start_idx} to {end_idx} out of {len(highlights)}")

    keyboard = []
    for highlight in current_highlights:
        title = highlight.title[:15] + "..." if len(highlight.title) > 15 else highlight.title
        keyboard.append([
            InlineKeyboardButton(
                f"🌟 {title}",
                callback_data=f"highlight_{highlight.unique_id}"
            )
        ])

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton("⏪ Kembali", callback_data=f"highlights_prev_{page - 1}")
        )
    if len(highlights) > end_idx:
        navigation_buttons.append(
            InlineKeyboardButton("⏩ Lanjutkan", callback_data=f"highlights_next_{page + 1}")
        )

    if navigation_buttons:
        keyboard.append(navigation_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)
    logger.info(f"Sending highlights menu for {username}")
    await query.message.reply_text(
        f"Pilih highlight untuk @{username} (Halaman {page + 1}):",
        reply_markup=reply_markup
    )

@log_errors(logger)
async def handle_highlight_items(query, username: str, highlight_id: str, client: InstagramClient, config: dict, lang: str):
    logger.info(f"Handling highlight items request for {username}, highlight ID {highlight_id}")
    profile = client.get_profile(username)
    highlights = client.get_highlights(profile)

    highlight_id_int = int(highlight_id)
    highlight = next((h for h in highlights if h.unique_id == highlight_id_int), None)

    if not highlight:
        logger.warning(f"Highlight with ID {highlight_id} not found for {username}")
        await query.message.reply_text("❌ Highlight tidak ditemukan")
        return

    temp_dir = create_temp_dir(f"temp_highlight_{username}_")
    sent_count = 0
    time_zone = pytz.timezone(config["timezone"])

    highlight_items = list(highlight.get_items())
    logger.info(f"Processing {len(highlight_items)} items from highlight '{highlight.title}'")
    await query.message.reply_text(f"🔄 Memproses {len(highlight_items)} item dari highlight '{highlight.title}'")

    try:
        for idx, item in enumerate(highlight_items, start=1):
            client.download_storyitem(item, temp_dir)
            latest_file = get_latest_file(temp_dir)
            if not latest_file:
                logger.warning(f"No valid file downloaded for highlight item {item.mediaid}")
                continue

            file_size = os.path.getsize(latest_file)
            if file_size > config["max_file_size_mb"] * 1024 * 1024:
                logger.warning(f"File {latest_file} exceeds size limit: {file_size} bytes")
                await query.message.reply_text("⚠️ File melebihi batas ukuran")
                os.remove(latest_file)
                continue

            local_time = item.date_utc.replace(tzinfo=pytz.utc).astimezone(time_zone)
            caption = f"**[{idx}]**.🌟 {highlight.title} - {'📹' if item.is_video else '📸'} {local_time.strftime('%d-%m-%Y %H:%M')}"
            with open(latest_file, "rb") as f:
                logger.info(f"Sending highlight item {item.mediaid} for {username}")
                if item.is_video:
                    await query.message.reply_video(video=f, caption=caption, read_timeout=60, write_timeout=60)
                else:
                    await query.message.reply_photo(photo=f, caption=caption, read_timeout=60)
            sent_count += 1
            os.remove(latest_file)

        logger.info(f"Sent {sent_count} items from highlight '{highlight.title}'")
        await query.message.reply_text(f"✅ {sent_count} item dari highlight '{highlight.title}' berhasil dikirim")
    finally:
        cleanup_temp_dir(temp_dir)

@log_errors(logger)
async def handle_profile_info(query, username: str, client: InstagramClient, config: dict, lang: str):
    logger.info(f"Handling profile info request for {username}")
    profile = client.get_profile(username)
    info_text = (
        f"📊 Info Profil @{username}:\n"
        f"👤 Nama: {profile.full_name}\n"
        f"📝 Bio: {profile.biography}\n"
        f"✅ Terverifikasi: {'Ya' if profile.is_verified else 'Tidak'}\n"
        f"🏢 Bisnis: {'Ya' if profile.is_business_account else 'Tidak'}\n"
        f"🔗 Followers: {profile.followers:,}\n"
        f"👀 Following: {profile.followees:,}\n"
        f"📌 Post: {profile.mediacount:,}"
    )
    logger.info(f"Sending profile info for {username}")
    await query.message.reply_text(info_text)
