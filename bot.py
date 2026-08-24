import os
import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ChatMemberHandler, CallbackQueryHandler, filters, ContextTypes
)

ADMIN_KODU = "892000"
BOT_USERNAME = "@Group_Assistant_offical_bot"
HAKKINDA_METNI = f"🤖 **Group Assistant**\nOfficial Bot: {BOT_USERNAME}\nAdvanced Group Management & Security Bot\nVersion v10.4 (Webhook)"

user_last_message_time = {}

conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()

# Tablolar
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER UNIQUE,
    title TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS grup_notlari (
    chat_id INTEGER,
    not_adi TEXT,
    not_icerik TEXT,
    PRIMARY KEY (chat_id, not_adi)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS grup_ayarlari (
    chat_id INTEGER PRIMARY KEY,
    hosgeldin_mesaj TEXT DEFAULT 'Merhaba {kullanici}!\n\n**{grup}** grubuna hoş geldin! 🎉',
    hoscakal_mesaj TEXT DEFAULT 'Güle güle {kullanici}! 👋\n\n**{grup}** grubundan ayrıldı.',
    buton_aktif INTEGER DEFAULT 1,
    buton_yazisi TEXT DEFAULT '📢 Resmi Kanalımıza Katıl',
    buton_linki TEXT DEFAULT 'https://t.me/ProyuncuTR_hck',
    antispam INTEGER DEFAULT 1,
    kufur_filtresi INTEGER DEFAULT 1,
    lock_links INTEGER DEFAULT 0,
    lock_media INTEGER DEFAULT 0,
    lock_stickers INTEGER DEFAULT 0
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
    chat_id = int(chat_id)
    cursor.execute("SELECT hosgeldin_mesaj, hoscakal_mesaj, buton_aktif, buton_yazisi, buton_linki, antispam, kufur_filtresi, lock_links, lock_media, lock_stickers FROM grup_ayarlari WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO grup_ayarlari (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
        return ('Merhaba {kullanici}!\n\n**{grup}** grubuna hoş geldin! 🎉', 'Güle güle {kullanici}! 👋\n\n**{grup}** grubundan ayrıldı.', 1, '📢 Resmi Kanalımıza Katıl', 'https://t.me/ProyuncuTR_hck', 1, 1, 0, 0, 0)
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
    
    hosgeldin_fmt, hoscakal_fmt, buton_aktif, b_yazisi, b_linki, _, _, _, _, _ = get_grup_ayar(chat_id)
    
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
            
        await context.bot.send_message(chat_id=chat_id, text=mesaj, parse_mode="HTML", reply_markup=reply_markup)
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
        await context.bot.send_message(chat_id=chat_id, text=gule_gule_mesaji, parse_mode="HTML")

async def mesaj_takip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or update.effective_user.is_bot:
        return
        
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id
    full_name = user.full_name or "Kullanıcı"
    username = user.username or ""
    
    if update.effective_chat.type in ["group", "supergroup"]:
        kaydet_grup(chat_id, update.effective_chat.title)
        
        _, _, _, _, _, antispam_aktif, kufur_aktif, lock_links, lock_media, lock_stickers = get_grup_ayar(chat_id)
        
        if antispam_aktif == 1:
            import time
            current_time = time.time()
            key = (chat_id, user_id)
            if key in user_last_message_time:
                if current_time - user_last_message_time[key] < 1.0:
                    try:
                        await update.message.delete()
                        return
                    except Exception:
                        pass
            user_last_message_time[key] = current_time

        if lock_media == 1 and (update.message.photo or update.message.video or update.message.document):
            try:
                await update.message.delete()
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {user.mention_html()}, bu grupta medya paylaşımı yasaktır!", parse_mode="HTML")
                return
            except Exception:
                pass

        if lock_stickers == 1 and (update.message.sticker or update.message.animation):
            try:
                await update.message.delete()
                return
            except Exception:
                pass

        metin_raw = update.message.text or update.message.caption or ""
        metin = metin_raw.lower().strip()

        if lock_links == 1 and ("http://" in metin or "https://" in metin or "t.me/" in metin):
            try:
                await update.message.delete()
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {user.mention_html()}, bu grupta link paylaşımı yasaktır!", parse_mode="HTML")
                return
            except Exception:
                pass

        yasakli_kelimeler = ["amk", "aq", "orospu", "sik", "anan", "piç"]
        if kufur_aktif == 1 and any(k in metin for k in yasakli_kelimeler):
            try:
                await update.message.delete()
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {user.mention_html()}, küfür etmek yasaktır!", parse_mode="HTML")
                return
            except Exception:
                pass

    else:
        metin_raw = update.message.text or ""
        metin = metin_raw.lower().strip()

    if metin == "grup ayarları":
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🔐 **Group Assistant Yönetici Doğrulaması:**\n\nÖrnek: `/kod 892000`",
                parse_mode="Markdown"
            )
            if update.effective_chat.type != "private":
                await update.message.reply_text("📩 DM mesajlarına bak! Ayar paneli özel mesaj üzerinden gönderildi.")
        except Exception:
            await update.message.reply_text("⚠️ Lütfen önce bota özelden (DM) `/start` yazarak başlatın.")
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

    if update.effective_chat.type in ["group", "supergroup"]:
        cursor.execute("""
        INSERT INTO mesajlar (chat_id, user_id, username, full_name, mesaj_sayisi)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(chat_id, user_id) DO UPDATE SET
            mesaj_sayisi = mesaj_sayisi + 1,
            username = excluded.username,
            full_name = excluded.full_name
        """, (chat_id, user_id, username, full_name))
        conn.commit()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("➕ Beni Gruba Ekle", url=f"https://t.me/{BOT_USERNAME.replace('@','')}?startgroup=true")],
        [InlineKeyboardButton("⚙️ Yönetim Paneli", callback_data="start_panel_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🤖 **Group Assistant**\n\n"
        f"Merhaba **{user.full_name}**! Ben profesyonel bir grup yönetim ve koruma asistanıyım.\n\n"
        f"• Gelişmiş Anti-Spam ve Küfür Koruması\n"
        f"• Medya, Sticker ve Link Filtreleri\n"
        f"• Özel Notlar ve Detaylı Liderlik İstatistikleri\n\n"
        f"Beni grubunuza ekleyip **Yönetici** yaparak hemen kullanmaya başlayabilirsiniz."
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def cmd_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) > 0 and context.args[0] == ADMIN_KODU:
        cursor.execute("INSERT INTO oturumlar (user_id, son_giris) VALUES (?, CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET son_giris = CURRENT_TIMESTAMP", (user_id,))
        conn.commit()
        await send_grup_secim_menu(user_id, context)
    else:
        await update.message.reply_text("🔐 **Yönetici Doğrulaması:** Lütfen doğru kodu yazın.\nÖrnek: `/kod 892000`", parse_mode="Markdown")

async def send_grup_secim_menu(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT id, title FROM gruplar")
    rows = cursor.fetchall()
    
    if not rows:
        await context.bot.send_message(chat_id=user_id, text="⚠️ Kayıtlı grup bulunamadı. Botun olduğu grupta `/reload` yazın.")
        return

    keyboard = []
    for internal_id, title in rows:
        keyboard.append([InlineKeyboardButton(f"👥 {title}", callback_data=f"grup_{internal_id}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=user_id,
        text="⚙️ **Yönetim Paneli**\n\nAyar yapmak istediğiniz grubu seçin:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="🔐 **Yönetici Doğrulaması:**\n\nÖrnek: `/kod 892000`",
            parse_mode="Markdown"
        )
        if update.effective_chat.type != "private":
            await update.message.reply_text("📩 Ayar paneli özel mesaj (DM) üzerinden gönderildi.")
    except Exception:
        await update.message.reply_text("⚠️ Lütfen önce bota özelden (DM) `/start` yazarak sohbeti başlatın.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data

    if data == "start_panel_info":
        await query.message.reply_text("💡 Ayar paneline erişmek için `/panel` komutunu yazıp ardından `/kod 892000` kullanabilirsiniz.")
        return

    if not await is_admin(user_id):
        await query.edit_message_text("⚠️ Oturum süresi dolmuş. Lütfen tekrar `/kod 892000` kullanın.")
        return

    try:
        if data.startswith("grup_"):
            internal_id = int(data.replace("grup_", ""))
            cursor.execute("SELECT chat_id FROM gruplar WHERE id = ?", (internal_id,))
            row = cursor.fetchone()
            if row:
                await show_grup_panel(query, row[0])
            else:
                await query.edit_message_text("⚠️ Grup veritabanında bulunamadı.")
            
        elif data.startswith("tb_"):
            chat_id = int(data.replace("tb_", ""))
            _, _, b_aktif, _, _, _, _, _, _, _ = get_grup_ayar(chat_id)
            yeni_durum = 0 if b_aktif == 1 else 1
            cursor.execute("UPDATE grup_ayarlari SET buton_aktif = ? WHERE chat_id = ?", (yeni_durum, chat_id))
            conn.commit()
            await show_grup_panel(query, chat_id)

        elif data.startswith("tkufur_"):
            chat_id = int(data.replace("tkufur_", ""))
            _, _, _, _, _, _, kufur_aktif, _, _, _ = get_grup_ayar(chat_id)
            yeni_durum = 0 if kufur_aktif == 1 else 1
            cursor.execute("UPDATE grup_ayarlari SET kufur_filtresi = ? WHERE chat_id = ?", (yeni_durum, chat_id))
            conn.commit()
            await show_grup_panel(query, chat_id)

        elif data.startswith("tlink_"):
            chat_id = int(data.replace("tlink_", ""))
            _, _, _, _, _, _, _, link_aktif, _, _ = get_grup_ayar(chat_id)
            yeni_durum = 0 if link_aktif == 1 else 1
            cursor.execute("UPDATE grup_ayarlari SET lock_links = ? WHERE chat_id = ?", (yeni_durum, chat_id))
            conn.commit()
            await show_grup_panel(query, chat_id)

        elif data.startswith("tmedia_"):
            chat_id = int(data.replace("tmedia_", ""))
            _, _, _, _, _, _, _, _, medya_aktif, _ = get_grup_ayar(chat_id)
            yeni_durum = 0 if medya_aktif == 1 else 1
            cursor.execute("UPDATE grup_ayarlari SET lock_media = ? WHERE chat_id = ?", (yeni_durum, chat_id))
            conn.commit()
            await show_grup_panel(query, chat_id)

        elif data.startswith("tsticker_"):
            chat_id = int(data.replace("tsticker_", ""))
            _, _, _, _, _, _, _, _, _, sticker_aktif = get_grup_ayar(chat_id)
            yeni_durum = 0 if sticker_aktif == 1 else 1
            cursor.execute("UPDATE grup_ayarlari SET lock_stickers = ? WHERE chat_id = ?", (yeni_durum, chat_id))
            conn.commit()
            await show_grup_panel(query, chat_id)
            
        elif data.startswith("ehg_"):
            chat_id = int(data.replace("ehg_", ""))
            cursor.execute("INSERT INTO beklemedeki_islemler (user_id, chat_id, islem) VALUES (?, ?, 'set_hg') ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id, islem = excluded.islem", (user_id, chat_id))
            conn.commit()
            await query.message.reply_text("✍️ Yeni **Hoş Geldin** mesajını gönderin:\n(`{kullanici}` ve `{grup}` kullanabilirsiniz)")

        elif data.startswith("ehk_"):
            chat_id = int(data.replace("ehk_", ""))
            cursor.execute("INSERT INTO beklemedeki_islemler (user_id, chat_id, islem) VALUES (?, ?, 'set_hk') ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id, islem = excluded.islem", (user_id, chat_id))
            conn.commit()
            await query.message.reply_text("✍️ Yeni **Hoşça Kal** mesajını gönderin:")

        elif data.startswith("eby_"):
            chat_id = int(data.replace("eby_", ""))
            cursor.execute("INSERT INTO beklemedeki_islemler (user_id, chat_id, islem) VALUES (?, ?, 'set_byazisi') ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id, islem = excluded.islem", (user_id, chat_id))
            conn.commit()
            await query.message.reply_text("✍️ Buton üzerinde görünecek yeni yazıyı gönderin:")

        elif data.startswith("ebl_"):
            chat_id = int(data.replace("ebl_", ""))
            cursor.execute("INSERT INTO beklemedeki_islemler (user_id, chat_id, islem) VALUES (?, ?, 'set_blink') ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id, islem = excluded.islem", (user_id, chat_id))
            conn.commit()
            await query.message.reply_text("✍️ Buton için yeni web linkini (URL) gönderin:")

        elif data == "back_to_gruplar":
            cursor.execute("SELECT id, title FROM gruplar")
            rows = cursor.fetchall()
            keyboard = []
            for internal_id, title in rows:
                keyboard.append([InlineKeyboardButton(f"👥 {title}", callback_data=f"grup_{internal_id}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("⚙️ **Yönetim Paneli**\n\nAyar yapmak istediğiniz grubu seçin:", reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        await context.bot.send_message(chat_id=user_id, text=f"❌ Hata: {str(e)}")

async def show_grup_panel(query, chat_id: int):
    cursor.execute("SELECT title FROM gruplar WHERE chat_id = ?", (chat_id,))
    row_title = cursor.fetchone()
    title = row_title[0] if row_title else "Grup"
    
    _, _, b_aktif, b_yazisi, b_linki, _, kufur_aktif, link_aktif, medya_aktif, sticker_aktif = get_grup_ayar(chat_id)
    durum_str = "AÇIK 🟢" if b_aktif == 1 else "KAPALI 🔴"
    kufur_str = "AÇIK 🟢" if kufur_aktif == 1 else "KAPALI 🔴"
    link_str = "AÇIK 🟢" if link_aktif == 1 else "KAPALI 🔴"
    medya_str = "AÇIK 🟢" if medya_aktif == 1 else "KAPALI 🔴"
    sticker_str = "AÇIK 🟢" if sticker_aktif == 1 else "KAPALI 🔴"
    
    keyboard = [
        [InlineKeyboardButton(f"🔘 Hoş Geldin Butonu: {durum_str}", callback_data=f"tb_{chat_id}")],
        [InlineKeyboardButton(f"🛡️ Küfür Filtresi: {kufur_str}", callback_data=f"tkufur_{chat_id}")],
        [InlineKeyboardButton(f"🔗 Link Engeli: {link_str}", callback_data=f"tlink_{chat_id}")],
        [InlineKeyboardButton(f"🖼️ Medya Engeli: {medya_str}", callback_data=f"tmedia_{chat_id}")],
        [InlineKeyboardButton(f"🎭 Sticker Engeli: {sticker_str}", callback_data=f"tsticker_{chat_id}")],
        [InlineKeyboardButton("✏️ Hoş Geldin Mesajını Düzenle", callback_data=f"ehg_{chat_id}")],
        [InlineKeyboardButton("✏️ Hoşça Kal Mesajını Düzenle", callback_data=f"ehk_{chat_id}")],
        [InlineKeyboardButton(f"✏️ Buton Yazısı ({b_yazisi})", callback_data=f"eby_{chat_id}")],
        [InlineKeyboardButton("🔗 Buton Linkini Düzenle", callback_data=f"ebl_{chat_id}")],
        [InlineKeyboardButton("🔙 Grup Listesine Dön", callback_data="back_to_gruplar")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"⚙️ **{title}** - Grup Yönetim Paneli\n\n- Buton Link: {b_linki}\n- Buton Yazı: {b_yazisi}"
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")

async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        kaydet_grup(update.effective_chat.id, update.effective_chat.title)
    await update.message.reply_text("🔄 Grup verileri ve bot durumu tazelendi.")

async def cmd_kurallar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📜 **Grup Kuralları:**\n1. Küfür, hakaret ve argo yasaktır.\n2. İzinsiz reklam ve link paylaşımı yasaktır.\n3. Herkese saygılı olun.")

async def cmd_hakkinda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HAKKINDA_METNI, parse_mode="Markdown")

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    chat = update.effective_chat
    await update.message.reply_text(f"👤 **Kullanıcı:** {user.full_name}\n🆔 **User ID:** `{user.id}`\n💬 **Chat ID:** `{chat.id}`", parse_mode="Markdown")

# Not Sistemi
async def cmd_setnot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Kullanım: `/setnot <not_adı> <içerik>`")
        return
    not_adi = context.args[0].lower()
    not_icerik = " ".join(context.args[1:])
    chat_id = update.effective_chat.id
    
    cursor.execute("INSERT INTO grup_notlari (chat_id, not_adi, not_icerik) VALUES (?, ?, ?) ON CONFLICT(chat_id, not_adi) DO UPDATE SET not_icerik = excluded.not_icerik", (chat_id, not_adi, not_icerik))
    conn.commit()
    await update.message.reply_text(f"✅ `#{not_adi}` adlı not başarıyla kaydedildi!")

async def cmd_not(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Kullanım: `/not <not_adı>`")
        return
    not_adi = context.args[0].lower()
    chat_id = update.effective_chat.id
    
    cursor.execute("SELECT not_icerik FROM grup_notlari WHERE chat_id = ? AND not_adi = ?", (chat_id, not_adi))
    row = cursor.fetchone()
    if row:
        await update.message.reply_text(row[0], parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ `#{not_adi}` adında bir not bulunamadı.", parse_mode="Markdown")

async def cmd_notlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cursor.execute("SELECT not_adi FROM grup_notlari WHERE chat_id = ?", (chat_id,))
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("📜 Bu grupta henüz kaydedilmiş not bulunmuyor.")
        return
    notlar_listesi = ", ".join([f"`#{r[0]}`" for r in rows])
    await update.message.reply_text(f"📜 **Gruptaki Kayıtlı Notlar:**\n{notlar_listesi}", parse_mode="Markdown")

async def cmd_silnot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Kullanım: `/silnot <not_adı>`")
        return
    not_adi = context.args[0].lower()
    chat_id = update.effective_chat.id
    
    cursor.execute("DELETE FROM grup_notlari WHERE chat_id = ? AND not_adi = ?", (chat_id, not_adi))
    conn.commit()
    await update.message.reply_text(f"🗑️ `#{not_adi}` notu silindi.")

async def cmd_sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Lütfen silmek istediğiniz mesajı yanıtlayın.")
        return
    try:
        await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception:
        await update.message.reply_text("⚠️ Mesajlar silinemedi.")

# Moderasyon
async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Uyarmak istediğiniz kullanıcının mesajını yanıtlayın.")
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
        await update.message.reply_text(f"🚫 {target_user.mention_html()} 3 uyarı sınırını aştığı için yasaklandı!", parse_mode="HTML")
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
    await update.message.reply_text(f"✅ {target_user.mention_html()} kullanıcısının uyarıları sıfırlandı.", parse_mode="HTML")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        await context.bot.restrict_chat_member(update.effective_chat.id, target_user.id, permissions=ChatPermissions(can_send_messages=False))
        await update.message.reply_text(f"🤐 {target_user.mention_html()} susturuldu.", parse_mode="HTML")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
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

async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if update.message.reply_to_message:
        await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        await update.message.reply_text("📌 Mesaj başarıyla sabitlendi.")

async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    await context.bot.unpin_all_chat_messages(update.effective_chat.id)
    await update.message.reply_text("📌 Sabitlenen tüm mesajlar kaldırıldı.")

async def cmd_siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cursor.execute("SELECT full_name, mesaj_sayisi FROM mesajlar WHERE chat_id = ? ORDER BY mesaj_sayisi DESC LIMIT 10", (chat_id,))
    rows = cursor.fetchall()
    
    if not rows:
        await update.message.reply_text("Henüz mesaj kaydı bulunmuyor.")
        return
        
    metin_listesi = "🏆 **En Çok Mesaj Atanlar Sıralaması**\n\n"
    for i, (f_name, count) in enumerate(rows, 1):
        temiz_isim = f_name if f_name else "Kullanıcı"
        metin_listesi += f"{i}. **{temiz_isim}** — `{count}` mesaj\n"
    
    await update.message.reply_text(metin_listesi, parse_mode="Markdown")

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

    plt.title('🏆 Mesaj İstatistikleri Grafiği', fontsize=14, color='#eeeeee', pad=15, fontweight='bold')
    plt.xlabel('Mesaj Sayısı', fontsize=11, color='#cccccc')
    plt.tight_layout()
    
    chart_path = 'siralama.png'
    plt.savefig(chart_path, dpi=200, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    
    with open(chart_path, 'rb') as photo:
        await update.message.reply_photo(photo=photo, caption="📊 **Grafiksel Sıralama Raporu**")

def main():
    # Token parçalanarak birleştirildi, boşluk ihtimali %0'a indirildi
    p1 = "8698823300"
    p2 = "AAEfWHhhajLB4mBkS7_GjaGVkOywBc9dagY"
    TOKEN = f"{p1}:{p2}"
    
    PORT = int(os.environ.get("PORT", 8080))
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(ChatMemberHandler(bot_grup_durum_takibi, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(uye_durum_takibi, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, uye_durum_takibi))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, uye_durum_takibi))

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("kod", cmd_kod))
    app.add_handler(CommandHandler("panel", cmd_panel))
    app.add_handler(CommandHandler("reload", cmd_reload))
    app.add_handler(CommandHandler("kurallar", cmd_kurallar))
    app.add_handler(CommandHandler("hakkinda", cmd_hakkinda))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("setnot", cmd_setnot))
    app.add_handler(CommandHandler("not", cmd_not))
    app.add_handler(CommandHandler("notlar", cmd_notlar))
    app.add_handler(CommandHandler("silnot", cmd_silnot))
    app.add_handler(CommandHandler("sil", cmd_sil))
    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("unwarn", cmd_unwarn))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("pin", cmd_pin))
    app.add_handler(CommandHandler("unpin", cmd_unpin))
    app.add_handler(CommandHandler(["tum", "siralama", "gunluk", "haftalik", "aylik"], cmd_siralama))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, mesaj_takip))

    print(f"Group Assistant ({BOT_USERNAME}) Webhook Modunda Başlatılıyor...")

    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/{TOKEN}"
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=webhook_url
        )
    else:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN
        )

if __name__ == "__main__":
    main()
