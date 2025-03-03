import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional, List, Dict

# Cấu hình logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Hằng số
SUPABASE_URL = "https://ifkusnuoxzllhniwkywh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlma3VzbnVveHpsbGhuaXdreXdoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNjE0MTY1MywiZXhwIjoyMDUxNzE3NjUzfQ.PcLgon96CK6xB8Mf82FRRCZ_b7XvidAQlDD4cQ_wFKM"
TOKEN = os.getenv("TOKEN", "7615236413:AAE_tfOvqkUGNOqf1XyT5SleHUrG0POl_Lo")
ANSWER_LIMIT = 3
WAIT_TIME_SECONDS = 30

# Khởi tạo Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Lưu trữ mã code của user và trạng thái chặn
user_codes = {}
user_blocked = {}  # Dictionary để lưu trạng thái chặn của user (user_id: True/False)

def get_user_answer_tracking(code: str) -> dict:
    """Lấy thông tin giới hạn nạp đáp án của user từ Supabase."""
    response = supabase.table('user_answer_tracking').select('*').eq('code', code).execute()
    return response.data[0] if response.data else None

def initialize_answer_tracking(code: str) -> None:
    """Khởi tạo record giới hạn nạp đáp án nếu chưa tồn tại."""
    supabase.table('user_answer_tracking').insert({
        'code': code,
        'answer_count': 0,
        'last_reset_timestamp': datetime.utcnow().isoformat()
    }).execute()

def reset_answer_tracking(code: str) -> None:
    """Reset số lần nạp đáp án sau khi hết thời gian chờ."""
    supabase.table('user_answer_tracking').update({
        'answer_count': 0,
        'last_reset_timestamp': datetime.utcnow().isoformat()
    }).eq('code', code).execute()

def increment_answer_count(code: str) -> None:
    """Tăng số lần nạp đáp án."""
    current_count_response = supabase.table('user_answer_tracking').select('answer_count').eq('code', code).execute()
    if current_count_response.data:
        current_count = current_count_response.data[0]['answer_count']
        supabase.table('user_answer_tracking').update({
            'answer_count': current_count + 1
        }).eq('code', code).execute()

def check_answer_limit(code: str) -> Tuple[bool, str]:
    """Kiểm tra xem user có thể nạp đáp án hay không."""
    tracking_data = get_user_answer_tracking(code)
    
    if not tracking_data:
        initialize_answer_tracking(code)
        return True, ""

    answer_count = tracking_data['answer_count']
    # Chuẩn hóa chuỗi last_reset_timestamp, thêm múi giờ UTC nếu cần
    last_reset_str = tracking_data['last_reset_timestamp']
    if 'Z' not in last_reset_str and '+' not in last_reset_str:
        last_reset_str += '+00:00'  # Thêm múi giờ UTC nếu thiếu
    last_reset = datetime.fromisoformat(last_reset_str.replace('Z', '+00:00'))
    
    # Sử dụng datetime.now(timezone.utc) để tạo current_time offset-aware
    current_time = datetime.now(timezone.utc)

    if answer_count >= ANSWER_LIMIT:
        if current_time >= last_reset + timedelta(seconds=WAIT_TIME_SECONDS):
            reset_answer_tracking(code)
            return True, ""
        time_left = (last_reset + timedelta(seconds=WAIT_TIME_SECONDS) - current_time).total_seconds()
        return False, f"Vui lòng đợi {int(time_left)} giây trước khi nạp đáp án tiếp theo\\."

    return True, ""

def update_msg_history(code: str, msg: str, is_correct: bool, chapter: int, block: bool, ranking_chapter: Optional[int] = None) -> None:
    """Cập nhật lịch sử tin nhắn vào Supabase với ranking_chapter."""
    try:
        supabase.table('msg_history').insert({
            'code': code,
            'msg': msg,
            'is_correct': is_correct,
            'chapter': chapter,
            'block': block,
            'ranking_chapter': ranking_chapter  # Thêm ranking_chapter
        }).execute()
        # Cập nhật tổng điểm của user trong bảng users
        update_user_score(code)
    except Exception as e:
        logger.error(f"Failed to update msg_history: {e}")

def update_chapter_rankings(chapter: int, code: str, ranking_chapter: int) -> None:
    """Chèn vị trí xếp hạng mới vào bảng chapter_rankings (không cập nhật)."""
    try:
        # Kiểm tra xem đội này đã có bản ghi trong chapter_rankings chưa
        existing_record = supabase.table('chapter_rankings').select('*').eq('chapter', chapter).eq('code', code).execute()
        if existing_record.data:
            logger.warning(f"Team {code} has already been ranked for chapter {chapter}")
            return

        # Chèn mới vào bảng chapter_rankings (không cập nhật)
        supabase.table('chapter_rankings').insert({
            'chapter': chapter,
            'code': code,
            'ranking_chapter': ranking_chapter  # Sử dụng ranking_chapter
        }).execute()
        # Cập nhật tổng điểm của user trong bảng users
        update_user_score(code)
    except Exception as e:
        logger.error(f"Failed to update chapter_rankings: {e}")

def has_user_answered_correctly(code: str, chapter: int) -> bool:
    """Kiểm tra xem user đã trả lời đúng chapter này chưa."""
    response = supabase.table('msg_history').select('is_correct').eq('code', code).eq('chapter', chapter).eq('is_correct', True).execute()
    return bool(response.data)

def update_user_score(code: str) -> None:
    """Cập nhật tổng điểm của user trong bảng users dựa trên tất cả ranking_chapter."""
    try:
        # Tính tổng điểm từ tất cả ranking_chapter trong chapter_rankings
        total_score = get_user_total_score(code)
        # Cập nhật cột score trong bảng users
        supabase.table('users').update({'score': total_score}).eq('code', code).execute()
    except Exception as e:
        logger.error(f"Failed to update user score for code {code}: {e}")

def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /start."""
    user_id = update.message.from_user.id
    logger.info(f"User {user_id} started the bot")
    update.message.reply_text("Xin chào Tôi là chatbot của bạn\\. Vui lòng nhập mã code của bạn\\.", parse_mode="MarkdownV2")

def get_score_coefficient(rank: int) -> int:
    """Lấy hệ số điểm từ bảng config dựa trên vị trí xếp hạng."""
    response = supabase.table('config').select('score_coefficient').eq('rank_position', rank).execute()
    return response.data[0]['score_coefficient'] if response.data else 10  # Mặc định 10 nếu không tìm thấy

def get_user_total_score(code: str) -> float:
    """Tính tổng điểm của user dựa trên vị trí xếp hạng trong bảng chapter_rankings."""
    try:
        # Lấy tất cả vị trí xếp hạng của user trong các chapter
        rankings_response = supabase.table('chapter_rankings').select('ranking_chapter').eq('code', code).execute()
        
        if not rankings_response.data:
            return 0.0

        total_score = 0.0
        for record in rankings_response.data:
            rank = record['ranking_chapter']
            total_score += get_score_coefficient(rank)

        return total_score
    except Exception as e:
        logger.error(f"Error calculating user total score: {e}")
        return 0.0

def get_top_team() -> Tuple[Optional[str], float]:
    """Lấy thông tin đội đứng nhất (tên đội và tổng điểm)."""
    try:
        # Lấy tất cả user và tổng điểm của họ
        users_response = supabase.table('users').select('code, name, score').order('score', desc=True).execute()
        top_team_name = users_response.data[0]['name'] if users_response.data else None
        top_team_score = users_response.data[0]['score'] if users_response.data else 0.0

        return top_team_name, top_team_score
    except Exception as e:
        logger.error(f"Error getting top team: {e}")
        return None, 0.0

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /ranking, hiển thị tổng điểm của user và đội đứng nhất."""
    user_id = update.message.from_user.id
    logger.info(f"User {user_id} requested ranking")
    
    if user_id not in user_codes or not user_codes[user_id]:
        logger.warning(f"User {user_id} has not provided a code yet")
        await update.message.reply_text("*Bạn chưa nhập mã code\\. Vui lòng nhập mã code trước*", parse_mode="MarkdownV2")
        return

    code = user_codes[user_id]
    
    # Lấy tổng điểm của user hiện tại
    user_score = get_user_total_score(code)
    logger.info(f"Ranking for code {code}: {user_score} points")
    
    # Lấy thông tin đội đứng nhất
    top_team_name, top_team_score = get_top_team()
    
    if top_team_name:
        top_info = f"Đội đứng nhất: *{top_team_name}* với *{top_team_score}* điểm"
    else:
        top_info = "*Không tìm thấy đội đứng nhất.*"

    # Gửi thông báo
    await update.message.reply_text(
        f"Điểm của bạn là: {user_score} điểm\n{top_info}"
    )

def validate_code(user_id: int, text: str) -> Optional[str]:
    """Xác thực mã code và trả về tên đơn vị nếu hợp lệ."""
    response = supabase.table('users').select('name').eq('code', text).execute()
    if response.data:
        user_codes[user_id] = text
        name = response.data[0].get('name', 'Không xác định')
        logger.info(f"Valid code {text} for user {user_id}, name: {name}")
        return name
    logger.warning(f"Invalid code: {text}")
    return None

def process_answer(code: str, text: str, user_id: int) -> Optional[str]:
    """Xử lý đáp án của user."""
    logger.info(f"Checking answer '{text}' for code: {code}")
    response = supabase.table('answers').select('chapter').eq('answer', text).execute()
    
    increment_answer_count(code)
    
    if response.data:
        chapter = response.data[0].get('chapter', 0)
        # Kiểm tra xem team đã trả lời đúng chapter này chưa
        if has_user_answered_correctly(code, chapter):
            return f"Đáp án *{text}* đã được ghi nhận trên hệ thống trước đó\\, vui lòng không nhập lại đáp án\\."

        logger.info(f"Correct answer '{text}' from user {user_id}")
        
        # Lấy danh sách các bản ghi đúng trong chapter này để xác định ranking_chapter
        correct_answers = supabase.table('msg_history').select('code').eq('chapter', chapter).eq('is_correct', True).execute()
        current_rank = len(correct_answers.data) + 1  # Vị trí mới (1-based)
        current_rank = min(current_rank, 8)  # Giới hạn tối đa là 8 (theo config)

        # Tính điểm dựa trên ranking_chapter
        score = get_score_coefficient(current_rank)

        # Chèn vào msg_history với ranking_chapter
        update_msg_history(code, text, True, chapter, False, current_rank)
        
        # Chèn vào chapter_rankings với ranking_chapter
        update_chapter_rankings(chapter, code, current_rank)
        return f"Chúc mừng Đáp án của bạn đúng\\. Bạn đứng vị trí *{current_rank}* ở mật thư này\\."
    
    logger.info(f"Incorrect or no response for answer '{text}' from user {user_id}")
    update_msg_history(code, text, False, 0, False, None)  # ranking_chapter là None cho đáp án sai
    return f"Đáp án *{text}* chưa đúng\\, vui lòng thử lại"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý tin nhắn từ user (mã code hoặc đáp án) và chặn tin nhắn sau khi xử lý."""
    user_id = update.message.from_user.id
    text = update.message.text
    logger.info(f"Received message from user {user_id}: {text}")

    # Kiểm tra trạng thái chặn của user
    if user_id in user_blocked and user_blocked[user_id]:
        await update.message.reply_text("*Vui lòng đợi\\, chúng tôi đã kiểm tra*", parse_mode="MarkdownV2")
        return

    # Đặt trạng thái chặn cho user
    user_blocked[user_id] = True

    try:
        # Gửi thông báo ngay lập tức
        await update.message.reply_text("*Vui lòng đợi\\, chúng tôi đã kiểm tra*", parse_mode="MarkdownV2")

        # Kiểm tra và xác thực mã code
        if user_id not in user_codes or not user_codes[user_id]:
            name = validate_code(user_id, text)
            if name:
                await update.message.reply_text(f"Chào mừng đơn vị *{name}*\\.", parse_mode="MarkdownV2")
                await update.message.reply_text("*Tôi đang luôn sẵn sàng lắng nghe đáp án của bạn\\.*", parse_mode="MarkdownV2")
            else:
                await update.message.reply_text("*Mã code không tồn tại\\. Vui lòng nhập lại*", parse_mode="MarkdownV2")
            user_blocked[user_id] = False  # Mở chặn sau khi xử lý
            return

        code = user_codes[user_id]
        # Kiểm tra giới hạn nạp đáp án
        can_answer, message = check_answer_limit(code)
        if not can_answer:
            await update.message.reply_text(f"*Vui lòng đợi {int(float(message.split()[2]))} giây trước khi nạp đáp án tiếp theo\\.*", parse_mode="MarkdownV2")
            update_msg_history(code, text, None, None, True, None)
            user_blocked[user_id] = False  # Mở chặn sau khi xử lý
            return

        # Xử lý đáp án
        reply = process_answer(code, text, user_id)
        if reply:
            await update.message.reply_text(reply, parse_mode="MarkdownV2")
        user_blocked[user_id] = False  # Mở chặn sau khi xử lý

    except Exception as e:
        logger.error(f"Error processing message from user {user_id}: {e}")
        await update.message.reply_text("*Đã xảy ra lỗi\\, vui lòng thử lại sau\\.*", parse_mode="MarkdownV2")
        user_blocked[user_id] = False  # Mở chặn trong trường hợp lỗi

def main() -> None:
    """Khởi động bot."""
    logger.info("Starting the bot...")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ranking", ranking))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()