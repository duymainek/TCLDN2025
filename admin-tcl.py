import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from supabase import create_client, Client
from datetime import datetime, timezone
from typing import Tuple, Optional, List, Dict

# Check installed packages (for debugging)
# Cấu hình logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Hằng số
SUPABASE_URL = "https://ifkusnuoxzllhniwkywh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlma3VzbnVveHpsbGhuaXdreXdoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNjE0MTY1MywiZXhwIjoyMDUxNzE3NjUzfQ.PcLgon96CK6xB8Mf82FRRCZ_b7XvidAQlDD4cQ_wFKM"
TOKEN = "7072191078:AAGwmKPkZPunE9Qp2sFOMPvunwPfljqKsco"
PASSWORD = "Mksai123"  # Mật khẩu cố định

# Khởi tạo Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Các trạng thái cuộc trò chuyện
ENTER_PASSWORD, SELECT_CHAPTER, SELECT_TEAM, ENTER_POINTS, SELECT_DEDUCT_TEAM, ENTER_DEDUCT_POINTS = range(6)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Yêu cầu nhập mật khẩu khi người dùng dùng lệnh /start"""
    await update.message.reply_text(
        "Vui lòng nhập mật khẩu để tiếp tục:",
        reply_markup=ReplyKeyboardRemove()  # Xóa bàn phím nếu có
    )
    return ENTER_PASSWORD

async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kiểm tra mật khẩu người dùng nhập"""
    user_input = update.message.text.strip()
    
    if user_input == PASSWORD:
        welcome_message = (
            "Mật khẩu đúng! Chào mừng bạn đến với bot của chúng tôi!\n"
            "Dùng /addpoints để cộng điểm cho một đội, /deductpoints để trừ điểm, hoặc /ranking để xem bảng xếp hạng."
        )
        await update.message.reply_text(welcome_message)
        return ConversationHandler.END  # Kết thúc trạng thái kiểm tra mật khẩu
    else:
        await update.message.reply_text("Mật khẩu sai. Vui lòng nhập lại:")
        return ENTER_PASSWORD  # Quay lại trạng thái nhập mật khẩu

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hiển thị bảng xếp hạng của các đội"""
    response = supabase.table("users").select("code, name, score").order("score", desc=True).execute()
    ranking_message = "Bảng xếp hạng:\n"
    for i, user in enumerate(response.data, 1):
        ranking_message += f"{i}. {user['name']} - {user['score']} điểm\n"
    await update.message.reply_text(ranking_message)

async def addpoints(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bắt đầu quá trình cộng điểm và hiển thị danh sách các chapter trước"""
    response = supabase.table("chapter").select("id, name").execute()
    chapters = response.data
    
    if not chapters:
        await update.message.reply_text("Không có chapter nào trong danh sách.")
        return ConversationHandler.END
    
    # Lưu thông tin rằng đây là tác vụ cộng điểm
    context.user_data["task"] = "add"
    
    keyboard = [[f"{chapter['name']} (ID: {chapter['id']})"] for chapter in chapters]
    keyboard.append(["Hủy"])
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard=keyboard,
        one_time_keyboard=True,
        resize_keyboard=True
    )
    
    await update.message.reply_text(
        "Vui lòng chọn chapter:", 
        reply_markup=reply_markup
    )
    return SELECT_CHAPTER

async def deductpoints(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bắt đầu quá trình trừ điểm và hiển thị danh sách các chapter trước"""
    response = supabase.table("chapter").select("id, name").execute()
    chapters = response.data
    
    if not chapters:
        await update.message.reply_text("Không có chapter nào trong danh sách.")
        return ConversationHandler.END
    
    # Lưu thông tin rằng đây là tác vụ trừ điểm
    context.user_data["task"] = "deduct"
    
    keyboard = [[f"{chapter['name']} (ID: {chapter['id']})"] for chapter in chapters]
    keyboard.append(["Hủy"])
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard=keyboard,
        one_time_keyboard=True,
        resize_keyboard=True
    )
    
    await update.message.reply_text(
        "Vui lòng chọn chapter:", 
        reply_markup=reply_markup
    )
    return SELECT_CHAPTER

async def select_chapter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý lựa chọn chapter từ keyboard"""
    selected_text = update.message.text.strip()
    
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        chapter_id = int(selected_text.split("(ID: ")[1].rstrip(")"))
        
        response = supabase.table("chapter").select("id").eq("id", chapter_id).execute()
        if not response.data:
            await update.message.reply_text("Chapter không hợp lệ. Vui lòng thử lại.")
            return SELECT_CHAPTER
        
        context.user_data["chapter_id"] = chapter_id
        # Tiếp tục hiển thị danh sách đội theo chapter
        response = supabase.table("users").select("code, name").execute()
        teams = response.data
        
        if not teams:
            await update.message.reply_text("Không có đội nào trong chapter này.")
            return ConversationHandler.END
        
        keyboard = [[f"{team['name']} (Code: {team['code']})"] for team in teams]
        keyboard.append(["Hủy"])
        
        reply_markup = ReplyKeyboardMarkup(
            keyboard=keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        task = context.user_data.get("task", "add")  # Mặc định là "add" nếu không có
        if task == "add":
            await update.message.reply_text(
                "Vui lòng chọn đội để cộng điểm:", 
                reply_markup=reply_markup
            )
            return SELECT_TEAM  # Chuyển sang chọn đội để cộng điểm
        elif task == "deduct":
            await update.message.reply_text(
                "Vui lòng chọn đội để trừ điểm:", 
                reply_markup=reply_markup
            )
            return SELECT_DEDUCT_TEAM  # Chuyển sang chọn đội để trừ điểm
    
    except (IndexError, ValueError):
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_CHAPTER

async def select_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý lựa chọn đội từ keyboard"""
    selected_text = update.message.text.strip()
    
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình cộng điểm.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        
        # Lọc đội theo chapter_id
        response = supabase.table("users").select("code").eq("code", user_code).execute()
        
        if not response.data:
            await update.message.reply_text("Mã đội không hợp lệ hoặc không thuộc chapter này. Vui lòng thử lại.")
            return SELECT_TEAM
        
        context.user_data["user_code"] = user_code
        await update.message.reply_text(
            "Bạn muốn cộng bao nhiêu điểm? (Nhập số, ví dụ: 10.5)",
            reply_markup=ReplyKeyboardRemove()
        )
        return ENTER_POINTS
    
    except IndexError:
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_TEAM

async def enter_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý số điểm người dùng nhập (double) và cập nhật điểm"""
    try:
        points = float(update.message.text.strip())
        user_code = context.user_data["user_code"]
        
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        
        new_score = current_score + points
        supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
        
        admin_code = "admin123"
        chapter_id = context.user_data.get("chapter_id")
        supabase.table("point_history").insert({
            "user_code": user_code,
            "points_added": points,
            "admin_code": admin_code,
            "chapter": chapter_id
        }).execute()
        
        await update.message.reply_text(
            f"Đã cộng {points} điểm cho đội {user_code}.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        context.user_data.clear()  # Xóa tất cả dữ liệu, bao gồm "task" và "chapter_id"
        return ConversationHandler.END
    
    except ValueError:
        await update.message.reply_text("Vui lòng nhập một số hợp lệ (ví dụ: 10 hoặc 10.5).")
        return ENTER_POINTS

async def select_deduct_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý lựa chọn đội từ keyboard cho việc trừ điểm"""
    selected_text = update.message.text.strip()
    
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình trừ điểm.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        
        # Lọc đội theo chapter_id
        response = supabase.table("users").select("code").eq("code", user_code).execute()
        
        if not response.data:
            await update.message.reply_text("Mã đội không hợp lệ hoặc không thuộc chapter này. Vui lòng thử lại.")
            return SELECT_DEDUCT_TEAM
        
        context.user_data["user_code"] = user_code
        await update.message.reply_text(
            "Bạn muốn trừ bao nhiêu điểm? (Nhập số, ví dụ: 10.5)",
            reply_markup=ReplyKeyboardRemove()
        )
        return ENTER_DEDUCT_POINTS
    
    except IndexError:
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_DEDUCT_TEAM

async def enter_deduct_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý số điểm người dùng nhập (double) và cập nhật điểm khi trừ"""
    try:
        points = float(update.message.text.strip())
        user_code = context.user_data["user_code"]
        
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        
        # Trừ điểm (nếu điểm hiện tại < điểm muốn trừ, có thể thêm logic kiểm tra)
        if current_score < points:
            await update.message.reply_text("Điểm hiện tại không đủ để trừ. Vui lòng nhập số điểm nhỏ hơn.")
            return ENTER_DEDUCT_POINTS
        
        new_score = current_score - points
        supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
        chapter_id = context.user_data.get("chapter_id")
        admin_code = "admin123"
        supabase.table("point_deduct_history").insert({
            "user_code": user_code,
            "points_deducted": points,
            "admin_code": admin_code,
            "chapter": chapter_id
        }).execute()
        
        await update.message.reply_text(
            f"Đã trừ {points} điểm cho đội {user_code}.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        context.user_data.clear()  # Xóa tất cả dữ liệu, bao gồm "task" và "chapter_id"
        return ConversationHandler.END
    
    except ValueError:
        await update.message.reply_text("Vui lòng nhập một số hợp lệ (ví dụ: 10 hoặc 10.5).")
        return ENTER_DEDUCT_POINTS

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Hủy cuộc trò chuyện"""
    await update.message.reply_text("Đã hủy quá trình.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    """Khởi động bot."""
    logger.info("Starting the bot...")
    application = Application.builder().token(TOKEN).build()

    # Thêm ConversationHandler bao gồm trạng thái kiểm tra mật khẩu và trừ điểm
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start), 
            CommandHandler("addpoints", addpoints),
            CommandHandler("deductpoints", deductpoints)
        ],
        states={
            ENTER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
            SELECT_CHAPTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_chapter)],
            SELECT_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_team)],
            ENTER_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_points)],
            SELECT_DEDUCT_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_deduct_team)],
            ENTER_DEDUCT_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_deduct_points)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Thêm các handler
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("ranking", ranking))

    application.run_polling()

if __name__ == '__main__':
    main()