"""
Configuration for Bridge to Success Telegram Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8845555323:AAHzKabLkl1h1LuSQh5cYUYyVxslGHmmte8")

# API Configuration
BASE_URL = "https://bridgetosuccess.learncentre.tech"
API_BASE = f"{BASE_URL}/public/study_api_sprint13_security_promo/"

STORAGE_PDF = f"{BASE_URL}/public/storage/pdf/"
STORAGE_VID = f"{BASE_URL}/public/storage/video/"
PLAYER_URL = "https://lctplayer.learncentre.online/v/player.php?v="
LIVE_URL = "https://lctplayer.learncentre.online/live/live_player.php?v="

HEADERS = {
    "User-Agent": "okhttp/4.9.3",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Connection": "keep-alive",
}

# All discovered endpoints
ENDPOINTS = {
    # Auth
    "send_otp": "send-otp",
    "verify_otp": "verify-otp",
    "login": "login",
    "register": "register",
    
    # Courses
    "all_courses": "get-all-courses",
    "my_courses": "get-my-courses",
    "top_courses": "get-top-courses",
    "course_detail": "get-course-detail",
    "categories": "get-categories",
    "category_courses": "get-category-courses",
    
    # Content hierarchy
    "batch_list": "get-batch-list",
    "subject_list": "get-subject-list",
    "chapter_list": "get-chapter-list",
    "topic_list": "get-topic-list",
    
    # Videos & PDFs
    "video_list": "get-video-list",
    "video_detail": "get-video-detail",
    "pdf_list": "get-pdf-list",
    "pdf_detail": "get-pdf-detail",
    "free_videos": "get-free-video",
    "free_pdfs": "get-free-pdf",
    
    # Mixed content
    "mixed_content": "get-mixed-content",
    
    # Live classes
    "live_classes": "get-live-class",
    "live_stream": "get-live-stream",
    
    # Tests
    "test_series": "get-test-series",
    "test_list": "get-test-list",
    "test_detail": "get-test-detail",
    
    # EBooks
    "ebook_list": "get-ebook-list",
    "ebook_series": "get-ebook-series",
    
    # Doubts / Tickets
    "doubt_courses": "get-doubt-courses",
    "doubt_list": "get-doubt-list",
    "ticket_list": "get-ticket-list",
    
    # Events
    "events": "get-events",
    "event_video": "get-event-video",
    
    # Downloads
    "download_list": "get-download-list",
    
    # News
    "news": "get-news",
    "board_result": "get-board-result",
}
