import logging
import sqlite3
import os
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot Active"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

Thread(target=run_flask, daemon=True).start()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8698823300:AAFdPKZJUSWthv_xWeetYlA4yZJ2EvXugfM"
GLOBAL_ADMINS = {6115982173, 8140417937}

db = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    chat_id INTEGER PRIMARY KEY,
    anti_spam INTEGER DEFAULT 1,
    anti_curse INTEGER DEFAULT 1,
    welcome_msg TEXT DEFAULT 'Hoş geldin!'
)
""")
cursor.execute("CREATE TABLE IF NOT EXISTS messages (chat_id INTEGER, user_id INTEGER, username TEXT, message_count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id))")
cursor.execute("CREATE TABLE IF NOT EXISTS warnings (chat_id INTEGER, user_id INTEGER, count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id))")
cursor.execute("CREATE TABLE IF NOT EXISTS notes (chat_id INTEGER, keyword TEXT, content TEXT, PRIMARY KEY (chat_id, keyword))")
cursor.execute("CREATE TABLE IF NOT EXISTS auto_replies (chat_id INTEGER, keyword TEXT, reply TEXT, PRIMARY KEY (chat_id, keyword))")
cursor.execute("CREATE TABLE IF NOT EXISTS filters_db (chat_id INTEGER, word TEXT, PRIMARY KEY (chat_id, word))")
db.commit()

async def ayar_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("⚠️ Bu komut sadece grup içinde kullanılabilir!")
        return

    chat_id = update.effective_chat.id
    cursor.execute("SELECT anti_spam, anti_curse FROM settings WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    
    spam_stat = "AÇIK" if not row or row[0] == 1 else "KAPALI"
    curse_stat = "AÇIK" if not row or row[1] == 1 else "KAPALI"

    keyboard = [
        [InlineKeyboardButton(f"🛡️ Anti-Spam: {spam_stat}", callback_data="toggle_spam"),
         InlineKeyboardButton(f"🤬 Küfür Koruması: {curse_stat}", callback_data="toggle_curse")],
        [InlineKeyboardButton("📋 Sistem Bilgisi", callback_data="sys_info"),
         InlineKeyboardButton("🔄 Yenile", callback_data="reload_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚙️ **Grup Yönetim Paneli (v18.0 Full)**\nAşağıdaki butonlardan grup koruma katmanlarını yönetebilirsin:", reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat.id
    data = query.data

    if data == "toggle_spam":
        cursor.execute("SELECT anti_spam FROM settings WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        new_val = 0 if (row and row[0] == 1) else 1
        cursor.execute("INSERT OR REPLACE INTO settings (chat_id, anti_spam) VALUES (?, ?)", (chat_id, new_val))
        db.commit()
        await query.edit_message_text(f"✅ Anti-Spam durumu güncellendi: {'AÇIK' if new_val==1 else 'KAPALI'}")
        
    elif data == "toggle_curse":
        cursor.execute("SELECT anti_curse FROM settings WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        new_val = 0 if (row and row[1] == 1) else 1
        cursor.execute("INSERT OR REPLACE INTO settings (chat_id, anti_curse) VALUES (?, ?)", (chat_id, new_val))
        db.commit()
        await query.edit_message_text(f"✅ Küfür Koruması güncellendi: {'AÇIK' if new_val==1 else 'KAPALI'}")
        
    elif data == "sys_info":
        await query.edit_message_text("📊 **v18.0 Full Engine**\n- Durum: Kararlı (Stabil)\n- Veritabanı: SQLite3\n- Modüller: Aktif", parse_mode="Markdown")

async def mesaj_takip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user or update.effective_chat.type == "private":
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.effective_message.text

    cursor.execute("SELECT message_count FROM messages WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE messages SET message_count = message_count + 1, username = ? WHERE chat_id = ? AND user_id = ?", (username, chat_id, user_id))
    else:
        cursor.execute("INSERT INTO messages (chat_id, user_id, username, message_count) VALUES (?, ?, ?, 1)", (chat_id, user_id, username))
    db.commit()

    if text:
        cursor.execute("SELECT word FROM filters_db WHERE chat_id = ?", (chat_id,))
        filtered_words = cursor.fetchall()
        for (f_word,) in filtered_words:
            if f_word.lower() in text.lower():
                try:
                    await update.effective_message.delete()
                except Exception:
                    pass
                return

        cursor.execute("SELECT reply FROM auto_replies WHERE chat_id = ? AND ? LIKE '%' || keyword || '%'", (chat_id, text))
        reply_row = cursor.fetchone()
        if reply_row:
            await update.message.reply_text(reply_row[0])

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cursor.execute("SELECT username, message_count FROM messages WHERE chat_id = ? ORDER BY message_count DESC LIMIT 10", (chat_id,))
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("📊 Henüz kayıtlı mesaj bulunmuyor.")
        return

    text = "🏆 **Grup Mesaj Sıralaması (v18.0 Full Skorboard)**\n\n"
    for i, (uname, count) in enumerate(rows, 1):
        text += f"{i}. **{uname}**: {count} mesaj\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def ban_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in GLOBAL_ADMINS:
        await update.message.reply_text("⛔ Yetkin yok!")
        return
    if not update.effective_message.reply_to_message:
        await update.message.reply_text("⚠️ Banlanacak kullanıcı mesajına yanıt vermelisin.")
        return
    target = update.effective_message.reply_to_message.from_user
    await update.effective_chat.ban_member(target.id)
    await update.message.reply_text(f"🔨 {target.first_name} yasaklandı!")

async def mute_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in GLOBAL_ADMINS:
        await update.message.reply_text("⛔ Yetkin yok!")
        return
    if not update.effective_message.reply_to_message:
        await update.message.reply_text("⚠️ Susturulacak kullanıcı mesajına yanıt vermelisin.")
        return
    target = update.effective_message.reply_to_message.from_user
    await update.effective_chat.restrict_member(target.id, permissions=ChatPermissions(can_send_messages=False))
    await update.message.reply_text(f"🔇 {target.first_name} susturuldu!")

async def warn_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in GLOBAL_ADMINS:
        await update.message.reply_text("⛔ Yetkin yok!")
        return
    if not update.effective_message.reply_to_message:
        await update.message.reply_text("⚠️ Uyarılacak kullanıcı mesajına yanıt vermelisin.")
        return
    target = update.effective_message.reply_to_message.from_user
    chat_id = update.effective_chat.id

    cursor.execute("SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?", (chat_id, target.id))
    row = cursor.fetchone()
    count = (row[0] + 1) if row else 1

    cursor.execute("INSERT OR REPLACE INTO warnings (chat_id, user_id, count) VALUES (?, ?, ?)", (chat_id, target.id, count))
    db.commit()

    await update.message.reply_text(f"⚠️ {target.first_name} uyarıldı! (Toplam: {count}/3)")
    if count >= 3:
        await update.effective_chat.ban_member(target.id)
        await update.message.reply_text(f"🚨 {target.first_name} 3 uyarı sınırını aştığı için banlandı!")

async def sil_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message.reply_to_message:
        await update.message.reply_text("⚠️ Silinecek mesaja yanıt vermelisin.")
        return
    await update.effective_message.reply_to_message.delete()
    await update.message.delete()

async def setnot_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Kullanım: `/setnot <anahtar> <içerik>`", parse_mode="Markdown")
        return
    chat_id = update.effective_chat.id
    keyword = context.args[0].lower()
    content = " ".join(context.args[1:])

    cursor.execute("INSERT OR REPLACE INTO notes (chat_id, keyword, content) VALUES (?, ?, ?)", (chat_id, keyword, content))
    db.commit()
    await update.message.reply_text(f"✅ '{keyword}' notu kaydedildi!")

async def not_getir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Kullanım: `/not <anahtar>`", parse_mode="Markdown")
        return
    chat_id = update.effective_chat.id
    keyword = context.args[0].lower()

    cursor.execute("SELECT content FROM notes WHERE chat_id = ? AND keyword = ?", (chat_id, keyword))
    row = cursor.fetchone()
    if row:
        await update.message.reply_text(f"📌 **Not ({keyword}):**\n\n{row[0]}", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Bu anahtarla kayıtlı not bulunamadı.")

async def setcevap_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Kullanım: `/setcevap <tetikleyici> <cevap>`", parse_mode="Markdown")
        return
    chat_id = update.effective_chat.id
    keyword = context.args[0].lower()
    reply = " ".join(context.args[1:])

    cursor.execute("INSERT OR REPLACE INTO auto_replies (chat_id, keyword, reply) VALUES (?, ?, ?)", (chat_id, keyword, reply))
    db.commit()
    await update.message.reply_text(f"✅ Oto-cevap eklendi: '{keyword}' tetiklendiğinde yanıt verilecek.")

async def duyuru_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in GLOBAL_ADMINS:
        await update.message.reply_text("⛔ Bu komutu sadece global yöneticiler kullanabilir!")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Kullanım: `/duyuru <mesaj>`", parse_mode="Markdown")
        return

    duyuru_metni = "📢 **GLOBAL DUYURU (v18.0)**\n\n" + " ".join(context.args)
    cursor.execute("SELECT DISTINCT chat_id FROM settings")
    chats = cursor.fetchall()
    
    success = 0
    for (c_id,) in chats:
        try:
            await context.bot.send_message(chat_id=c_id, text=duyuru_metni, parse_mode="Markdown")
            success += 1
        except Exception:
            pass

    await update.message.reply_text(f"✅ Duyuru başarıyla {success} gruba iletildi.")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("ayar", ayar_komutu))
    app.add_handler(CommandHandler("gunluk", leaderboard))
    app.add_handler(CommandHandler("haftalik", leaderboard))
    app.add_handler(CommandHandler("aylik", leaderboard))
    app.add_handler(CommandHandler("tum", leaderboard))
    app.add_handler(CommandHandler("ban", ban_komutu))
    app.add_handler(CommandHandler("mute", mute_komutu))
    app.add_handler(CommandHandler("warn", warn_komutu))
    app.add_handler(CommandHandler("sil", sil_komutu))
    app.add_handler(CommandHandler("setnot", setnot_komutu))
    app.add_handler(CommandHandler("not", not_getir))
    app.add_handler(CommandHandler("setcevap", setcevap_komutu))
    app.add_handler(CommandHandler("duyuru", duyuru_komutu))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_takip))

    print("Group Assistant v18.0 Full Engine Başlatılıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
