import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from supabase import create_client, Client
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
SUPABASE_URL = "https://ifkusnuoxzllhniwkywh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlma3VzbnVveHpsbGhuaXdreXdoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNjE0MTY1MywiZXhwIjoyMDUxNzE3NjUzfQ.PcLgon96CK6xB8Mf82FRRCZ_b7XvidAQlDD4cQ_wFKM"
TOKEN = os.getenv("TOKEN", "7068524025:AAENh2Ns6RZ33tTKLwRLlwMNxZUmd-x9Pi8")
ANSWER_LIMIT = 3
WAIT_TIME_SECONDS = 30

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# State management
user_codes: Dict[int, str] = {}  # Store user_id -> code mapping
user_blocked: Dict[int, bool] = {}  # Store user_id -> blocked status
_config_cache: Dict[int, int] = {}

def load_config_cache() -> None:
    """Load config data from Supabase into cache."""
    global _config_cache
    try:
        response = supabase.table('config').select('rank_position, score_coefficient').execute()
        _config_cache = {row['rank_position']: row['score_coefficient'] for row in response.data}
        logger.info(f"Loaded config cache: {_config_cache}")
    except Exception as e:
        logger.error(f"Failed to load config cache: {e}")
        _config_cache = {}  # Default to empty cache if loading fails

def get_score_coefficient(rank: int) -> int:
    """Get the score coefficient for a given rank from cache, with fallback to database if not in cache."""
    if not _config_cache:
        load_config_cache()  # Load cache if not already loaded
    
    if rank in _config_cache:
        return _config_cache[rank]
    
    # Fallback: query database if rank not in cache (should not happen with current data)
    try:
        response = supabase.table('config').select('score_coefficient').eq('rank_position', rank).execute()
        if response.data:
            _config_cache[rank] = response.data[0]['score_coefficient']
            return _config_cache[rank]
        return 10  # Default value if not found (matches your original code)
    except Exception as e:
        logger.error(f"Error fetching score coefficient for rank {rank}: {e}")
        return 10  # Default value on error

class BotState:
    """Manage bot state for users."""
    @staticmethod
    def is_blocked(user_id: int) -> bool:
        return user_blocked.get(user_id, False)

    @staticmethod
    def set_blocked(user_id: int, blocked: bool) -> None:
        user_blocked[user_id] = blocked

    @staticmethod
    def get_code(user_id: int) -> Optional[str]:
        return user_codes.get(user_id)

    @staticmethod
    def set_code(user_id: int, code: str) -> None:
        user_codes[user_id] = code

def check_answer_limit(code: str) -> Tuple[bool, str]:
    """Check if the user can submit another answer using Supabase function."""
    logger.info(f"Checking answer limit for code: {code}")
    response = supabase.rpc('check_user_answer_limit', {'p_code': code}).execute()
    logger.info(f"Answer limit check response: {response.data}")
    if response.data:
        return response.data[0]['can_answer'], response.data[0]['message'] or "", response.data[0]['remain_answer']
    return True, "", 3

def has_user_answered_correctly(code: str, chapter: int) -> bool:
    """Check if the user has answered correctly for a chapter using Supabase function."""
    response = supabase.rpc('has_user_answered_correctly_supabase', {
        'p_code': code,
        'p_chapter': chapter
    }).execute()
    return response.data[0] if response.data else False

def update_user_score(code: str, score: float) -> None:
    """Update the user's total score using Supabase function."""
    try:
        current_score = get_user_total_score(code)
        supabase.table('users').update({'score': current_score + score}).eq('code', code).execute()
    except Exception as e:
        logger.error(f"Failed to update user score for code {code}: {e}")
        raise

def update_msg_history(code: str, msg: str,) -> None:
    """Update message history in Supabase without ranking_chapter."""
    if not code:
        logger.warning("Attempted to update msg_history with null code")
        return

    try:
        supabase.table('msg_history').insert({
            'code': code,
            'msg': msg,
        }).execute()
    except Exception as e:
        logger.error(f"Failed to update msg_history: {e}")
        raise

def get_score_coefficient(rank: int) -> int:
    """Get the score coefficient from the config table."""
    response = supabase.table('config').select('score_coefficient').eq('rank_position', rank).execute()
    return response.data[0]['score_coefficient'] if response.data else 10  # Default to 10

def get_user_total_score(code: str) -> float:
    """Calculate the user's total score from the users table."""
    try:
        user_response = supabase.table('users').select('score').eq('code', code).execute()
        return user_response.data[0]['score'] if user_response.data else 0.0
    except Exception as e:
        logger.error(f"Error calculating user total score: {e}")
        return 0.0

def get_top_team() -> Tuple[Optional[str], float]:
    """Fetch the top team (name and score) from the users table."""
    try:
        users_response = supabase.table('users').select('code, name, score').order('score', desc=True).execute()
        if users_response.data:
            return users_response.data[0]['name'], users_response.data[0]['score']
        return None, 0.0
    except Exception as e:
        logger.error(f"Error getting top team: {e}")
        return None, 0.0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user_id = update.message.from_user.id
    logger.info(f"User {user_id} started the bot")
    await update.message.reply_text(
        "*Chào mừng bạn đến với TRÒ CHƠI LỚN ĐÀ NẴNG 2025\\!* 🎉\n"
        "Tôi là *Giao liên* – người bạn đồng hành bí mật của bạn trong hành trình đầy kịch tính này\\. Tôi sẽ luôn *lắng nghe*, *thầm lặng* truyền tải mọi thông điệp của bạn đến Ban Tổ Chức \\(BTC\\) một cách nhanh nhất\\!\n\n"
        "Bạn có thể ra lệnh cho tôi như một điệp viên thực thụ:\n"
        "*/ranking* – Xem ngay số điểm của bạn và so kè với đội đang *thống lĩnh* bảng xếp hạng\\!\n\n"
        "Bây giờ, hãy nhập *mật mã* mà BTC đã giao phó cho bạn\\. Đó là chìa khóa để tôi nhận diện bạn trong cuộc chiến này\\! Nhanh lên nào, thời gian không chờ đợi ai đâu\\! ⏳",
        parse_mode="MarkdownV2"
    )

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /ranking command to show user and top team scores."""
    user_id = update.message.from_user.id
    logger.info(f"User {user_id} requested ranking")
    
    code = BotState.get_code(user_id)
    if not code:
        await update.message.reply_text(
    "*Ôi không\\!* 😱 *Bạn chưa nhập mật mã\\!* \n"
    "Nhanh tay nhập *mật mã* mà BTC đã giao cho bạn đi nào\\. Không có nó, tôi không thể xác nhận bạn là chiến binh thực thụ trong hành trình này được\\! ⏰",
    parse_mode="MarkdownV2"
)
        return

    user_score = get_user_total_score(code)
    top_team_name, top_team_score = get_top_team()
    
    top_info = f"Đội đang đứng đầu tính đến thời điểm hiện tại: {top_team_name}" if top_team_name else "*Không tìm thấy đội đứng nhất.*"
    await update.message.reply_text(
        f"Điểm của bạn là: {user_score} điểm\n{top_info}",
        parse_mode="MarkdownV2"
    )

def validate_code(user_id: int, text: str) -> Optional[str]:
    """Validate a user code and return the team name if valid."""
    response = supabase.table('users').select('name').eq('code', text).execute()
    if response.data:
        BotState.set_code(user_id, text)
        name = response.data[0].get('name', 'Không xác định')
        logger.info(f"Valid code {text} for user {user_id}, name: {name}")
        return name
    logger.warning(f"Invalid code: {text}")
    return None

def process_answer(code: str, text: str, user_id: int, remain_answer: int) -> Optional[str]:
    """Process an answer submission, updating msg_history for both correct and incorrect answers, and handle ranking for correct answers."""
    logger.info(f"Checking answer '{text.replace(' ', '').lower()}' for code: {code}")
    
    # Kiểm tra đáp án có đúng không (query bảng answers)
    answer_response = supabase.table('answers').select('chapter, is_lock').eq('answer', text.replace(' ', '').lower()).execute()

    # Log the answer response for debugging
    logger.info(f"Answer response: {answer_response.data}")
    # Luôn cập nhật msg_history (dù đúng hay sai)
    is_correct = bool(answer_response.data)  # True nếu tìm thấy trong answers, False nếu không
    
    if is_correct:
        chapter = answer_response.data[0]['chapter'] if answer_response.data else 0  # Mặc định chapter = 0 nếu không tìm thấy
        is_chapter_lock = answer_response.data[0]['is_lock']
        if is_chapter_lock:
            return f"Trạm {chapter} đã được khóa, bạn không thể trả lời được nữa"
        result = supabase.rpc('update_ranking', {
            'p_chapter_id': chapter,
            'p_user_code': code,
            'p_answer_text': text.replace(' ', '').lower()
        }).execute()
        supabase.table('user_answer_tracking').update({'answer_count': 0}).eq('code', code).execute()
        
        if result.data:
            current_rank = result.data[0] if isinstance(result.data, list) else result.data
            score_coeff = get_score_coefficient(current_rank)
            update_user_score(code, score_coeff)
            # Reset answer count for the user after correct answer
            return f"🎉 *Chính xác\\!* Đáp án của bạn hoàn toàn đúng\\! ✅\n\n\\. 🏆 Bạn hiện đang đứng ở *vị trí {current_rank}* trong thử thách mật thư trạm {chapter} \\. Tiếp tục cố gắng nhé\\! 🚀\\."
    else:
        return f"Đáp án *{text}* chưa đúng\\, bạn còn {remain_answer} lần để trả lời" + (f"\\n\\n Vui lòng đợi trong 30s để tiếp tục trả lời" if remain_answer == 0 else "")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming user messages (codes or answers) with blocking mechanism."""
    user_id = update.message.from_user.id
    text = update.message.text
    logger.info(f"Received message from user {user_id}: {text}")

    code = BotState.get_code(user_id)

    update_msg_history(code, text)

    if BotState.is_blocked(user_id):
        await update.message.reply_text(
    "⏳ *Vui lòng chờ giây lát\\.\\.\\.* \n\n"
    "Chúng tôi đang xác minh thông tin của bạn\\. Hãy giữ kết nối và đừng rời đi nhé\\! 🔍", 
    parse_mode="MarkdownV2"
)

        return

    BotState.set_blocked(user_id, True)
    try:
        await update.message.reply_text(
    "⏳ *Vui lòng chờ giây lát\\.\\.\\.* \n\n"
    "Chúng tôi đang xác minh thông tin của bạn\\. Hãy giữ kết nối và đừng rời đi nhé\\! 🔍", 
    parse_mode="MarkdownV2"
)
        if not code:
            name = validate_code(user_id, text)
            if name:
                await update.message.reply_text(f"🎉 *Chào mừng đội chơi {name} đến với hành trình đầy thử thách\\!*\n\n"
    "Hãy sẵn sàng, vì phía trước là những nhiệm vụ cam go đang chờ đón bạn\\. Cùng nhau, chúng ta sẽ chinh phục tất cả\\! 💪", 
    parse_mode="MarkdownV2")

                await update.message.reply_text(
    "*📝 Tôi luôn sẵn sàng lắng nghe đáp án của bạn\\!* 📩\n\n"
    "⚠️ *Lưu ý:* Đừng gửi quá nhiều đáp án liên tục, nếu không bạn có thể bị *tạm khoá* và không thể gửi thêm\\.\n"
    "Điều đó cũng có thể khiến quá trình xử lý đáp án của bạn *chậm hơn* ⏳\\.\n\n"
    "Hãy *bình tĩnh*, suy nghĩ kỹ và gửi đáp án chính xác nhất rồi đợi phản hồi nhé\\! ✅",
    parse_mode="MarkdownV2"
)

            else:
                await update.message.reply_text("*Mật mã này không tồn tại\\. Vui lòng nhập lại hoặc liên hệ BTC nhé*", parse_mode="MarkdownV2")
            BotState.set_blocked(user_id, False)
            return

        # Check answer limit using Supabase function
        can_answer, message, remain_answer = check_answer_limit(code)
        if not can_answer:
            await update.message.reply_text(f"*{message}*", parse_mode="MarkdownV2")
            BotState.set_blocked(user_id, False)
            return

        # Process the answer
        reply = process_answer(code, text, user_id, remain_answer)
        if reply:
            await update.message.reply_text(reply, parse_mode="MarkdownV2")
        BotState.set_blocked(user_id, False)

    except Exception as e:
        logger.error(f"Error processing message from user {user_id}: {e}")
        await update.message.reply_text("⚠️ *Đã xảy ra lỗi\\!* \n\nVui lòng chụp màn hình lại và liên hệ với BTC để được hỗ trợ \\. ⏳",  
    parse_mode="MarkdownV2"
)

        BotState.set_blocked(user_id, False)

def main() -> None:
    """Start the Telegram bot."""
    logger.info("Starting the bot...")
    application = Application.builder().token(TOKEN).build()
    load_config_cache()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ranking", ranking))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()