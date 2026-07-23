"""
Bridge to Success Telegram Bot
Supports both login and no-login content extraction
"""
import logging
import re
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters, ConversationHandler
)
from config import BOT_TOKEN
from extractor import BridgeExtractor, format_content_list, format_courses_list

# ─── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Conversation States ──────────────────────────────────────────────────
(MOBILE, OTP) = range(2)

# ─── Session Storage ──────────────────────────────────────────────────────
user_sessions: Dict[int, Dict] = {}
# Structure: { user_id: {"token": str, "mobile": str, "name": str} }


# ─── Helper Functions ────────────────────────────────────────────────────
def get_extractor(user_id: int) -> BridgeExtractor:
    """Get extractor instance for user (with or without token)"""
    token = None
    if user_id in user_sessions:
        token = user_sessions[user_id].get("token")
    return BridgeExtractor(token)


# ─── Keyboard Builders ──────────────────────────────────────────────────
def get_main_keyboard() -> InlineKeyboardMarkup:
    """Build main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("🆓 Free Content (No Login)", callback_data="free")],
        [InlineKeyboardButton("🔑 Login", callback_data="login")],
        [InlineKeyboardButton("📚 My Courses (Login)", callback_data="my_courses")],
        [InlineKeyboardButton("📦 Extract All (Login)", callback_data="extract_all")],
        [InlineKeyboardButton("📄 Status", callback_data="status")],
        [InlineKeyboardButton("🚪 Logout", callback_data="logout")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ─── Command Handlers ────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with main menu"""
    user = update.effective_user
    await update.message.reply_text(
        f"🎓 *Welcome to Bridge to Success Extractor, {user.first_name}!*\n\n"
        "I can extract videos and PDFs from the app.\n"
        "Choose an option below:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    await update.message.reply_text(
        "📖 *Commands*\n\n"
        "/start — Show main menu\n"
        "/free — Get free content (no login)\n"
        "/login — Login with mobile OTP\n"
        "/mycourses — View your enrolled courses\n"
        "/extract — Extract all your content\n"
        "/status — Show your session status\n"
        "/logout — Clear your session\n",
        parse_mode="Markdown"
    )


async def free_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch free content without login"""
    user_id = update.effective_user.id
    msg = update.message or update.callback_query.message
    
    status_msg = await msg.reply_text("🔍 Fetching free content...")
    
    extractor = get_extractor(user_id)
    items = extractor.fetch_free_content()
    
    if not items:
        await status_msg.edit_text("ℹ️ No free content found.")
        return
    
    await status_msg.edit_text(f"✅ Found *{len(items)}* free items:", parse_mode="Markdown")
    
    for chunk in format_content_list(items):
        await msg.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)


async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start OTP login flow"""
    user_id = update.effective_user.id
    msg = update.message or update.callback_query.message
    
    # Check if already logged in
    if user_id in user_sessions and user_sessions[user_id].get("token"):
        await msg.reply_text(
            "✅ You are already logged in!\n"
            "Use /extract to get your content or /logout to clear session."
        )
        return
    
    await msg.reply_text(
        "📱 Please enter your *registered mobile number*\n"
        "(10 digits, no country code):",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def handle_mobile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mobile number input"""
    user_id = update.effective_user.id
    mobile = update.message.text.strip()
    
    if not mobile.isdigit() or len(mobile) != 10:
        await update.message.reply_text("❌ Invalid mobile number. Enter 10 digits only.")
        return ConversationHandler.END
    
    context.user_data["mobile"] = mobile
    
    # Send OTP
    extractor = get_extractor(user_id)
    resp = extractor.send_otp(mobile)
    
    if resp.get("status") == 1:
        await update.message.reply_text(
            f"✅ OTP sent to {mobile}.\n"
            "Please enter the *OTP* you received:",
            parse_mode="Markdown"
        )
        return OTP
    else:
        await update.message.reply_text(
            f"❌ Failed to send OTP: {resp.get('message', 'Unknown error')}"
        )
        return ConversationHandler.END


async def handle_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle OTP verification"""
    user_id = update.effective_user.id
    otp = update.message.text.strip()
    mobile = context.user_data.get("mobile", "")
    
    if not otp.isdigit():
        await update.message.reply_text("❌ OTP must be digits only.")
        return OTP
    
    extractor = get_extractor(user_id)
    result = extractor.login_with_otp(mobile, otp)
    
    if result.get("success"):
        user_sessions[user_id] = {
            "token": result.get("token"),
            "mobile": mobile,
            "name": result.get("user", {}).get("name", mobile),
        }
        await update.message.reply_text(
            f"✅ *Logged in successfully!*\n\n"
            f"Welcome {user_sessions[user_id]['name']}! 🎉\n"
            "Use /extract to fetch all your content.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            f"❌ Login failed: {result.get('message', 'Wrong OTP')}\n"
            "Please try again or use /login to restart."
        )
        return ConversationHandler.END


async def login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel login flow"""
    await update.message.reply_text("❌ Login cancelled.")
    return ConversationHandler.END


async def my_courses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's enrolled courses"""
    user_id = update.effective_user.id
    msg = update.message or update.callback_query.message
    
    if user_id not in user_sessions:
        await msg.reply_text("⚠️ Please /login first.")
        return
    
    extractor = get_extractor(user_id)
    courses = extractor.get_my_courses()
    
    if not courses:
        await msg.reply_text("ℹ️ No enrolled courses found.")
        return
    
    # Store courses in context for extraction
    context.user_data["courses"] = courses
    
    await msg.reply_text(
        f"📚 *Your Courses ({len(courses)})*\n\n"
        "Use /extract_all to extract content from all courses.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 Extract All", callback_data="extract_all")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")]
        ])
    )


async def extract_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extract all content from user's courses"""
    user_id = update.effective_user.id
    msg = update.message or update.callback_query.message
    
    if user_id not in user_sessions:
        await msg.reply_text("⚠️ Please /login first.")
        return
    
    extractor = get_extractor(user_id)
    
    status_msg = await msg.reply_text(
        "⚙️ Extracting all content...\n"
        "_This may take a few minutes._",
        parse_mode="Markdown"
    )
    
    try:
        result = extractor.extract_all_user_content()
        
        free_count = len(result.get("free", []))
        extracted_count = len(result.get("extracted", []))
        
        await status_msg.edit_text(
            f"✅ *Extraction Complete!*\n\n"
            f"🆓 Free items: {free_count}\n"
            f"📦 Extracted items: {extracted_count}\n"
            f"📚 Courses: {len(result.get('my_courses', []))}\n\n"
            f"Sending content now...",
            parse_mode="Markdown"
        )
        
        # Send free content first
        if result.get("free"):
            await msg.reply_text("*🆓 FREE CONTENT:*", parse_mode="Markdown")
            for chunk in format_content_list(result["free"]):
                await msg.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)
        
        # Send extracted content
        if result.get("extracted"):
            videos = [i for i in result["extracted"] if "VIDEO" in i["type"]]
            pdfs = [i for i in result["extracted"] if "PDF" in i["type"]]
            
            if videos:
                await msg.reply_text(f"*🎬 VIDEOS ({len(videos)})*", parse_mode="Markdown")
                for chunk in format_content_list(videos):
                    await msg.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)
            
            if pdfs:
                await msg.reply_text(f"*📄 PDFs ({len(pdfs)})*", parse_mode="Markdown")
                for chunk in format_content_list(pdfs):
                    await msg.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user session status"""
    user_id = update.effective_user.id
    
    if user_id in user_sessions:
        session = user_sessions[user_id]
        await update.message.reply_text(
            f"✅ *Logged In*\n\n"
            f"👤 Name: {session.get('name', 'N/A')}\n"
            f"📱 Mobile: {session.get('mobile', 'N/A')}\n"
            f"🔑 Token: {session.get('token', '')[:30]}...",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Not logged in. Use /login to authenticate.")


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logout user"""
    user_id = update.effective_user.id
    msg = update.message or update.callback_query.message
    
    if user_id in user_sessions:
        del user_sessions[user_id]
        await msg.reply_text("🚪 Logged out successfully.")
    else:
        await msg.reply_text("ℹ️ You were not logged in.")


# ─── Button Handler ──────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    # Map button actions to functions
    action_map = {
        "free": free_content,
        "login": login_start,
        "my_courses": my_courses,
        "extract_all": extract_all,
        "status": status_command,
        "logout": logout,
    }
    
    # Temporarily set callback_query to None so handlers work correctly
    update.callback_query = None
    
    if action in action_map:
        await action_map[action](update, context)
    else:
        await query.message.reply_text("❌ Unknown action.")


# ─── Conversation Handler ──────────────────────────────────────────────
def get_conversation_handler():
    """Create conversation handler for login flow"""
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("login", login_start),
            CallbackQueryHandler(login_start, pattern="^login$"),
        ],
        states={
            MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mobile)],
            OTP: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_otp)],
        },
        fallbacks=[
            CommandHandler("cancel", login_cancel),
            MessageHandler(filters.COMMAND, login_cancel),
        ],
        per_message=False,
        per_chat=True,
    )
    return conv_handler


# ─── Main ──────────────────────────────────────────────────────────────
def main():
    """Run the bot"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please set BOT_TOKEN in config.py or environment variables!")
        return
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("free", free_content))
    app.add_handler(CommandHandler("mycourses", my_courses))
    app.add_handler(CommandHandler("extract", extract_all))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("logout", logout))
    
    # Add login conversation handler
    app.add_handler(get_conversation_handler())
    
    # Add button handler
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Start bot
    print("🤖 Bridge to Success Bot is running...")
    print("📱 Bot username: @" + app.bot.username if app.bot.username else "Unknown")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
