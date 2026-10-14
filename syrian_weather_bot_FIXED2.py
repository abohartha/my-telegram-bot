# -*- coding: utf-8 -*-

import asyncio
import logging
from datetime import datetime, timezone, timedelta

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import BadRequest

# ============================================================
# 1) توكن البوت الخاص بك وتحديد التوقيت (GMT+3)
# ============================================================
BOT_TOKEN = "8663638521:AAH6YFb20Vbu0rllOD6gLcBx5xmGJdX0eno"
TZ_GMT3 = timezone(timedelta(hours=3))  # توقيت غرينتش +3

# ============================================================
# 2) نماذج الطقس المتاحة (مصادر البيانات)
# ============================================================
WEATHER_MODELS = {
    "ecmwf": {"code": "ecmwf_ifs025", "name": "🇪🇺 النموذج الأوروبي (ECMWF)"},
    "icon": {"code": "icon_seamless", "name": "🇩🇪 النموذج الألماني (ICON)"},
    "gfs": {"code": "gfs_seamless", "name": "🇺🇸 النموذج الأمريكي (GFS)"},
}

# ============================================================
# 3) بيانات المناطق والمحافظات في سوريا
# ============================================================
GITHUB_RAW = "https://raw.githubusercontent.com/Open-Syria/data-geography/main/data/"

DATA_URLS = {
    "governorates": GITHUB_RAW + "governorates.json",
    "districts": GITHUB_RAW + "districts.json",
    "subdistricts": GITHUB_RAW + "subdistricts.json",
    "localities": GITHUB_RAW + "localities.json",
}

PAGE_SIZE = 12
GOV_PAGE_SIZE = 15

GEO = {"governorates": [], "districts": [], "subdistricts": [], "localities": []}
INDEX = {"governorates": {}, "districts": {}, "subdistricts": {}, "localities": {}}

DAYS = {0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"}


def get_name(item):
    name = item.get("name", {})
    if isinstance(name, dict):
        return name.get("ar") or name.get("arabic") or name.get("en") or "بدون اسم"
    return str(name)


def get_id(item):
    return str(item.get("id", ""))


def get_coordinates(item):
    centroid = item.get("centroid")
    if isinstance(centroid, dict):
        lat = centroid.get("latitude")
        lon = centroid.get("longitude")
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    return None, None


def get_parent(item, field):
    value = item.get(field)
    return "" if value is None else str(value)


def download_json(url):
    response = requests.get(url, timeout=60, headers={"User-Agent": "SyrianWeatherBot/1.0"})
    response.raise_for_status()
    return response.json()


def load_geography():
    print("Downloading Syrian geography data...")
    for key, url in DATA_URLS.items():
        GEO[key] = download_json(url)
        if not isinstance(GEO[key], list):
            raise RuntimeError("ملف البيانات غير صالح: " + key)
    rebuild_indexes()
    print("Geography data loaded successfully.")


def rebuild_indexes():
    for key in INDEX:
        INDEX[key].clear()
    for item in GEO["governorates"]:
        INDEX["governorates"][get_id(item)] = item
    for item in GEO["districts"]:
        INDEX["districts"][get_id(item)] = item
    for item in GEO["subdistricts"]:
        INDEX["subdistricts"][get_id(item)] = item
    for item in GEO["localities"]:
        INDEX["localities"][get_id(item)] = item


def districts_for_governorate(governorate_id):
    return sorted(
        [item for item in GEO["districts"] if get_parent(item, "governorateId") == str(governorate_id)],
        key=get_name,
    )


def subdistricts_for_district(district_id):
    return sorted(
        [item for item in GEO["subdistricts"] if get_parent(item, "districtId") == str(district_id)],
        key=get_name,
    )


def localities_for_subdistrict(subdistrict_id):
    return sorted(
        [item for item in GEO["localities"] if get_parent(item, "subdistrictId") == str(subdistrict_id)],
        key=get_name,
    )


def paginate(items, page, size=PAGE_SIZE):
    total = len(items)
    pages = max(1, (total + size - 1) // size)
    page = max(0, min(page, pages - 1))
    return items[page * size : (page + 1) * size], page, pages


def navigation(prefix, page, pages, back=None):
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(f"📄 {page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        row.append(InlineKeyboardButton("التالي ➡️️", callback_data=f"{prefix}:{page + 1}"))
    rows = [row]
    if back:
        rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=back)])
    rows.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="home")])
    return rows


def governorates_keyboard(page=0):
    items = sorted(GEO["governorates"], key=get_name)
    items, page, pages = paginate(items, page, size=GOV_PAGE_SIZE)

    rows = [[InlineKeyboardButton("🔍 بحث سريع عن مكان", callback_data="btn_search")]]
    rows.extend([[InlineKeyboardButton("📍 " + get_name(item), callback_data="gov:" + get_id(item))] for item in items])
    if pages > 1:
        rows.extend(navigation("govpage", page, pages))
    return InlineKeyboardMarkup(rows)


def districts_keyboard(governorate_id, page=0):
    items = districts_for_governorate(governorate_id)
    items, page, pages = paginate(items, page)
    rows = [[InlineKeyboardButton("📍 " + get_name(item), callback_data="dist:" + get_id(item))] for item in items]
    rows.extend(navigation(f"distpage:{governorate_id}", page, pages, f"gov:{governorate_id}"))
    return InlineKeyboardMarkup(rows)


def subdistricts_keyboard(district_id, page=0):
    items = subdistricts_for_district(district_id)
    items, page, pages = paginate(items, page)
    rows = [[InlineKeyboardButton("📍 " + get_name(item), callback_data="sub:" + get_id(item))] for item in items]
    rows.extend(navigation(f"subpage:{district_id}", page, pages, f"dist:{district_id}"))
    return InlineKeyboardMarkup(rows)


def localities_keyboard(subdistrict_id, page=0):
    items = localities_for_subdistrict(subdistrict_id)
    items, page, pages = paginate(items, page)
    rows = []
    for item in items:
        lat, lon = get_coordinates(item)
        if lat is not None and lon is not None:
            rows.append([InlineKeyboardButton("🌤️ " + get_name(item), callback_data="loc:" + get_id(item))])
    rows.extend(navigation(f"locpage:{subdistrict_id}", page, pages, f"sub:{subdistrict_id}"))
    return InlineKeyboardMarkup(rows)


def weather_description(code):
    code = int(code)
    if code == 0: return "☀️ مشمس"
    if code in (1, 2): return "🌤️ غائم جزئياً"
    if code == 3: return "☁️ غائم"
    if code in (45, 48): return "🌫 الضباب"
    if code in (51, 53, 55, 56, 57): return "🌦 ممطر خفيف"
    if code in (61, 63, 65, 66, 67): return "🌧️ ممطر"
    if code in (71, 73, 75, 77, 85, 86): return "❄️ ثلوج"
    if code in (80, 81, 82): return "🌧 زخات مطر"
    if code in (95, 96, 99): return "⛈️ عواصف رعدية"
    return "🌤️ متقلب"


def kmh_to_ms(value):
    return float(value or 0) / 3.6


def format_date(value):
    dt = datetime.strptime(value, "%Y-%m-%d")
    return f"{DAYS[dt.weekday()]} {dt.day:02d}/{dt.month:02d}"


def get_weather(latitude, longitude, model_key="ecmwf"):
    model_code = WEATHER_MODELS.get(model_key, WEATHER_MODELS["ecmwf"])["code"]
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code,wind_speed_10m,wind_gusts_10m,precipitation,cloud_cover",
        "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max",
        "forecast_days": 5,
        "timezone": "Asia/Damascus",
        "wind_speed_unit": "kmh",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "models": model_code,
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_next_3_hours(hourly_data):
    times = hourly_data.get("time", [])
    temps = hourly_data.get("temperature_2m", [])
    codes = hourly_data.get("weather_code", [])
    precip = hourly_data.get("precipitation", [])
    prob = hourly_data.get("precipitation_probability", [])

    if not times:
        return "☀️ لا تتوفر بيانات للساعات القادمة."

    now_str = datetime.now(TZ_GMT3).strftime("%Y-%m-%dT%H:00")

    start_idx = 0
    for i, t in enumerate(times):
        if t >= now_str:
            start_idx = i
            break

    entries = []
    for i in range(start_idx, min(start_idx + 3, len(times))):
        time_str = times[i].split("T")[1][:5]
        temp_val = f"*{temps[i]:.1f}°C*" if i < len(temps) and temps[i] is not None else ""
        desc_val = weather_description(codes[i]) if i < len(codes) and codes[i] is not None else ""
        p_amount = precip[i] if i < len(precip) and precip[i] is not None else 0.0
        p_prob = prob[i] if (prob and i < len(prob) and prob[i] is not None) else 0

        rain_str = f" | 🌧️ {p_amount:.1f} مم ({p_prob}%)" if (p_amount > 0 or p_prob > 0) else ""
        entries.append(f"  • الساعة *{time_str}*: {desc_val} {temp_val}{rain_str}")

    if not entries:
        return "☀️ لا تتوفر بيانات للساعات القادمة."

    return "\n".join(entries)


def build_current_weather(place, model_key="ecmwf"):
    name = get_name(place)
    latitude, longitude = get_coordinates(place)
    if latitude is None or longitude is None:
        raise ValueError("لا توجد إحداثيات لهذا المكان.")

    data = get_weather(latitude, longitude, model_key)
    current = data["current"]
    daily = data.get("daily", {})
    hourly = data.get("hourly", {})

    wind = kmh_to_ms(current.get("wind_speed_10m", 0))
    gust = kmh_to_ms(current.get("wind_gusts_10m", 0))
    model_name = WEATHER_MODELS.get(model_key, WEATHER_MODELS["ecmwf"])["name"]
    now_str = datetime.now(TZ_GMT3).strftime("%H:%M:%S")

    today_rain = daily.get("precipitation_sum", [0.0])[0] if daily.get("precipitation_sum") else 0.0
    next_3_hours = parse_next_3_hours(hourly)

    return (
        f"🌦️ *طقس {name} (الحالي)*\n"
        "━━━━━━━━━━━━━━━━\n"
        f"📍 المكان: *{name}*\n"
        f"🌡 الحرارة الآن: *{current['temperature_2m']:.1f}°C*\n"
        f"🌤 الحالة: *{weather_description(current['weather_code'])}*\n"
        f"💨 سرعة الرياح: *{wind:.1f} م/ث*\n"
        f"💨 هبات الرياح: *{gust:.1f} م/ث*\n"
        f"☁️ الغيوم: *{current['cloud_cover']}%*\n"
        f"🌧 الهطول خلال الساعة الماضية: *{current['precipitation']:.1f} مم*\n"
        f"🌧️ إجمالي أمطار اليوم المتوقعة: *{today_rain:.1f} مم*\n\n"
        f"⏱️ *توقعات الـ 3 ساعات القادمة (GMT+3):*\n"
        f"{next_3_hours}\n\n"
        f"📡 المصدر: *Open-Meteo ({model_name})*\n"
        f"🕒 وقت العرض: *{now_str} (GMT+3)*"
    )


def build_forecast_5days(place, model_key="ecmwf"):
    name = get_name(place)
    latitude, longitude = get_coordinates(place)
    if latitude is None or longitude is None:
        raise ValueError("لا توجد إحداثيات لهذا المكان.")

    data = get_weather(latitude, longitude, model_key)
    daily = data["daily"]
    model_name = WEATHER_MODELS.get(model_key, WEATHER_MODELS["ecmwf"])["name"]
    now_str = datetime.now(TZ_GMT3).strftime("%H:%M:%S")

    text = f"📅 *توقعات 5 أيام - {name}*\n━━━━━━━━━━━━━━━━\n"

    for i, date in enumerate(daily["time"]):
        state = weather_description(daily["weather_code"][i])
        minimum = daily["temperature_2m_min"][i]
        maximum = daily["temperature_2m_max"][i]
        rain = daily["precipitation_sum"][i]
        wind = kmh_to_ms(daily["wind_speed_10m_max"][i])
        gust = kmh_to_ms(daily["wind_gusts_10m_max"][i])

        text += (
            f"\n📆 *{format_date(date)}*\n"
            f"{state}\n"
            f"🌡️ {minimum:.0f}° → {maximum:.0f}°C | "
            f"🌧 {rain:.1f} مم\n"
            f"💨 الرياح: {wind:.1f} م/ث (هبات {gust:.1f})\n"
        )

    text += (
        f"\n━━━━━━━━━━━━━━━━\n"
        f"📡 المصدر: *Open-Meteo ({model_name})*\n"
        f"🕒 وقت العرض: *{now_str} (GMT+3)*"
    )
    return text


def build_model_buttons(locality_id, current_model="ecmwf", is_forecast=False):
    prefix = "f5" if is_forecast else "loc"
    buttons = []
    row = []
    for key, info in WEATHER_MODELS.items():
        label = ("✅ " if key == current_model else "") + info["name"].split()[1]
        row.append(InlineKeyboardButton(label, callback_data=f"{prefix}:{locality_id}:{key}"))
    buttons.append(row)
    return buttons


def search_places(query, limit=30):
    query = query.strip().casefold().replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    results = []
    collections = [
        ("محافظة", GEO["governorates"]),
        ("منطقة", GEO["districts"]),
        ("ناحية", GEO["subdistricts"]),
        ("مكان", GEO["localities"]),
    ]
    for kind, collection in collections:
        for item in collection:
            name = get_name(item).casefold().replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
            if query in name:
                results.append((kind, item))
                if len(results) >= limit:
                    return results
    return results


def search_keyboard(results):
    rows = []
    for kind, item in results:
        item_id = get_id(item)
        if kind == "محافظة": callback = "gov:" + item_id
        elif kind == "منطقة": callback = "dist:" + item_id
        elif kind == "ناحية": callback = "sub:" + item_id
        else: callback = "loc:" + item_id

        rows.append([InlineKeyboardButton(f"📍 {get_name(item)} — {kind}", callback_data=callback)])

    rows.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(rows)


HOME_TEXT = (
    "🇸🇾 *بوت طقس سوريا الشامل*\n\n"
    "اختر المحافظة من القائمة أدناه أو استخدم البحث السريع.\n\n"
    "🌡️ درجات الحرارة والطقس وتوقعات الـ 3 ساعات القادمة\n"
    "📅 توقعات 5 أيام تفصيلية (الأوروبي / الألماني / الأمريكي)\n"
    "📡 مصدر البيانات: Open-Meteo API (التوقيت: GMT+3)\n\n"
    "🔎 *طريقة البحث السريع:*\n"
    "اكتب اسم المكان مباشرة في المحادثة (مثال: `جرمانا` أو `النبك` أو `ريف دمشق`)"
)


async def start(update, context):
    await update.message.reply_text(
        HOME_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=governorates_keyboard(),
    )


async def help_command(update, context):
    await update.message.reply_text(
        "ℹ️ *طريقة الاستخدام*\n\n"
        "1️⃣ اضغط /start واختر المكان عبر الأزرار.\n"
        "2️⃣ التبديل بين النماذج الجوية العالمية (ECMWF, ICON, GFS) بنقرة واحدة عبر Open-Meteo.\n"
        "3️⃣ أو اكتب اسم المكان مباشرة في المحادثة.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_text_search(update, context):
    if not update.message or not update.message.text:
        return
    raw = update.message.text.strip()
    if raw.startswith("/"):
        return

    query = raw[3:].strip() if raw.startswith("بحث") else raw

    if not query:
        return

    results = search_places(query)

    if not results:
        await update.message.reply_text(
            f"❌ لم يتم العثور على أي نتائج لـ: *{query}*\n\nتأكد من الاسم أو جرب كلمة أخرى.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await update.message.reply_text(
        f"🔎 نتائج البحث عن: *{query}*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=search_keyboard(results),
    )


async def search_command(update, context):
    if not context.args:
        await update.message.reply_text("🔎 اكتب اسم المكان بعد الأمر.\nمثال: `/search ريف دمشق`", parse_mode=ParseMode.MARKDOWN)
        return

    query = " ".join(context.args)
    results = search_places(query)

    if not results:
        await update.message.reply_text("❌ لم أجد المكان: " + query)
        return

    await update.message.reply_text(
        f"🔎 نتائج البحث عن: *{query}*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=search_keyboard(results),
    )


async def callback_handler(update, context):
    query = update.callback_query
    data = query.data

    try:
        if data == "noop":
            await query.answer()
            return

        if data == "btn_search":
            await query.answer()
            await query.edit_message_text(
                "🔎 *البحث السريع عن مكان*\n\n"
                "اكتب اسم القرية، الناحية، المدينة، أو المحافظة مباشرة في المحادثة الآن وسيقوم البوت بالبحث عنها فوراً.\n\n"
                "💡 *أمثلة:* `جرمانا` | `مصياف` | `السويداء` | `النبك`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]]),
            )
            return

        if data == "home":
            await query.answer()
            await query.edit_message_text(HOME_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=governorates_keyboard())
            return

        if data.startswith("govpage:"):
            await query.answer()
            page = int(data.split(":", 1)[1])
            await query.edit_message_text("🇸🇾 *اختر المحافظة:*", parse_mode=ParseMode.MARKDOWN, reply_markup=governorates_keyboard(page))
            return

        if data.startswith("gov:"):
            await query.answer()
            governorate_id = data.split(":", 1)[1]
            governorate = INDEX["governorates"].get(governorate_id)
            if not governorate:
                await query.answer("المحافظة غير موجودة", show_alert=True)
                return
            await query.edit_message_text(f"📍 *{get_name(governorate)}*\n\nاختر المنطقة:", parse_mode=ParseMode.MARKDOWN, reply_markup=districts_keyboard(governorate_id))
            return

        if data.startswith("distpage:"):
            await query.answer()
            parts = data.split(":")
            await query.edit_message_text("📍 *اختر المنطقة:*", parse_mode=ParseMode.MARKDOWN, reply_markup=districts_keyboard(parts[1], int(parts[2])))
            return

        if data.startswith("dist:"):
            await query.answer()
            district_id = data.split(":", 1)[1]
            district = INDEX["districts"].get(district_id)
            if not district:
                await query.answer("المنطقة غير موجودة", show_alert=True)
                return
            await query.edit_message_text(f"📍 *{get_name(district)}*\n\nاختر الناحية:", parse_mode=ParseMode.MARKDOWN, reply_markup=subdistricts_keyboard(district_id))
            return

        if data.startswith("subpage:"):
            await query.answer()
            parts = data.split(":")
            await query.edit_message_text("📍 *اختر الناحية:*", parse_mode=ParseMode.MARKDOWN, reply_markup=subdistricts_keyboard(parts[1], int(parts[2])))
            return

        if data.startswith("sub:"):
            await query.answer()
            subdistrict_id = data.split(":", 1)[1]
            subdistrict = INDEX["subdistricts"].get(subdistrict_id)
            if not subdistrict:
                await query.answer("الناحية غير موجودة", show_alert=True)
                return
            await query.edit_message_text(f"📍 *{get_name(subdistrict)}*\n\nاختر المدينة أو البلدة أو القرية:", parse_mode=ParseMode.MARKDOWN, reply_markup=localities_keyboard(subdistrict_id))
            return

        if data.startswith("locpage:"):
            await query.answer()
            parts = data.split(":")
            await query.edit_message_text("🏘️ *اختر المدينة أو البلدة أو القرية:*", parse_mode=ParseMode.MARKDOWN, reply_markup=localities_keyboard(parts[1], int(parts[2])))
            return

        if data.startswith("loc:"):
            parts = data.split(":")
            locality_id = parts[1]
            model_key = parts[2] if len(parts) > 2 else "ecmwf"

            locality = INDEX["localities"].get(locality_id)
            if not locality:
                await query.answer("المكان غير موجود", show_alert=True)
                return

            await query.answer()
            weather_text = await asyncio.to_thread(build_current_weather, locality, model_key)
            subdistrict_id = get_parent(locality, "subdistrictId")

            rows = build_model_buttons(locality_id, current_model=model_key, is_forecast=False)
            rows.extend([
                [InlineKeyboardButton("📅 توقعات 5 أيام", callback_data=f"f5:{locality_id}:{model_key}")],
                [InlineKeyboardButton("🔙 القرى والبلدات", callback_data=f"sub:{subdistrict_id}")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")],
            ])

            try:
                await query.edit_message_text(
                    weather_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(rows),
                )
            except BadRequest:
                pass
            return

        if data.startswith("f5:"):
            parts = data.split(":")
            locality_id = parts[1]
            model_key = parts[2] if len(parts) > 2 else "ecmwf"

            locality = INDEX["localities"].get(locality_id)
            if not locality:
                await query.answer("المكان غير موجود", show_alert=True)
                return

            await query.answer()
            forecast_text = await asyncio.to_thread(build_forecast_5days, locality, model_key)
            subdistrict_id = get_parent(locality, "subdistrictId")

            rows = build_model_buttons(locality_id, current_model=model_key, is_forecast=True)
            rows.extend([
                [InlineKeyboardButton("🌡️ الطقس الحالي", callback_data=f"loc:{locality_id}:{model_key}")],
                [InlineKeyboardButton("🔙 القرى والبلدات", callback_data=f"sub:{subdistrict_id}")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")],
            ])

            try:
                await query.edit_message_text(
                    forecast_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(rows),
                )
            except BadRequest:
                pass
            return

    except requests.RequestException as error:
        logging.exception("Network error: %s", error)
        await query.edit_message_text("❌ تعذر الاتصال بمصدر البيانات.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]]))
    except Exception as error:
        logging.exception("Callback error: %s", error)
        await query.edit_message_text("❌ حدث خطأ أثناء تنفيذ الطلب.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]]))


def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("ضع توكن Telegram الجديد في BOT_TOKEN أولاً.")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    load_geography()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .get_updates_http_version("1.1")
        .http_version("1.1")
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_search))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("================================")
    print("SYRIA WEATHER BOT IS RUNNING (GMT+3)")
    print("================================")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
