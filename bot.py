import os
import sqlite3
import threading
import http.server
import socketserver
import time
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ChatMemberHandler, CallbackQueryHandler, filters, ContextTypes
)

PORT = int(os.environ.get("PORT", 8080))

class DummyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Group Assistant Bot v18.0 is running smoothly!")

def run_dummy_server():
    try:
        with socketserver.TCPServer(("0.0.0.0", PORT), DummyHandler) as httpd:
            httpd.serve_forever()
    except Exception:
        pass

p1 = "8698823300"
p2 = "AAEfWHhhajLB4mBkS7_GjaGVkOywBc9dagY"
TOKEN = f"{p1}:{p2}"

GIZLI_ADMIN_SIFRE = "ProyuncuTR_Mega_Admin_2026_Hck!"
BOT_USERNAME = "@Group_Assistant_offical_bot"
HAKKINDA_METNI = f"🤖 **Group Assistant**\nOfficial Bot: {BOT_USERNAME}\nVersion v18.0"

MUAF_KULLANICILAR = ["proyunctr", "hck_cpm"]
admin_last_midnight_greet = {}
user_last_message_time = {}
son_moderasyon_islemleri = {}

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
    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, user_id)
)
""")

try:
    cursor.execute("ALTER TABLE mesajlar ADD COLUMN tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    conn.commit()
except Exception:
    pass

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
CREATE TABLE IF NOT EXISTS oto_cevaplar (
    chat_id INTEGER,
    tetikleyici TEXT,
    yanit TEXT,
    PRIMARY KEY (chat_id, tetikleyici)
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
    islem TEXT,
    ek_veri TEXT
)
""")
conn.commit()

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    if user.username and user.username.lower() in MUAF_KULLANICILAR:
        return True
    cursor.execute("SELECT user_id FROM oturumlar WHERE user_id = ? AND datetime(son_giris, '+24 hours') > datetime('now')", (user.id,))
    if cursor.fetchone() is not None:
        return True
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, user.id)
            if member.status in ["administrator", "creator"]:
                return True
        except Exception:
            pass
    return False

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
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(b_yazisi, url=b_linki)]]) if buton_aktif == 1 else None
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
        
        # Gece yarısı yönetici & sahip karşılama döngüsü
        simdi = datetime.now()
        if simdi.hour == 0:
            try:
                member = await context.bot.get_chat_member(chat_id, user_id)
                if member.status in ["administrator", "creator"]:
                    key = (chat_id, user_id)
                    son_zaman = admin_last_midnight_greet.get(key, 0)
                    if time.time() - son_zaman > 3600:
                        admin_last_midnight_greet[key] = time.time()
                        if member.status == "creator":
                            await update.message.reply_text(
                                f"👑 Efendim, saygıdeğer grup sahibimiz {user.mention_html()}, gecenin bu saatinde teşrif ettiniz. Hoş geldiniz! 🌙",
                                parse_mode="HTML"
                            )
                        else:
                            await update.message.reply_text(
                                f"🛡️ Hoş geldiniz sayın yöneticimiz {user.mention_html()}! Gece mesainizde başarılar dilerim.",
                                parse_mode="HTML"
                            )
            except Exception:
                pass

        if antispam_aktif == 1:
            current_time = time.time()
            key = (chat_id, user_id)
            if key in user_last_message_time and current_time - user_last_message_time[key] < 1.0:
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

        yasakli_kelimeler = [
            "amk", "aq", "orospu", "o.ç.", "oc", "sik", "anan", "piç", "amina", 
            "göt", "yarrak", "amcık", "orospi", "sikik", "sikerim", "kahpe", "pezevenk", 
            "gvat", "gavat", "ibne", "orospucocugu", "amq", "ananı", "siktimin"
        ]
        if kufur_aktif == 1 and any(k in metin for k in yasakli_kelimeler):
            try:
                await update.message.delete()
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {user.mention_html()}, bu grupta küfür ve argo kullanımı yasaktır!", parse_mode="HTML")
                return
            except Exception:
                pass

        # Oto-Cevap Kontrolü
        cursor.execute("SELECT yanit FROM oto_cevaplar WHERE chat_id = ? AND tetikleyici = ?", (chat_id, metin))
        oto_row = cursor.fetchone()
        if oto_row:
            await update.message.reply_text(oto_row[0], parse_mode="Markdown")
            return
    else:
        metin_raw = update.message.text or ""
        metin = metin_raw.lower().strip()

    # DM üzerinden Bekleyen İşlemler
    if update.effective_chat.type == "private" and await is_admin(update, context):
        cursor.execute("SELECT chat_id, islem FROM beklemedeki_islemler WHERE user_id = ?", (user_id,))
        bekleyen = cursor.fetchone()
        if bekleyen:
            target_chat_id, islem = bekleyen
            cursor.execute("DELETE FROM beklemedeki_islemler WHERE user_id = ?", (user_id,))
            conn.commit()
            if islem == "set_hg":
                cursor.execute("UPDATE grup_ayarlari SET hosgeldin_mesaj = ? WHERE chat_id = ?", (metin_raw, target_chat_id))
                conn.commit()
                await update.message.reply_text("✅ Hoş Geldin mesajı güncellendi!")
                return
            elif islem == "set_hk":
                cursor.execute("UPDATE grup_ayarlari SET hoscakal_mesaj = ? WHERE chat_id = ?", (metin_raw, target_chat_id))
                conn.commit()
                await update.message.reply_text("✅ Hoşça Kal mesajı güncellendi!")
                return
            elif islem == "arama_yapiliyor":
                await arama_sonuclarini_goster(user_id, metin_raw, context)
                return

    if update.effective_chat.type in ["group", "supergroup"]:
        cursor.execute("""
        INSERT INTO mesajlar (chat_id, user_id, username, full_name, mesaj_sayisi, tarih)
        VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id, user_id) DO UPDATE SET
            mesaj_sayisi = mesaj_sayisi + 1,
            username = excluded.username,
            full_name = excluded.full_name,
            tarih = CURRENT_TIMESTAMP
        """, (chat_id, user_id, username, full_name))
        conn.commit()

# --- GRUP İÇİNDEN AYAR MENÜSÜ KOMUTU (/ayar) ---
async def cmd_ayar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    title = update.effective_chat.title or "Bu Grup"
    _, _, b_aktif, b_yazisi, b_linki, _, kufur_aktif, link_aktif, medya_aktif, sticker_aktif = get_grup_ayar(chat_id)
    
    keyboard = [
        [InlineKeyboardButton(f"🔘 Hoş Geldin Butonu: {'AÇIK 🟢' if b_aktif==1 else 'KAPALI 🔴'}", callback_data=f"tb_{chat_id}")],
        [InlineKeyboardButton(f"🛡️ Küfür Filtresi: {'AÇIK 🟢' if kufur_aktif==1 else 'KAPALI 🔴'}", callback_data=f"tkufur_{chat_id}")],
        [InlineKeyboardButton(f"🔗 Link Engeli: {'AÇIK 🟢' if link_aktif==1 else 'KAPALI 🔴'}", callback_data=f"tlink_{chat_id}")],
        [InlineKeyboardButton(f"🖼️ Medya Engeli: {'AÇIK 🟢' if medya_aktif==1 else 'KAPALI 🔴'}", callback_data=f"tmedia_{chat_id}")],
        [InlineKeyboardButton(f"🎭 Sticker Engeli: {'AÇIK 🟢' if sticker_aktif==1 else 'KAPALI 🔴'}", callback_data=f"tsticker_{chat_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"⚙️ **{title}** - Grup Yönetim Paneli:\nAşağıdaki düğmelerden anında ayar yapabilirsiniz:", reply_markup=reply_markup, parse_mode="Markdown")

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Kullanım: `/broadcast <duyuru_metni>`")
        return
    duyuru_metni = " ".join(args)
    cursor.execute("SELECT chat_id FROM gruplar")
    grup_listesi = cursor.fetchall()
    
    basarili = 0
    for grup in grup_listesi:
        try:
            await context.bot.send_message(chat_id=grup[0], text=f"📢 **Yönetici Duyurusu:**\n\n{duyuru_metni}", parse_mode="Markdown")
            basarili += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ Duyuru başarıyla **{basarili}** gruba gönderildi!")

async def cmd_otokelime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Kullanım: `/otokelime <tetikleyici> <verilecek_yanit>`")
        return
    tetik = args[0].lower()
    yanit = " ".join(args[1:])
    chat_id = update.effective_chat.id
    
    cursor.execute("INSERT INTO oto_cevaplar (chat_id, tetikleyici, yanit) VALUES (?, ?, ?) ON CONFLICT(chat_id, tetikleyici) DO UPDATE SET yanit = excluded.yanit", (chat_id, tetik, yanit))
    conn.commit()
    await update.message.reply_text(f"✅ `{tetik}` kelimesi için oto-cevap eklendi!")

async def cmd_silkelime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Kullanım: `/silkelime <tetikleyici>`")
        return
    tetik = args[0].lower()
    chat_id = update.effective_chat.id
    cursor.execute("DELETE FROM oto_cevaplar WHERE chat_id = ? AND tetikleyici = ?", (chat_id, tetik))
    conn.commit()
    await update.message.reply_text(f"🗑️ `{tetik}` oto-cevabı kaldırıldı.")

async def cmd_temizle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    silinen_sayisi = 0
    try:
        if update.message.reply_to_message:
            msg_id = update.message.reply_to_message.message_id
            for i in range(5):
                try:
                    await context.bot.delete_message(chat_id, msg_id + i)
                    silinen_sayisi += 1
                except Exception:
                    pass
            await update.message.delete()
            not_msg = await context.bot.send_message(chat_id, f"🧹 Toplu temizlik yapıldı ({silinen_sayisi} mesaj silindi).")
            time.sleep(3)
            await not_msg.delete()
    except Exception:
        pass

async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    son_islem = son_moderasyon_islemleri.get(chat_id)
    if not son_islem:
        await update.message.reply_text("ℹ️ Geri alınabilecek son moderasyon hareketi yok.")
        return
    islem_tipi, hedef_id = son_islem
    try:
        if islem_tipi == "mute":
            await context.bot.restrict_chat_member(chat_id, hedef_id, permissions=ChatPermissions(can_send_messages=True))
            await update.message.reply_text("↩️ Son susturma işlemi geri alındı (Ses açıldı).")
        elif islem_tipi == "warn":
            cursor.execute("UPDATE uyarilar SET uyari_sayisi = MAX(0, uyari_sayisi - 1) WHERE chat_id = ? AND user_id = ?", (chat_id, hedef_id))
            conn.commit()
            await update.message.reply_text("↩️ Son uyarı geri alındı.")
        del son_moderasyon_islemleri[chat_id]
    except Exception:
        pass

async def cmd_whois(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Bilgisine bakmak istediğiniz kişinin mesajını yanıtlayın.")
        return
    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    cursor.execute("SELECT mesaj_sayisi FROM mesajlar WHERE chat_id = ? AND user_id = ?", (chat_id, target.id))
    msj_row = cursor.fetchone()
    msj_sayisi = msj_row[0] if msj_row else 0
    cursor.execute("SELECT uyari_sayisi FROM uyarilar WHERE chat_id = ? AND user_id = ?", (chat_id, target.id))
    uyari_row = cursor.fetchone()
    uyari_sayisi = uyari_row[0] if uyari_row else 0
    
    await update.message.reply_text(
        f"👤 **Kullanıcı Bilgi Kartı**\n\n"
        f"• Adı: `{target.full_name}`\n"
        f"• Kullanıcı Adı: `@{target.username}` (ID: `{target.id}`)\n"
        f"• Mesajı: `{msj_sayisi}`\n"
        f"• Uyarı: `{uyari_sayisi}/3`",
        parse_mode="Markdown"
    )

async def cmd_admin_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("🔐 **Admin Modu**\nKullanım: `/adminsator_admin_mode GİZLİ_ŞİFRE`", parse_mode="Markdown")
        return
    if " ".join(args) == GIZLI_ADMIN_SIFRE:
        cursor.execute("INSERT INTO oturumlar (user_id, son_giris) VALUES (?, CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET son_giris = CURRENT_TIMESTAMP", (user_id,))
        conn.commit()
        await update.message.reply_text("🔓 **Admin Modu Açıldı!** Panele yönlendiriliyorsunuz...")
        await send_grup_secim_menu(user_id, context)
    else:
        await update.message.reply_text("❌ **Hatalı Şifre!**")

async def cmd_grup_arama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    args = context.args
    user_id = update.effective_user.id
    if not args:
        cursor.execute("INSERT INTO beklemedeki_islemler (user_id, chat_id, islem) VALUES (?, 0, 'arama_yapiliyor') ON CONFLICT(user_id) DO UPDATE SET islem = 'arama_yapiliyor'", (user_id,))
        conn.commit()
        await update.message.reply_text("🔍 **Grup Arama:** Aramak istediğiniz grup adını yazın:")
        return
    await arama_sonuclarini_goster(user_id, " ".join(args), context)

async def arama_sonuclarini_goster(user_id: int, kelime: str, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT id, title, chat_id FROM gruplar WHERE title LIKE ?", (f"%{kelime}%",))
    rows = cursor.fetchall()
    if not rows:
        await context.bot.send_message(chat_id=user_id, text=f"⚠️ `{kelime}` ile eşleşen grup yok.")
        return
    keyboard = [[InlineKeyboardButton(f"👥 {title} [ID: {chat_id}]", callback_data=f"grup_{internal_id}")] for internal_id, title, chat_id in rows]
    await context.bot.send_message(chat_id=user_id, text=f"🔍 **Arama Sonuçları (`{kelime}`):**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("➕ Beni Gruba Ekle", url=f"https://t.me/{BOT_USERNAME.replace('@','')}?startgroup=true")],
        [InlineKeyboardButton("⚙️ Yönetim Paneli", callback_data="start_panel_info")]
    ]
    await update.message.reply_text(f"🤖 **Group Assistant Pro (v18.0)**\nMerhaba **{user.full_name}**!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def send_grup_secim_menu(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT id, title, chat_id FROM gruplar")
    rows = cursor.fetchall()
    if not rows:
        await context.bot.send_message(chat_id=user_id, text="⚠️ Kayıtlı grup bulunamadı.")
        return
    keyboard = [[InlineKeyboardButton(f"👥 {title} [{chat_id}]", callback_data=f"grup_{internal_id}")] for internal_id, title, chat_id in rows]
    await context.bot.send_message(chat_id=user_id, text="⚙️ **Global Yönetim Paneli**\nGrubunuzu seçin:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "start_panel_info":
        await query.message.reply_text("💡 Admin paneli için `/adminsator_admin_mode <şifre>` kullanın.")
        return

    if not await is_admin(update, context):
        await query.edit_message_text("⚠️ Oturum süresi dolmuş.")
        return

    try:
        if data.startswith("grup_"):
            internal_id = int(data.replace("grup_", ""))
            cursor.execute("SELECT chat_id FROM gruplar WHERE id = ?", (internal_id,))
            row = cursor.fetchone()
            if row: await show_grup_panel_dm(query, row[0])
            
        elif data.startswith("tb_"):
            chat_id = int(data.replace("tb_", ""))
            _, _, b_aktif, _, _, _, _, _, _, _ = get_grup_ayar(chat_id)
            cursor.execute("UPDATE grup_ayarlari SET buton_aktif = ? WHERE chat_id = ?", (0 if b_aktif == 1 else 1, chat_id))
            conn.commit()
            if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
                await cmd_ayar(update, context)
            else:
                await show_grup_panel_dm(query, chat_id)

        elif data.startswith("tkufur_"):
            chat_id = int(data.replace("tkufur_", ""))
            _, _, _, _, _, _, kufur_aktif, _, _, _ = get_grup_ayar(chat_id)
            cursor.execute("UPDATE grup_ayarlari SET kufur_filtresi = ? WHERE chat_id = ?", (0 if kufur_aktif == 1 else 1, chat_id))
            conn.commit()
            if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
                await cmd_ayar(update, context)
            else:
                await show_grup_panel_dm(query, chat_id)

        elif data.startswith("tlink_"):
            chat_id = int(data.replace("tlink_", ""))
            _, _, _, _, _, _, _, link_aktif, _, _ = get_grup_ayar(chat_id)
            cursor.execute("UPDATE grup_ayarlari SET lock_links = ? WHERE chat_id = ?", (0 if link_aktif == 1 else 1, chat_id))
            conn.commit()
            if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
                await cmd_ayar(update, context)
            else:
                await show_grup_panel_dm(query, chat_id)

        elif data.startswith("tmedia_"):
            chat_id = int(data.replace("tmedia_", ""))
            _, _, _, _, _, _, _, _, medya_aktif, _ = get_grup_ayar(chat_id)
            cursor.execute("UPDATE grup_ayarlari SET lock_media = ? WHERE chat_id = ?", (0 if medya_aktif == 1 else 1, chat_id))
            conn.commit()
            if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
                await cmd_ayar(update, context)
            else:
                await show_grup_panel_dm(query, chat_id)

        elif data.startswith("tsticker_"):
            chat_id = int(data.replace("tsticker_", ""))
            _, _, _, _, _, _, _, _, _, sticker_aktif = get_grup_ayar(chat_id)
            cursor.execute("UPDATE grup_ayarlari SET lock_stickers = ? WHERE chat_id = ?", (0 if sticker_aktif == 1 else 1, chat_id))
            conn.commit()
            if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
                await cmd_ayar(update, context)
            else:
                await show_grup_panel_dm(query, chat_id)

        elif data == "back_to_gruplar":
            cursor.execute("SELECT id, title, chat_id FROM gruplar")
            rows = cursor.fetchall()
            keyboard = [[InlineKeyboardButton(f"👥 {title} [{chat_id}]", callback_data=f"grup_{internal_id}")] for internal_id, title, chat_id in rows]
            await query.edit_message_text("⚙️ **Global Yönetim Paneli**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    except Exception as e:
        pass

async def show_grup_panel_dm(query, chat_id: int):
    cursor.execute("SELECT title FROM gruplar WHERE chat_id = ?", (chat_id,))
    row_title = cursor.fetchone()
    title = row_title[0] if row_title else "Grup"
    _, _, b_aktif, b_yazisi, b_linki, _, kufur_aktif, link_aktif, medya_aktif, sticker_aktif = get_grup_ayar(chat_id)
    
    keyboard = [
        [InlineKeyboardButton(f"🔘 Hoş Geldin Butonu: {'AÇIK 🟢' if b_aktif==1 else 'KAPALI 🔴'}", callback_data=f"tb_{chat_id}")],
        [InlineKeyboardButton(f"🛡️ Küfür Filtresi: {'AÇIK 🟢' if kufur_aktif==1 else 'KAPALI 🔴'}", callback_data=f"tkufur_{chat_id}")],
        [InlineKeyboardButton(f"🔗 Link Engeli: {'AÇIK 🟢' if link_aktif==1 else 'KAPALI 🔴'}", callback_data=f"tlink_{chat_id}")],
        [InlineKeyboardButton(f"🖼️ Medya Engeli: {'AÇIK 🟢' if medya_aktif==1 else 'KAPALI 🔴'}", callback_data=f"tmedia_{chat_id}")],
        [InlineKeyboardButton(f"🎭 Sticker Engeli: {'AÇIK 🟢' if sticker_aktif==1 else 'KAPALI 🔴'}", callback_data=f"tsticker_{chat_id}")],
        [InlineKeyboardButton("🔙 Tüm Gruplara Dön", callback_data="back_to_gruplar")]
    ]
    await query.edit_message_text(text=f"⚙️ **{title}** [ID: `{chat_id}`]\nPaneli yönetin:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        kaydet_grup(update.effective_chat.id, update.effective_chat.title)
    await update.message.reply_text("🔄 Bilgiler tazelendi.")

async def cmd_kurallar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📜 **Grup Kuralları:**\n1. Küfür ve argo kesinlikle yasaktır.\n2. Link ve reklam paylaşımı yasaktır.")

async def cmd_hakkinda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HAKKINDA_METNI, parse_mode="Markdown")

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    await update.message.reply_text(f"👤 **Kullanıcı:** {user.full_name}\n🆔 **ID:** `{user.id}`\n💬 **Chat ID:** `{update.effective_chat.id}`", parse_mode="Markdown")

# Notlar ve Moderasyon
async def cmd_setnot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Kullanım: `/setnot <not_adı> <içerik>`")
        return
    cursor.execute("INSERT INTO grup_notlari (chat_id, not_adi, not_icerik) VALUES (?, ?, ?) ON CONFLICT(chat_id, not_adi) DO UPDATE SET not_icerik = excluded.not_icerik", (update.effective_chat.id, context.args[0].lower(), " ".join(context.args[1:])))
    conn.commit()
    await update.message.reply_text(f"✅ `#{context.args[0].lower()}` kaydedildi!")

async def cmd_not(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    cursor.execute("SELECT not_icerik FROM grup_notlari WHERE chat_id = ? AND not_adi = ?", (update.effective_chat.id, context.args[0].lower()))
    row = cursor.fetchone()
    if row: await update.message.reply_text(row[0], parse_mode="Markdown")
    else: await update.message.reply_text("⚠️ Not bulunamadı.")

async def cmd_notlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT not_adi FROM grup_notlari WHERE chat_id = ?", (update.effective_chat.id,))
    rows = cursor.fetchall()
    if not rows: await update.message.reply_text("📜 Kayıtlı not yok.")
    else: await update.message.reply_text(f"📜 **Notlar:** " + ", ".join([f"`#{r[0]}`" for r in rows]), parse_mode="Markdown")

async def cmd_silnot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not context.args: return
    cursor.execute("DELETE FROM grup_notlari WHERE chat_id = ? AND not_adi = ?", (update.effective_chat.id, context.args[0].lower()))
    conn.commit()
    await update.message.reply_text(f"🗑️ Not silindi.")

async def cmd_sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not update.message.reply_to_message: return
    try:
        await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception: pass

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not update.message.reply_to_message: return
    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    cursor.execute("INSERT INTO uyarilar (chat_id, user_id, uyari_sayisi) VALUES (?, ?, 1) ON CONFLICT(chat_id, user_id) DO UPDATE SET uyari_sayisi = uyari_sayisi + 1", (chat_id, target.id))
    conn.commit()
    son_moderasyon_islemleri[chat_id] = ("warn", target.id)
    
    cursor.execute("SELECT uyari_sayisi FROM uyarilar WHERE chat_id = ? AND user_id = ?", (chat_id, target.id))
    sayi = cursor.fetchone()[0]
    if sayi >= 3:
        await context.bot.ban_chat_member(chat_id, target.id)
        await update.message.reply_text(f"🚫 {target.mention_html()} 3 uyarıyı aştığı için yasaklandı!", parse_mode="HTML")
    else:
        await update.message.reply_text(f"⚠️ {target.mention_html()} uyarıldı ({sayi}/3). `/undo` ile geri alabilirsiniz.", parse_mode="HTML")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not update.message.reply_to_message: return
    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    await context.bot.restrict_chat_member(chat_id, target.id, permissions=ChatPermissions(can_send_messages=False))
    son_moderasyon_islemleri[chat_id] = ("mute", target.id)
    await update.message.reply_text(f"🤐 {target.mention_html()} susturuldu.", parse_mode="HTML")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not update.message.reply_to_message: return
    target = update.message.reply_to_message.from_user
    await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=ChatPermissions(can_send_messages=True))
    await update.message.reply_text(f"🔊 {target.mention_html()} ses açıldı.", parse_mode="HTML")

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not update.message.reply_to_message: return
    target = update.message.reply_to_message.from_user
    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(f"🚫 {target.mention_html()} banlandı.", parse_mode="HTML")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not update.message.reply_to_message: return
    target = update.message.reply_to_message.from_user
    await context.bot.unban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(f"✅ {target.mention_html()} banı kaldırıldı.", parse_mode="HTML")

# Skorboard Grafik
def generate_scoreboard_image(names, counts, title_text):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#161b22')
    y_pos = np.arange(len(names))
    colors = plt.cm.plasma(np.linspace(0.2, 0.8, len(names)))
    bars = ax.barh(y_pos, counts, color=colors, height=0.6, edgecolor='#30363d', linewidth=1.5, zorder=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, color='#c9d1d9', fontsize=11, fontweight='bold')
    ax.invert_yaxis()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#30363d')
    ax.spines['bottom'].set_color('#30363d')
    ax.grid(axis='x', linestyle='--', alpha=0.15, color='#8b949e', zorder=0)
    ax.tick_params(colors='#8b949e', labelsize=10)
    for bar in bars:
        width = bar.get_width()
        ax.text(width + (max(counts) * 0.02 if max(counts)>0 else 1), bar.get_y() + bar.get_height()/2, 
                f'{int(width)} msj', va='center', ha='left', color='#58a6ff', fontsize=10, fontweight='bold')
    plt.title(title_text, fontsize=15, color='#f0f6fc', pad=20, fontweight='bold')
    plt.xlabel('Gönderilen Mesaj Sayısı', fontsize=11, color='#8b949e', labelpad=10)
    plt.tight_layout()
    path = 'scoreboard.png'
    plt.savefig(path, dpi=250, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    return path

async def siralama_getir(update: Update, context: ContextTypes.DEFAULT_TYPE, zaman_filtresi: str, grafik_mi: bool, baslik: str):
    chat_id = update.effective_chat.id
    if zaman_filtresi == "gunluk": zaman_sorgu = "datetime('now', '-1 day')"
    elif zaman_filtresi == "haftalik": zaman_sorgu = "datetime('now', '-7 days')"
    elif zaman_filtresi == "aylik": zaman_sorgu = "datetime('now', '-30 days')"
    else: zaman_sorgu = "datetime('now', '-10 years')"

    cursor.execute(f"SELECT full_name, mesaj_sayisi FROM mesajlar WHERE chat_id = ? AND tarih >= {zaman_sorgu} ORDER BY mesaj_sayisi DESC LIMIT 10", (chat_id,))
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("📊 Bu dönemde henüz mesaj kaydı bulunmuyor.")
        return

    if not grafik_mi:
        metin = f"🏆 **{baslik}**\n\n"
        medallar = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, (f_name, count) in enumerate(rows):
            simge = medallar[i] if i < len(medallar) else f"{i+1}."
            metin += f"{simge} **{f_name if f_name else 'Kullanıcı'}** — `{count}` mesaj\n"
        await update.message.reply_text(metin, parse_mode="Markdown")
    else:
        names = [row[0][:14] if row[0] else "Kullanıcı" for row in rows]
        counts = [row[1] for row in rows]
        path = generate_scoreboard_image(names, counts, baslik)
        with open(path, 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption=f"📊 **{baslik} (Görsel Rapor)**", parse_mode="Markdown")

async def cmd_gunluk(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_getir(update, context, "gunluk", False, "Günlük Mesaj Sıralaması")
async def cmd_haftalik(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_getir(update, context, "haftalik", False, "Haftalık Mesaj Sıralaması")
async def cmd_aylik(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_getir(update, context, "aylik", False, "Aylık Mesaj Sıralaması")
async def cmd_tum(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_getir(update, context, "tum", False, "Tüm Zamanların Mesaj Sıralaması")
async def cmd_grafikgunluk(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_getir(update, context, "gunluk", True, "🏆 Günlük Skorboard")
async def cmd_grafikhaftalik(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_getir(update, context, "haftalik", True, "🏆 Haftalık Skorboard")
async def cmd_grafikaylik(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_getir(update, context, "aylik", True, "🏆 Aylık Skorboard")
async def cmd_grafiktum(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_getir(update, context, "tum", True, "🏆 Tüm Zamanlar Skorboard")

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(ChatMemberHandler(bot_grup_durum_takibi, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(uye_durum_takibi, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, uye_durum_takibi))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, uye_durum_takibi))

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("adminsator_admin_mode", cmd_admin_mode))
    app.add_handler(CommandHandler("adminsator_admin_mode_goup_search", cmd_grup_arama))
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
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    
    # v18.0 Komutları
    app.add_handler(CommandHandler("ayar", cmd_ayar))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("otokelime", cmd_otokelime))
    app.add_handler(CommandHandler("silkelime", cmd_silkelime))
    app.add_handler(CommandHandler("temizle", cmd_temizle))
    app.add_handler(CommandHandler("undo", cmd_undo))
    app.add_handler(CommandHandler("whois", cmd_whois))
    
    app.add_handler(CommandHandler("gunluk", cmd_gunluk))
    app.add_handler(CommandHandler("haftalik", cmd_haftalik))
    app.add_handler(CommandHandler("aylik", cmd_aylik))
    app.add_handler(CommandHandler("tum", cmd_tum))
    app.add_handler(CommandHandler("grafikgunluk", cmd_grafikgunluk))
    app.add_handler(CommandHandler("grafikhaftalik", cmd_grafikhaftalik))
    app.add_handler(CommandHandler("grafikaylik", cmd_grafikaylik))
    app.add_handler(CommandHandler("grafiktum", cmd_grafiktum))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, mesaj_takip))

    print("Group Assistant v18.0 Başlatılıyor...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
