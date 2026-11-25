# -*- coding: utf-8 -*-
"""
Shahnoza uchun Telegram userbot (Telethon).
Siz offline bo'lganingizda shaxsiy chatga yozganlarga avtomatik javob beradi.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ai_modul
from telethon import TelegramClient, events
from telethon.tl.types import User, UserStatusOffline, UserStatusOnline

BASE_DIR = Path(__file__).resolve().parent


def _data_dir():
    """Holat, log va session fayllari papkasi. Railway'da Volume ulangan bo'lsa, DATA_DIR=/data qiling."""
    custom = (os.environ.get("DATA_DIR") or "").strip()
    if custom:
        try:
            Path(custom).mkdir(parents=True, exist_ok=True)
            return Path(custom)
        except OSError as exc:
            print(f"DATA_DIR='{custom}' ishlatib bo'lmadi ({exc}). Bot papkasi ishlatiladi.", file=sys.stderr)
    return BASE_DIR


DATA_DIR = _data_dir()
LOG_FILE = DATA_DIR / "bot.log"
STATE_FILE = DATA_DIR / "holat.json"
SESSION_PATH = str(DATA_DIR / "akkaunt")  # Telethon ".session" qo'shadi -> akkaunt.session

TELEGRAM_SERVICE_ID = 777000
OWN_SEND_MARK_SECONDS = 5
MEDIA_MARK = "[rasm/fayl/ovozli xabar]"
MAX_UNREPLIED = 50

MODES = {
    "avto": "online holatingizga qarab ishlaydi",
    "yoq": "doim javob beradi",
    "bor": "umuman javob bermaydi",
}

DEFAULTS = {
    "AWAY_MESSAGE": "Shahnoza hozir band.",
    "OFFLINE_AFTER_MINUTES": 0,
    "AWAY_AFTER_MINUTES": 10,
    "REPLY_COOLDOWN_HOURS": 0,
    "REPLY_DELAY_SECONDS": 3,
    "NIGHT_HOURS": None,
    "IGNORE_CONTACTS": False,
    "NOTIFY_ME": True,
    "TIMEZONE": "Asia/Tashkent",
    "AI_PROVIDER": "yoq",
    "GEMINI_API_KEY": "",
    "GEMINI_MODEL": "gemini-2.5-flash",
    "OLLAMA_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "llama3.1",
    "AI_HISTORY_MESSAGES": 6,
    "AI_TIMEOUT_SECONDS": 30,
    "AI_PREFIX": "🤖 Avtomatik yordamchi:",
    "AI_PERSONAL_REPLY": "Xabaringizni albatta yetkazaman, tez orada o'zim javob beraman",
}

HELP_TEXT = (
    "Buyruqlar (Saqlangan xabarlarda yoziladi):\n"
    ".yoq - doim javob bersin\n"
    ".bor - umuman javob bermasin\n"
    ".avto - online holatimga qarab ishlasin (standart)\n"
    ".holat - rejim va hozir javob berish-bermasligi\n"
    ".matn <matn> - javob matnini o'zgartirish ({ism} ishlatish mumkin)\n"
    ".yordam - shu ro'yxat"
)

log = logging.getLogger("userbot")


TRUE_WORDS = ("1", "true", "yes", "on", "ha", "yoq", "yoqilgan")


def cast_env(name, raw, default):
    """Muhit o'zgaruvchisi matnini sozlama turiga keltiradi (xato bo'lsa ValueError)."""
    raw = raw.strip()
    if name == "NIGHT_HOURS":  # masalan: 23:00-08:00  (o'chirish uchun: yoq)
        if raw.lower() in ("yoq", "none", "off", "-"):
            return None
        parts = [p.strip() for p in raw.replace("-", " ").split()]
        if len(parts) != 2:
            raise ValueError("NIGHT_HOURS '23:00-08:00' ko'rinishida bo'lishi kerak")
        return (parts[0], parts[1])
    if isinstance(default, bool):
        return raw.lower() in TRUE_WORDS
    if isinstance(default, int):
        return int(raw)
    return raw


class Settings:
    """config.py dagi qiymatlarni o'qiydi; yetishmaganlari uchun standart qiymat ishlatadi.
    Bir xil nomli muhit o'zgaruvchisi (Railway Variables) config.py dagi qiymatni bosib o'tadi."""

    def __init__(self, module):
        self.API_ID = getattr(module, "API_ID", 0)
        self.API_HASH = getattr(module, "API_HASH", "")
        for key, value in DEFAULTS.items():
            setattr(self, key, getattr(module, key, value))
        for key in ("API_ID", "API_HASH", *DEFAULTS):
            raw = os.environ.get(key)
            if raw is None or not raw.strip():
                continue
            try:
                setattr(self, key, cast_env(key, raw, getattr(self, key)))
            except ValueError as exc:
                log.warning("Muhit o'zgaruvchisi %s noto'g'ri (%s). config.py dagi qiymat ishlatiladi.", key, exc)


class State:
    """Rejim, maxsus matn va javoblar tarixi (holat.json)."""

    def __init__(self, path):
        self.path = Path(path)
        self.mode = "avto"
        self.text = None
        self.replied = {}  # {user_id (str): ISO vaqt}
        self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except Exception as exc:
            log.warning("holat.json o'qib bo'lmadi, standart holat ishlatiladi: %s", exc)
            return
        if data.get("mode") in MODES:
            self.mode = data["mode"]
        if isinstance(data.get("matn"), str) and data["matn"].strip():
            self.text = data["matn"]
        if isinstance(data.get("javoblar"), dict):
            self.replied = {str(k): str(v) for k, v in data["javoblar"].items()}

    def save(self):
        data = {"mode": self.mode, "matn": self.text, "javoblar": self.replied}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)


def parse_hhmm(value):
    hours, minutes = str(value).split(":")
    return int(hours) * 60 + int(minutes)


def describe_message(message):
    """Xabarni matn ko'rinishiga keltiradi (media bo'lsa belgi qo'yadi)."""
    text = (getattr(message, "raw_text", "") or "").strip()
    media = getattr(message, "media", None)
    if media is not None and type(media).__name__ == "MessageMediaWebPage":
        media = None  # havola ko'rinishi media hisoblanmaydi
    if text and media is not None:
        return f"{text} {MEDIA_MARK}"
    if media is not None:
        return MEDIA_MARK
    return text or "[bo'sh xabar]"


def full_name(user):
    name = " ".join(p for p in (user.first_name, user.last_name) if p)
    return name or (f"@{user.username}" if user.username else str(user.id))


class Bot:
    def __init__(self, client, cfg, state):
        self.client = client
        self.cfg = cfg
        self.state = state
        self.me = None
        self.tz = self._load_tz()
        self.last_activity = None  # sizning oxirgi faolligingiz (UTC)
        self.marks = {}            # chat_id -> botning o'z xabari belgisi tugash vaqti
        self.unreplied = {}        # user_id -> javobsiz xabarlar matni
        self.seq = {}              # user_id -> xabar tartib raqami (ketma-ket xabarlarni jamlash uchun)
        self.tasks = set()
        self.last_bot_send = None      # botning oxirgi yuborgan xabari vaqti (UTC)
        self.bot_offline_since = None  # bot "online" qilib qo'ygunga qadar haqiqiy offline vaqti
        self.ai = None                 # ai_modul.Assistant yoki None (AI_PROVIDER = "yoq")
        self.locks = {}                # user_id -> asyncio.Lock (bir odamga bir vaqtda bitta javob)

    # ---------- yordamchi ----------
    def _load_tz(self):
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(self.cfg.TIMEZONE)
        except Exception as exc:
            log.warning("Vaqt mintaqasi '%s' topilmadi (%s). UTC ishlatiladi. "
                        "'pip install tzdata' ni tekshiring.", self.cfg.TIMEZONE, exc)
            return timezone.utc

    def now(self):
        return datetime.now(timezone.utc)

    def mark(self, chat_id):
        """Botning o'zi yuborgan xabar sizning faolligingiz hisoblanmasligi uchun 5 soniyalik belgi."""
        self.marks[chat_id] = self.now() + timedelta(seconds=OWN_SEND_MARK_SECONDS)

    def is_marked(self, chat_id):
        until = self.marks.get(chat_id)
        if until is None:
            return False
        if self.now() <= until:
            return True
        del self.marks[chat_id]
        return False

    def register(self):
        self.client.add_event_handler(self.on_incoming, events.NewMessage(incoming=True))
        self.client.add_event_handler(self.on_outgoing, events.NewMessage(outgoing=True))

    async def say(self, text):
        """Saqlangan xabarlarga (me) xabar yuboradi."""
        self.mark(self.me.id)
        await self.client.send_message("me", text)
        self.last_bot_send = self.now()

    async def begin_quiet(self):
        """Xabar yuborishdan OLDIN chaqiriladi: hozir offline bo'lsangiz, True qaytaradi.
        Telegram akkauntga xabar yuborilganda uni qisqa muddatga 'online' qilib qo'yadi.
        Shuning uchun bot o'z xabaridan keyin holatni qayta 'offline'ga qaytaradi (end_quiet)."""
        status, was = await self.get_presence()
        if status == "offline":
            self.bot_offline_since = was
            return True
        return False

    async def end_quiet(self, was_offline):
        """Botning o'z xabari sabab paydo bo'lgan 'online' holatini bekor qiladi."""
        if not was_offline:
            return
        try:
            from telethon.tl.functions.account import UpdateStatusRequest
            await self.client(UpdateStatusRequest(offline=True))
            log.info("Bot xabaridan keyin holat 'offline'ga qaytarildi")
        except Exception as exc:
            log.warning("Holatni 'offline'ga qaytarib bo'lmadi: %s", exc)

    # ---------- holatni aniqlash ----------
    async def get_presence(self):
        """('online', None) | ('offline', was_online) | ('unknown', None)"""
        try:
            me = await self.client.get_me()
            status = getattr(me, "status", None)
        except Exception as exc:
            log.warning("Holatni olib bo'lmadi: %s", exc)
            return "unknown", None
        if isinstance(status, UserStatusOnline):
            self.bot_offline_since = None  # hozir online - eski offline vaqti eskirdi
            return "online", None
        if isinstance(status, UserStatusOffline) and status.was_online:
            was = status.was_online
            if was.tzinfo is None:
                was = was.replace(tzinfo=timezone.utc)
            # Bot xabari holatni bir lahzaga 'online' qilgan bo'lsa, offline vaqtini yo'qotmaymiz.
            if (self.bot_offline_since and self.last_bot_send
                    and abs((was - self.last_bot_send).total_seconds()) < 180):
                was = self.bot_offline_since
            return "offline", was
        return "unknown", None

    def in_night(self):
        hours = self.cfg.NIGHT_HOURS
        if not hours:
            return False
        try:
            start, end = parse_hhmm(hours[0]), parse_hhmm(hours[1])
        except Exception:
            log.warning("NIGHT_HOURS noto'g'ri formatda: %r", hours)
            return False
        local = self.now().astimezone(self.tz)
        cur = local.hour * 60 + local.minute
        if start <= end:
            return start <= cur < end
        return cur >= start or cur < end  # yarim tundan o'tadigan oraliq

    async def presence_decision(self):
        if self.in_night():
            return True, f"tungi vaqt ({self.cfg.NIGHT_HOURS[0]}-{self.cfg.NIGHT_HOURS[1]}) - doim javob"
        status, was = await self.get_presence()
        now = self.now()
        if status == "online":
            if self.last_bot_send:
                ago = int((now - self.last_bot_send).total_seconds())
                return False, f"siz hozir online (bot oxirgi marta {ago} soniya oldin xabar yuborgan)"
            return False, "siz hozir online"
        if status == "offline":
            mins = max(0.0, (now - was).total_seconds()) / 60
            need = self.cfg.OFFLINE_AFTER_MINUTES
            if mins >= need:
                return True, f"siz {int(mins)} daqiqadan beri offline"
            return False, f"siz {int(mins)} daqiqadan beri offline (kutish: {need} daqiqa)"
        # holat noma'lum -> oxirgi faolligingizga qaraymiz
        if self.last_activity is None:
            return True, "holat noma'lum, faollik kuzatilmagan - offline deb hisoblandi"
        mins = (now - self.last_activity).total_seconds() / 60
        limit = self.cfg.AWAY_AFTER_MINUTES
        if mins > limit:
            return True, f"holat noma'lum, oxirgi faolligingiz {int(mins)} daqiqa oldin"
        return False, f"holat noma'lum, oxirgi faolligingiz {int(mins)} daqiqa oldin (chegara: {limit} daqiqa)"

    async def should_reply(self, user_id=None, use_cooldown=True):
        mode = self.state.mode
        if mode == "bor":
            return False, "rejim .bor - umuman javob berilmaydi"
        if mode == "yoq":
            ok, reason = True, "rejim .yoq - doim javob"
        else:
            ok, reason = await self.presence_decision()
        cooldown = self.cfg.REPLY_COOLDOWN_HOURS
        if ok and use_cooldown and user_id is not None and cooldown and cooldown > 0:
            last = self.state.replied.get(str(user_id))
            if last:
                try:
                    passed = self.now() - datetime.fromisoformat(last)
                    if passed < timedelta(hours=cooldown):
                        return False, (f"{int(passed.total_seconds() // 60)} daqiqa oldin javob berilgan "
                                       f"(REPLY_COOLDOWN_HOURS={cooldown})")
                except ValueError:
                    pass
        return ok, reason

    # ---------- kiruvchi xabarlar ----------
    async def on_incoming(self, event):
        try:
            await self._on_incoming(event)
        except Exception:
            log.exception("Kiruvchi xabarni qayta ishlashda xato")

    async def _on_incoming(self, event):
        if not event.is_private:
            return
        sender = await event.get_sender()
        if not isinstance(sender, User):
            return
        if sender.bot or sender.id == self.me.id or sender.id == TELEGRAM_SERVICE_ID:
            return
        if self.cfg.IGNORE_CONTACTS and getattr(sender, "contact", False):
            log.info("O'tkazildi: %s - kontakt (IGNORE_CONTACTS=True)", full_name(sender))
            return
        uid = sender.id
        pending = self.unreplied.setdefault(uid, [])
        pending.append(describe_message(event.message))
        del pending[:-MAX_UNREPLIED]
        self.seq[uid] = self.seq.get(uid, 0) + 1
        task = asyncio.create_task(self._answer_later(sender, self.seq[uid], event.message.id))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _answer_later(self, sender, my_seq, last_msg_id):
        try:
            await asyncio.sleep(self.cfg.REPLY_DELAY_SECONDS)
            if self.seq.get(sender.id) != my_seq:
                return  # yangi xabar keldi (yoki siz o'zingiz yozdingiz) - oxirgisi javob beradi
            name = full_name(sender)
            lock = self.locks.setdefault(sender.id, asyncio.Lock())
            async with lock:  # AI sekin bo'lsa ham bir odamga ikki marta javob ketmasin
                if not self.unreplied.get(sender.id):
                    return  # xabarlar allaqachon javobsiz emas (oldingi vazifa hal qilgan yoki siz yozgansiz)
                # AI rejimida har bir savolga javob beriladi, shuning uchun cooldown bu yerda tekshirilmaydi
                ok, reason = await self.should_reply(sender.id, use_cooldown=self.ai is None)
                if not ok:
                    log.info("O'tkazildi: %s - %s", name, reason)
                    return
                if self.ai is not None:
                    await self.send_ai_reply(sender, name, reason, last_msg_id)
                else:
                    await self.send_reply(sender, name, reason, last_msg_id)
        except Exception:
            log.exception("Javob berishda xato")

    async def send_reply(self, sender, name, reason, reply_to_id):
        template = self.state.text or self.cfg.AWAY_MESSAGE
        text = template.replace("{ism}", sender.first_name or name)
        was_offline = await self.begin_quiet()
        self.mark(sender.id)
        try:
            await self.client.send_message(sender, text, reply_to=reply_to_id)
            self.last_bot_send = self.now()
        except Exception as exc:
            log.error("Javob yuborilmadi: %s - %s", name, exc)
            return
        self.state.replied[str(sender.id)] = self.now().isoformat()
        self.state.save()
        messages = self.unreplied.pop(sender.id, [])
        log.info("Javob yuborildi: %s - %s", name, reason)
        try:
            if self.cfg.NOTIFY_ME:
                await self.notify(sender, messages)
        finally:
            await self.end_quiet(was_offline)

    @staticmethod
    def who_line(sender):
        who = full_name(sender)
        if sender.username:
            who += f" (@{sender.username})"
        return who

    async def notify(self, sender, messages):
        lines = [f"{i}. {m[:300]}" for i, m in enumerate(messages, 1)] or ["(xabar matni yo'q)"]
        note = (f"Avto-javob yuborildi\nKim: {self.who_line(sender)}\n"
                "Javobsiz xabarlari:\n" + "\n".join(lines))
        try:
            await self.say(note[:4000])
        except Exception as exc:
            log.error("Eslatmani yuborib bo'lmadi: %s", exc)

    # ---------- sun'iy intellekt rejimi ----------
    async def build_history(self, sender):
        """Chatdagi oxirgi AI_HISTORY_MESSAGES ta xabar: [("Ular"|"Men", matn), ...] (eskisidan yangisiga)."""
        limit = int(self.cfg.AI_HISTORY_MESSAGES)
        if limit <= 0:
            return []
        try:
            msgs = await self.client.get_messages(sender, limit=limit)
        except Exception as exc:
            log.warning("AI: chat tarixini o'qib bo'lmadi: %s", exc)
            return []
        return [("Men" if getattr(m, "out", False) else "Ular", describe_message(m))
                for m in reversed(list(msgs))]

    async def classify(self, sender, messages):
        """[(tur, javob)] qaytaradi. AI ishlamasa hammasi "shaxsiy" bo'ladi."""
        batch = messages[-ai_modul.MAX_MESSAGES:]
        older = len(messages) - len(batch)  # juda eski xabarlar AI ga yuborilmaydi, "shaxsiy" hisoblanadi
        try:
            history = await self.build_history(sender)
            results = await asyncio.wait_for(self.ai.classify(history, batch),
                                             timeout=float(self.cfg.AI_TIMEOUT_SECONDS) + 5)
        except asyncio.TimeoutError:
            log.warning("AI: javob kutish vaqti tugadi - xabarlar 'shaxsiy' deb hisoblandi")
            results = None
        except ai_modul.AIError as exc:
            log.warning("AI ishlamadi (%s) - xabarlar 'shaxsiy' deb hisoblandi", exc)
            results = None
        except Exception:
            log.exception("AI kutilmagan xato - xabarlar 'shaxsiy' deb hisoblandi")
            results = None
        if results is None:
            results = [("shaxsiy", "")] * len(batch)
        return [("shaxsiy", "")] * older + list(results)

    async def send_to(self, sender, text, **kw):
        self.mark(sender.id)
        await self.client.send_message(sender, text, **kw)
        self.last_bot_send = self.now()

    async def send_ai_reply(self, sender, name, reason, reply_to_id):
        messages = list(self.unreplied.get(sender.id, []))
        was_offline = await self.begin_quiet()
        try:
            results = await self.classify(sender, messages)
            if len(self.unreplied.get(sender.id, [])) < len(messages):
                log.info("O'tkazildi: %s - AI ishlayotganda siz o'zingiz yozdingiz", name)
                return
            fan = [(m, ans) for m, (tur, ans) in zip(messages, results) if tur == "fan"]
            personal = [m for m, (tur, _) in zip(messages, results) if tur != "fan"]
            log.info("AI [%s]: %s - fan: %d, shaxsiy: %d (%s)", self.ai.label, name,
                     len(fan), len(personal), reason)

            for question, answer in fan:
                try:
                    await self.send_to(sender, f"{self.cfg.AI_PREFIX}\n{answer}")
                except Exception as exc:
                    log.error("AI javobi yuborilmadi: %s - %s", name, exc)
                    personal.append(question)  # yuborilmagan savol "shaxsiy" sifatida sizga yetkaziladi

            if personal:
                if self.reply_cooldown_ok(sender.id):
                    text = self.cfg.AI_PERSONAL_REPLY.replace("{ism}", sender.first_name or name)
                    try:
                        await self.send_to(sender, text, reply_to=reply_to_id)
                        # cooldown faqat "shaxsiy" javob matniga tegishli; AI savollariga javob doim beriladi
                        self.state.replied[str(sender.id)] = self.now().isoformat()
                        self.state.save()
                    except Exception as exc:
                        log.error("Javob yuborilmadi: %s - %s", name, exc)
                else:
                    log.info("%s: 'shaxsiy' javob matni yuborilmadi (REPLY_COOLDOWN_HOURS)", name)
                await self.deliver_personal(sender, personal)  # bu har doim sizga yetkaziladi
            elif fan and self.cfg.NOTIFY_ME:
                await self.deliver_answers(sender, fan)

            # Faqat ko'rib chiqilgan xabarlar olib tashlanadi (yangilari qoladi)
            pending = self.unreplied.get(sender.id, [])
            del pending[:len(messages)]
        finally:
            await self.end_quiet(was_offline)

    def reply_cooldown_ok(self, user_id):
        cooldown = self.cfg.REPLY_COOLDOWN_HOURS
        last = self.state.replied.get(str(user_id))
        if not (cooldown and cooldown > 0 and last):
            return True
        try:
            return self.now() - datetime.fromisoformat(last) >= timedelta(hours=cooldown)
        except ValueError:
            return True

    async def deliver_personal(self, sender, messages):
        lines = [f"{i}. {m[:600]}" for i, m in enumerate(messages, 1)]
        note = (f"Shaxsiy xabar (AI ajratdi)\nKim: {self.who_line(sender)}\n"
                "Xabarlari:\n" + "\n".join(lines))
        try:
            await self.say(note[:4000])
        except Exception as exc:
            log.error("Shaxsiy xabarni yetkazib bo'lmadi: %s", exc)

    async def deliver_answers(self, sender, pairs):
        lines = [f"{i}. Savol: {q[:300]}\n   Javob: {a[:500]}" for i, (q, a) in enumerate(pairs, 1)]
        note = (f"AI savollarga javob berdi\nKim: {self.who_line(sender)}\n" + "\n".join(lines))
        try:
            await self.say(note[:4000])
        except Exception as exc:
            log.error("Eslatmani yuborib bo'lmadi: %s", exc)

    # ---------- sizning xabarlaringiz ----------
    async def on_outgoing(self, event):
        try:
            await self._on_outgoing(event)
        except Exception:
            log.exception("Chiquvchi xabarni qayta ishlashda xato")

    async def _on_outgoing(self, event):
        chat_id = event.chat_id
        text = (event.raw_text or "").strip()
        is_command = chat_id == self.me.id and text.startswith(".")
        # Botning o'z xabari faollik emas. Lekin "." bilan boshlangan buyruqni
        # (bot xabarlari hech qachon "." bilan boshlanmaydi) har doim qabul qilamiz.
        if self.is_marked(chat_id) and not is_command:
            return
        self.last_activity = self.now()
        if chat_id is not None:
            self.unreplied.pop(chat_id, None)
            self.seq[chat_id] = self.seq.get(chat_id, 0) + 1  # kutayotgan avto-javobni bekor qiladi
        if is_command:
            await self.command(text)

    # ---------- buyruqlar ----------
    async def command(self, text):
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd in (".yoq", ".bor", ".avto"):
            self.state.mode = cmd[1:]
            self.state.save()
            log.info("Rejim o'zgardi: %s", self.state.mode)
            await self.say(f"Rejim: {self.state.mode} - {MODES[self.state.mode]}")
        elif cmd == ".holat":
            ok, reason = await self.should_reply()
            await self.say(
                f"Rejim: {self.state.mode} - {MODES[self.state.mode]}\n"
                f"Hozir: {'javob BERADI' if ok else 'javob BERMAYDI'}\n"
                f"Sabab: {reason}\n"
                f"Javob matni: {self.state.text or self.cfg.AWAY_MESSAGE}"
            )
        elif cmd == ".matn":
            if not arg:
                await self.say(f"Hozirgi javob matni: {self.state.text or self.cfg.AWAY_MESSAGE}\n"
                               "O'zgartirish: .matn <yangi matn>")
                return
            self.state.text = arg
            self.state.save()
            log.info("Javob matni o'zgardi: %s", arg)
            await self.say(f"Javob matni yangilandi: {arg}")
        elif cmd == ".yordam":
            await self.say(HELP_TEXT)

    # ---------- ishga tushish ----------
    async def start_up(self):
        self.me = await self.client.get_me()
        ok, reason = await self.should_reply()
        ai_text = self.ai.provider if self.ai else "yoq"
        log.info("Bot ishga tushdi. Rejim: %s. AI: %s. Hozir: %s (%s)",
                 self.state.mode, ai_text, "javob beradi" if ok else "javob bermaydi", reason)
        was_offline = await self.begin_quiet()
        try:
            await self.say(f"Bot ishga tushdi\nRejim: {self.state.mode} - {MODES[self.state.mode]}\n"
                           f"AI: {ai_text}\nBuyruqlar ro'yxati: .yordam")
        finally:
            await self.end_quiet(was_offline)


def setup_logging():
    log.setLevel(logging.INFO)
    if log.handlers:
        return
    fmt = logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))
    except OSError as exc:  # fayl tizimi yozishga yopiq bo'lsa ham bot konsolga yozishda davom etadi
        print(f"bot.log ochib bo'lmadi ({exc}). Yozuvlar faqat konsolga chiqadi.", file=sys.stderr)
    for handler in handlers:
        handler.setFormatter(fmt)
        log.addHandler(handler)
    logging.getLogger("telethon").setLevel(logging.WARNING)


def load_config():
    """config.py ni yuklaydi. Railway'da u bo'lmasligi mumkin: u holda hamma narsa muhit o'zgaruvchilaridan olinadi."""
    try:
        import config
        return config
    except ImportError:
        log.info("config.py topilmadi, sozlamalar muhit o'zgaruvchilaridan olinadi.")
        import types
        return types.SimpleNamespace()


def make_client(cfg):
    """SESSION_STRING bo'lsa matnli session (Railway), bo'lmasa akkaunt.session fayli (kompyuter)."""
    session_string = (os.environ.get("SESSION_STRING") or "").strip()
    if session_string:
        from telethon.sessions import StringSession
        log.info("Session: SESSION_STRING muhit o'zgaruvchisidan")
        return TelegramClient(StringSession(session_string), cfg.API_ID, cfg.API_HASH)
    log.info("Session: %s.session fayli", SESSION_PATH)
    return TelegramClient(SESSION_PATH, cfg.API_ID, cfg.API_HASH)


async def main():
    setup_logging()
    cfg = Settings(load_config())
    if not cfg.API_ID or not cfg.API_HASH:
        log.error("API_ID va API_HASH to'ldirilmagan (my.telegram.org dan oling). "
                  "Kompyuterda: config.py ga, Railway'da: Variables bo'limiga yozing.")
        return
    client = make_client(cfg)
    state = State(STATE_FILE)
    bot = Bot(client, cfg, state)
    bot.ai = ai_modul.create(cfg)
    bot.register()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            if not sys.stdin or not sys.stdin.isatty():
                log.error("Akkauntga kirilmagan va bu yerda telefon/kod kiritib bo'lmaydi. "
                          "Kompyuterda session_yarat.py ni ishga tushirib, chiqqan matnni "
                          "SESSION_STRING o'zgaruvchisiga qo'ying.")
                return
            await client.start()  # birinchi marta: telefon raqami va kod so'raladi
        await bot.start_up()
        await client.run_until_disconnected()
    except Exception as exc:
        if type(exc).__name__ == "AuthKeyDuplicatedError":
            log.error("Bu session boshqa joyda ham ishlatilmoqda (masalan, kompyuterda yoki eski Railway "
                      "deploy'ida). Bittasini to'xtating yoki session_yarat.py bilan yangi session oling.")
            return
        raise
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")
