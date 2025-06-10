from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import os
from datetime import datetime
from google_sheets import save_to_sheet

# Bosqichlar
CONTACT, ORG, COUNT, STUDENTS, PHOTOS = range(5)
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = KeyboardButton("📞 Telefon raqam yuborish", request_contact=True)
    markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True)
    await update.message.reply_text("Ro'yxatdan o'tish uchun telefon raqamingizni yuboring.", reply_markup=markup)
    return CONTACT

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact.phone_number
    user_data[update.effective_user.id] = {'phone': contact}
    markup = ReplyKeyboardMarkup([["Maktab", "MTT"]], resize_keyboard=True)
    await update.message.reply_text("Tashkilot turini tanlang:", reply_markup=markup)
    return ORG

async def org_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    org = update.message.text
    user_data[update.effective_user.id]['org'] = org
    await update.message.reply_text("Tadbirlar sonini kiriting:")
    return COUNT

async def count_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id]['event_count'] = update.message.text
    await update.message.reply_text("Tadbirda qatnashgan o'quvchilar sonini kiriting:")
    return STUDENTS

async def students_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id]['students'] = update.message.text
    user_data[update.effective_user.id]['photos'] = []
    await update.message.reply_text("Endi 4 ta rasm yuboring. Har birini alohida yuboring.")
    return PHOTOS

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    date_str = datetime.now().strftime("%Y-%m-%d")
    save_path = f"images/{user_id}/{date_str}/"
    os.makedirs(save_path, exist_ok=True)

    photo_path = f"{save_path}{len(user_data[user_id]['photos']) + 1}.jpg"
    await photo_file.download_to_drive(photo_path)
    user_data[user_id]['photos'].append(photo_path)

    if len(user_data[user_id]['photos']) == 4:
        save_to_sheet(user_data[user_id])
        await update.message.reply_text("Ma'lumotlaringiz saqlandi. Rahmat!")
        return ConversationHandler.END
    else:
        await update.message.reply_text(f"{len(user_data[user_id]['photos'])}/4 rasm qabul qilindi. Davom eting.")
        return PHOTOS

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.")
    return ConversationHandler.END

app = ApplicationBuilder().token("8008196564:AAHfzO7JM5S1PbVRPEkUXNl6vYXckhnX3oY").build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        CONTACT: [MessageHandler(filters.CONTACT, contact_handler)],
        ORG: [MessageHandler(filters.TEXT, org_handler)],
        COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, count_handler)],
        STUDENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, students_handler)],
        PHOTOS: [MessageHandler(filters.PHOTO, photo_handler)],
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

app.add_handler(conv_handler)
app.run_polling()
