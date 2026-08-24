from datetime import datetime
import os
import re
import sqlite3
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ChatMemberHandler, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "8823945672:AAHnfiT2s2PR3Vt4o_8xD6ro3tgrs5T1RMk"

def veritabani_kur():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kullanicilar (
            uid INTEGER PRIMARY KEY,
            name TEXT,
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

KURALLAR_METNI = """
📜 **ProyuncuTR_hck Sohbet Grup Kuralları / Chat Group Rules**

🇹🇷 **Türkçe Kurallar:**
1️⃣ Küfür/Argo kelimeler kesinlikle yasaktır. 5 uyarı alırsanız banlanırsınız.
2️⃣ Link göndermek otomatik olarak mesaj gönderme özelliğinizin kapatılmasına (mute) sebep olur.
3️⃣ İzinsiz reklam yapmak kesinlikle yasaktır! Reklam için @ProyuncuTR adresine DM atınız.

🇬🇧 **English Rules:**
1️⃣ Profanity/slang is strictly prohibited. Accumulating 5 warnings results in a ban.
2️⃣ Sending links will automatically disable your ability to send messages.
3️⃣ Unauthorized advertising is strictly prohibited! Contact @ProyuncuTR via DM.

2026© ProyuncuTR_hck
"""

async def admin_mi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private": return True
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ["administrator", "creator"]

async def mesajlari_takip_et(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user: return
    user = update.message.from_user
    if user.is_bot: return

    uid, name, chat_id = user.id, user.first_name, update.effective_chat.id
    mesaj_metni = update.message.text.lower() if update.message.text else ""
    is_admin = await admin_mi(update, context)

    # LİNK ENGELLEME
    link_regex = r"(https?://\S+|www\.\S+|\S+\.(com|net|org|io|tk|ml|ga|xyz|cf|gq))"
    if re.search(link_regex, mesaj_metni) and not is_admin:
        try:
            await update.message.delete()
            await context.bot.restrict_chat_member(chat_id=chat_id, user_id=uid, permissions=ChatPermissions(can_send_messages=False))
            await context.bot.send_message(chat_id=chat_id, text=f"🚫 {name}, grupta link paylaşmak yasaktır! / Sharing links is prohibited!")
            return
        except Exception as e: print(f"Link hatası: {e}")

    # KÜFÜR ENGELLEME (5 UYARI)
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT uyari FROM kullanicilar WHERE uid = ?", (uid,))
    res = cursor.fetchone()
    mevcut_uyari = (res[0] if res else 0)

    if any(kufur in mesaj_metni for kufur in KUFUR_LISTESI) and not is_admin:
        try:
            await update.message.delete()
            mevcut_uyari += 1
            if mevcut_uyari >= 5:
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=uid)
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {name} 5/5 uyarıya ulaştı ve yasaklandı / reached 5/5 warnings and has been banned! 🚷")
                cursor.execute("UPDATE kullanicilar SET uyari = 0 WHERE uid = ?", (uid,))
            else:
                cursor.execute("INSERT INTO kullanicilar (uid, name, uyari) VALUES (?, ?, ?) ON CONFLICT(uid) DO UPDATE SET uyari = ?", (uid, name, mevcut_uyari, mevcut_uyari))
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {name}, küfür yasaktır! Uyarı: **{mevcut_uyari}/5**", parse_mode="Markdown")
            conn.commit()
            conn.close()
            return
        except Exception as e: print(f"Küfür hatası: {e}")

    # SAYAÇ
    cursor.execute("""
        INSERT INTO kullanicilar (uid, name, gunluk, haftalik, aylik, toplam) VALUES (?, ?, 1, 1, 1, 1)
        ON CONFLICT(uid) DO UPDATE SET name=excluded.name, gunluk=gunluk+1, haftalik=haftalik+1, aylik=aylik+1, toplam=toplam+1
    """, (uid, name))
    conn.commit()
    conn.close()

async def kurallari_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(KURALLAR_METNI, parse_mode="Markdown")

async def uyari_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_mi(update, context) or not update.message.reply_to_message: return
    hedef = update.message.reply_to_message.from_user
    uid, chat_id = hedef.id, update.effective_chat.id

    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT uyari FROM kullanicilar WHERE uid = ?", (uid,))
    res = cursor.fetchone()
    mevcut = (res[0] if res else 0) + 1

    if mevcut >= 5:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=uid)
        cursor.execute("UPDATE kullanicilar SET uyari = 0 WHERE uid = ?", (uid,))
        await update.message.reply_text(f"⚠️ {hedef.first_name} 5/5 uyarıya ulaştı ve banlandı! / banned!")
    else:
        cursor.execute("INSERT INTO kullanicilar (uid, name, uyari) VALUES (?, ?, ?) ON CONFLICT(uid) DO UPDATE SET uyari = ?", (uid, hedef.first_name, mevcut, mevcut))
        await update.message.reply_text(f"⚠️ {hedef.first_name} uyarıldı! Uyarı: **{mevcut}/5**", parse_mode="Markdown")

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
        await update.message.reply_text(f"✅ {hedef.first_name} uyarısı silindi. Kalan: **{mevcut}/5**", parse_mode="Markdown")
    conn.commit()
    conn.close()

async def siralama_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, toplam FROM kullanicilar ORDER BY toplam DESC LIMIT 5")
    toplam_liste = cursor.fetchall()
    conn.close()

    if not toplam_liste:
        await update.message.reply_text("ℹ️ Henüz veri yok! / No data!")
        return

    metin = "📊 **PROYUNCUTR_HCK AKTİFLİK SIRALAMASI / LEADERBOARD** 📊\n\n"
    metin += "🏆 **Tüm Zamanlar / All Time:**\n" + "".join([f"{i}. {d[0]} - {d[1]} mesaj\n" for i, d in enumerate(toplam_liste, 1)])
    await update.message.reply_text(metin, parse_mode="Markdown")

async def grup_hareketleri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if result.old_chat_member.status in ["left", "kicked"] and result.new_chat_member.status == "member":
        kullanici_adi = result.new_chat_member.user.first_name
        su_an = datetime.now().strftime("%d.%m.%Y - %H:%M")
        mesaj = (
            f"🇹🇷 Merhaba {kullanici_adi}, ProyuncuTR_hck Sohbet grubuna hoş geldin! 🤗\n"
            f"🇬🇧 Hello {kullanici_adi}, welcome to the ProyuncuTR_hck chat group! 🤗\n\n"
            f"⏰ (ZAMAN / TIME: {su_an})"
        )
        keyboard = [[InlineKeyboardButton("📢 Telegram", url="https://t.me/ProyuncuTR_hck"), InlineKeyboardButton("▶️ YouTube", url="https://www.youtube.com/@ProyuncuTR_hck")]]
        await context.bot.send_message(chat_id=update.effective_chat.id, text=mesaj, reply_markup=InlineKeyboardMarkup(keyboard))

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(ChatMemberHandler(grup_hareketleri, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mesajlari_takip_et))
    app.add_handler(CommandHandler("kurallar", kurallari_goster))
    app.add_handler(CommandHandler("rules", kurallari_goster))
    app.add_handler(CommandHandler("siralama", siralama_goster))
    app.add_handler(CommandHandler("top", siralama_goster))
    app.add_handler(CommandHandler("warn", uyari_ver))
    app.add_handler(CommandHandler("unwarn", uyari_sil))

    print("Bulut Sunucu Botu Çalışıyor!")
    app.run_polling(allowed_updates=["chat_member", "message"])
