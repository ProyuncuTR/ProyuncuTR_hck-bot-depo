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
CREATE TABLE IF NOT EXISTS gruplar (
    chat_id INTEGER PRIMARY KEY,
    title TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS grup_ayarlari (
    chat_id INTEGER PRIMARY KEY,
    hosgeldin_mesaj TEXT DEFAULT 'Merhaba {kullanici}!\n\n**{grup}** grubuna hoş geldin! 🎉',
    hoscakal_mesaj TEXT DEFAULT 'Güle güle {kullanici}! 👋\n\n**{grup}** grubundan ayrıldı.',
    buton_aktif INTEGER DEFAULT 1,
    buton_yazisi TEXT DEFAULT '📢 Resmi Kanalımıza Katıl',
    buton_linki TEXT DEFAULT 'https://t.me/ProyuncuTR_hck'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS beklemedeki_islemler (
    user_id INTEGER PRIMARY KEY,
    chat_id INTEGER,
    islem TEXT
)
""")
conn.commit()

async def is_admin(user_id: int) -> bool:
    cursor.execute("SELECT user_id FROM oturumlar WHERE user_id = ? AND datetime(son_giris, '+24 hours') > datetime('now')", (user_id,))
    return cursor.fetchone() is not None

def get_grup_ayar(chat_id: int):
    cursor.execute("SELECT hosgeldin_mesaj, hoscakal_mesaj, buton_aktif, buton_yazisi, buton_linki FROM grup_ayarlari WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO grup_ayarlari (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
        return ('Merhaba {kullanici}!\n\n**{grup}** grubuna hoş geldin! 🎉', 'Güle güle {kullanici}! 👋\n\n**{grup}** grubundan ayrıldı.', 1, '📢 Resmi Kanalımıza Katıl', 'https://t.me/ProyuncuTR_hck')
    return row

def kaydet_grup(chat_id: int, title: str):
    if not title:
        title = f"Grup ({chat_id})"
    cursor.execute("INSERT INTO gruplar (chat_id, title) VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title", (chat_id, title))
    conn.commit()

async def bot_grup_durum_takibi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member and update.my_chat_member.chat:
        chat = update.my_chat_member.chat
        if chat.type in ["group", "supergroup"]:
            kaydet_grup(chat.id, chat.title)

async def uye_durum_takibi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    grup_adi = update.effective_chat.title or "Grubumuza"
    kaydet_grup(chat_id, grup_adi)
    
    hosgeldin_fmt, hoscakal_fmt, buton_aktif, b_yazisi, b_linki = get_grup_ayar(chat_id)
    
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
            keyboard = [[InlineKeyboardButton(b_yazisi, url=b_linki)]]
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
    metin_raw = update.message.text or ""
    metin = metin_raw.lower().strip()
    
    if update.effective_chat.type in ["group", "supergroup"]:
        kaydet_grup(chat_id, update.effective_chat.title)

    if metin == "grup ayarları":
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🔐 Yönetici Doğrulaması: Lütfen doğru kodu yazınız.\n\nÖrnek: `/kod 000000`",
                parse_mode="Markdown"
            )
            if update.effective_chat.type != "private":
                await update.message.reply_text("📩 DM mesajlarına bak! Ayar paneli özel mesaj üzerinden gönderildi.")
        except Exception:
            await update.message.reply_text("⚠️ Lütfen önce bota özelden (DM) `/start` yazarak mesaj gönderin.")
        return

    if update.effective_chat.type == "private" and await is_admin(user_id):
        cursor.execute("SELECT chat_id, islem FROM beklemedeki_islemler WHERE user_id = ?", (user_id,))
        bekleyen = cursor.fetchone()
        if bekleyen:
            target_chat_id, islem = bekleyen
            if islem == "set_hg":
                cursor.execute("UPDATE grup_ayarlari SET hosgeldin_mesaj = ? WHERE chat_id = ?", (metin_raw, target_chat_id))
                conn.commit()
                cursor.execute("DELETE FROM beklemedeki_islemler WHERE user_id = ?", (user_id,))
                conn.commit()
                await update.message.reply_text("✅ Hoş Geldin mesajı güncellendi!")
                return
            elif islem == "set_hk":
                cursor.execute("UPDATE grup_ayarlari SET hoscakal_mesaj = ? WHERE chat_id = ?", (metin_raw, target_chat_id))
                conn.commit()
                cursor.execute("DELETE FROM beklemedeki_islemler WHERE user_id = ?", (user_id,))
                conn.commit()
                await update.message.reply_text("✅ Hoşça Kal mesajı güncellendi!")
                return
            elif islem == "set_byazisi":
                cursor.execute("UPDATE grup_ayarlari SET buton_yazisi = ? WHERE chat_id = ?", (metin_raw, target_chat_id))
                conn.commit()
                cursor.execute("DELETE FROM beklemedeki_islemler WHERE user_id = ?", (user_id,))
                conn.commit()
                await update.message.reply_text("✅ Buton yazısı güncellendi!")
                return
            elif islem == "set_blink":
                cursor.execute("UPDATE grup_ayarlari SET buton_linki = ? WHERE chat_id = ?", (metin_raw, target_chat_id))
                conn.commit()
                cursor.execute("DELETE FROM beklemedeki_islemler WHERE user_id = ?", (user_id,))
                conn.commit()
                await update.message.reply_text("✅ Buton linki güncellendi!")
                return

    cursor.execute("""
    INSERT INTO mesajlar (chat_id, user_id, username, full_name, mesaj_sayisi)
    VALUES (?, ?, ?, ?, 1)
    ON CONFLICT(chat_id, user_id) DO UPDATE SET
        mesaj_sayisi = mesaj_sayisi + 1,
        username = excluded.username,
        full_name = excluded.full_name
    """, (chat_id, user_id, update.effective_user.username or "", update.effective_user.full_name or "Kullanıcı"))
    conn.commit()

async def cmd_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) > 0 and context.args[0] == ADMIN_KODU:
        cursor.execute("INSERT INTO oturumlar (user_id, son_giris) VALUES (?, CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET son_giris = CURRENT_TIMESTAMP", (user_id,))
        conn.commit()
        await send_grup_secim_menu(user_id, context)
    else:
        await update.message.reply_text("🔐 Yönetici Doğrulaması: Lütfen doğru kodu yazın. Örnek: `/kod 000000`", parse_mode="Markdown")

async def send_grup_secim_menu(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT chat_id, title FROM gruplar")
    rows = cursor.fetchall()
    
    if not rows:
        await context.bot.send_message(chat_id=user_id, text="⚠️ Kayıtlı grup bulunamadı.")
        return

    keyboard = []
    for cid, title in rows:
        keyboard.append([InlineKeyboardButton(f"👥 {title}", callback_data=f"sg_{cid}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=user_id,
        text="✅ Yönetici girişi başarılı!\n\n⚙️ **Ayar Yapmak İstediğiniz Grubu Seçin:**",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

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
    if not await is_admin(user_id):
        await query.edit_message_text("⚠️ Oturumunuzun süresi dolmuş. Lütfen tekrar `/kod` kullanın.")
        return

    data = query.data

    if data.startswith("sg_"):
        chat_id = int(data.replace("sg_", ""))
        await show_grup_panel(query, chat_id)
        
    elif data.startswith("tb_"):
        chat_id = int(data.replace("tb_", ""))
        _, _, b_aktif, _, _ = get_grup_ayar(chat_id)
        yeni_durum = 0 if b_aktif == 1 else 1
        cursor.execute("UPDATE grup_ayarlari SET buton_aktif = ? WHERE chat_id = ?", (yeni_durum, chat_id))
        conn.commit()
        await show_grup_panel(query, chat_id)
        
    elif data.startswith("ehg_"):
        chat_id = int(data.replace("ehg_", ""))
        cursor.execute("INSERT INTO beklemedeki_islemler (user_id, chat_id, islem) VALUES (?, ?, 'set_hg') ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id, islem = excluded.islem", (user_id, chat_id))
        conn.commit()
        await query.message.reply_text("✍️ Lütfen bu grup için yeni **Hoş Geldin** mesajını yazın:\n(Metinde `{kullanici}` ve `{grup}` kullanabilirsiniz)")

    elif data.startswith("ehk_"):
        chat_id = int(data.replace("ehk_", ""))
        cursor.execute("INSERT INTO beklemedeki_islemler (user_id, chat_id, islem) VALUES (?, ?, 'set_hk') ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id, islem = excluded.islem", (user_id, chat_id))
        conn.commit()
        await query.message.reply_text("✍️ Lütfen bu grup için yeni **Hoşça Kal** mesajını yazın:\n(Metinde `{kullanici}` ve `{grup}` kullanabilirsiniz)")

    elif data.startswith("eby_"):
        chat_id = int(data.replace("eby_", ""))
        cursor.execute("INSERT INTO beklemedeki_islemler (user_id, chat_id, islem) VALUES (?, ?, 'set_byazisi') ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id, islem = excluded.islem", (user_id, chat_id))
        conn.commit()
        await query.message.reply_text("✍️ Lütfen butonun üzerinde görünecek yeni **yazıyı** gönderin:")

    elif data.startswith("ebl_"):
        chat_id = int(data.replace("ebl_", ""))
        cursor.execute("INSERT INTO beklemedeki_islemler (user_id, chat_id, islem) VALUES (?, ?, 'set_blink') ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id, islem = excluded.islem", (user_id, chat_id))
        conn.commit()
        await query.message.reply_text("✍️ Lütfen butonun açacağı yeni **linki (URL)** gönderin:\n(Örn: `https://t.me/kanaliniz`)")

    elif data == "back_to_gruplar":
        cursor.execute("SELECT chat_id, title FROM gruplar")
        rows = cursor.fetchall()
        keyboard = []
        for cid, title in rows:
            keyboard.append([InlineKeyboardButton(f"👥 {title}", callback_data=f"sg_{cid}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("⚙️ **Ayar Yapmak İstediğiniz Grubu Seçin:**", reply_markup=reply_markup, parse_mode="Markdown")

async def show_grup_panel(query, chat_id: int):
    cursor.execute("SELECT title FROM gruplar WHERE chat_id = ?", (chat_id,))
    row_title = cursor.fetchone()
    title = row_title[0] if row_title else "Grup"
    
    _, _, b_aktif, b_yazisi, b_linki = get_grup_ayar(chat_id)
    durum_str = "AÇIK 🟢" if b_aktif == 1 else "KAPALI 🔴"
    
    keyboard = [
        [InlineKeyboardButton(f"🔘 Buton Durumu: {durum_str}", callback_data=f"tb_{chat_id}")],
        [InlineKeyboardButton("✏️ Hoş Geldin Mesajını Düzenle", callback_data=f"ehg_{chat_id}")],
        [InlineKeyboardButton("✏️ Hoşça Kal Mesajını Düzenle", callback_data=f"ehk_{chat_id}")],
        [InlineKeyboardButton(f"✏️ Buton Yazısı ({b_yazisi})", callback_data=f"eby_{chat_id}")],
        [InlineKeyboardButton("🔗 Buton Linkini Düzenle", callback_data=f"ebl_{chat_id}")],
        [InlineKeyboardButton("🔙 Grup Listesine Dön", callback_data="back_to_gruplar")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"⚙️ **{title}** Grubu Yönetim Paneli\n\n- Buton Linki: {b_linki}\n- Buton Yazısı: {b_yazisi}\n\nAşağıdaki butonlara tıklayarak istediğiniz ayarı değiştirebilirsiniz:"
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")

async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        kaydet_grup(update.effective_chat.id, update.effective_chat.title)
    await update.message.reply_text("🔄 Bot yeniden başlatıldı! Yönetici listesi ve veritabanı güncellendi!")

async def cmd_kurallar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📜 **Grup Kuralları:**\n1. Küfür ve hakaret yasaktır.\n2. Reklam ve link paylaşımı yasaktır.\n3. Saygılı olun.")

async def cmd_hakkinda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HAKKINDA_METNI, parse_mode="Markdown")

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
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
    if not await is_admin(update.effective_user.id):
        return
    if not update.message.reply_to_message:
        return
    target_user = update.message.reply_to_message.from_user
    cursor.execute("UPDATE uyarilar SET uyari_sayisi = 0 WHERE chat_id = ? AND user_id = ?", (update.effective_chat.id, target_user.id))
    conn.commit()
    await update.message.reply_text(f"✅ {target_user.mention_html()} uyarısı sıfırlandı.", parse_mode="HTML")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(update.effective_chat.id, target_user.id, permissions=ChatPermissions(can_send_messages=False))
        await update.message.reply_text(f"🤐 {target_user.mention_html()} susturuldu.", parse_mode="HTML")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(update.effective_chat.id, target_user.id, permissions=ChatPermissions(can_send_messages=True))
        await update.message.reply_text(f"🔊 {target_user.mention_html()} susturması kaldırıldı.", parse_mode="HTML")

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
        await update.message.reply_text(f"🚫 {target_user.mention_html()} gruptan yasaklandı.", parse_mode="HTML")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
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
        
    names = [row[0][:12] for row in rows]
    counts = [row[1] for row in rows]
    
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor('#121212')
    ax.set_facecolor('#1e1e1e')
    
    bars = ax.barh(names[::-1], counts[::-1], color='#00adb5', edgecolor='#393e46', height=0.6, linewidth=1.2)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#555555')
    ax.spines['bottom'].set_color('#555555')
    ax.tick_params(colors='#ffffff', labelsize=10)
    ax.grid(axis='x', linestyle='--', alpha=0.2, color='#aaaaaa')
    
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, f'{int(width)}', 
                va='center', ha='left', color='#00adb5', fontsize=10, fontweight='bold')

    plt.title('🏆 En Çok Mesaj Atanlar Sıralaması', fontsize=14, color='#eeeeee', pad=15, fontweight='bold')
    plt.xlabel('Mesaj Sayısı', fontsize=11, color='#cccccc')
    plt.tight_layout()
    
    chart_path = 'siralama.png'
    plt.savefig(chart_path, dpi=200, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    
    with open(chart_path, 'rb') as photo:
        await update.message.reply_photo(photo=photo, caption="📊 **Güncel Mesaj Sıralaması Grafiği**", parse_mode="Markdown")

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        TOKEN = "8823945672:AAHnfiT2s2PR3Vt4o_8xD6ro3tgrs5T1RMk"
        
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(ChatMemberHandler(bot_grup_durum_takibi, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(uye_durum_takibi, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, uye_durum_takibi))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, uye_durum_takibi))

    app.add_handler(CommandHandler("kod", cmd_kod))
    app.add_handler(CommandHandler("panel", cmd_panel))
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
    app.run_polling(allowed_updates=["chat_member", "my_chat_member", "message", "callback_query"])

if __name__ == "__main__":
    main()
