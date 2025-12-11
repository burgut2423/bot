# bot_group_monitor_forward_album_fixed.py
import logging
from datetime import datetime
import os
import pandas as pd
from telegram import InputFile

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

# ===== CONFIG =====
BOT_TOKEN = "8592016139:AAFg3vZWI4wXybymfs1g3hATmgAma3ZOF9A"
TARGET_GROUP_ID = -1002532769289 
EXCEL_FILE = "monitoring.xlsx"

# Standart mavzular
TOPICS = [
    ("ma_naviy", "📚 Ma'naviy tadbir (308)"),
    ("yangi_yil", "🎄 Yangi yilga tayyorgarlik"),
    ("dars", "📸 Dars jarayonlaridan lavhalar"),
    ("other", "➕ Boshqa tadbir (qo'lda kiriting)"),
]

# Excel ustunlari
COL_DATE = "sana"
COL_SCHOOL = "maktab"
COL_USER = "user"
COL_MA = "Ma'naviy tadbir"
COL_NEW = "Yangi yil"
COL_DARS = "Dars jarayonlari"
COL_BOSHQA = "Boshqa tadbirlar"
COL_LASTMSG = "oxirgi_message_id"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# In-memory storage
user_school = {}  # user_id -> maktab
user_sessions = {}  # user_id -> list of session entries

# Excel tayyorlash
if not os.path.exists(EXCEL_FILE):
    df_init = pd.DataFrame(
        columns=[COL_DATE, COL_SCHOOL, COL_USER, COL_MA, COL_NEW, COL_DARS, COL_BOSHQA, COL_LASTMSG]
    )
    df_init.to_excel(EXCEL_FILE, index=False)


def load_df():
    return pd.read_excel(EXCEL_FILE)


def save_df(df):
    df.to_excel(EXCEL_FILE, index=False)


def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")


def ensure_row_and_get_mask(df, school, user):
    today = get_today_str()
    mask = (df[COL_DATE] == today) & (df[COL_SCHOOL] == str(school)) & (df[COL_USER] == user)
    if df[mask].empty:
        new_row = {COL_DATE: today, COL_SCHOOL: str(school), COL_USER: user,
                   COL_MA: 0, COL_NEW: 0, COL_DARS: 0, COL_BOSHQA: "", COL_LASTMSG: ""}
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_df(df)
        mask = (df[COL_DATE] == today) & (df[COL_SCHOOL] == str(school)) & (df[COL_USER] == user)
    return df, mask


# ---------- Inline Maktab keyboard ----------
def build_school_keyboard():
    buttons = [InlineKeyboardButton(text=f"{i}", callback_data=f"school|{i}") for i in range(1, 55)]
    buttons.append(InlineKeyboardButton(text="PIMA", callback_data="school|PIMA"))
    buttons.append(InlineKeyboardButton(text="1-IMI", callback_data="school|1-IMI"))
    kb = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    return InlineKeyboardMarkup(kb)


# ---------- Inline Mavzu keyboard ----------
def build_topic_keyboard(entry_index: int):
    buttons = [InlineKeyboardButton(text=label, callback_data=f"pick|{entry_index}|{key}") for key, label in TOPICS]
    kb = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(kb)


# ---------- /start ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum!\n\n"
        "🔹 Maktabni tanlash uchun quyidagi tugmalardan birini bosing:",
        reply_markup=build_school_keyboard(),
    )

    # ---------- /start ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Foydalanuvchi /start yozganda ishga tushadi.
    Inline keyboard bilan maktab tanlashni chiqaradi.
    """
    await update.message.reply_text(
        "Assalomu alaykum!\n\n"
        "🔹 Maktabni tanlash uchun quyidagi tugmalardan birini bosing:",
        reply_markup=build_school_keyboard(),
    )
   


# ---------- Callback handler ----------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("|")
    user_id = query.from_user.id

    if parts[0] == "school":
        school = parts[1]
        user_school[user_id] = school
        await query.edit_message_text(f"✅ {school}-maktab tanlandi. Endi media yuboring.")
        return

    if parts[0] == "pick":
        idx = int(parts[1])
        topic = parts[2]
        if user_id not in user_sessions or idx >= len(user_sessions[user_id]):
            await query.edit_message_text("Session topilmadi.")
            return

        entry = user_sessions[user_id][idx]
        entry["topic"] = topic

        if topic == "other":
            await query.edit_message_text("➕ Iltimos, boshqa tadbir nomini yozing:")
            return

        await send_to_group(user_id, idx, context)
        await query.edit_message_text(f"✅ Tanlandi: {dict(TOPICS)[topic]} va guruhga yuborildi!")


# ---------- Text input (for 'other') ----------
async def text_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if user_id in user_sessions:
        for idx, entry in enumerate(user_sessions[user_id]):
            if entry.get("topic") == "other" and entry.get("other_text") is None:
                entry["other_text"] = text
                await send_to_group(user_id, idx, context)
                await update.message.reply_text(f"✅ Boshqa tadbir '{text}' guruhga yuborildi!")
                return


# ---------- Media handler ----------
async def media_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message

    if user_id not in user_school:
        await msg.reply_text("❗ Iltimos, avval maktabni tanlang (inline keyboard).")
        return

    mgid = getattr(msg, "media_group_id", None)
    if user_id not in user_sessions:
        user_sessions[user_id] = []

    # Albom bo'lsa, sessionga qo'shish
    if mgid:
        for e in user_sessions[user_id]:
            if e.get("media_group_id") == mgid:
                e["messages"].append(msg)
                return

    entry_index = len(user_sessions[user_id])
    entry = {"messages": [msg], "topic": None, "other_text": None,
             "media_group_id": mgid,
             "is_forwarded": msg.forward_from is not None or msg.forward_from_chat is not None}
    user_sessions[user_id].append(entry)

    kb = build_topic_keyboard(entry_index)
    await msg.reply_text(
        f"📌 Mavzu tanlang (xabar #{entry_index + 1})\n"
        f"🧾 Maktab: {user_school[user_id]}\n"
        f"📤 User: @{update.effective_user.username or update.effective_user.first_name}",
        reply_markup=kb,
    )


# ---------- Send to group ----------
async def send_to_group(user_id, entry_index, context: ContextTypes.DEFAULT_TYPE):
    entry = user_sessions[user_id][entry_index]
    topic = entry["topic"]
    other_text = entry.get("other_text", "")

    school = user_school.get(user_id, "Noma'lum")
    user_tag = entry["messages"][0].from_user.username or entry["messages"][0].from_user.first_name

    caption = f"🏫 Maktab:Oo'shko'pir tumani {school}-son maktab \n" \
              f"📌 Mavzu: {other_text if topic=='other' else dict(TOPICS)[topic]}\n" \
              f"📤 Foydalanuvchi: @{user_tag}\n" \
              f"📅 Sana: {get_today_str()}"

    # Albom yaratish
    media_group = []
    for m in entry["messages"]:
        if m.photo:
            media_group.append(InputMediaPhoto(media=m.photo[-1].file_id,
                                               caption=caption if len(media_group) == 0 else None))
        elif m.video:
            media_group.append(InputMediaVideo(media=m.video.file_id,
                                               caption=caption if len(media_group) == 0 else None))

    # Guruhga yuborish
    if len(media_group) > 1:
        await context.bot.send_media_group(chat_id=TARGET_GROUP_ID, media=media_group)
    elif len(media_group) == 1:
        if isinstance(media_group[0], InputMediaPhoto):
            await context.bot.send_photo(chat_id=TARGET_GROUP_ID,
                                         photo=media_group[0].media, caption=caption)
        else:
            await context.bot.send_video(chat_id=TARGET_GROUP_ID,
                                         video=media_group[0].media, caption=caption)

    # Excel yangilash
    df = load_df()
    df, mask = ensure_row_and_get_mask(df, school, user_tag)
    if topic == "ma_naviy":
        df.loc[mask, COL_MA] = df.loc[mask, COL_MA].astype(int) + 1
    elif topic == "yangi_yil":
        df.loc[mask, COL_NEW] = df.loc[mask, COL_NEW].astype(int) + 1
    elif topic == "dars":
        df.loc[mask, COL_DARS] = df.loc[mask, COL_DARS].astype(int) + 1
    elif topic == "other":
        existing = df.loc[mask, COL_BOSHQA].astype(str).iloc[0]
        d = {}
        if existing.strip():
            for p in existing.split(","):
                if ":" in p:
                    k, v = p.rsplit(":", 1)
                    d[k.strip()] = int(v.strip())
        label = other_text or "Boshqa"
        d[label] = d.get(label, 0) + 1
        df.loc[mask, COL_BOSHQA] = ", ".join([f"{k}:{v}" for k, v in d.items()])

    df.loc[mask, COL_LASTMSG] = entry["messages"][-1].message_id
    save_df(df)

    # User xabarlarini o'chirish
    for m in entry["messages"]:
        try:
            await context.bot.delete_message(chat_id=m.chat.id, message_id=m.message_id)
        except:
            pass

async def export_excel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not os.path.exists(EXCEL_FILE):
            await update.message.reply_text("❌ Excel fayl mavjud emas.")
            return

        # --- Excel faylni birlashtirish ---
        df = pd.read_excel(EXCEL_FILE)
        df_grouped = df.groupby(['sana', 'maktab', 'user'], as_index=False).agg({
            'Ma\'naviy tadbir': 'sum',
            'Yangi yil': 'sum',
            'Dars jarayonlari': 'sum',
            'Boshqa tadbirlar': lambda x: ', '.join([str(i) for i in x if str(i) != '0']),
            'oxirgi_message_id': 'max'
        })
        df_grouped.to_excel(EXCEL_FILE, index=False)  # eski faylni yangilash

        # Faylni yuborish
        with open(EXCEL_FILE, "rb") as f:
            await update.message.reply_document(document=InputFile(f), filename=EXCEL_FILE)

        await update.message.reply_text("✅ Excel fayl muvaffaqiyatli yuborildi!")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik yuz berdi: {e}")




# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                                   media_message_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_input_handler))
    app.add_handler(CommandHandler("export_excel", export_excel_cmd))

    print("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
