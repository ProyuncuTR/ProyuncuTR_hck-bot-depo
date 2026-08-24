import os
import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ChatMemberHandler, CallbackQueryHandler, filters, ContextTypes
)

# --- AYARLAR ---
ADMIN_KODU = "890678"
BUTONLU_GRUPLAR = ["@ProyuncuTR_hck"]
KANAL_LINKI = "https://t.me/ProyuncuTR_hck"
BUTON_YAZISI = "📢 Resmi Kanalımıza Katıl"
HAKKINDA_METNI = "🤖 **ProyuncuTR_hck Chat Bot**\nVersion v1.3\nBy @ProyuncuTR\n2026 ProyuncuTR_hck chat bot"

# --- VERİTABANI KURULUMU ---
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
conn.commit()

# --- YARDIMCI FONKSİYONLAR ---
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    cursor.execute("SELECT user_id FROM oturumlar WHERE user_id = ? AND datetime(son_giris, '+24 hours') > datetime('now')", (user_id,))
    if cursor.fetchone():
        return True
    chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
    return chat_member.status in ["administrator", "creator"]

# --- HOŞ GELDİN VE HOŞÇA KAL SİSTEMİ ---
async def uye_durum_takibi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    grup_adi = update.effective_chat.title or "Grubumuza"
    chat_username = update.effective_chat.username
    
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
        mesaj = f"Merhaba {kullanici_adi}!\n\n**{grup_adi}** grubuna hoş geldin! 🎉"
        
        reply_markup = None
        if chat_username and f"@{chat_username}" in BUTONLU_GRUPLAR:
            keyboard = [[InlineKeyboardButton(BUTON_YAZISI, url=KANAL_LINKI)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
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
        gule_gule_mesaji = f"Güle güle {kullanici_adi}! 👋\n\n**{grup_adi}** grubundan ayrıldı."
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=gule_gule_mesaji,
            parse_mode="HTML"
        )

# --- MESAJ TAKİBİ ---
async def mesaj_takip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or update.effective_user.is_bot:
        return
        
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    full_name = update.effective_user.full_name or "Kullanıcı"
    
    cursor.execute("""
    INSERT INTO mesajlar (chat_id, user_id, username, full_name, mesaj_sayisi)
    VALUES (?, ?, ?, ?, 1)
    ON CONFLICT(chat_id, user_id) DO UPDATE SET
        mesaj_sayisi = mesaj_sayisi + 1,
        username = excluded.username,
        full_name = excluded.full_name
    """, (chat_id, user_id, username, full_name))
    conn.commit()

# --- KOMUTLAR ---
async def cmd_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) > 0 and context.args[0] == ADMIN_KODU:
        cursor.execute("INSERT OR REPLACE INTO oturumlar (user_id) VALUES (?)", (user_id,))
        conn.commit()
        await update.message.reply_text("✅ Yönetici doğrulaması başarılı! 24 saatlik oturum açıldı.")
    else:
        await update.message.reply_text("🔐 Yönetici Doğrulaması: Lütfen doğru kodu yazın. Örnek: `/kod 890678`", parse_mode="Markdown")

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

# --- MAIN ---
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        TOKEN = "YOUR_BOT_TOKEN_HERE"
        
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(ChatMemberHandler(uye_durum_takibi, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, uye_durum_takibi))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, uye_durum_takibi))

    app.add_handler(CommandHandler("kod", cmd_kod))
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

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_takip))

    print("Bulut Sunucu Botu Başarıyla Çalışıyor!")
    app.run_polling(allowed_updates=["chat_member", "message"])

if __name__ == "__main__":
    main()
