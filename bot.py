import os
import sqlite3
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ChatMemberHandler, CallbackQueryHandler, filters, ContextTypes
)

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Aktif")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

ADMIN_KODU = "57000"
KANAL_LINKI = "https://t.me/ProyuncuTR_hck"
BUTON_YAZISI = "📢 Resmi Kanalımıza Katıl"
HAKKINDA_METNI = "🤖 **ProyuncuTR_hck Chat Bot**\nVersion v1.3\nBy @ProyuncuTR\n2026 ProyuncuTR_hck chat bot"

conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS mesajlar (
    chat_id INTEGER,
    user_id INTEGER,
    username TEXT,
    full_name TEXT,
    mesaj_sayisi INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS uyarilar (
    chat_id INTEGER,
    user_id INTEGER,
    uyari_sayisi INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS oturumlar (
    user_id INTEGER PRIMARY KEY,
    son_giris TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS grup_ayarlari (
    chat_id INTEGER PRIMARY KEY,
    hosgeldin_mesaj TEXT DEFAULT 'Merhaba {kullanici}!\n\n**{grup}** grubuna hoş geldin! 🎉',
    hoscakal_mesaj TEXT DEFAULT 'Güle güle {kullanici}! 👋\n\n**{grup}** grubundan ayrıldı.',
    buton_aktif INTEGER DEFAULT 1
)
""")
conn.commit()

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    cursor.execute("SELECT user_id FROM oturumlar WHERE user_id = ? AND datetime(son_giris, '+24 hours') > datetime('now')", (user_id,))
    if cursor.fetchone():
        return True
    if update.effective_chat:
        chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
        return chat_member.status in ["administrator", "creator"]
    return False

def get_grup_ayar(chat_id: int):
    cursor.execute("SELECT hosgeldin_mesaj, hoscakal_mesaj, buton_aktif FROM grup_ayarlari WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO grup_ayarlari (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
        return ('Merhaba {kullanici}!\n\n**{grup}** grubuna hoş geldin! 🎉', 'Güle güle {kullanici}! 👋\n\n**{grup}** grubundan ayrıldı.', 1)
    return row

async def uye_durum_takibi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    grup_adi = update.effective_chat.title or "Grubumuza"
    hosgeldin_fmt, hoscakal_fmt, buton_aktif = get_grup_ayar(chat_id)
    
    uye_geldi = False
    kullanici = None
    
    if update.message and update.message.new_chat_members:
        for u in update.message.new_chat_members:
            if not u.is_bot:
                uye_geldi = True
                kullanici = u
                break
    elif update.chat_member:
        eski = update.chat_member.old_chat_member.status
        yeni = update.chat_member.new_chat_member.status
        if eski in ["left", "kicked"] and yeni in ["member", "administrator"]:
            if not update.chat_member.new_chat_member.user.is_bot:
                uye_geldi = True
                kullanici = update.chat_member.new_chat_member.user

    if uye_geldi and kullanici:
        kullanici_adi = kullanici.mention_html()
        mesaj = hosgeldin_fmt.replace("{kullanici}", kullanici_adi).replace("{grup}", grup_adi)
        
        reply_markup = None
        if buton_aktif == 1:
            keyboard = [[InlineKeyboardButton(BUTON_YAZISI, url=KANAL_LINKI)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
        await context.bot.send_message(
            chat_id=chat_id,
            text=mesaj,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return

    uye_gitti = False
    ayrilan_kullanici = None
    
    if update.message and update.message.left_chat_member:
        if not update.message.left_chat_member.is_bot:
            uye_gitti = True
            ayrilan_kullanici = update.message.left_chat_member
    elif update.chat_member:
        eski = update.chat_member.old_chat_member.status
        yeni = update.chat_member.new_chat_member.status
        if eski in ["member", "administrator"] and yeni in ["left", "kicked"]:
            if not update.chat_member.new_chat_member.user.is_bot:
                uye_gitti = True
                ayrilan_kullanici = update.chat_member.new_chat_member.user

    if uye_gitti and ayrilan_kullanici:
        kullanici_adi = ayrilan_kullanici.mention_html()
        gule_gule_mesaji = hoscakal_fmt.replace("{kullanici}", kullanici_adi).replace("{grup}", grup_adi)
        await context.bot.send_message(
            chat_id=chat_id,
            text=gule_gule_mesaji,
            parse_mode="HTML"
        )

async def mesaj_takip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or update.effective_user.is_bot:
        return
        
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    full_name = update.effective_user.full_name or "Kullanıcı"
    metin = update.message.text.lower().strip() if update.message.text else ""
    
    if metin == "grup ayarları":
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🔐 Yönetici Doğrulaması: Lütfen doğru kodu yazınız.\n\nÖrnek: `/kod 000000`",
                parse_mode="Markdown"
            )
            await update.message.reply_text("📩 DM mesajlarına bak! Ayar paneli özel mesaj üzerinden gönderildi.")
        except Exception:
            await update.message.reply_text("⚠️ Lütfen önce bota özelden (DM) `/start` yazarak mesaj gönderin.")
        return

    cursor.execute("""
    INSERT INTO mesajlar (chat_id, user_id, username, full_name, mesaj_sayisi)
    VALUES (?, ?, ?, ?, 1)
    ON CONFLICT(chat_id, user_id) DO UPDATE SET
        mesaj_sayisi = mesaj_sayisi + 1,
        username = excluded.username,
        full_name = excluded.full_name
    """, (chat_id, user_id, username, full_name))
    conn.commit()

async def cmd_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) > 0 and context.args[0] == ADMIN_KODU:
        cursor.execute("INSERT INTO oturumlar (user_id, son_giris) VALUES (?, CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET son_giris = CURRENT_TIMESTAMP", (user_id,))
        conn.commit()
        
        keyboard = [
            [InlineKeyboardButton("📢 Kanal Butonu Durumu", callback_data="toggle_button")],
            [InlineKeyboardButton("📝 Hoş Geldin Mesajı Değiştir", callback_data="info_hg")],
            [InlineKeyboardButton("📝 Hoşça Kal Mesajı Değiştir", callback_data="info_hk")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✅ Yönetici doğrulaması başarılı! 24 saatlik oturum açıldı.\n\n⚙️ **Grup Yönetim Paneli**", reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text("🔐 Yönetici Doğrulaması: Lütfen doğru kodu yazın. Örnek: `/kod 000000`", parse_mode="Markdown")

async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="🔐 Yönetici Doğrulaması: Lütfen doğru kodu yazınız.\n\nÖrnek: `/kod 000000`",
            parse_mode="Markdown"
        )
        if update.effective_chat.type != "private":
            await update.message.reply_text("📩 DM mesajlarına bak! Ayar paneli özel mesaj üzerinden gönderildi.")
    except Exception:
        await update.message.reply_text("⚠️ Lütfen önce bota özelden (DM) `/start` yazarak mesaj başlatın.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    cursor.execute("SELECT user_id FROM oturumlar WHERE user_id = ? AND datetime(son_giris, '+24 hours') > datetime('now')", (user_id,))
    if not cursor.fetchone():
        await query.edit_message_text("⚠️ Oturumunuzun süresi dolmuş. Lütfen tekrar `/kod` kullanın.")
        return

    chat_id = query.message.chat_id
    _, _, buton_aktif = get_grup_ayar(chat_id)

    if query.data == "toggle_button":
        yeni_durum = 0 if buton_aktif == 1 else 1
        cursor.execute("UPDATE grup_ayarlari SET buton_aktif = ? WHERE chat_id = ?", (yeni_durum, chat_id))
        conn.commit()
        
        durum_str = "AÇIK 🟢" if yeni_durum == 1 else "KAPALI 🔴"
        keyboard = [
            [InlineKeyboardButton(f"Kanal Butonu: {durum_str}", callback_data="toggle_button")],
            [InlineKeyboardButton("📝 Hoş Geldin Mesajı Değiştir", callback_data="info_hg")],
            [InlineKeyboardButton("📝 Hoşça Kal Mesajı Değiştir", callback_data="info_hk")]
        ]
        await query.edit_message_text("⚙️ **Grup Yönetim Paneli**\n\nKanal butonu durumu güncellendi!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "info_hg":
        await query.message.reply_text("💡 Hoş geldin mesajını değiştirmek için komut kullanımı:\n`/hosgeldin_set Merhaba {kullanici}! {grup} grubuna hoş geldin.`", parse_mode="Markdown")
    elif query.data == "info_hk":
        await query.message.reply_text("💡 Hoşça kal mesajını değiştirmek için komut kullanımı:\n`/hoscakal_set Güle güle {kullanici}! {grup} grubundan ayrıldı.`", parse_mode="Markdown")

async def cmd_set_hosgeldin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    yeni_metin = " ".join(context.args)
    if not yeni_metin:
        await update.message.reply_text("Lütfen yeni metni yazın. Örnek:\n`/hosgeldin_set Merhaba {kullanici}! {grup} grubuna hoş geldin.`", parse_mode="Markdown")
        return
    cursor.execute("UPDATE grup_ayarlari SET hosgeldin_mesaj = ? WHERE chat_id = ?", (yeni_metin, update.effective_chat.id))
    conn.commit()
    await update.message.reply_text("✅ Bu grubun karşılama mesajı başarıyla güncellendi!")

async def cmd_set_hoscakal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    yeni_metin = " ".join(context.args)
    if not yeni_metin:
        await update.message.reply_text("Lütfen yeni metni yazın. Örnek:\n`/hoscakal_set Güle güle {kullanici}! {grup} grubundan ayrıldı.`", parse_mode="Markdown")
        return
    cursor.execute("UPDATE grup_ayarlari SET hoscakal_mesaj = ? WHERE chat_id = ?", (yeni_metin, update.effective_chat.id))
    conn.commit()
    await update.message.reply_text("✅ Bu grubun uğurlama mesajı başarıyla güncellendi!")

async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Bot sistemi aktif ve pürüzsüz çalışıyor!")

async def cmd_kurallar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📜 **Grup Kuralları:**\n1. Küfür ve hakaret yasaktır.\n2. Reklam ve link paylaşımı yasaktır.\n3. Saygılı olun.")

async def cmd_hakkinda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HAKKINDA_METNI, parse_mode="Markdown")

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Lütfen uyarmak istediğiniz kullanıcının mesajını yanıtlayın.")
        return
    
    target_user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    
    cursor.execute("""
    INSERT INTO uyarilar (chat_id, user_id, uyari_sayisi)
    VALUES (?, ?, 1)
    ON CONFLICT(chat_id, user_id) DO UPDATE SET uyari_sayisi = uyari_sayisi + 1
    """, (chat_id, target_user.id))
    conn.commit()
    
    cursor.execute("SELECT uyari_sayisi FROM uyarilar WHERE chat_id = ? AND user_id = ?", (chat_id, target_user.id))
    sayi = cursor.fetchone()[0]
    
    if sayi >= 3:
        await context.bot.ban_chat_member(chat_id, target_user.id)
        await update.message.reply_text(f"🚫 {target_user.mention_html()} 3 uyarı aldığı için gruptan yasaklandı!", parse_mode="HTML")
    else:
        await update.message.reply_text(f"⚠️ {target_user.mention_html()} uyarıldı! (Toplam: {sayi}/3)", parse_mode="HTML")

async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        return
    target_user = update.message.reply_to_message.from_user
    cursor.execute("UPDATE uyarilar SET uyari_sayisi = 0 WHERE chat_id = ? AND user_id = ?", (update.effective_chat.id, target_user.id))
    conn.commit()
    await update.message.reply_text(f"✅ {target_user.mention_html()} uyarısı sıfırlandı.", parse_mode="HTML")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(update.effective_chat.id, target_user.id, permissions=ChatPermissions(can_send_messages=False))
        await update.message.reply_text(f"🤐 {target_user.mention_html()} susturuldu.", parse_mode="HTML")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(update.effective_chat.id, target_user.id, permissions=ChatPermissions(can_send_messages=True))
        await update.message.reply_text(f"🔊 {target_user.mention_html()} susturması kaldırıldı.", parse_mode="HTML")

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
        await update.message.reply_text(f"🚫 {target_user.mention_html()} gruptan yasaklandı.", parse_mode="HTML")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        await context.bot.unban_chat_member(update.effective_chat.id, target_user.id)
        await update.message.reply_text(f"✅ {target_user.mention_html()} yasağı kaldırıldı.", parse_mode="HTML")

async def cmd_siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cursor.execute("SELECT full_name, mesaj_sayisi FROM mesajlar WHERE chat_id = ? ORDER BY mesaj_sayisi DESC LIMIT 10", (chat_id,))
    rows = cursor.fetchall()
    
    if not rows:
        await update.message.reply_text("Henüz mesaj kaydı bulunmuyor.")
        return
        
    metin = "🏆 **En Çok Mesaj Atanlar Sıralaması:**\n\n"
    for idx, (name, count) in enumerate(rows, start=1):
        metin += f"{idx}. {name} - {count} mesaj\n"
        
    await update.message.reply_text(metin, parse_mode="Markdown")

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        TOKEN = "8823945672:AAHnfiT2s2PR3Vt4o_8xD6ro3tgrs5T1RMk"
        
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(ChatMemberHandler(uye_durum_takibi, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, uye_durum_takibi))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, uye_durum_takibi))

    app.add_handler(CommandHandler("kod", cmd_kod))
    app.add_handler(CommandHandler("panel", cmd_panel))
    app.add_handler(CommandHandler("hosgeldin_set", cmd_set_hosgeldin))
    app.add_handler(CommandHandler("hoscakal_set", cmd_set_hoscakal))
    app.add_handler(CommandHandler("reload", cmd_reload))
    app.add_handler(CommandHandler("kurallar", cmd_kurallar))
    app.add_handler(CommandHandler("hakkinda", cmd_hakkinda))
    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("unwarn", cmd_unwarn))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler(["tum", "siralama", "gunluk", "haftalik", "aylik"], cmd_siralama))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_takip))

    print("Bulut Sunucu Botu Başarıyla Çalışıyor!")
    app.run_polling(allowed_updates=["chat_member", "message", "callback_query"])

if __name__ == "__main__":
    main()
