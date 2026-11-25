# -*- coding: utf-8 -*-
# RAILWAY/GITHUB NUSXASI: bu faylda maxfiy kalitlar YO'Q.
# Railway'da API_ID, API_HASH, SESSION_STRING, GEMINI_API_KEY va boshqa sozlamalar
# "Variables" bo'limidan olinadi (bir xil nomli o'zgaruvchi shu fayldagi qiymatni bosib o'tadi).
# Kalitlarni bu faylga yozib GitHub'ga YUKLAMANG.
"""
Userbot sozlamalari.
Faqat shu faylni tahrirlang. O'zgartirgandan keyin botni qayta ishga tushiring.
"""

# --- Telegram API kalitlari (https://my.telegram.org -> API development tools) ---

# API_ID: my.telegram.org dan olingan raqam (masalan, 1234567).
API_ID = 0

# API_HASH: my.telegram.org dan olingan uzun harf-raqamli satr, qo'shtirnoq ichida.
API_HASH = ""


# --- Avto-javob sozlamalari ---

# AWAY_MESSAGE: offline paytingizda yuboriladigan javob matni.
# {ism} yozsangiz, u xabar yozgan odamning ismi bilan almashtiriladi.
# Masalan: "Salom, {ism}! Shahnoza hozir band."
AWAY_MESSAGE = "Shahnoza hozir band."

# OFFLINE_AFTER_MINUTES: offline bo'lganingizdan necha daqiqa o'tgach javob berilsin.
# 0 bo'lsa, offline bo'lishingiz bilan darhol javob beriladi.
OFFLINE_AFTER_MINUTES = 0

# AWAY_AFTER_MINUTES: Telegram holatingizni aniqlab bo'lmasa (masalan, "oxirgi marta
# yaqinda" deb yashirilgan bo'lsa), siz oxirgi marta xabar yozganingizdan beri shuncha
# daqiqadan ko'p o'tgan bo'lsa, offline deb hisoblanadi.
AWAY_AFTER_MINUTES = 0

# REPLY_COOLDOWN_HOURS: bitta odamga necha soatda bir marta javob berilsin.
# 0 bo'lsa, har bir xabarga javob beriladi.
REPLY_COOLDOWN_HOURS = 0

# REPLY_DELAY_SECONDS: javob berishdan oldin necha soniya kutiladi. Shu vaqtda
# o'sha odamdan yana xabar kelsa, faqat bitta javob yuboriladi (ketma-ket xabarlar jamlanadi).
REPLY_DELAY_SECONDS = 3

# NIGHT_HOURS: tungi vaqt oralig'i. Masalan ("23:00", "08:00") berilsa, shu oraliqda
# online bo'lsangiz ham doim javob beriladi. O'chirish uchun None qoldiring.
NIGHT_HOURS = None

# IGNORE_CONTACTS: True bo'lsa, kontaktlaringizdagi odamlarga javob berilmaydi.
IGNORE_CONTACTS = False

# NOTIFY_ME: True bo'lsa, har bir avto-javobdan keyin "Saqlangan xabarlar"ga
# eslatma yuboriladi (kim yozgani va javobsiz qolgan xabarlari).
NOTIFY_ME = True

# TIMEZONE: vaqt mintaqangiz (NIGHT_HOURS shu mintaqa bo'yicha hisoblanadi).
TIMEZONE = "Asia/Tashkent"


# --- Sun'iy intellekt (AI) rejimi ---
# Yoqilganda bot kelgan xabarlarni "fan" (o'quv savoli) yoki "shaxsiy" ga ajratadi:
#   fan      - savolga o'zi javob beradi (javob AI_PREFIX bilan boshlanadi)
#   shaxsiy  - AI_PERSONAL_REPLY deb javob beradi va xabarni "Saqlangan xabarlar"ga yetkazadi
# AI ishlamay qolsa (internet yo'q, kalit xato va h.k.), xabar "shaxsiy" deb hisoblanadi.
# DIQQAT: AI yoqilganda yozishmalar (oxirgi xabarlar) tanlangan xizmatga yuboriladi.

# AI_PROVIDER: "yoq" (AI o'chiq, standart), "gemini" (Google, internet kerak) yoki
# "ollama" (kompyuteringizdagi mahalliy model, hech narsa tashqariga chiqmaydi).
AI_PROVIDER = "gemini"

# GEMINI_API_KEY: https://aistudio.google.com/apikey dan olingan kalit (qo'shtirnoq ichida).
# Faqat AI_PROVIDER = "gemini" bo'lganda kerak. Kalitni hech kimga bermang.
GEMINI_API_KEY = ""

# GEMINI_MODEL: Gemini modeli. Bo'sh qoldirilsa (tavsiya), bot mavjud eng yaxshi "flash" modelni o'zi
# tanlaydi; model band bo'lsa, keyingisiga o'tadi. Aniq nom yozsangiz (masalan, "gemini-2.5-flash"),
# u topilmasa ham bot o'zi boshqasini tanlaydi.
GEMINI_MODEL = ""

# OLLAMA_URL va OLLAMA_MODEL: faqat AI_PROVIDER = "ollama" uchun.
# Model topilmasa, o'rnatilgan modellardan biri tanlanadi.
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1"

# AI_HISTORY_MESSAGES: AI kontekst uchun chatdagi oxirgi nechta xabarni o'qisin.
AI_HISTORY_MESSAGES = 6

# AI_TIMEOUT_SECONDS: AI javobini necha soniya kutish. Shundan oshsa, xabar "shaxsiy" bo'ladi.
AI_TIMEOUT_SECONDS = 30

# AI_PREFIX: "fan" savollariga yuboriladigan javobning boshi.
AI_PREFIX = "🤖 Avtomatik yordamchi:"

# AI_PERSONAL_REPLY: "shaxsiy" xabarlarga javob matni ({ism} ishlatish mumkin).
AI_PERSONAL_REPLY = "Xabaringizni albatta yetkazaman, tez orada o'zim javob beraman"
