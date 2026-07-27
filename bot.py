"""
Bridge to Success Telegram Bot
Supports mobile + password login and no‑login free content extraction.
"""
import logging
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)
from config import BOT_TOKEN
from extractor import BridgeExtractor, format_content_list, format_courses_list

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Conversation states ---
MOBILE, PASSWORD = range(2)

# --- In‑memory session storage (user_id → {token, mobile, name}) ---
user_sessions: Dict[int, Dict] = {}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def get_extractor(user_id: int) -> BridgeExtractor:
    """Returns an extractor with the user's token (if logged in)."""
    token = None
    if user_id in user_sessions:
        token = user_sessions[user_id].get("token")
    return BridgeExtractor(token)


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Build the main menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("🆓 Free Content (No Login)", callback_data="free")],
        [InlineKeyboardButton("🔑 Login", callback_data="login")],
        [InlineKeyboardButton("📚 My Courses (Login)", callback_data="my_courses")],
        [InlineKeyboardButton("📦 Extract All (Login)", callback_data="extract_all")],
        [InlineKeyboardButton("📄 Status", callback_data="status")],
        [InlineKeyboardButton("🚪 Logout", callback_data="logout")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_message(update: Update):
    """Return the appropriate message object (from command or callback)."""
    if update.message:
        return update.message
    elif update.callback_query and update.callback_query.message:
        return update.callback_query.message
    return None


# ----------------------------------------------------------------------
# Command / Callback handlers
# ----------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with main menu."""
    user = update.effective_user
    msg = get_message(update)
    if msg is None:
        return
    await msg.reply_text(
        f"🎓 *Welcome to Bridge to Success Extractor, {user.first_name}!*\n\n"
        "I can extract videos and PDFs from the app.\n"
        "Choose an option below:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available commands."""
    msg = get_message(update)
    if msg is None:
        return
    await msg.reply_text(
        "📖 *Commands*\n\n"
        "/start — Show main menu\n"
        "/free — Get free content (no login)\n"
        "/login — Login with mobile and password\n"
        "/mycourses — View your enrolled courses\n"
        "/extract — Extract all your content\n"
        "/status — Show your session status\n"
        "/logout — Clear your session\n",
        parse_mode="Markdown"
    )


async def free_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch free content without authentication."""
    user_id = update.effective_user.id
    msg = get_message(update)
    if msg is None:
        return

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
    """Start the mobile + password login conversation."""
    user_id = update.effective_user.id
    msg = get_message(update)
    if msg is None:
        return

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
    return MOBILE


async def handle_mobile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the mobile number input."""
    mobile = update.message.text.strip()

    if not mobile.isdigit() or len(mobile) != 10:
        await update.message.reply_text("❌ Invalid mobile number. Enter 10 digits only.")
        return MOBILE

    context.user_data["mobile"] = mobile

    await update.message.reply_text(
        "🔑 Please enter your *password*:\n"
        "(It will be visible but not stored after login)",
        parse_mode="Markdown"
    )
    return PASSWORD


async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle password input, perform login, and store token."""
    user_id = update.effective_user.id
    password = update.message.text.strip()
    mobile = context.user_data.get("mobile", "")

    if not password:
        await update.message.reply_text("❌ Password cannot be empty. Please try again.")
        return PASSWORD

    # Perform login
    extractor = get_extractor(user_id)
    await update.message.reply_text("⏳ Logging in...")

    result = extractor.login_with_password(mobile, password)

    if result.get("success"):
        user_sessions[user_id] = {
            "token": result["token"],
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
            f"❌ Login failed: {result.get('message', 'Wrong credentials')}\n"
            "Please try again with /login."
        )
        return ConversationHandler.END


async def login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the login conversation."""
    await update.message.reply_text("❌ Login cancelled.")
    return ConversationHandler.END


async def my_courses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the user's enrolled courses."""
    user_id = update.effective_user.id
    msg = get_message(update)
    if msg is None:
        return

    if user_id not in user_sessions:
        await msg.reply_text("⚠️ Please /login first.")
        return

    extractor = get_extractor(user_id)
    courses = extractor.get_my_courses()

    if not courses:
        await msg.reply_text("ℹ️ No enrolled courses found.")
        return

    context.user_data["courses"] = courses
    await msg.reply_text(
        f"📚 *Your Courses ({len(courses)})*\n\n"
        "Use /extract to extract content from all courses.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 Extract All", callback_data="extract_all")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")]
        ])
    )


async def extract_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extract all content from the user's courses (authenticated)."""
    user_id = update.effective_user.id
    msg = get_message(update)
    if msg is None:
        return

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

        # Send extracted content (videos and PDFs separately)
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
    """Show the user's current session status."""
    user_id = update.effective_user.id
    msg = get_message(update)
    if msg is None:
        return

    if user_id in user_sessions:
        session = user_sessions[user_id]
        await msg.reply_text(
            f"✅ *Logged In*\n\n"
            f"👤 Name: {session.get('name', 'N/A')}\n"
            f"📱 Mobile: {session.get('mobile', 'N/A')}\n"
            f"🔑 Token: {session.get('token', '')[:30]}...",
            parse_mode="Markdown"
        )
    else:
        await msg.reply_text("❌ Not logged in. Use /login to authenticate.")


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear the user's session."""
    user_id = update.effective_user.id
    msg = get_message(update)
    if msg is None:
        return

    if user_id in user_sessions:
        del user_sessions[user_id]
        await msg.reply_text("🚪 Logged out successfully.")
    else:
        await msg.reply_text("ℹ️ You were not logged in.")


# ----------------------------------------------------------------------
# Button dispatcher
# ----------------------------------------------------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route inline keyboard callbacks to the appropriate handlers."""
    query = update.callback_query
    await query.answer()
    action = query.data

    # Map action to handler (we reuse the same async functions)
    handlers = {
        "free": free_content,
        "login": login_start,
        "my_courses": my_courses,
        "extract_all": extract_all,
        "status": status_command,
        "logout": logout,
    }

    if action in handlers:
        # The handlers will use get_message(update) to get the correct message object
        await handlers[action](update, context)
    elif action == "back":
        await query.message.reply_text(
            "🎓 *Main Menu*",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    else:
        await query.message.reply_text("❌ Unknown action.")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    """Start the bot."""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not BOT_TOKEN:
        print("❌ Please set BOT_TOKEN in config.py or environment variables!")
        return

    print("🤖 Starting Bridge to Success Bot...")
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("free", free_content))
    app.add_handler(CommandHandler("mycourses", my_courses))
    app.add_handler(CommandHandler("extract", extract_all))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("logout", logout))

    # Login conversation (mobile → password)
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("login", login_start),
            CallbackQueryHandler(login_start, pattern="^login$"),
        ],
        states={
            MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mobile)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password)],
        },
        fallbacks=[
            CommandHandler("cancel", login_cancel),
            MessageHandler(filters.COMMAND, login_cancel),
        ],
        per_message=False,
        per_chat=True,
    )
    app.add_handler(conv_handler)

    # Inline buttons
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Bot is ready and polling for updates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
