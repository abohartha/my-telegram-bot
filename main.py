import os
import requests
from telebot import TeleBot, types

# 1. قراءة التوكن بأمان من متغيرات البيئة (Railway)
BOT_TOKEN = os.environ.get("8976478095:AAHylUWqsVT5biaksxdqH1rbt98RyyW-znU")

if not BOT_TOKEN:
    raise ValueError("⚠️ خطأ حرج: لم يتم العثور على BOT_TOKEN في متغيرات البيئة.")

bot = TeleBot(BOT_TOKEN)

# 2. بيانات أشهر القراء وروابط خوادمهم الصوتية الموثوقة
RECITERS = {
    "afs": {"name": "مشاري العفاسي", "server": "https://server8.mp3quran.net/afs/"},
    "basit": {"name": "عبد الباسط عبد الصمد", "server": "https://server7.mp3quran.net/basit/"},
    "maher": {"name": "ماهر المعيقلي", "server": "https://server12.mp3quran.net/maher/"},
    "minsh": {"name": "محمد صديق المنشاوي", "server": "https://server10.mp3quran.net/minsh/"},
    "husr": {"name": "محمود خليل الحصري", "server": "https://server13.mp3quran.net/husr/"},
    "sds": {"name": "عبد الرحمن السديس", "server": "https://server11.mp3quran.net/sds/"},
}

# 3. دالة لجلب أسماء السور
def get_surahs():
    try:
        response = requests.get("https://api.alquran.cloud/v1/surah", timeout=10)
        if response.status_code == 200:
            return response.json().get("data", [])
    except Exception as e:
        print(f"خطأ في الاتصال: {e}")
    return []

# تحميل السور مرة واحدة عند تشغيل البوت لتسريع الاستجابة
SURAH_DATA = get_surahs()

# 4. رسالة الترحيب وقائمة القراء
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    text = (
        "✨ *مرحباً بك في بوت القرآن الكريم الصوتي* ✨\n\n"
        "اختر القارئ الذي تود الاستماع إليه من القائمة أدناه:"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # إنشاء زر لكل قارئ
    for reciter_id, info in RECITERS.items():
        markup.add(types.InlineKeyboardButton(f"🎙️ {info['name']}", callback_data=f"reciter_{reciter_id}"))
        
    # تعديل أو إرسال الرسالة
    if getattr(message, 'message_id', None) and not message.text.startswith('/'):
        bot.edit_message_text(text, message.chat.id, message.message_id, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)


# 5. عرض قائمة السور عند اختيار القارئ (مع خاصية الصفحات)
@bot.callback_query_handler(func=lambda call: call.data.startswith("reciter_") or call.data.startswith("page_"))
def handle_surahs_pagination(call):
    if not SURAH_DATA:
        bot.answer_callback_query(call.id, "❌ تعذر جلب قائمة السور، جرب لاحقاً.", show_alert=True)
        return

    # تحليل البيانات القادمة من الزر
    if call.data.startswith("reciter_"):
        reciter_id = call.data.split("_")[1]
        page = 0
    else:
        parts = call.data.split("_")
        page = int(parts[1])
        reciter_id = parts[2]

    items_per_page = 15
    total_pages = (len(SURAH_DATA) + items_per_page - 1) // items_per_page
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_surahs = SURAH_DATA[start_idx:end_idx]

    reciter_name = RECITERS[reciter_id]['name']
    text = f"📖 *القارئ: {reciter_name}*\nاختر السورة (الصفحة {page + 1} من {total_pages}):"
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    
    for surah in current_surahs:
        s_num = surah["number"]
        s_name = surah["name"]
        # زر تشغيل السورة يحمل رقمها واسم القارئ المختصر
        buttons.append(types.InlineKeyboardButton(s_name, callback_data=f"play_{s_num}_{reciter_id}"))
    
    markup.add(*buttons)

    # أزرار التنقل السفلية
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("◀️ السابق", callback_data=f"page_{page-1}_{reciter_id}"))
    
    nav.append(types.InlineKeyboardButton("🔙 عودة للقراء", callback_data="back_to_reciters"))
    
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton("التالي ▶️", callback_data=f"page_{page+1}_{reciter_id}"))
        
    markup.row(*nav)

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)


# 6. زر العودة للقائمة الرئيسية
@bot.callback_query_handler(func=lambda call: call.data == "back_to_reciters")
def back_to_main(call):
    send_welcome(call.message)


# 7. إرسال المقطع الصوتي عند اختيار السورة
@bot.callback_query_handler(func=lambda call: call.data.startswith("play_"))
def play_audio(call):
    parts = call.data.split("_")
    surah_num = int(parts[1])
    reciter_id = parts[2]
    
    surah_name = SURAH_DATA[surah_num - 1]["name"]
    reciter_name = RECITERS[reciter_id]["name"]
    server = RECITERS[reciter_id]["server"]
    
    # صيغة روابط mp3quran تتطلب أن يكون رقم السورة من 3 خانات (مثل: 001.mp3)
    audio_url = f"{server}{str(surah_num).zfill(3)}.mp3"

    bot.answer_callback_query(call.id, f"جاري التجهيز: {surah_name}")
    
    processing_msg = bot.send_message(
        call.message.chat.id, 
        f"🎧 جاري جلب *{surah_name}* بصوت *{reciter_name}*...\n⏳ يرجى الانتظار...", 
        parse_mode="Markdown"
    )
    
    try:
        # إرسال الملف الصوتي كمقطع Audio في تليجرام
        bot.send_audio(
            call.message.chat.id, 
            audio=audio_url, 
            title=surah_name, 
            performer=reciter_name
        )
        bot.delete_message(call.message.chat.id, processing_msg.message_id)
    except Exception as e:
        bot.edit_message_text(
            "❌ عذراً، لا يمكن إرسال هذه السورة مباشرة لأن حجمها كبير جداً على خوادم تليجرام. يمكنك الاستماع إليها عبر تطبيقات خارجية.",
            call.message.chat.id, 
            processing_msg.message_id
        )

# 8. تشغيل البوت
if __name__ == "__main__":
    print("🤖 بوت القرآن يعمل الآن بنجاح...")
    bot.infinity_polling(skip_pending=True)
