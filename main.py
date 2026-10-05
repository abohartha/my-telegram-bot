import logging
import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# إعداد السجلات (Logging) لمتابعة الأخطاء
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 🔑 ضع توكن البوت الخاص بك هنا (من @BotFather)
TOKEN = "8976478095:AAHylUWqsVT5biaksxdqH1rbt98RyyW-znU"
API_BASE = "https://quran.yousefheiba.com/api"

SURAHS_PER_PAGE = 10


async def fetch_surahs():
    """جلب قائمة السور من الـ API"""
    url = f"{API_BASE}/surahs"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                # قد تكون القائمة داخل مفتاح 'data' أو مباشرة
                return data.get("data", data) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"خطأ في جلب السور: {e}")
    return None


async def fetch_surah_detail(surah_number: int):
    """جلب تفاصيل سورة معينة"""
    url = f"{API_BASE}/surahs/{surah_number}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"خطأ في جلب السورة {surah_number}: {e}")
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البداية /start"""
    welcome_text = (
        "📖 **مرحباً بك في بوت القرآن الكريم**\n\n"
        "يمكنك تصفح جميع سور القرآن الكريم بسهولة عبر الأزرار أدناه.\n"
        "اختر **قائمة السور** للبدء:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📜 قائمة السور", callback_data="surahs_page_0")],
        [InlineKeyboardButton("ℹ️ معلومات عن البوت", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)
    elifيمكنك بناء بوت تليجرام متكامل للقرآن الكريم باستخدام لغة **Python** ومكتبة `python-telegram-bot` (الإصدار 20+) مع استخدام مكتبة `httpx` لإجراء طلبات API بشكل غير متزامن (Async) لضمان السرعة والسلاسة دون حظر البوت عند الضغط العالي.

---

### 1. تثبيت المكتبات المطلوبة

قبل تشغيل الكود، قم بتثبيت حزم بايثون التالية:

```bash
pip install python-telegram-bot httpx
