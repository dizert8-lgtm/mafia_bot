"""
Система добычи валюты:
/rob    — ограбление (раз в 2 часа)
/casino — казино (раз в 6 часов)
/work   — работа на семью (раз в 4 часа)
/balance — баланс и кулдауны
"""

import random
import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database import get_conn
from images import send_photo_message

def init_economy_tables():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS cooldowns (
        user_id     INTEGER,
        action      TEXT,
        last_used   TEXT,
        PRIMARY KEY (user_id, action)
    )""")
    conn.commit()
    conn.close()

def get_cooldown(user_id: int, action: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT last_used FROM cooldowns WHERE user_id=? AND action=?",
              (user_id, action))
    row = c.fetchone()
    conn.close()
    if row:
        return datetime.datetime.fromisoformat(row[0])
    return None

def set_cooldown(user_id: int, action: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO cooldowns (user_id, action, last_used) VALUES (?, ?, ?)",
              (user_id, action, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def check_cooldown(user_id: int, action: str, hours: int):
    last = get_cooldown(user_id, action)
    if not last:
        return True, ""
    delta = datetime.datetime.now() - last
    required = datetime.timedelta(hours=hours)
    if delta >= required:
        return True, ""
    remaining = required - delta
    total_seconds = int(remaining.total_seconds())
    hours_left = total_seconds // 3600
    minutes_left = (total_seconds % 3600) // 60
    wait_str = f"{hours_left}ч {minutes_left}мин" if hours_left > 0 else f"{minutes_left}мин"
    return False, wait_str

def add_coins(user_id: int, amount: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET coins=coins+? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def remove_coins(user_id: int, amount: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT coins FROM players WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row or row[0] < amount:
        conn.close()
        return False
    c.execute("UPDATE players SET coins=coins-? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()
    return True

def add_exp(user_id: int, amount: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT level, experience FROM players WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    level, exp = row
    new_exp = exp + amount
    new_level = level
    while new_exp >= new_level * 1000:
        new_exp -= new_level * 1000
        new_level += 1
    c.execute("UPDATE players SET level=?, experience=? WHERE user_id=?",
              (new_level, new_exp, user_id))
    conn.commit()
    conn.close()

ROB_STORIES = [
    ("ограбил ночной магазин", "Кассир даже не пикнул."),
    ("вскрыл чужой автомобиль", "Сигнализация не сработала."),
    ("обчистил пьяного на улице", "Он ничего не заметил."),
    ("взял деньги из кассы ресторана", "Повар смотрел в другую сторону."),
    ("ограбил букмекерскую контору", "Охранник спал на посту."),
    ("вскрыл сейф в офисе", "Пароль оказался простым."),
]

ROB_FAIL_STORIES = [
    "Тебя заметила камера. Пришлось бежать.",
    "Охранник оказался не таким сонным.",
    "Кто-то вызвал полицию. Ушёл с пустыми руками.",
    "Добыча оказалась фальшивой.",
    "Тебя узнали. Пришлось всё вернуть.",
]

WORK_STORIES = [
    "собирал долги для семьи",
    "охранял склад всю ночь",
    "перевозил груз через город",
    "следил за конкурентами",
    "вёл переговоры с поставщиком",
    "контролировал точку на рынке",
]

async def rob(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player:
        await update.message.reply_text("Напиши /start"); return

    can_act, wait = check_cooldown(user_id, "rob", 2)
    if not can_act:
        await update.message.reply_text(
            f"<b>Слишком рано.</b>\n\nСледующее ограбление через: <b>{wait}</b>",
            parse_mode="HTML"); return

    set_cooldown(user_id, "rob")

    if random.random() < 0.70:
        amount = random.randint(50, 300)
        story, detail = random.choice(ROB_STORIES)
        add_coins(user_id, amount)
        add_exp(user_id, 25)
        text = (
            f"<b>[ Ограбление ]</b>\n"
            f"{'─' * 22}\n\n"
            f"Ты {story}.\n<i>{detail}</i>\n\n"
            f"💰  Добыча:   <b>+{amount} монет</b>\n"
            f"📊  Опыт:     <b>+25</b>"
        )
        await send_photo_message(ctx.bot, update.effective_chat.id, "attack", text)
    else:
        fail = random.choice(ROB_FAIL_STORIES)
        text = (
            f"<b>[ Ограбление провалено ]</b>\n"
            f"{'─' * 22}\n\n"
            f"<i>{fail}</i>\n\n"
            f"💰  Добыча:   <b>0 монет</b>\n\n"
            f"Попробуй снова через 2 часа."
        )
        await send_photo_message(ctx.bot, update.effective_chat.id, "lose", text)

async def work(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player:
        await update.message.reply_text("Напиши /start"); return

    can_act, wait = check_cooldown(user_id, "work", 4)
    if not can_act:
        await update.message.reply_text(
            f"<b>Ты уже работал.</b>\n\nСледующая работа через: <b>{wait}</b>",
            parse_mode="HTML"); return

    set_cooldown(user_id, "work")
    amount = random.randint(100, 250)
    story = random.choice(WORK_STORIES)
    add_coins(user_id, amount)
    add_exp(user_id, 40)

    bonus = 0
    if player[2]:
        bonus = random.randint(20, 80)
        add_coins(user_id, bonus)

    bonus_text = f"\n🏛  Бонус клана: <b>+{bonus} монет</b>" if bonus else ""
    text = (
        f"<b>[ Работа выполнена ]</b>\n"
        f"{'─' * 22}\n\n"
        f"Ты {story}.\n\n"
        f"💰  Оплата:   <b>+{amount} монет</b>"
        f"{bonus_text}\n"
        f"📊  Опыт:     <b>+40</b>\n\n"
        f"<i>Семья ценит преданных людей.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "profile", text)

async def casino(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player:
        await update.message.reply_text("Напиши /start"); return

    can_act, wait = check_cooldown(user_id, "casino", 6)
    if not can_act:
        await update.message.reply_text(
            f"<b>Казино закрыто для тебя.</b>\n\nВозвращайся через: <b>{wait}</b>",
            parse_mode="HTML"); return

    if not ctx.args:
        await update.message.reply_text(
            f"<b>Укажи ставку:</b>\n<code>/casino 100</code>\n\n"
            f"💰  Твои монеты: <b>{player[4]:,}</b>\n\n"
            f"<i>Мин. ставка: 50  |  Макс: 5,000</i>",
            parse_mode="HTML"); return

    try:
        bet = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Укажи число. Пример: /casino 100"); return

    if bet < 50:
        await update.message.reply_text("Минимальная ставка: 50 монет"); return
    if bet > 5000:
        await update.message.reply_text("Максимальная ставка: 5,000 монет"); return
    if player[4] < bet:
        await update.message.reply_text(
            f"Недостаточно монет.\nСтавка: {bet:,}  |  Есть: {player[4]:,}"); return

    set_cooldown(user_id, "casino")
    roll = random.random()

    if roll < 0.45:
        add_coins(user_id, bet)
        add_exp(user_id, 50)
        text = (
            f"<b>[ Казино — Победа ]</b>\n"
            f"{'─' * 22}\n\n"
            f"🎰  Колесо остановилось на тебе!\n\n"
            f"💰  Ставка:    <b>{bet:,} монет</b>\n"
            f"💰  Выигрыш:  <b>+{bet:,} монет</b>\n"
            f"📊  Опыт:      <b>+50</b>\n\n"
            f"<i>Удача благосклонна к смелым.</i>"
        )
        await send_photo_message(ctx.bot, update.effective_chat.id, "win", text)
    elif roll < 0.55:
        text = (
            f"<b>[ Казино — Ничья ]</b>\n"
            f"{'─' * 22}\n\n"
            f"🎰  Колесо остановилось на нуле.\n\n"
            f"💰  Ставка возвращена: <b>{bet:,} монет</b>\n\n"
            f"<i>В следующий раз повезёт.</i>"
        )
        await send_photo_message(ctx.bot, update.effective_chat.id, "treasury", text)
    else:
        remove_coins(user_id, bet)
        text = (
            f"<b>[ Казино — Поражение ]</b>\n"
            f"{'─' * 22}\n\n"
            f"🎰  Колесо не на твоей стороне.\n\n"
            f"💰  Потеряно:  <b>-{bet:,} монет</b>\n\n"
            f"<i>Казино всегда выигрывает.</i>"
        )
        await send_photo_message(ctx.bot, update.effective_chat.id, "lose", text)

async def balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT coins, level, experience FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player:
        await update.message.reply_text("Напиши /start"); return

    coins, level, exp = player
    _, rob_wait   = check_cooldown(user_id, "rob", 2)
    _, work_wait  = check_cooldown(user_id, "work", 4)
    _, casino_wait = check_cooldown(user_id, "casino", 6)

    rob_status    = f"через {rob_wait}"    if rob_wait    else "✓ доступно"
    work_status   = f"через {work_wait}"   if work_wait   else "✓ доступно"
    casino_status = f"через {casino_wait}" if casino_wait else "✓ доступно"

    text = (
        f"<b>[ Финансы ]</b>\n"
        f"{'─' * 22}\n\n"
        f"💰  Монеты:    <b>{coins:,}</b>\n"
        f"⭐  Уровень:   <b>{level}</b>\n"
        f"📊  Опыт:      <b>{exp}</b>\n\n"
        f"<b>Доступные действия:</b>\n"
        f"⚔️  /rob       — {rob_status}\n"
        f"💼  /work      — {work_status}\n"
        f"🎰  /casino    — {casino_status}"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "treasury", text)
