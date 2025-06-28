import os
import logging
import re
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    CallbackContext, CallbackQueryHandler, ConversationHandler
)

# CONFIG
TELEGRAM_TOKEN = 'your_bot_token_here'
OCR_SPACE_API_KEY = 'your_ocr_space_api_key'
WEB_APP_URL = 'your_google_apps_script_webhook_url'


# STATES
CHOOSE_MODE, WAIT_FOR_IMAGE, MANUAL_DISTRICT_SELECT = range(3)
user_mode = {}

REGIONS = {
    "Northern": ["Chitipa", "Karonga", "Likoma", "Mzimba", "Nkhata Bay", "Rumphi"],
    "Central": ["Dedza", "Dowa", "Kasungu", "Lilongwe", "Mchinji", "Nkhotakota", "Ntcheu", "Ntchisi", "Salima"],
    "Southern": ["Balaka", "Blantyre", "Chikwawa", "Chiradzulu", "Machinga", "Mangochi", "Mulanje",
                 "Mwanza", "Neno", "Nsanje", "Phalombe", "Thyolo", "Zomba"]
}

# KEYBOARDS
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start", callback_data='start')]
    ])

def cancel_back_keyboard(include_back=False):
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data='cancel')]]
    if include_back:
        buttons[0].insert(0, InlineKeyboardButton("⬅️ Go Back", callback_data='go_back'))
    return InlineKeyboardMarkup(buttons)

# OCR FUNCTION (FIXED)
def ocr_space_image(image_path):
    payload = {
        'apikey': OCR_SPACE_API_KEY,
        'language': 'eng',
        'isOverlayRequired': False,
        'isTable': False,
        'scale': True,
        'OCREngine': 2
    }

    try:
        with open(image_path, 'rb') as image_file:
            response = requests.post(
                'https://api.ocr.space/parse/image',
                files={'filename': image_file},
                data=payload,
                timeout=15
            )

        try:
            result = response.json()
        except ValueError:
            return None, "❌ OCR API returned invalid JSON."

        if result.get("IsErroredOnProcessing"):
            return None, result.get("ErrorMessage", "❌ Unknown OCR error.")
        return result['ParsedResults'][0]['ParsedText'], None

    except requests.RequestException as e:
        return None, f"❌ Network error: {e}"

# SHOW START MENU
def show_start_menu(update: Update, context: CallbackContext):
    if update.message:
        update.message.reply_text("Welcome! Press ▶️ Start to begin.", reply_markup=main_menu_keyboard())
    elif update.callback_query:
        update.callback_query.answer()
        update.callback_query.message.edit_text("Welcome! Press ▶️ Start to begin.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# STARTING FLOW
def begin_process(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("📊 All 4 Candidates", callback_data='all')],
        [InlineKeyboardButton("🖐️ One Candidate", callback_data='one')],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancel')]
    ]
    query.edit_message_text("Do you want to submit votes for one candidate or all 4?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_MODE

def choose_mode(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_mode[query.from_user.id] = query.data
    query.edit_message_text("Please upload the vote count image.", reply_markup=cancel_back_keyboard(include_back=True))
    return WAIT_FOR_IMAGE

def handle_photo(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    mode = user_mode.get(user_id, "all")
    photo = update.message.photo[-1].get_file()
    file_path = f"{user_id}_vote.jpg"
    photo.download(file_path)

    context.user_data['file_path'] = file_path
    context.user_data['mode'] = mode

    keyboard = [
        [InlineKeyboardButton("🌍 Northern", callback_data='region_Northern')],
        [InlineKeyboardButton("🏙️ Central", callback_data='region_Central')],
        [InlineKeyboardButton("🌇 Southern", callback_data='region_Southern')],
        [InlineKeyboardButton("⬅️ Go Back", callback_data='go_back'), InlineKeyboardButton("❌ Cancel", callback_data='cancel')]
    ]
    update.message.reply_text("🤔 Image received. Please choose the REGION:", reply_markup=InlineKeyboardMarkup(keyboard))
    return MANUAL_DISTRICT_SELECT

def choose_region(update: Update, context: CallbackContext):
    query = update.callback_query
    region_name = query.data.split("_")[1]
    query.answer()
    buttons = [[InlineKeyboardButton(d, callback_data=f'district_{d}')] for d in REGIONS[region_name]]
    buttons.append([InlineKeyboardButton("⬅️ Go Back", callback_data='go_back'), InlineKeyboardButton("❌ Cancel", callback_data='cancel')])
    query.edit_message_text(f"📍 Region selected: {region_name}. Now choose your DISTRICT:", reply_markup=InlineKeyboardMarkup(buttons))
    return MANUAL_DISTRICT_SELECT

def manual_district_selected(update: Update, context: CallbackContext):
    query = update.callback_query
    district = query.data.split("_")[1].strip().title()
    query.answer()
    query.edit_message_text(f"✅ District selected: {district}. Processing OCR...")

    file_path = context.user_data.get('file_path')
    mode = context.user_data.get('mode', 'all')

    text, error = ocr_space_image(file_path)

    if os.path.exists(file_path):
        os.remove(file_path)

    if error or not text:
        context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ OCR failed: {error}")
        return show_start_menu(update, context)

    def get_votes(name):
        match = re.search(rf'{name}[:\-\s]*([0-9,]+)', text, re.IGNORECASE)
        if match:
            number_str = match.group(1).replace(',', '')
            return int(number_str)
        return None

    candidates = ["Chakwera", "Mutharika", "Muluzi", "Kabambe"]
    votes = {}

    if mode == "all":
        for name in candidates:
            v = get_votes(name)
            if v is not None:
                votes[name] = v
    else:
        for name in candidates:
            v = get_votes(name)
            if v is not None:
                votes[name] = v
                break

    if not votes:
        context.bot.send_message(chat_id=query.message.chat_id, text="❌ No valid vote counts found.")
        return show_start_menu(update, context)

    payload = {
        "district": district,
        "votes": votes
    }

    try:
        res = requests.post(WEB_APP_URL, json=payload)
        context.bot.send_message(chat_id=query.message.chat_id, text=f"✅ Data sent: {res.text}")
    except Exception as e:
        context.bot.send_message(chat_id=query.message.chat_id, text=f"⚠️ Failed to send data: {e}")

    return show_start_menu(update, context)

# CANCEL / GO BACK HANDLERS
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("❌ Cancelled.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

def cancel_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text("❌ Cancelled. Press ▶️ Start to begin again.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

def go_back(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("📊 All 4 Candidates", callback_data='all')],
        [InlineKeyboardButton("🖐️ One Candidate", callback_data='one')],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancel')]
    ]
    query.edit_message_text("⬅️ Went back. Choose again:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_MODE

def unknown(update: Update, context: CallbackContext):
    update.message.reply_text("Please press ▶️ Start to begin.", reply_markup=main_menu_keyboard())

# MAIN
def main():
    logging.basicConfig(level=logging.INFO)
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(begin_process, pattern='^start$')],
        states={
            CHOOSE_MODE: [
                CallbackQueryHandler(choose_mode, pattern='^(all|one)$'),
                CallbackQueryHandler(cancel_callback, pattern='^cancel$'),
                CallbackQueryHandler(go_back, pattern='^go_back$')
            ],
            WAIT_FOR_IMAGE: [
                MessageHandler(Filters.photo, handle_photo),
                CallbackQueryHandler(cancel_callback, pattern='^cancel$'),
                CallbackQueryHandler(go_back, pattern='^go_back$')
            ],
            MANUAL_DISTRICT_SELECT: [
                CallbackQueryHandler(choose_region, pattern='^region_'),
                CallbackQueryHandler(manual_district_selected, pattern='^district_'),
                CallbackQueryHandler(cancel_callback, pattern='^cancel$'),
                CallbackQueryHandler(go_back, pattern='^go_back$')
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler('start', show_start_menu))
    dp.add_handler(MessageHandler(Filters.text | Filters.command, unknown))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
    