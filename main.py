# -*- coding: utf-8 -*-
"""
بوت تيليجرام - القرآن الكريم
النسخة المحسنة (تعمل بالذاكرة المؤقتة RAM والتحميل غير المتزامن aiohttp)
لحل مشكلة حظر سيرفرات تليجرام من قبل مصادر الصوت.
"""

import logging
import io
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ============ الإعدادات ============
# ضع توكن البوت الخاص بك هنا
BOT_TOKEN = "8810555109:AAFC35pCG0j8P2H1eyE-PfFbwFJ7FybjY7A"

# ============ القراء ============
RECITERS = {
    "مشاري العفاسي":         "ar.alafasy",
    "محمود خليل الحصري":     "ar.husary",
    "محمد صديق المنشاوي":    "ar.minshawi",
    "عبد الباسط عبد الصمد":  "ar.abdulbasitmurattal",
    "ماهر المعيقلي":         "ar.mahermuaiqly",
    "سعد الغامدي":           "ar.saadalghamdi",
    "عبد الرحمن السديس":     "ar.abdurrahmaansudais",
    "أحمد العجمي":           "ar.ahmedajamy",
    "ياسر الدوسري":          "ar.yasseraldossari",
    "علي الحذيفي":           "ar.alhudhaify",
    "ناصر القطامي":          "ar.nasseralqatami",
    "فارس عباد":             "ar.faresabbad",
}

SURAHS = [
    "الفاتحة","البقرة","آل عمران","النساء","المائدة","الأنعام","الأعراف","الأنفال","التوبة","يونس",
    "هود","يوسف","الرعد","إبراهيم","الحجر","النحل","الإسراء","الكهف","مريم","طه",
    "الأنبياء","الحج","المؤمنون","النور","الفرقان","الشعراء","النمل","القصص","العنكبوت","الروم",
    "لقمان","السجدة","الأحزاب","سبأ","فاطر","يس","الصافات","ص","الزمر","غافر",
    "فصلت","الشورى","الزخرف","الدخان","الجاثية","الأحقاف","محمد","الفتح","الحجرات","ق",
    "الذاريات","الطور","النجم","القمر","الرحمن","الواقعة","الحديد","المجادلة","الحشر","الممتحنة",
    "الصف","الجمعة","المنافقون","التغابن","الطلاق","التحريم","الملك","القلم","الحاقة","المعارج",
    "نوح","الجن","المزمل","المدثر","القيامة","الإنسان","المرسلات","النبأ","النازعات","عبس",
    "التكوير","الانفطار","المطففين","الانشقاق","البروج","الطارق","الأعلى","الغاشية","الفجر","البلد",
    "الشمس","الليل","الضحى","الشرح","التين","العلق","القدر","البينة","الزلزلة","العاديات",
    "القارعة","التكاثر","العصر","الهمزة","الفيل","قريش","الماعون","الكوثر","الكافرون","النصر",
    "المسد","الإخلاص","الفلق","الناس"
]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ============ دوال مساعدة ============
def get_url(reciter_name: str, surah_num: int) -> str:
    """إرجاع الرابط المباشر"""
    reciter_id = RECITERS.get(reciter_name, "ar.alafasy")
    return f"https://cdn.islamic.network/quran/audio-surah/128/{reciter_id}/{surah_num:03d}.mp3"


# ============ لوحات المفاتيح ============
def reciters_keyboard() -> InlineKeyboardMarkup:
    kb = []
    names = list(RECITERS.keys())
    for i in range(0, len(names), 2):
        row = [InlineKeyboardButton(names[i], callback_data=f"r:{i}")]
        if i + 1 < len(names):
            row.append(InlineKeyboardButton(names[i + 1], callback_data=f"r:{i+1}"))
        kb.append(row)
    return InlineKeyboardMarkup(kb)


def surahs_keyboard(reciter_idx: int, page: int) -> InlineKeyboardMarkup:
    kb = []
    per_page = 12
    start = page * per_page
    end = min(start + per_page, len(SURAHS))
    row = []
    for i in range(start, end):
        row.append(InlineKeyboardButton(
            f"{i+1}. {SURAHS[i]}",
            callback_data=f"p:{reciter_idx}:{i+1}"
        ))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"s:{reciter_idx}:{page-1}"))
    if end < len(SURAHS):
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"s:{reciter_idx}:{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("🔙 تغيير القارئ", callback_data="home")])
    return InlineKeyboardMarkup(kb)


# ============ /start ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (
        f"السلام عليكم {user.first_name} 🌙\n\n"
        f"📖 *بوت القرآن الكريم*\n\n"
        f"🎙 *اختر القارئ* وستظهر لك السور مباشرة:"
    )
    if update.message:
        await update.message.reply_text(
            text, reply_markup=reciters_keyboard(), parse_mode="Markdown"
        )


# ============ معالج الأزرار ============
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    data = q.data
    await q.answer()

    # 🏠 رجوع للقراء
    if data == "home":
        await q.message.edit_text(
            "🎙️ *اختر القارئ:*",
            reply_markup=reciters_keyboard(),
            parse_mode="Markdown",
        )
        return

    # 🎙 اختيار قارئ
    if data.startswith("r:"):
        idx = int(data.split(":")[1])
        reciter_name = list(RECITERS.keys())[idx]
        text = (
            f"🎙️ القارئ: *{reciter_name}*\n\n"
            f"📖 *اختر السورة للاستماع أو التحميل:*"
        )
        await q.message.edit_text(
            text,
            reply_markup=surahs_keyboard(idx, 0),
            parse_mode="Markdown",
        )
        return

    # 📖 التنقل بين الصفحات
    if data.startswith("s:"):
        _, idx_s, page_s = data.split(":")
        idx = int(idx_s)
        page = int(page_s)
        reciter_name = list(RECITERS.keys())[idx]
        text = f"🎙️ القارئ: *{reciter_name}*\n\n📖 *اختر السورة:*"
        await q.message.edit_text(
            text,
            reply_markup=surahs_keyboard(idx, page),
            parse_mode="Markdown",
        )
        return

    # 🎧 الضغط على سورة (استماع) أو (تحميل)
    if data.startswith("p:") or data.startswith("d:"):
        action = data.split(":")[0] # 'p' للاستماع، 'd' للتحميل كملف
        _, idx_s, surah_s = data.split(":")
        idx = int(idx_s)
        surah_num = int(surah_s)
        surah_name = SURAHS[surah_num - 1]
        reciter_name = list(RECITERS.keys())[idx]

        wait = await q.message.reply_text(
            f"⏳ جاري جلب سورة *{surah_name}* بصوت *{reciter_name}*...\n(يرجى الانتظار ثوانٍ معدودة)",
            parse_mode="Markdown",
        )

        audio_url = get_url(reciter_name, surah_num)

        try:
            # تحميل الملف إلى الذاكرة العشوائية (RAM) بشكل سريع وغير متزامن
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url) as response:
                    if response.status != 200:
                        raise Exception("فشل جلب الملف من المصدر")
                    audio_data = await response.read()

            # تحويل البيانات إلى كائن يمكن لتليجرام قراءته كملف
            audio_file = io.BytesIO(audio_data)
            audio_file.name = f"{surah_num:03d}.mp3" # اسم الملف ضروري لتليجرام

            if action == "p": # إرسال كمقطع صوتي للاستماع
                download_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬇ تحميل كملف للحفظ", callback_data=f"d:{idx}:{surah_num}")],
                    [InlineKeyboardButton("🔙 قائمة السور", callback_data=f"s:{idx}:0")],
                ])
                await context.bot.send_audio(
                    chat_id=q.message.chat_id,
                    audio=audio_file,
                    title=f"{surah_num:03d}. سورة {surah_name}",
                    performer=reciter_name,
                    caption=(
                        f"📖 *سورة {surah_name}*\n"
                        f"🎙️ *{reciter_name}*\n\n"
                        f"🎧 استمع الآن، أو اضغط ⬇️ للتحميل كملف"
                    ),
                    parse_mode="Markdown",
                    reply_markup=download_kb,
                    read_timeout=100,
                    write_timeout=100,
                )

            elif action == "d": # إرسال كمستند (Document) للتحميل
                await context.bot.send_document(
                    chat_id=q.message.chat_id,
                    document=audio_file,
                    filename=f"Surah_{surah_num:03d}_{reciter_name}.mp3",
                    caption=(
                        f"📖 *سورة {surah_name}*\n"
                        f"🎙️ {reciter_name}\n\n"
                        f"⬇️ ملف جاهز للحفظ على جهازك"
                    ),
                    parse_mode="Markdown",
                    read_timeout=100,
                    write_timeout=100,
                )
            
            await wait.delete()

        except Exception as e:
            logger.error(f"❌ فشل المعالجة: {e}")
            await wait.edit_text(
                f"⚠️ *عذراً، مصدر الصوت لا يستجيب حالياً*\n\n"
                f"📖 {surah_name}\n"
                f"🎙️ {reciter_name}\n\n"
                f"🔗 [اضغط هنا للاستماع أو التحميل المباشر عبر المتصفح]({audio_url})",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        return


# ============ Main ============
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))
    
    print("✅ البوت يعمل بنجاح ومستعد لاستقبال الأوامر...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
