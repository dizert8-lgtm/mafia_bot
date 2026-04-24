"""
Динамическое меню в зависимости от звания игрока.
Эмодзи в стиле мафии — серьёзные, без лишней яркости.
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from database import get_conn
from ranks import get_rank, RANKS

# ══════════════════════════════════════════
#  Меню по звания
# ══════════════════════════════════════════

MENU = {
    None: [
        ["◈ Профиль", "◈ Топ кланов"],
        ["◈ Создать клан", "◈ Вступить в клан"],
    ],
    "associate": [
        ["◈ Профиль", "◈ Клан"],
        ["◈ Состав", "◈ Статистика"],
        ["◈ Конфликты", "◈ Топ кланов"],
    ],
    "mafioso": [
        ["◈ Профиль", "◈ Клан"],
        ["◈ Состав", "◈ Статистика"],
        ["◈ Атаковать", "◈ Конфликты"],
        ["◈ Топ кланов"],
    ],
    "capo": [
        ["◈ Профиль", "◈ Клан"],
        ["◈ Состав", "◈ Статистика"],
        ["◈ Атаковать", "◈ Заявки"],
        ["◈ Конфликты", "◈ Топ кланов"],
    ],
    "underboss": [
        ["◈ Профиль", "◈ Клан"],
        ["◈ Состав", "◈ Статистика"],
        ["◈ Атаковать", "◈ Заявки"],
        ["◈ Повысить", "◈ Выгнать"],
        ["◈ Конфликты", "◈ Топ кланов"],
    ],
    "godfather": [
        ["◈ Профиль", "◈ Клан"],
        ["◈ Состав", "◈ Статистика"],
        ["◈ Заявки", "◈ Повысить"],
        ["◈ Выгнать", "◈ Атаковать"],
        ["◈ Объявить войну", "◈ Конфликты"],
        ["◈ Объявление", "◈ Топ кланов"],
    ],
}

# Маппинг кнопок → команды
BUTTON_MAP = {
    "◈ Профиль":        "/profile",
    "◈ Клан":           "/clan_info",
    "◈ Состав":         "/members",
    "◈ Статистика":     "/stat",
    "◈ Конфликты":      "/conflicts",
    "◈ Топ кланов":     "/top",
    "◈ Создать клан":   "/create_clan",
    "◈ Вступить в клан":"/request_join",
    "◈ Атаковать":      "/attack",
    "◈ Заявки":         "/requests",
    "◈ Повысить":       "/promote",
    "◈ Выгнать":        "/kick",
    "◈ Объявить войну": "/war",
    "◈ Объявление":     "/announce",
}

# Описания для каждого звания
RANK_WELCOME = {
    None:         "Ты не состоишь ни в одном клане.",
    "associate":  "Ты делаешь первые шаги в семье.",
    "mafioso":    "Ты проверенный член семьи.",
    "capo":       "Ты ведёшь свою группу.",
    "underboss":  "Ты — правая рука Крёстного отца.",
    "godfather":  "Ты держишь власть в своих руках.",
}

def get_player_rank(user_id: int):
    """Возвращает звание игрока или None если не в клане."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player or not player[0]:
        return None
    return get_rank(user_id, player[0])

def build_keyboard(rank: str | None) -> ReplyKeyboardMarkup:
    """Строит клавиатуру для данного звания."""
    buttons = MENU.get(rank, MENU[None])
    keyboard = [[KeyboardButton(btn) for btn in row] for row in buttons]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_rank_header(rank: str | None) -> str:
    """Возвращает заголовок с текущим званием."""
    if rank is None:
        return "— Без клана"
    rank_name = RANKS.get(rank, "?")
    return f"— {rank_name}"

async def handle_menu_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия кнопок меню."""
    text = update.message.text
    command = BUTTON_MAP.get(text)
    if command:
        update.message.text = command
        ctx.args = []
        # Перенаправляем как команду
        await update.message.reply_text(
            f"Используй команду: {command}",
        )
