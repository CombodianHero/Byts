"""
Core extraction logic for Bridge to Success
"""
import re
import time
import json
import requests
from typing import List, Dict, Any, Optional
from config import (
    API_BASE, API_BASE_ALT1, API_BASE_ALT2, API_BASE_ALT3,
    ENDPOINTS, HEADERS, STORAGE_PDF, STORAGE_VID, PLAYER_URL, LIVE_URL
)


class BridgeExtractor:
    """Main extractor class for Bridge to Success content"""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        if token:
            self.session.headers["authtoken"] = token
            self.session.headers["Authorization"] = f"Bearer {token}"
    
    def _api_call(self, endpoint_key: str, method: str = "POST", data: Dict = None, params: Dict = None) -> Dict:
        """Make API call with fallback to alternative bases"""
        bases = [API_BASE, API_BASE_ALT1, API_BASE_ALT2, API_BASE_ALT3]
        endpoint = ENDPOINTS.get(endpoint_key, endpoint_key)
        
        # Try different endpoint name variations
        endpoint_variations = [
            endpoint,
            endpoint.replace("-", "_"),
            endpoint.replace("_", "-"),
            endpoint.replace("get-", ""),
            endpoint.replace("get_", ""),
        ]
        
        for base in bases:
            for ep in set(endpoint_variations):
                url = base + ep
                try:
                    if method.upper() == "POST":
                        resp = self.session.post(url, json=data, params=params, timeout=30)
                    else:
                        resp = self.session.get(url, params=params, timeout=30)
                    
                    if resp.status_code == 200:
                        result = resp.json()
                        if result.get("status") == 1 or result.get("success") is True:
                            return result
                        # If status is 0 but we got a response, it might still work
                        if "data" in result:
                            return result
                except Exception as e:
                    continue
        
        return {"status": 0, "message": "All API endpoints failed"}
    
    def _extract_video_url(self, video_data: Dict) -> str:
        """Extract video URL from various response formats"""
        fields = ["video_url", "videoUrl", "videoLink", "video_link", "hls_url",
                  "stream_url", "url", "file_url", "dash_url", "mp4_url", "link"]
        for f in fields:
            val = video_data.get(f)
            if val and isinstance(val, str) and len(val) > 3:
                if val.startswith("storage/"):
                    return STORAGE_VID + val.replace("storage/video/", "")
                if val.startswith("http"):
                    return val
                if val.isdigit() or ("/" not in val and len(val) < 30):
                    return PLAYER_URL + val
        vid_id = video_data.get("video_id") or video_data.get("videoId") or video_data.get("id")
        if vid_id:
            return PLAYER_URL + str(vid_id)
        return "URL_NOT_FOUND"
    
    def _extract_pdf_url(self, pdf_data: Dict) -> str:
        """Extract PDF URL from various response formats"""
        fields = ["pdf_url", "pdfUrl", "pdf_link", "file_url", "url", "pdf_file", "file", "link", "pdf_path"]
        for f in fields:
            val = pdf_data.get(f)
            if val and isinstance(val, str) and len(val) > 3:
                if val.startswith("storage/"):
                    return "https://bridgetosuccess.learncentre.tech/public/" + val
                if val.startswith("http"):
                    return val
                if not val.startswith("/"):
                    return STORAGE_PDF + val
        pdf_name = pdf_data.get("pdf_name") or pdf_data.get("name") or pdf_data.get("pdf_id")
        if pdf_name:
            return STORAGE_PDF + str(pdf_name)
        return "URL_NOT_FOUND"
    
    # ─── Free Content (No Login) ────────────────────────────────────────
    def fetch_free_content(self) -> List[Dict]:
        """Fetch free videos and PDFs without authentication"""
        results = []
        
        # Free videos
        fv = self._api_call("free_videos", method="GET")
        if fv.get("status") == 1 or "data" in fv:
            data = fv.get("data", [])
            if isinstance(data, dict):
                data = list(data.values())
            for v in data:
                results.append({
                    "type": "FREE_VIDEO",
                    "title": v.get("title") or v.get("name") or "Untitled",
                    "url": self._extract_video_url(v),
                    "course": v.get("course_name") or "Free",
                })
        
        # Free PDFs
        fp = self._api_call("free_pdfs", method="GET")
        if fp.get("status") == 1 or "data" in fp:
            data = fp.get("data", [])
            if isinstance(data, dict):
                data = list(data.values())
            for p in data:
                results.append({
                    "type": "FREE_PDF",
                    "title": p.get("title") or p.get("name") or "Untitled",
                    "url": self._extract_pdf_url(p),
                    "course": p.get("course_name") or "Free",
                })
        
        return results
    
    # ─── Authentication ──────────────────────────────────────────────────
    def send_otp(self, mobile: str) -> Dict:
        """Send OTP to mobile number"""
        # Try different payload formats
        payloads = [
            {"mobile": mobile, "type": "login"},
            {"mobile": mobile, "type": "register"},
            {"mobile": mobile},
            {"phone": mobile, "type": "login"},
            {"phone": mobile},
        ]
        
        for payload in payloads:
            result = self._api_call("send_otp", data=payload)
            if result.get("status") == 1 or result.get("success") is True:
                return result
        
        return {"status": 0, "message": "Could not send OTP"}
    
    def login_with_otp(self, mobile: str, otp: str) -> Dict:
        """Login with OTP and get token"""
        # Try different login endpoints
        endpoints = ["login", "verify_otp", "verify-otp"]
        payloads = [
            {"mobile": mobile, "otp": otp},
            {"phone": mobile, "otp": otp},
            {"mobile": mobile, "otp": otp, "type": "login"},
        ]
        
        for endpoint in endpoints:
            for payload in payloads:
                # Temporarily override the endpoint
                result = self._api_call(endpoint, data=payload)
                if result.get("status") == 1 or result.get("success") is True:
                    data = result.get("data", {})
                    token = data.get("token") or data.get("authtoken") or data.get("api_token")
                    if token:
                        return {"success": True, "token": token, "user": data}
        
        return {"success": False, "message": "Login failed"}
    
    # ─── Course Extraction ──────────────────────────────────────────────
    def get_my_courses(self) -> List[Dict]:
        """Get user's enrolled courses (requires auth)"""
        if not self.token:
            return []
        
        resp = self._api_call("my_courses", method="GET")
        if resp.get("status") != 1 and "data" not in resp:
            return []
        data = resp.get("data", [])
        if isinstance(data, dict):
            data = list(data.values())
        return data
    
    def get_all_courses(self) -> List[Dict]:
        """Get all available courses (may or may not require auth)"""
        resp = self._api_call("all_courses", method="GET")
        if resp.get("status") != 1 and "data" not in resp:
            return []
        data = resp.get("data", [])
        if isinstance(data, dict):
            data = list(data.values())
        return data
    
    def extract_course_full(self, course: Dict) -> List[Dict]:
        """Extract ALL content from a course: videos, PDFs, mixed content"""
        results = []
        course_id = course.get("id") or course.get("course_id")
        course_name = course.get("name") or course.get("course_name") or f"Course-{course_id}"
        
        # Get batches
        batch_resp = self._api_call("batch_list", data={"course_id": course_id})
        batches = batch_resp.get("data", [])
        if isinstance(batches, dict):
            batches = list(batches.values())
        if not batches:
            detail = self._api_call("course_detail", data={"course_id": course_id})
            batches = detail.get("data", {}).get("batch", [])
        if not batches:
            return results
        
        for b in batches:
            batch_id = b.get("id") or b.get("batch_id")
            batch_name = b.get("name") or b.get("batch_name") or f"Batch-{batch_id}"
            
            # Get subjects
            subj_resp = self._api_call("subject_list", data={"course_id": course_id, "batch_id": batch_id})
            subjects = subj_resp.get("data", [])
            if isinstance(subjects, dict):
                subjects = list(subjects.values())
            
            for s in subjects:
                subj_id = s.get("id") or s.get("subject_id")
                subj_name = s.get("name") or s.get("subject_name") or f"Subject-{subj_id}"
                
                # Get chapters
                chap_resp = self._api_call("chapter_list", data={
                    "course_id": course_id, "batch_id": batch_id, "subject_id": subj_id
                })
                chapters = chap_resp.get("data", [])
                if isinstance(chapters, dict):
                    chapters = list(chapters.values())
                
                for ch in chapters:
                    ch_id = ch.get("id") or ch.get("chapter_id")
                    ch_name = ch.get("name") or ch.get("chapter_name") or f"Chapter-{ch_id}"
                    
                    # Videos
                    vid_resp = self._api_call("video_list", data={
                        "course_id": course_id, "batch_id": batch_id,
                        "subject_id": subj_id, "chapter_id": ch_id
                    })
                    videos = vid_resp.get("data", [])
                    if isinstance(videos, dict):
                        videos = list(videos.values())
                    for v in videos:
                        results.append({
                            "type": "VIDEO",
                            "course": course_name,
                            "batch": batch_name,
                            "subject": subj_name,
                            "chapter": ch_name,
                            "title": v.get("title") or v.get("name") or "Untitled",
                            "url": self._extract_video_url(v),
                            "duration": v.get("duration") or v.get("video_duration") or "",
                        })
                    
                    # PDFs
                    pdf_resp = self._api_call("pdf_list", data={
                        "course_id": course_id, "batch_id": batch_id,
                        "subject_id": subj_id, "chapter_id": ch_id
                    })
                    pdfs = pdf_resp.get("data", [])
                    if isinstance(pdfs, dict):
                        pdfs = list(pdfs.values())
                    for p in pdfs:
                        results.append({
                            "type": "PDF",
                            "course": course_name,
                            "batch": batch_name,
                            "subject": subj_name,
                            "chapter": ch_name,
                            "title": p.get("title") or p.get("name") or "Untitled",
                            "url": self._extract_pdf_url(p),
                        })
                    
                    time.sleep(0.15)
                time.sleep(0.15)
            time.sleep(0.15)
        
        return results
    
    def extract_all_user_content(self) -> Dict[str, List]:
        """Extract all content for logged-in user"""
        result = {
            "free": [],
            "my_courses": [],
            "all_courses": [],
            "extracted": []
        }
        
        # Free content (always available)
        result["free"] = self.fetch_free_content()
        
        # My courses (requires auth)
        if self.token:
            my_courses = self.get_my_courses()
            if my_courses:
                result["my_courses"] = my_courses
                for course in my_courses:
                    extracted = self.extract_course_full(course)
                    result["extracted"].extend(extracted)
        
        # All courses (try without auth first)
        if not result["my_courses"]:
            all_courses = self.get_all_courses()
            if all_courses:
                result["all_courses"] = all_courses
                for course in all_courses:
                    extracted = self.extract_course_full(course)
                    result["extracted"].extend(extracted)
        
        return result


# ─── Utility functions ──────────────────────────────────────────────────

def format_content_list(items: List[Dict], max_chars: int = 4000) -> List[str]:
    """Format content list into Telegram-safe message chunks"""
    chunks = []
    current = ""
    
    for i, item in enumerate(items, 1):
        icon = "🎬" if "VIDEO" in item["type"] else "📄"
        line = f"{icon} *{i}. {item['title']}*\n"
        line += f"   📂 {item.get('course', '')}"
        if item.get("batch"):
            line += f" → {item.get('batch', '')}"
        if item.get("subject"):
            line += f"\n   📌 {item.get('subject', '')}"
        if item.get("chapter"):
            line += f" → {item.get('chapter', '')}"
        line += f"\n   🔗 `{item.get('url', 'NO_URL')}`\n\n"
        
        if len(current) + len(line) > max_chars:
            chunks.append(current)
            current = line
        else:
            current += line
    
    if current:
        chunks.append(current)
    
    return chunks if chunks else ["No content found."]


def format_courses_list(courses: List[Dict]) -> str:
    """Format courses list for display"""
    if not courses:
        return "No courses found."
    
    lines = ["📚 *Available Courses:*\n"]
    for i, c in enumerate(courses, 1):
        name = c.get("name") or c.get("course_name") or f"Course-{c.get('id')}"
        lines.append(f"{i}. {name}")
    
    return "\n".join(lines)
