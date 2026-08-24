from datetime import datetime, timedelta
import os
import re
import sqlite3
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ChatMemberHandler, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "8823945672:AAHnfiT2s2PR3Vt4o_8xD6ro3tgrs5T1RMk"

ADMIN_KODU = "890678"
BEKLEYEN_ADMINLER = set()
ADMIN_OTURUMLARI = {}

def veritabani_kur():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kullanicilar (
            uid INTEGER PRIMARY KEY,
            name TEXT,
            username TEXT,
            gunluk INTEGER DEFAULT 0,
            haftalik INTEGER DEFAULT 0,
            aylik INTEGER DEFAULT 0,
            toplam INTEGER DEFAULT 0,
            uyari INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

veritabani_kur()

KUFUR_LISTESI = ["amk", "aq", "sik", "piç", "yarrak", "orospu", "ibne", "göt"]

KURALLAR_METNI = """📜 ProyuncuTR_hck Sohbet Grup Kuralları / Chat Group Rules

🇹🇷 Türkçe Kurallar:
1️⃣ Küfür/Argo kelimeler kesinlikle yasaktır. 3 uyarı alırsanız banlanırsınız.
2️⃣ Link göndermek otomatik olarak mesaj gönderme özelliğinizin kapatılmasına (mute) sebep olur.
3️⃣ İzinsiz reklam yapmak kesinlikle yasaktır! Reklam için @ProyuncuTR adresine DM atınız.

🇬🇧 English Rules:
1️⃣ Profanity/slang is strictly prohibited. Accumulating 3 warnings results in a ban.
2️⃣ Sending links will automatically disable your ability to send messages.
3️⃣ Unauthorized advertising is strictly prohibited! Contact @ProyuncuTR via DM.

2026© ProyuncuTR_hck Sohbet"""

async def admin_mi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.effective_chat: return False
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private": return True
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ["administrator", "creator"]

async def start_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        mesaj = "Sadece adminler bu bölümü açabilir. Eğer bu botu kullanmak istiyorsanız grubunuzda satın almanız gerekmektedir."
        await update.message.reply_text(mesaj)
    else:
        await update.message.reply_text("👋 Bot grupta aktif olarak çalışıyor!")

async def reload_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await admin_mi(update, context):
        await update.message.reply_text("🔄 Bot sistemi aktif ve pürüzsüz çalışıyor!")

async def panel_goster(update: Update):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(toplam) FROM kullanicilar")
    kullanici_sayisi, toplam_mesaj = cursor.fetchone()
    conn.close()

    admin_panel_metni = (
        f"✅ ADMIN PANELİ AKTİF ✅\n\n"
        f"📊 Yönetim Paneli & İstatistikler:\n"
        f"• Kayıtlı Kullanıcı: {kullanici_sayisi if kullanici_sayisi else 0}\n"
        f"• Toplam Takip Edilen Mesaj: {toplam_mesaj if toplam_mesaj else 0}\n\n"
        f"🔧 Yönetim Seçenekleri:\n"
        f"└ /warn - Uyarı Ver\n"
        f"└ /unwarn - Uyarı Sil\n"
        f"└ /mute / /unmute - Sustur / Aç\n"
        f"└ /ban / /unban - Banla / Kaldır"
    )
    await update.message.reply_text(admin_panel_metni)

async def kod_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await admin_mi(update, context):
        await update.message.reply_text("⛔ Bu komutu sadece grup yöneticileri kullanabilir!")
        return

    simdi = datetime.now()
    if user_id in ADMIN_OTURUMLARI:
        son_giris = ADMIN_OTURUMLARI[user_id]
        if simdi - son_giris < timedelta(hours=24):
            ADMIN_OTURUMLARI[user_id] = simdi
            await panel_goster(update)
            return

    BEKLEYEN_ADMINLER.add(user_id)
    await update.message.reply_text("🔐 Yönetici Doğrulaması:\nKod: ______")

async def mesajlari_takip_et(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user: return
    
    user = update.message.from_user
    uid, name, chat_id = user.id, user.first_name, update.effective_chat.id
    mesaj_metni = update.message.text.strip() if update.message.text else ""

    if uid in BEKLEYEN_ADMINLER:
        BEKLEYEN_ADMINLER.remove(uid)
        if mesaj_metni == ADMIN_KODU:
            ADMIN_OTURUMLARI[uid] = datetime.now()
            await panel_goster(update)
            return
        else:
            await update.message.reply_text("❌ Hatalı kod girdiniz! Erişim reddedildi.")
            return

    if update.message.new_chat_members:
        for yeni_uye in update.message.new_chat_members:
            if yeni_uye.is_bot: continue
            kullanici_adi = yeni_uye.first_name
            su_an = datetime.now().strftime("%d.%m.%Y - %H:%M")
            
            mesaj = (
                f"Merhaba {kullanici_adi}, ProyuncuTR_hck Sohbet grubuna hoş geldin! Nasılsın? 🤗\n\n"
                f"⏰ (Katılım Zamanı: {su_an})"
            )
            keyboard = [
                [InlineKeyboardButton("📢 Telegram Kanalı", url="https://t.me/ProyuncuTR_hck")],
                [InlineKeyboardButton("▶️ YouTube Kanalı", url="https://www.youtube.com/@ProyuncuTR_hck")]
            ]
            await update.message.reply_text(mesaj, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if user.is_bot: return

    mention_name = f"@{user.username}" if user.username else f"@{user.first_name}"
    is_admin = await admin_mi(update, context)

    # LİNK ENGELLEME
    link_regex = r"(https?://\S+|www\.\S+|\S+\.(com|net|org|io|tk|ml|ga|xyz|cf|gq))"
    if re.search(link_regex, mesaj_metni.lower()) and not is_admin:
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id, 
                user_id=uid, 
                permissions=ChatPermissions(can_send_messages=False)
            )
            bildirim_mesaji = (
                f"{mention_name} izin Verilmeyen bir link gönderdi :\n"
                f"Eylem: Sesize Aldım"
            )
            await update.message.reply_text(bildirim_mesaji)
            return
        except Exception as e: 
            print(f"Link işlem hatası: {e}")

    # KÜFÜR ENGELLEME (3 UYARI)
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT uyari FROM kullanicilar WHERE uid = ?", (uid,))
    res = cursor.fetchone()
    mevcut_uyari = (res[0] if res else 0)

    if any(kufur in mesaj_metni.lower() for kufur in KUFUR_LISTESI) and not is_admin:
        try:
            await update.message.delete()
            mevcut_uyari += 1
            if mevcut_uyari >= 3:
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=uid)
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {name} 3/3 uyarıya ulaştı ve yasaklandı! 🚷")
                cursor.execute("UPDATE kullanicilar SET uyari = 0 WHERE uid = ?", (uid,))
            else:
                cursor.execute("INSERT INTO kullanicilar (uid, name, uyari) VALUES (?, ?, ?) ON CONFLICT(uid) DO UPDATE SET uyari = ?", (uid, name, mevcut_uyari, mevcut_uyari))
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {name}, küfür yasaktır! Uyarı: {mevcut_uyari}/3")
            conn.commit()
            conn.close()
            return
        except Exception as e: print(f"Küfür hatası: {e}")

    # SAYAÇ
    cursor.execute("""
        INSERT INTO kullanicilar (uid, name, username, gunluk, haftalik, aylik, toplam) VALUES (?, ?, ?, 1, 1, 1, 1)
        ON CONFLICT(uid) DO UPDATE SET name=excluded.name, username=excluded.username, gunluk=gunluk+1, haftalik=haftalik+1, aylik=aylik+1, toplam=toplam+1
    """, (uid, name, user.username))
    conn.commit()
    conn.close()

async def siralama_olustur_yazili(update: Update, kategori: str, baslik: str):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT uid, name, {kategori} FROM kullanicilar WHERE {kategori} > 0 ORDER BY {kategori} DESC LIMIT 5")
    top_liste = cursor.fetchall()

    if not top_liste:
        await update.message.reply_text(f"ℹ️ Henüz {baslik} alanında mesaj verisi yok!")
        conn.close()
        return

    metin = f"📊 PROYUNCUTR_HCK SOHBET {baslik.upper()} SIRALAMASI 📊\n\n"
    for i, d in enumerate(top_liste, 1):
        metin += f"{i}. {d[1]} - {d[2]} mesaj\n"

    user = update.message.from_user
    cursor.execute(f"SELECT uid, name, {kategori} FROM kullanicilar WHERE {kategori} > 0 ORDER BY {kategori} DESC")
    tum_liste = cursor.fetchall()
    
    kendi_sira = None
    kendi_mesaj = 0
    for idx, row in enumerate(tum_liste, 1):
        if row[0] == user.id:
            kendi_sira = idx
            kendi_mesaj = row[2]
            break

    metin += "\n───────────────\n"
    if kendi_sira:
        metin += f"👤 Senin Durumun: {kendi_sira}. sıradasın ({kendi_mesaj} mesaj)"
    else:
        metin += f"👤 Senin Durumun: {user.first_name}, bu kategoride mesajın yok!"

    conn.close()
    await update.message.reply_text(metin)

async def siralama_olustur_grafik(update: Update, kategori: str, baslik: str):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT name, {kategori} FROM kullanicilar WHERE {kategori} > 0 ORDER BY {kategori} DESC LIMIT 5")
    top_liste = cursor.fetchall()
    conn.close()

    if not top_liste:
        await update.message.reply_text(f"ℹ️ Henüz {baslik} alanında grafik verisi yok!")
        return

    isimler = [row[0] for row in reversed(top_liste)]
    mesajlar = [row[1] for row in reversed(top_liste)]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.barh(isimler, mesajlar, color='#10B981')
    ax.set_xlabel('Mesaj Sayısı', fontsize=12, fontweight='bold', color='#1F2937')
    ax.set_title(f'ProyuncuTR_hck Sohbet - {baslik} Aktiflik Grafiği', fontsize=14, fontweight='bold', color='#111827')
    
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.3, bar.get_y() + bar.get_height()/2, f'{int(width)}', ha='left', va='center', fontweight='bold')

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    plt.close(fig)

    await update.message.reply_photo(photo=buf, caption=f"📊 ProyuncuTR_hck Sohbet {baslik} Grafik Sıralaması")

async def gunluk_yazili(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_olustur_yazili(update, "gunluk", "Günlük")
async def haftalik_yazili(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_olustur_yazili(update, "haftalik", "Haftalık")
async def aylik_yazili(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_olustur_yazili(update, "aylik", "Aylık")
async def tum_yazili(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_olustur_yazili(update, "toplam", "Tüm Zamanlar")

async def gunluk_grafikli(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_olustur_grafik(update, "gunluk", "Günlük")
async def haftalik_grafikli(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_olustur_grafik(update, "haftalik", "Haftalık")
async def aylik_grafikli(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_olustur_grafik(update, "aylik", "Aylık")
async def tum_grafikli(update: Update, context: ContextTypes.DEFAULT_TYPE): await siralama_olustur_grafik(update, "toplam", "Tüm Zamanlar")

async def ban_at(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_mi(update, context) or not update.message.reply_to_message: return
    hedef = update.message.reply_to_message.from_user
    await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=hedef.id)
    await update.message.reply_text(f"🚫 {hedef.first_name} yasaklandı!")

async def unban_at(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_mi(update, context) or not update.message.reply_to_message: return
    hedef = update.message.reply_to_message.from_user
    await context.bot.unban_chat_member(chat_id=update.effective_chat.id, user_id=hedef.id)
    await update.message.reply_text(f"✅ {hedef.first_name} yasağı kaldırıldı!")

async def mute_at(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_mi(update, context) or not update.message.reply_to_message: return
    hedef = update.message.reply_to_message.from_user
    await context.bot.restrict_chat_member(chat_id=update.effective_chat.id, user_id=hedef.id, permissions=ChatPermissions(can_send_messages=False))
    await update.message.reply_text(f"🔇 {hedef.first_name} susturuldu!")

async def unmute_at(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_mi(update, context) or not update.message.reply_to_message: return
    hedef = update.message.reply_to_message.from_user
    await context.bot.restrict_chat_member(chat_id=update.effective_chat.id, user_id=hedef.id, permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
    await update.message.reply_text(f"🔊 {hedef.first_name} susturulması kaldırıldı!")

async def kurallari_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(KURALLAR_METNI)

async def uyari_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_mi(update, context) or not update.message.reply_to_message: return
    hedef = update.message.reply_to_message.from_user
    uid, chat_id = hedef.id, update.effective_chat.id

    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT uyari FROM kullanicilar WHERE uid = ?", (uid,))
    res = cursor.fetchone()
    mevcut = (res[0] if res else 0) + 1

    if mevcut >= 3:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=uid)
        cursor.execute("UPDATE kullanicilar SET uyari = 0 WHERE uid = ?", (uid,))
        await update.message.reply_text(f"⚠️ {hedef.first_name} 3/3 uyarıya ulaştı ve banlandı!")
    else:
        cursor.execute("INSERT INTO kullanicilar (uid, name, uyari) VALUES (?, ?, ?) ON CONFLICT(uid) DO UPDATE SET uyari = ?", (uid, hedef.first_name, mevcut, mevcut))
        await update.message.reply_text(f"⚠️ {hedef.first_name} uyarıldı! Uyarı: {mevcut}/3")

    conn.commit()
    conn.close()

async def uyari_sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_mi(update, context) or not update.message.reply_to_message: return
    hedef = update.message.reply_to_message.from_user
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT uyari FROM kullanicilar WHERE uid = ?", (hedef.id,))
    res = cursor.fetchone()
    mevcut = res[0] if res else 0
    if mevcut > 0:
        mevcut -= 1
        cursor.execute("UPDATE kullanicilar SET uyari = ? WHERE uid = ?", (mevcut, hedef.id))
        await update.message.reply_text(f"✅ {hedef.first_name} uyarısı silindi. Kalan: {mevcut}/3")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_komutu))
    app.add_handler(CommandHandler("kod", kod_komutu))
    app.add_handler(CommandHandler("reload", reload_komutu))
    app.add_handler(CommandHandler("kurallar", kurallari_goster))
    
    app.add_handler(CommandHandler("gunluk", gunluk_yazili))
    app.add_handler(CommandHandler("haftalik", haftalik_yazili))
    app.add_handler(CommandHandler("aylik", aylik_yazili))
    app.add_handler(CommandHandler("tum", tum_yazili))
    app.add_handler(CommandHandler("siralama", tum_yazili))

    app.add_handler(CommandHandler("grafikgunluk", gunluk_grafikli))
    app.add_handler(CommandHandler("grafikhaftalik", haftalik_grafikli))
    app.add_handler(CommandHandler("grafikaylik", aylik_grafikli))
    app.add_handler(CommandHandler("grafiktum", tum_grafikli))

    app.add_handler(CommandHandler("warn", uyari_ver))
    app.add_handler(CommandHandler("unwarn", uyari_sil))
    app.add_handler(CommandHandler("ban", ban_at))
    app.add_handler(CommandHandler("unban", unban_at))
    app.add_handler(CommandHandler("mute", mute_at))
    app.add_handler(CommandHandler("unmute", unmute_at))

    app.add_handler(MessageHandler(filters.ALL, mesajlari_takip_et))

    print("Bulut Sunucu Botu Çalışıyor!")
    app.run_polling(allowed_updates=["chat_member", "message"])
