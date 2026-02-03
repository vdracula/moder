import asyncio
import logging
import os
import re
import time
from collections import defaultdict
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ChatMemberUpdated, MessageEntity
from aiogram.client.default import DefaultBotProperties

logging.basicConfig(level=logging.INFO)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")  # подставь токен или используй env
ADMIN_IDS = {810620178}            # сюда свои Telegram ID

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

# ================== ТЕКСТЫ ==================

RULES_TEXT = (
    "📜 <b>Правила чата «Нейрокодер из Москвы»</b>\n\n"
    "1. По теме: нейросети, код, автоматизация, проекты и боли участников.\n"
    "2. Без спама и серой рекламы. Хотите поделиться своим продуктом — сначала напишите админу.\n"
    "3. Уважение превыше всего: без токсичности, наездов и личных разборок.\n"
    "4. Вопрос по коду/нейросети = контекст + что уже пробовал. Так экономим время себе и другим.\n"
    "5. Политика и срачи — мимо. Мы тут прокачиваем мозг и нейросети, а не нервную систему.\n"
    "6. Админы и бот могут удалять сообщения и ограничивать доступ без долгих споров.\n\n"
    "Если сомневаешься, ок ли пост — лучше сначала спроси 🙂"
)

WELCOME_TEXT = (
    "👋 На связи <b>«Нейрокодер из Москвы»</b>.\n\n"
    "Это комьюнити для тех, кто хочет не просто «поболтать с ИИ», а заставить нейросети работать на свои задачи:\n"
    "боты, автоматизация, генерация контента, свои продукты и эксперименты.\n\n"
    "Что можно делать в чате:\n"
    "• задавать вопросы по нейрокодингу, коду и интеграциям\n"
    "• показывать свои проекты и просить разбор\n"
    "• делиться находками: промпты, сервисы, лайфхаки\n\n"
    "С чего начать:\n"
    "1) Прочитать /rules\n"
    "2) Коротко представиться: кто ты, чем занимаешься и что хочешь собрать с ИИ\n"
    "3) При первой задаче — описать контекст и цель, не только «как написать код»\n\n"
    "Добро пожаловать. Здесь нейросети работают, а ты — думаешь стратегически 🙂"
)

HELP_TEXT = (
    "🤖 <b>Я — бот-модератор «Нейрокодера из Москвы»</b>\n\n"
    "Что я умею:\n"
    "• приветствовать новых участников и напоминать правила\n"
    "• по команде /rules показать правила\n"
    "• по команде /welcome рассказать, что здесь происходит\n"
    "• фильтровать спам и флуд от новичков\n\n"
    "Админские команды (по reply): /warn, /ban"
)

# ================== РОУТЕРЫ ==================

base_router = Router()
group_router = Router()
group_router.message.filter(F.chat.type.in_({"group", "supergroup"}))

antiflood_router = Router()
antiflood_router.message.filter(F.chat.type.in_({"group", "supergroup"}))

# ================== УТИЛИТЫ ==================


def is_admin(message: Message) -> bool:
    return message.from_user and message.from_user.id in ADMIN_IDS


# --- антиспам: ключевые слова и ссылки ---

BAD_KEYWORDS = {
    "заработок в день", "быстрый заработок", "ставки на спорт",
    "пассивный доход", "инвестиции без риска", "подпишись на мой канал"
}

BAD_DOMAINS = {
    "t.me/joinchat", "bit.ly", "goo.gl", "tinyurl.com",
    "click.ru", "clck.ru"
}

URL_PATTERN = re.compile(r"(https?://\S+|t\.me/\S+)", re.IGNORECASE)


def contains_bad_link(text: str) -> bool:
    text_lower = text.lower()
    for d in BAD_DOMAINS:
        if d in text_lower:
            return True
    urls = URL_PATTERN.findall(text)
    if len(urls) >= 2:
        return True
    return False


def contains_bad_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(w in text_lower for w in BAD_KEYWORDS)


def looks_like_code(text: str) -> bool:
    if "```" in text:
        return True
    lines = text.splitlines()
    code_like_lines = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(
            kw in stripped
            for kw in ("def ", "class ", "for ", "while ", "if ", "else:", "try:", "except")
        ):
            code_like_lines += 1
            continue
        if any(ch in stripped for ch in ("{", "}", ";", "=>", "==", "::")):
            code_like_lines += 1
    return code_like_lines >= 2


# --- онбординг / отслеживание входа ---

joined_at = {}  # user_id -> timestamp
NEWBIE_SECONDS = 60        # 1 минута
FLOOD_WINDOW = 20          # окно 20 секунд
FLOOD_MAX_MESSAGES = 3     # максимум 3 сообщения в окне
user_messages_ts = defaultdict(list)  # user_id -> [timestamps]


def is_newbie_id(user_id: int) -> bool:
    ts = joined_at.get(user_id)
    if not ts:
        return False
    return time.time() - ts < NEWBIE_SECONDS


# ================== ХЕНДЛЕРЫ: БАЗОВЫЕ КОМАНДЫ ==================


@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот-помощник чата <b>«Нейрокодер из Москвы»</b>.\n\n"
        "Я помогаю с онбордингом и модерацией.\n"
        "Основные команды:\n"
        "• /rules — правила чата\n"
        "• /welcome — краткий онбординг\n"
        "• /help — что я умею"
    )


@base_router.message(Command("rules"))
async def cmd_rules(message: Message):
    await message.answer(RULES_TEXT)


@base_router.message(Command("welcome"))
async def cmd_welcome(message: Message):
    await message.answer(WELCOME_TEXT)


@base_router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT)


# ================== ОНБОРДИНГ В ГРУППЕ ==================


@dp.chat_member()
async def on_user_join(event: ChatMemberUpdated):
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    old = event.old_chat_member
    new = event.new_chat_member

    if old.status in ("left", "kicked") and new.status == "member":
        user = new.user
        joined_at[user.id] = time.time()
        mention = user.mention_html()
        text = (
            f"👋 {mention}, добро пожаловать в чат <b>«Нейрокодер из Москвы»</b>!\n\n"
            "Пожалуйста, ознакомься с правилами: /rules\n"
            "И короткий онбординг: /welcome\n\n"
            "Будет круто, если коротко напишешь, чем занимаешься и что хочешь собрать с нейросетями 🙂"
        )
        await event.bot.send_message(chat_id=event.chat.id, text=text)


# ================== АНТИФЛУД ДЛЯ НОВИЧКОВ ==================


@antiflood_router.message(F.text)
async def newbie_antiflood(message: Message):
    user = message.from_user
    if not user:
        return

    if user.id in ADMIN_IDS:
        return

    if not is_newbie_id(user.id):
        return

    now = time.time()
    ts_list = user_messages_ts[user.id]
    ts_list.append(now)
    ts_list[:] = [t for t in ts_list if now - t <= FLOOD_WINDOW]

    if len(ts_list) > FLOOD_MAX_MESSAGES:
        try:
            await message.delete()
        except Exception:
            pass
        try:
            await message.chat.send_message(
                f"🧊 @{user.username or user.id}, без флуда.\n"
                "Ты только что зашёл в «Нейрокодер из Москвы» — сначала /rules и /welcome, "
                "потом один нормальный вопрос вместо простыни сообщений 🙂"
            )
        except Exception:
            pass


# ================== ОГРАНИЧЕНИЕ МЕДИА/ССЫЛОК ДЛЯ НОВИЧКОВ ==================


@antiflood_router.message()
async def newbie_restrict_media_and_links(message: Message):
    user = message.from_user
    if not user or not is_newbie_id(user.id):
        return

    if message.photo or message.video or message.document or message.animation:
        try:
            await message.delete()
            await message.chat.send_message(
                "📎 Медиа от новых участников временно запрещены.\n"
                "Сначала познакомься с чатом, а потом уже кидай скрины и файлы 🙂"
            )
        except Exception:
            pass
        return

    if message.entities:
        has_link = any(
            e.type in {MessageEntity.Type.URL, MessageEntity.Type.TEXT_LINK}
            for e in message.entities
        )
        if has_link:
            try:
                await message.delete()
                await message.chat.send_message(
                    "🔗 Ссылки от новых участников временно выключены.\n"
                    "Если это важная ссылка по теме — напиши админам."
                )
            except Exception:
                pass


# ================== УМНЫЙ АНТИСПАМ (НЕ ТРОГАЕМ КОД) ==================


@group_router.message(F.text)
async def smart_spam_filter(message: Message):
    if is_admin(message):
        return

    text = message.text or ""

    if looks_like_code(text):
        return

    if contains_bad_link(text) or contains_bad_keywords(text):
        try:
            await message.delete()
            await message.answer(
                "🚫 Сообщение удалено ботом‑модератором.\n"
                "Причина: похоже на спам/рекламу, не связанную с нейрокодингом."
            )
        except Exception:
            pass


# ================== АДМИН-КОМАНДЫ ==================


@group_router.message(Command("warn"))
async def cmd_warn(message: Message):
    if not is_admin(message):
        return

    if not message.reply_to_message:
        await message.reply("Эту команду нужно использовать в ответ на сообщение нарушителя.")
        return

    violator = message.reply_to_message.from_user
    mention = violator.mention_html()
    await message.reply(
        f"⚠ {mention}, предупреждение за нарушение правил чата.\n"
        "Повторные нарушения могут привести к ограничениям или бану."
    )


@group_router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject):
    if not is_admin(message):
        return

    if not message.reply_to_message:
        await message.reply("Используй /ban в ответ на сообщение того, кого нужно забанить.")
        return

    violator = message.reply_to_message.from_user
    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=violator.id)
        await message.reply(f"🔨 Пользователь {violator.mention_html()} забанен.")
    except Exception as e:
        logging.exception(e)
        await message.reply("Не получилось забанить пользователя. Проверь мои права администратора.")


# ================== ЗАПУСК ==================


async def main():
    dp.include_router(base_router)
    dp.include_router(group_router)
    dp.include_router(antiflood_router)

    # Важно: указываем типы обновлений, включая chat_member
    await dp.start_polling(
        bot,
        allowed_updates=["message", "chat_member", "my_chat_member"]
    )



if __name__ == "__main__":
    asyncio.run(main())
