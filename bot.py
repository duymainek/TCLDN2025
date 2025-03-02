import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import ReplyKeyboardMarkup
from supabase import create_client, Client

logger = logging.getLogger(__name__)
logger.info(f"Supabase version: {supabase.__version__}")

# Cấu hình logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Thông tin Supabase (lấy từ biến môi trường)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ifkusnuoxzllhniwkywh.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlma3VzbnVveHpsbGhuaXdreXdoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNjE0MTY1MywiZXhwIjoyMDUxNzE3NjUzfQ.PcLgon96CK6xB8Mf82FRRCZ_b7XvidAQlDD4cQ_wFKM")
supabase: Client = create_client("https://ifkusnuoxzllhniwkywh.supabase.co", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlma3VzbnVveHpsbGhuaXdreXdoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNjE0MTY1MywiZXhwIjoyMDUxNzE3NjUzfQ.PcLgon96CK6xB8Mf82FRRCZ_b7XvidAQlDD4cQ_wFKM")

# Token bot Telegram (lấy từ biến môi trường)
TOKEN = os.getenv("TOKEN", "7615236413:AAE_tfOvqkUGNOqf1XyT5SleHUrG0POl_Lo")

user_codes = {}
# Hàm xử lý lệnh /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    logger.info(f"User {user_id} started the bot")
    reply_keyboard = [['/ranking']]
    await update.message.reply_text(
        "Xin chào! Tôi là chatbot của bạn. Nhấn /ranking để xem thứ hạng!",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    await update.message.reply_text("Vui lòng nhập mã code của bạn:")

# Hàm xử lý lệnh /ranking
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    logger.info(f"User {user_id} requested ranking")
    if user_id not in user_codes or not user_codes[user_id]:
        logger.warning(f"User {user_id} has not provided a code yet")
        await update.message.reply_text("Bạn chưa nhập mã code. Vui lòng nhập mã code trước!")
        return

    code = user_codes[user_id]
    logger.info(f"Querying ranking for code: {code}")
    response = supabase.table('users').select('*').eq('code', code).execute()
    if response.data:
        score = response.data[0].get('score', 'Không xác định')
        logger.info(f"Ranking found for {code}: {score}")
        await update.message.reply_text(f"Thứ hạng của bạn là: {score}")
    else:
        logger.warning(f"No ranking found for code: {code}")
        await update.message.reply_text("Không tìm thấy thứ hạng cho mã code này!")

# Hàm xử lý khi user nhập mã code hoặc câu trả lời
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    text = update.message.text
    logger.info(f"Received message from user {user_id}: {text}")

    if user_id not in user_codes or not user_codes[user_id]:
        logger.info(f"Checking code: {text}")
        response = supabase.table('users').select('*').eq('code', text).execute()
        if response.data:
            user_codes[user_id] = text
            name = response.data[0].get('name', 'Không xác định')
            logger.info(f"Valid code {text} for user {user_id}, name: {name}")
            await update.message.reply_text(f"Chào mừng đơn vị {name}.")
            await update.message.reply_text("Tôi đang luôn sẵn sàng lắng nghe đáp án của bạn.")
        else:
            logger.warning(f"Invalid code: {text}")
            await update.message.reply_text("Mã code không tồn tại. Vui lòng nhập lại!")
        return

    code = user_codes[user_id]
    logger.info(f"Checking answer '{text}' for code: {code}")
    response = supabase.table('answers').select('*').eq('answer', text).execute()
    if response.data:
        logger.info(f"Correct answer '{text}' from user {user_id}")
        await update.message.reply_text("Chúc mừng! Đáp án của bạn đúng.")
    else:
        logger.info(f"Incorrect or no response for answer '{text}' from user {user_id}")

def main() -> None:
    logger.info("Starting the bot...")
    application = Application.builder().token("7615236413:AAE_tfOvqkUGNOqf1XyT5SleHUrG0POl_Lo").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ranking", ranking))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()