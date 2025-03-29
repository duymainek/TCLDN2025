import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from supabase import create_client, Client
from datetime import datetime, timezone
from typing import Tuple, Optional, List, Dict


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SUPABASE_URL = "https://ifkusnuoxzllhniwkywh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlma3VzbnVveHpsbGhuaXdreXdoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNjE0MTY1MywiZXhwIjoyMDUxNzE3NjUzfQ.PcLgon96CK6xB8Mf82FRRCZ_b7XvidAQlDD4cQ_wFKM"
TOKEN = "7072191078:AAGwmKPkZPunE9Qp2sFOMPvunwPfljqKsco"
PASSWORD = "Mksai123"
ADMIN_CHAT_ID = "YOUR_ADMIN_CHAT_ID"  # Thay bằng chat ID thực tế

# Cache data
teams_cache = []  # Cache for teams data
chapters_cache = []  # Cache for chapters data

def refresh_cache():
    """Refresh cache data from database"""
    global teams_cache, chapters_cache
    teams_response = supabase.table("users").select("code, name").execute()
    chapters_response = supabase.table("chapter").select("id, name").execute()
    teams_cache = teams_response.data
    chapters_cache = chapters_response.data

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initial cache load
refresh_cache()

# Các trạng thái cuộc trò chuyện
ENTER_PASSWORD, SELECT_CHAPTER, SELECT_TEAM, ENTER_POINTS, ENTER_REASON_ADD, SELECT_DEDUCT_TEAM, ENTER_DEDUCT_POINTS, ENTER_REASON_DEDUCT, SELECT_CHAPTER_TO_LOCK, SELECT_TCN_CHAPTER, SELECT_FIRST_TEAM, SELECT_SECOND_TEAM, SELECT_THIRD_TEAM, SELECT_FOURTH_TEAM, SELECT_TIN_CHAPTER, SELECT_TIN_FIRST_TEAM, SELECT_TIN_SECOND_TEAM, SELECT_TIN_THIRD_TEAM, SELECT_TIN_FOURTH_TEAM = range(19)

# Các hàm hiện có (chuyển sang bất đồng bộ)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Yêu cầu nhập mật khẩu khi người dùng dùng lệnh /start"""
    await update.message.reply_text(
        "Vui lòng nhập mật khẩu để tiếp tục:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ENTER_PASSWORD

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hiển thị thông tin trợ giúp về các lệnh có sẵn"""
    help_text = (
        "Danh sách các lệnh:\n\n"
        "/start - Bắt đầu sử dụng bot\n"
        "/help - Hiển thị trợ giúp này\n"
        "/addpoints - Cộng điểm cho một đội\n"
        "/deductpoints - Trừ điểm của một đội\n"
        "/ranking - Xem bảng xếp hạng\n"
        "/lockchapter - Khóa một trạm\n"
        "/tcn - Xếp hạng TCN\n"
        "/tin - Xếp hạng TIN\n"
        "/cancel - Hủy thao tác hiện tại"
    )
    await update.message.reply_text(help_text)

async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    if user_input == PASSWORD:
        welcome_message = (
            "Mật khẩu đúng! Chào mừng bạn đến với bot của chúng tôi!\n"
            "Dùng /addpoints để cộng điểm cho một đội\n"
            "Dùng /deductpoints để trừ điểm\n"
            "Dùng /ranking để xem bảng xếp hạng\n"
            "Dùng /lockchapter để khóa trạm\n"
            "Dùng /tcn để xếp hạng TCN\n"
            "Dùng /tin để xếp hạng TIN\n"
            "Dùng /help để xem hướng dẫn chi tiết."
        )
        await update.message.reply_text(welcome_message)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Mật khẩu sai. Vui lòng nhập lại:")
        return ENTER_PASSWORD

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    response = supabase.table("users").select("code, name, score").order("score", desc=True).execute()
    ranking_message = "Bảng xếp hạng:\n"
    for i, user in enumerate(response.data, 1):
        ranking_message += f"{i}. {user['name']} - {user['score']} điểm\n"
    await update.message.reply_text(ranking_message)

async def addpoints(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not chapters_cache:
        await update.message.reply_text("Không có chapter nào trong danh sách.")
        return ConversationHandler.END
    context.user_data["task"] = "add"
    keyboard = [[f"{chapter['name']}"] for chapter in chapters_cache]
    keyboard.append(["Hủy"])
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Vui lòng chọn chapter:", reply_markup=reply_markup)
    return SELECT_CHAPTER

async def deductpoints(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not chapters_cache:
        await update.message.reply_text("Không có chapter nào trong danh sách.")
        return ConversationHandler.END
    context.user_data["task"] = "deduct"
    keyboard = [[f"{chapter['name']} (ID: {chapter['id']})"] for chapter in chapters_cache]
    keyboard.append(["Hủy"])
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Vui lòng chọn chapter:", reply_markup=reply_markup)
    return SELECT_CHAPTER

async def select_chapter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    try:
        chapter_id = int(selected_text.split("(ID: ")[1].rstrip(")")) if "(ID: " in selected_text else None
        if not chapter_id:
            chapter = next((c for c in chapters_cache if c["name"] == selected_text), None)
            chapter_id = chapter["id"] if chapter else None
        if not chapter_id or not any(c["id"] == chapter_id for c in chapters_cache):
            await update.message.reply_text("Chapter không hợp lệ. Vui lòng thử lại.")
            return SELECT_CHAPTER
        context.user_data["chapter_id"] = chapter_id
        if not teams_cache:
            await update.message.reply_text("Không có đội nào trong chapter này.")
            return ConversationHandler.END
        keyboard = [[f"{team['name']} (Code: {team['code']})"] for team in teams_cache]
        keyboard.append(["Hủy"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        task = context.user_data.get("task", "add")
        if task == "add":
            await update.message.reply_text("Vui lòng chọn đội để cộng điểm:", reply_markup=reply_markup)
            return SELECT_TEAM
        elif task == "deduct":
            await update.message.reply_text("Vui lòng chọn đội để trừ điểm:", reply_markup=reply_markup)
            return SELECT_DEDUCT_TEAM
    except (IndexError, ValueError):
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_CHAPTER

async def select_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình cộng điểm.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        if not any(team["code"] == user_code for team in teams_cache):
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
    try:
        points = float(update.message.text.strip())
        context.user_data["points"] = points
        await update.message.reply_text(
            "Vui lòng nhập lý do cộng điểm:"
        )
        return ENTER_REASON_ADD
    except ValueError:
        await update.message.reply_text("Vui lòng nhập một số hợp lệ (ví dụ: 10 hoặc 10.5).")
        return ENTER_POINTS

async def enter_reason_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reason = update.message.text.strip()
    user_code = context.user_data["user_code"]
    points = context.user_data["points"]
    
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
        "chapter": chapter_id,
        "reason": reason
    }).execute()
    
    # Refresh cache after updating score
    refresh_cache()
    
    await update.message.reply_text(
        f"Đã cộng {points} điểm cho đội {user_code}.\nLý do: {reason}",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def select_deduct_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình trừ điểm.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        if not any(team["code"] == user_code for team in teams_cache):
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
    try:
        points = float(update.message.text.strip())
        context.user_data["points"] = points
        user_code = context.user_data["user_code"]
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        if current_score < points:
            await update.message.reply_text("Điểm hiện tại không đủ để trừ. Vui lòng nhập số điểm nhỏ hơn.")
            return ENTER_DEDUCT_POINTS
        await update.message.reply_text(
            "Vui lòng nhập lý do trừ điểm:"
        )
        return ENTER_REASON_DEDUCT
    except ValueError:
        await update.message.reply_text("Vui lòng nhập một số hợp lệ (ví dụ: 10 hoặc 10.5).")
        return ENTER_DEDUCT_POINTS

async def enter_reason_deduct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reason = update.message.text.strip()
    user_code = context.user_data["user_code"]
    points = context.user_data["points"]
    
    user_response = supabase.table("users").select("score").eq("code", user_code).execute()
    current_score = user_response.data[0]["score"]
    new_score = current_score - points
    
    supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
    chapter_id = context.user_data.get("chapter_id")
    admin_code = "admin123"
    supabase.table("point_deduct_history").insert({
        "user_code": user_code,
        "points_deducted": points,
        "admin_code": admin_code,
        "chapter": chapter_id,
        "reason": reason
    }).execute()
    
    # Refresh cache after updating score
    refresh_cache()
    
    await update.message.reply_text(
        f"Đã trừ {points} điểm cho đội {user_code}.\nLý do: {reason}",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Đã hủy quá trình.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END


async def lockchapter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not chapters_cache:
        await update.message.reply_text("Không có chapter nào trong danh sách.")
        return ConversationHandler.END
    keyboard = [[f"{chapter['name']} (ID: {chapter['id']})"] for chapter in chapters_cache]
    keyboard.append(["Hủy"])
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Vui lòng chọn trạm để khóa:", reply_markup=reply_markup)
    return SELECT_CHAPTER_TO_LOCK

async def select_chapter_to_lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình khóa chapter.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    try:
        chapter_id = int(selected_text.split("(ID: ")[1].rstrip(")"))
        chapter = next((c for c in chapters_cache if c["id"] == chapter_id), None)
        if not chapter:
            await update.message.reply_text("Trạm không hợp lệ. Vui lòng thử lại.")
            return SELECT_CHAPTER_TO_LOCK
        supabase.table("answers").update({"is_lock": True, "lock_at": "NOW()"}).eq("chapter", chapter_id).execute()

        chapter_ranking_response = supabase.table("chapter_rankings").select("code").eq("chapter", chapter_id).execute()
        # Log the number of teams in the chapter ranking
        logger.info(f"Number of teams in chapter {chapter_id} ranking: {len(chapter_ranking_response.data)}")
        if len(chapter_ranking_response.data) > 0:
            # Get all teams
            all_teams_response = supabase.table("users").select("code").execute()
            all_teams = [team["code"] for team in all_teams_response.data]
            
            # Get teams that are in the chapter ranking
            teams_in_ranking = [team["code"] for team in chapter_ranking_response.data]
            
            # Find teams not in the chapter ranking
            teams_not_in_ranking = [team for team in all_teams if team not in teams_in_ranking]
            
            logger.info(f"Teams not in chapter {chapter_id} ranking: {teams_not_in_ranking}")
            
            # Add 8 points to teams not in the chapter ranking
            for team_code in teams_not_in_ranking:
                # Get current score
                user_response = supabase.table("users").select("score").eq("code", team_code).execute()
                current_score = user_response.data[0]["score"] if user_response.data else 0
                
                if isinstance(current_score, (int, float)):
                    current_score = float(current_score)
                else:
                    current_score = 0.0
                
                # Update score by adding 8 points
                supabase.table("users").update({"score": current_score + 8}).eq("code", team_code).execute()
                
                # Log each team's score update
                logger.info(f"Added 8 points to team {team_code} (not in ranking), new score: {current_score + 8}")
            
            if teams_not_in_ranking:
                logger.info(f"Added 8 points to {len(teams_not_in_ranking)} teams not in chapter {chapter_id} ranking")
            else:
                logger.info(f"All teams are in chapter {chapter_id} ranking, no points added")
                
        else:
            logger.info(f"No teams found in chapter {chapter_id}")
            teams_response = supabase.table("users").select("code").execute()
            if teams_response.data:
                for team in teams_response.data:
                    # Update score by adding 8 points to each team
                    # Get current score
                    user_response = supabase.table("users").select("score").eq("code", team["code"]).execute()
                    current_score = user_response.data[0]["score"] if user_response.data else 0
                    if isinstance(current_score, (int, float)):
                        current_score = float(current_score)
                    else:
                        current_score = 0.0
                    # Update score by adding 8 points
                    supabase.table("users").update({"score": current_score + 8}).eq("code", team["code"]).execute()
                    # Log each team's score update
                    logger.info(f"Added 8 points to team {team['code']}, new score: {current_score + 8}")
                # Log the action
                logger.info(f"Added 8 points to all teams after locking chapter {chapter_id}")
            else:
                logger.warning(f"No teams found when trying to add points after locking chapter {chapter_id}")

        await update.message.reply_text(f"Đã khóa trạm {chapter['name']} thành công.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
    except (IndexError, ValueError):
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_CHAPTER_TO_LOCK

async def tcn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start TCN ranking process"""
    if not chapters_cache:
        await update.message.reply_text("Không có chapter nào trong danh sách.")
        return ConversationHandler.END
    
    keyboard = [[f"{chapter['name']} (ID: {chapter['id']})"] for chapter in chapters_cache]
    keyboard.append(["Hủy"])
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Vui lòng chọn chapter để xếp hạng TCN:", reply_markup=reply_markup)
    return SELECT_TCN_CHAPTER

async def select_tcn_chapter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình xếp hạng TCN.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        chapter_id = int(selected_text.split("(ID: ")[1].rstrip(")"))
        chapter = next((c for c in chapters_cache if c["id"] == chapter_id), None)
        if not chapter:
            await update.message.reply_text("Chapter không hợp lệ. Vui lòng thử lại.")
            return SELECT_TCN_CHAPTER
        
        context.user_data["tcn_chapter_id"] = chapter_id
        
        if not teams_cache:
            await update.message.reply_text("Không có đội nào trong chapter này.")
            return ConversationHandler.END
            
        keyboard = [[f"{team['name']} (Code: {team['code']})"] for team in teams_cache]
        keyboard.append(["Hủy"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Vui lòng chọn đội đứng nhất:", reply_markup=reply_markup)
        return SELECT_FIRST_TEAM
    except (IndexError, ValueError):
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_TCN_CHAPTER

async def select_first_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình xếp hạng TCN.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        if not any(team["code"] == user_code for team in teams_cache):
            await update.message.reply_text("Mã đội không hợp lệ. Vui lòng thử lại.")
            return SELECT_FIRST_TEAM
            
        context.user_data["first_team"] = user_code
        
        # Add 10 points to first team
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        new_score = current_score + 10
        
        supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
        supabase.table("point_history").insert({
            "user_code": user_code,
            "points_added": 10,
            "admin_code": "admin123",
            "chapter": context.user_data["tcn_chapter_id"],
            "reason": "Nhất tcn"
        }).execute()
        
        # Continue with second team selection
        keyboard = [[f"{team['name']} (Code: {team['code']})"] for team in teams_cache if team["code"] != user_code]
        keyboard.append(["Hủy"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Vui lòng chọn đội đứng nhì:", reply_markup=reply_markup)
        return SELECT_SECOND_TEAM
    except IndexError:
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_FIRST_TEAM

async def select_second_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình xếp hạng TCN.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        if not any(team["code"] == user_code for team in teams_cache) or user_code == context.user_data["first_team"]:
            await update.message.reply_text("Mã đội không hợp lệ hoặc đã được chọn. Vui lòng thử lại.")
            return SELECT_SECOND_TEAM
            
        context.user_data["second_team"] = user_code
        
        # Add 8 points to second team
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        new_score = current_score + 8
        
        supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
        supabase.table("point_history").insert({
            "user_code": user_code,
            "points_added": 8,
            "admin_code": "admin123",
            "chapter": context.user_data["tcn_chapter_id"],
            "reason": "Nhì tcn"
        }).execute()
        
        # Continue with third team selection
        keyboard = [[f"{team['name']} (Code: {team['code']})"] for team in teams_cache 
                   if team["code"] not in [context.user_data["first_team"], user_code]]
        keyboard.append(["Hủy"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Vui lòng chọn đội đứng ba:", reply_markup=reply_markup)
        return SELECT_THIRD_TEAM
    except IndexError:
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_SECOND_TEAM

async def select_third_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình xếp hạng TCN.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        if not any(team["code"] == user_code for team in teams_cache) or user_code in [context.user_data["first_team"], context.user_data["second_team"]]:
            await update.message.reply_text("Mã đội không hợp lệ hoặc đã được chọn. Vui lòng thử lại.")
            return SELECT_THIRD_TEAM
            
        context.user_data["third_team"] = user_code
        
        # Add 7 points to third team
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        new_score = current_score + 7
        
        supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
        supabase.table("point_history").insert({
            "user_code": user_code,
            "points_added": 7,
            "admin_code": "admin123",
            "chapter": context.user_data["tcn_chapter_id"],
            "reason": "Ba tcn"
        }).execute()
        
        # Continue with fourth team selection
        keyboard = [[f"{team['name']} (Code: {team['code']})"] for team in teams_cache 
                   if team["code"] not in [context.user_data["first_team"], context.user_data["second_team"], user_code]]
        keyboard.append(["Hủy"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Vui lòng chọn đội đứng tư:", reply_markup=reply_markup)
        return SELECT_FOURTH_TEAM
    except IndexError:
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_THIRD_TEAM

async def select_fourth_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình xếp hạng TCN.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        if not any(team["code"] == user_code for team in teams_cache) or user_code in [context.user_data["first_team"], context.user_data["second_team"], context.user_data["third_team"]]:
            await update.message.reply_text("Mã đội không hợp lệ hoặc đã được chọn. Vui lòng thử lại.")
            return SELECT_FOURTH_TEAM
            
        # Add 6 points to fourth team
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        new_score = current_score + 6
        
        supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
        supabase.table("point_history").insert({
            "user_code": user_code,
            "points_added": 6,
            "admin_code": "admin123",
            "chapter": context.user_data["tcn_chapter_id"],
            "reason": "Tư tcn"
        }).execute()
        
        # Add 4 points to all other teams
        all_teams = [team["code"] for team in teams_cache]
        selected_teams = [context.user_data["first_team"], context.user_data["second_team"], 
                         context.user_data["third_team"], user_code]
        other_teams = [team_code for team_code in all_teams if team_code not in selected_teams]
        
        for team_code in other_teams:
            user_response = supabase.table("users").select("score").eq("code", team_code).execute()
            current_score = user_response.data[0]["score"]
            if isinstance(current_score, (int, float)):
                current_score = float(current_score)
            else:
                current_score = 0.0
            new_score = current_score + 4
            
            supabase.table("users").update({"score": new_score}).eq("code", team_code).execute()
            supabase.table("point_history").insert({
                "user_code": team_code,
                "points_added": 4,
                "admin_code": "admin123",
                "chapter": context.user_data["tcn_chapter_id"],
                "reason": "Không có kết quả tcn"
            }).execute()
        
        # Refresh cache after updating scores
        refresh_cache()
        
        await update.message.reply_text(
            "Đã hoàn thành xếp hạng TCN và cập nhật điểm cho tất cả các đội.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END
    except IndexError:
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_FOURTH_TEAM

async def tin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start TIN ranking process"""
    if not chapters_cache:
        await update.message.reply_text("Không có chapter nào trong danh sách.")
        return ConversationHandler.END
    
    keyboard = [[f"{chapter['name']} (ID: {chapter['id']})"] for chapter in chapters_cache]
    keyboard.append(["Hủy"])
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Vui lòng chọn chapter để xếp hạng TIN:", reply_markup=reply_markup)
    return SELECT_TIN_CHAPTER

async def select_tin_chapter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình xếp hạng TIN.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        chapter_id = int(selected_text.split("(ID: ")[1].rstrip(")"))
        chapter = next((c for c in chapters_cache if c["id"] == chapter_id), None)
        if not chapter:
            await update.message.reply_text("Chapter không hợp lệ. Vui lòng thử lại.")
            return SELECT_TIN_CHAPTER
        
        context.user_data["tin_chapter_id"] = chapter_id
        
        if not teams_cache:
            await update.message.reply_text("Không có đội nào trong chapter này.")
            return ConversationHandler.END
            
        keyboard = [[f"{team['name']} (Code: {team['code']})"] for team in teams_cache]
        keyboard.append(["Hủy"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Vui lòng chọn đội đứng nhất:", reply_markup=reply_markup)
        return SELECT_TIN_FIRST_TEAM
    except (IndexError, ValueError):
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_TIN_CHAPTER

async def select_tin_first_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình xếp hạng TIN.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        if not any(team["code"] == user_code for team in teams_cache):
            await update.message.reply_text("Mã đội không hợp lệ. Vui lòng thử lại.")
            return SELECT_TIN_FIRST_TEAM
            
        context.user_data["tin_first_team"] = user_code
        
        # Add 5 points to first team
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        new_score = current_score + 5
        
        supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
        supabase.table("point_history").insert({
            "user_code": user_code,
            "points_added": 5,
            "admin_code": "admin123",
            "chapter": context.user_data["tin_chapter_id"],
            "reason": "Nhất tin"
        }).execute()
        
        # Continue with second team selection
        keyboard = [[f"{team['name']} (Code: {team['code']})"] for team in teams_cache if team["code"] != user_code]
        keyboard.append(["Hủy"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Vui lòng chọn đội đứng nhì:", reply_markup=reply_markup)
        return SELECT_TIN_SECOND_TEAM
    except IndexError:
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_TIN_FIRST_TEAM

async def select_tin_second_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình xếp hạng TIN.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        if not any(team["code"] == user_code for team in teams_cache) or user_code == context.user_data["tin_first_team"]:
            await update.message.reply_text("Mã đội không hợp lệ hoặc đã được chọn. Vui lòng thử lại.")
            return SELECT_TIN_SECOND_TEAM
            
        context.user_data["tin_second_team"] = user_code
        
        # Add 4 points to second team
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        new_score = current_score + 4
        
        supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
        supabase.table("point_history").insert({
            "user_code": user_code,
            "points_added": 4,
            "admin_code": "admin123",
            "chapter": context.user_data["tin_chapter_id"],
            "reason": "Nhì tin"
        }).execute()
        
        # Continue with third team selection
        keyboard = [[f"{team['name']} (Code: {team['code']})"] for team in teams_cache 
                   if team["code"] not in [context.user_data["tin_first_team"], user_code]]
        keyboard.append(["Hủy"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Vui lòng chọn đội đứng ba:", reply_markup=reply_markup)
        return SELECT_TIN_THIRD_TEAM
    except IndexError:
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_TIN_SECOND_TEAM

async def select_tin_third_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình xếp hạng TIN.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        if not any(team["code"] == user_code for team in teams_cache) or user_code in [context.user_data["tin_first_team"], context.user_data["tin_second_team"]]:
            await update.message.reply_text("Mã đội không hợp lệ hoặc đã được chọn. Vui lòng thử lại.")
            return SELECT_TIN_THIRD_TEAM
            
        context.user_data["tin_third_team"] = user_code
        
        # Add 3 points to third team
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        new_score = current_score + 3
        
        supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
        supabase.table("point_history").insert({
            "user_code": user_code,
            "points_added": 3,
            "admin_code": "admin123",
            "chapter": context.user_data["tin_chapter_id"],
            "reason": "Ba tin"
        }).execute()
        
        # Continue with fourth team selection
        keyboard = [[f"{team['name']} (Code: {team['code']})"] for team in teams_cache 
                   if team["code"] not in [context.user_data["tin_first_team"], context.user_data["tin_second_team"], user_code]]
        keyboard.append(["Hủy"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Vui lòng chọn đội đứng tư:", reply_markup=reply_markup)
        return SELECT_TIN_FOURTH_TEAM
    except IndexError:
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_TIN_THIRD_TEAM

async def select_tin_fourth_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_text = update.message.text.strip()
    if selected_text == "Hủy":
        await update.message.reply_text("Đã hủy quá trình xếp hạng TIN.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    try:
        user_code = selected_text.split("(Code: ")[1].rstrip(")")
        if not any(team["code"] == user_code for team in teams_cache) or user_code in [context.user_data["tin_first_team"], context.user_data["tin_second_team"], context.user_data["tin_third_team"]]:
            await update.message.reply_text("Mã đội không hợp lệ hoặc đã được chọn. Vui lòng thử lại.")
            return SELECT_TIN_FOURTH_TEAM
            
        # Add 2 points to fourth team
        user_response = supabase.table("users").select("score").eq("code", user_code).execute()
        current_score = user_response.data[0]["score"]
        if isinstance(current_score, (int, float)):
            current_score = float(current_score)
        else:
            current_score = 0.0
        new_score = current_score + 2
        
        supabase.table("users").update({"score": new_score}).eq("code", user_code).execute()
        supabase.table("point_history").insert({
            "user_code": user_code,
            "points_added": 2,
            "admin_code": "admin123",
            "chapter": context.user_data["tin_chapter_id"],
            "reason": "Tư tin"
        }).execute()
        
        # Add 1 point to all other teams
        all_teams = [team["code"] for team in teams_cache]
        selected_teams = [context.user_data["tin_first_team"], context.user_data["tin_second_team"], 
                         context.user_data["tin_third_team"], user_code]
        other_teams = [team_code for team_code in all_teams if team_code not in selected_teams]
        
        for team_code in other_teams:
            user_response = supabase.table("users").select("score").eq("code", team_code).execute()
            current_score = user_response.data[0]["score"]
            if isinstance(current_score, (int, float)):
                current_score = float(current_score)
            else:
                current_score = 0.0
            new_score = current_score + 1
            
            supabase.table("users").update({"score": new_score}).eq("code", team_code).execute()
            supabase.table("point_history").insert({
                "user_code": team_code,
                "points_added": 1,
                "admin_code": "admin123",
                "chapter": context.user_data["tin_chapter_id"],
                "reason": "Không có kết quả tin"
            }).execute()
        
        # Refresh cache after updating scores
        refresh_cache()
        
        await update.message.reply_text(
            "Đã hoàn thành xếp hạng TIN và cập nhật điểm cho tất cả các đội.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END
    except IndexError:
        await update.message.reply_text("Lựa chọn không hợp lệ. Vui lòng chọn lại từ danh sách.")
        return SELECT_TIN_FOURTH_TEAM

def main() -> None:
    """Khởi động bot."""
    logger.info("Starting the bot...")
    application = Application.builder().token(TOKEN).build()

    # Thêm ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start), 
            CommandHandler("addpoints", addpoints),
            CommandHandler("deductpoints", deductpoints),
            CommandHandler("lockchapter", lockchapter),
            CommandHandler("tcn", tcn),
            CommandHandler("tin", tin),
        ],
        states={
            ENTER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
            SELECT_CHAPTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_chapter)],
            SELECT_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_team)],
            ENTER_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_points)],
            ENTER_REASON_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_reason_add)],
            SELECT_DEDUCT_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_deduct_team)],
            ENTER_DEDUCT_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_deduct_points)],
            ENTER_REASON_DEDUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_reason_deduct)],
            SELECT_CHAPTER_TO_LOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_chapter_to_lock)],
            SELECT_TCN_CHAPTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_tcn_chapter)],
            SELECT_FIRST_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_first_team)],
            SELECT_SECOND_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_second_team)],
            SELECT_THIRD_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_third_team)],
            SELECT_FOURTH_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_fourth_team)],
            SELECT_TIN_CHAPTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_tin_chapter)],
            SELECT_TIN_FIRST_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_tin_first_team)],
            SELECT_TIN_SECOND_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_tin_second_team)],
            SELECT_TIN_THIRD_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_tin_third_team)],
            SELECT_TIN_FOURTH_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_tin_fourth_team)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Thêm các handler
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("ranking", ranking))
    application.add_handler(CommandHandler("help", help))

    # Chạy bot
    application.run_polling()

if __name__ == '__main__':
    main()