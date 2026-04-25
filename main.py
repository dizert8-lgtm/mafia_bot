import os
import datetime
from telegram import Update, Chat
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from database import init_db, get_conn
from ranks import (
    get_rank, has_permission, get_rank_label,
    get_next_rank, get_clan_members_by_rank
)
from stats import init_stats_tables, clan_stat, manage_conflict, list_conflicts
from menu import get_player_rank, build_keyboard, get_rank_header, RANK_WELCOME
from images import send_photo_message
from economy import init_economy_tables, rob, work, casino, balance

TOKEN    = os.getenv("TOKEN")
ADMIN_ID = 6353819309  # ← твой Telegram ID

def is_group(update: Update) -> bool:
    return update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]

def get_keyboard(update: Update, rank):
    if is_group(update):
        return None
    return build_keyboard(rank)

# ══════════════════════════════════════════
#  /getid — получить file_id фото (только админ)
# ══════════════════════════════════════════
async def getid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    # Случай 1: фото отправлено с подписью /getid
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        await update.message.reply_text(f"`{file_id}`", parse_mode="Markdown")
        return
    
    # Случай 2: /getid отправлен отдельно — просим фото
    await update.message.reply_text(
        "Отправь фото с подписью /getid"
    )

# ══════════════════════════════════════════
#  /start
# ══════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO players (user_id, username) VALUES (?, ?)",
              (user.id, user.username or user.first_name))
    conn.commit()
    conn.close()

    rank = get_player_rank(user.id)
    keyboard = get_keyboard(update, rank)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT text FROM announcements ORDER BY id DESC LIMIT 1")
    ann = c.fetchone()
    conn.close()
    ann_text = f"\n\n📢 <b>Последнее объявление:</b>\n{ann[0]}" if ann else ""

    rank_desc = RANK_WELCOME.get(rank, "")
    rank_header = get_rank_header(rank)

    text = (
        f"<b>🎩 Семья мафии</b>  {rank_header}\n"
        f"{'─' * 22}\n\n"
        f"{rank_desc}{ann_text}\n\n"
        f"<i>Выбери своё действие, уважаемый.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "start", text, keyboard)

# ══════════════════════════════════════════
#  Обработчик кнопок меню (только личка)
# ══════════════════════════════════════════
async def menu_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_group(update):
        return
    text = update.message.text

    if text == "◈ Профиль":           await profile(update, ctx)
    elif text == "◈ Клан":            await clan_info(update, ctx)
    elif text == "◈ Состав":          await members(update, ctx)
    elif text == "◈ Статистика":      await clan_stat(update, ctx)
    elif text == "◈ Конфликты":       await list_conflicts(update, ctx)
    elif text == "◈ Топ кланов":      await top_clans(update, ctx)
    elif text == "◈ Заявки":          await view_requests(update, ctx)
    elif text == "◈ Атаковать":
        await update.message.reply_text("Используй команду: /attack")
    elif text == "◈ Повысить":
        await update.message.reply_text("Используй команду: /promote @username")
    elif text == "◈ Выгнать":
        await update.message.reply_text("Используй команду: /kick @username")
    elif text == "◈ Объявить войну":
        await update.message.reply_text("Используй команду: /war <название клана>")
    elif text == "◈ Объявление":
        await update.message.reply_text("Используй команду: /announce <текст>")
    elif text == "◈ Создать клан":
        await update.message.reply_text(
            "Используй команду:\n/create_clan <название>\n\n"
            "💰 Стоимость: 20,000 монет"
        )
    elif text == "◈ Вступить в клан":
        await update.message.reply_text(
            "Используй команду:\n/request_join <название клана>"
        )

# ══════════════════════════════════════════
#  /profile
# ══════════════════════════════════════════
async def profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player:
        await update.message.reply_text("Напиши /start"); return

    uid, username, clan_id, strength, coins, level, exp = player
    clan_text = "Не состоит в клане"
    rank_text = ""

    if clan_id:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
        clan = c.fetchone()
        conn.close()
        if clan:
            rank = get_rank(user_id, clan_id)
            rank_text = f"\n🏅  <b>Звание</b>      {get_rank_label(rank)}"
            clan_text = clan[0]

    rank = get_player_rank(user_id)
    keyboard = get_keyboard(update, rank)

    text = (
        f"<b>[ Досье ]</b>\n"
        f"{'─' * 22}\n\n"
        f"👤  <b>Имя</b>          {username}\n"
        f"⭐  <b>Уровень</b>      {level}\n"
        f"📊  <b>Опыт</b>         {exp}\n"
        f"⚔️  <b>Сила</b>         {strength}\n"
        f"💰  <b>Казна</b>        {coins:,} монет\n"
        f"🏛  <b>Клан</b>         {clan_text}"
        f"{rank_text}"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "profile", text, keyboard)

# ══════════════════════════════════════════
#  /create_clan
# ══════════════════════════════════════════
async def create_clan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player:
        await update.message.reply_text("Напиши /start"); return
    if player[2]:
        await update.message.reply_text("Ты уже состоишь в клане."); return
    if player[4] < 20000:
        await update.message.reply_text(
            f"<b>Недостаточно средств.</b>\n\n"
            f"💰  Нужно:   20,000 монет\n"
            f"💰  Есть:    {player[4]:,} монет",
            parse_mode="HTML"
        ); return
    if not ctx.args:
        await update.message.reply_text(
            "Укажи название:\n<code>/create_clan Название</code>",
            parse_mode="HTML"
        ); return

    name = " ".join(ctx.args)
    if len(name) < 3 or len(name) > 30:
        await update.message.reply_text("Название: от 3 до 30 символов."); return

    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO clans (name, owner_id, created_at) VALUES (?, ?, ?)",
                  (name, user_id, datetime.datetime.now().isoformat()))
        clan_id = c.lastrowid
        c.execute("UPDATE players SET clan_id=?, coins=coins-20000 WHERE user_id=?",
                  (clan_id, user_id))
        c.execute("INSERT INTO clan_members (user_id, clan_id, rank, joined_at) VALUES (?, ?, 'godfather', ?)",
                  (user_id, clan_id, datetime.datetime.now().isoformat()))
        conn.commit()
        keyboard = get_keyboard(update, "godfather")
        text = (
            f"<b>[ Клан основан ]</b>\n"
            f"{'─' * 22}\n\n"
            f"🏛  <b>Название</b>     {name}\n"
            f"🎩  <b>Звание</b>       {get_rank_label('godfather')}\n"
            f"💰  <b>Оплачено</b>     20,000 монет\n\n"
            f"<i>Власть в твоих руках. Распоряжайся мудро.</i>"
        )
        await send_photo_message(ctx.bot, update.effective_chat.id, "create_clan", text, keyboard)
    except Exception:
        await update.message.reply_text("Клан с таким названием уже существует.")
    finally:
        conn.close()

# ══════════════════════════════════════════
#  /request_join
# ══════════════════════════════════════════
async def request_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player:
        await update.message.reply_text("Напиши /start"); return
    if player[2]:
        await update.message.reply_text("Ты уже состоишь в клане."); return
    if not ctx.args:
        await update.message.reply_text(
            "Укажи клан:\n<code>/request_join Название</code>",
            parse_mode="HTML"
        ); return

    clan_name = " ".join(ctx.args)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM clans WHERE name=?", (clan_name,))
    clan = c.fetchone()
    if not clan:
        conn.close()
        await update.message.reply_text(f"Клан «{clan_name}» не найден."); return

    c.execute("SELECT * FROM join_requests WHERE user_id=? AND clan_id=? AND status='pending'",
              (user_id, clan[0]))
    if c.fetchone():
        conn.close()
        await update.message.reply_text("Заявка уже отправлена. Ожидай решения."); return

    c.execute("INSERT INTO join_requests (user_id, clan_id, message, created_at) VALUES (?, ?, ?, ?)",
              (user_id, clan[0], "Прошу принять в клан", datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

    text = (
        f"<b>[ Заявка отправлена ]</b>\n"
        f"{'─' * 22}\n\n"
        f"🏛  Клан:   <b>{clan_name}</b>\n\n"
        f"<i>Ожидай решения руководства семьи.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "request", text)

# ══════════════════════════════════════════
#  /requests
# ══════════════════════════════════════════
async def view_requests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане."); return

    clan_id = player[0]
    if not has_permission(user_id, clan_id, "accept_member"):
        await update.message.reply_text("Недостаточно полномочий."); return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT jr.id, p.username, p.strength, p.level
                 FROM join_requests jr JOIN players p ON p.user_id=jr.user_id
                 WHERE jr.clan_id=? AND jr.status='pending'""", (clan_id,))
    requests = c.fetchall()
    conn.close()

    if not requests:
        await update.message.reply_text("<b>[ Заявок нет ]</b>", parse_mode="HTML"); return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    for req_id, username, strength, level in requests:
        keyboard = [[
            InlineKeyboardButton("✓ Принять", callback_data=f"accept_{req_id}"),
            InlineKeyboardButton("✗ Отклонить", callback_data=f"decline_{req_id}"),
        ]]
        text = (
            f"<b>[ Входящая заявка ]</b>\n"
            f"{'─' * 22}\n\n"
            f"👤  Кандидат:   @{username}\n"
            f"⭐  Уровень:    {level}\n"
            f"⚔️  Сила:       {strength}\n\n"
            f"<i>Принять его в семью?</i>"
        )
        await send_photo_message(
            ctx.bot, update.effective_chat.id, "request", text,
            InlineKeyboardMarkup(keyboard)
        )

# ══════════════════════════════════════════
#  Кнопки заявок
# ══════════════════════════════════════════
async def handle_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action, req_id = query.data.split("_", 1)
    req_id = int(req_id)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM join_requests WHERE id=?", (req_id,))
    req = c.fetchone()
    if not req or req[4] != "pending":
        conn.close()
        await query.edit_message_caption("Заявка уже обработана."); return

    req_user_id, clan_id = req[1], req[2]
    if not has_permission(user_id, clan_id, "accept_member"):
        conn.close()
        await query.answer("Недостаточно полномочий.", show_alert=True); return

    if action == "accept":
        c.execute("UPDATE join_requests SET status='accepted' WHERE id=?", (req_id,))
        c.execute("UPDATE players SET clan_id=? WHERE user_id=?", (clan_id, req_user_id))
        c.execute("INSERT OR IGNORE INTO clan_members (user_id, clan_id, rank, joined_at) VALUES (?, ?, 'associate', ?)",
                  (req_user_id, clan_id, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        await query.edit_message_caption("✓ Кандидат принят. Звание: ♟ Associate.")
        try:
            new_keyboard = build_keyboard("associate")
            text = (
                f"<b>[ Добро пожаловать в семью ]</b>\n"
                f"{'─' * 22}\n\n"
                f"♟  Твоё звание: <b>Associate</b>\n\n"
                f"<i>Докажи свою преданность. Семья смотрит.</i>"
            )
            await send_photo_message(ctx.bot, req_user_id, "join", text, new_keyboard)
        except: pass
    else:
        c.execute("UPDATE join_requests SET status='declined' WHERE id=?", (req_id,))
        conn.commit()
        conn.close()
        await query.edit_message_caption("✗ Заявка отклонена.")
        try:
            await ctx.bot.send_message(
                req_user_id,
                "<b>В приёме отказано.</b>\n\n<i>Семья приняла решение не в твою пользу.</i>",
                parse_mode="HTML"
            )
        except: pass

# ══════════════════════════════════════════
#  /members
# ══════════════════════════════════════════
async def members(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане."); return

    clan_id = player[0]
    members_list = get_clan_members_by_rank(clan_id)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
    clan = c.fetchone()
    conn.close()

    lines = ""
    for username, rank, uid in members_list:
        lines += f"{get_rank_label(rank)}\n    @{username}\n\n"

    rank = get_player_rank(user_id)
    keyboard = get_keyboard(update, rank)
    text = (
        f"<b>[ Состав семьи — {clan[0]} ]</b>\n"
        f"{'─' * 22}\n\n"
        f"{lines}"
        f"<i>Каждый знает своё место.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "members", text, keyboard)

# ══════════════════════════════════════════
#  /promote
# ══════════════════════════════════════════
async def promote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане."); return

    clan_id = player[0]
    if not has_permission(user_id, clan_id, "promote_member"):
        await update.message.reply_text("Недостаточно полномочий."); return
    if not ctx.args:
        await update.message.reply_text("Укажи: /promote @username"); return

    target_username = ctx.args[0].replace("@", "")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM players WHERE username=?", (target_username,))
    target = c.fetchone()
    if not target:
        conn.close()
        await update.message.reply_text("Игрок не найден."); return

    target_id = target[0]
    current_rank = get_rank(target_id, clan_id)
    if not current_rank:
        conn.close()
        await update.message.reply_text("Этот игрок не в твоём клане."); return
    if current_rank == "godfather":
        conn.close()
        await update.message.reply_text("Нельзя повысить Крёстного отца."); return

    next_rank = get_next_rank(current_rank)
    if not next_rank:
        conn.close()
        await update.message.reply_text("Игрок уже на максимальном звании."); return

    if next_rank == "underboss":
        c.execute("UPDATE clan_members SET rank='capo' WHERE clan_id=? AND rank='underboss'",
                  (clan_id,))
    c.execute("UPDATE clan_members SET rank=? WHERE user_id=? AND clan_id=?",
              (next_rank, target_id, clan_id))
    conn.commit()
    conn.close()

    text = (
        f"<b>[ Повышение ]</b>\n"
        f"{'─' * 22}\n\n"
        f"👤  @{target_username}\n"
        f"⬆️  Новое звание: <b>{get_rank_label(next_rank)}</b>\n\n"
        f"<i>Семья признала твои заслуги.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "promote", text)
    try:
        new_keyboard = build_keyboard(next_rank)
        await send_photo_message(ctx.bot, target_id, "promote", text, new_keyboard)
    except: pass

# ══════════════════════════════════════════
#  /kick
# ══════════════════════════════════════════
async def kick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане."); return

    clan_id = player[0]
    if not has_permission(user_id, clan_id, "kick_member"):
        await update.message.reply_text("Недостаточно полномочий."); return
    if not ctx.args:
        await update.message.reply_text("Укажи: /kick @username"); return

    target_username = ctx.args[0].replace("@", "")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM players WHERE username=?", (target_username,))
    target = c.fetchone()
    if not target:
        conn.close()
        await update.message.reply_text("Игрок не найден."); return

    target_id = target[0]
    rank = get_rank(target_id, clan_id)
    if not rank:
        conn.close()
        await update.message.reply_text("Этот игрок не в твоём клане."); return
    if rank == "godfather":
        conn.close()
        await update.message.reply_text("Нельзя исключить Крёстного отца."); return

    c.execute("DELETE FROM clan_members WHERE user_id=? AND clan_id=?", (target_id, clan_id))
    c.execute("UPDATE players SET clan_id=NULL WHERE user_id=?", (target_id,))
    conn.commit()
    conn.close()

    text = (
        f"<b>[ Исключение ]</b>\n"
        f"{'─' * 22}\n\n"
        f"👤  @{target_username} исключён из семьи.\n\n"
        f"<i>Семья не прощает слабых.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "kick", text)
    try:
        no_clan_keyboard = build_keyboard(None)
        await ctx.bot.send_message(
            target_id,
            "<b>Тебя исключили из семьи.</b>\n\n<i>Ты снова один.</i>",
            parse_mode="HTML",
            reply_markup=no_clan_keyboard
        )
    except: pass

# ══════════════════════════════════════════
#  /clan_info
# ══════════════════════════════════════════
async def clan_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    if not player or not player[0]:
        conn.close()
        await update.message.reply_text("Ты не в клане."); return

    clan_id = player[0]
    c.execute("SELECT * FROM clans WHERE id=?", (clan_id,))
    clan = c.fetchone()
    c.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id=?", (clan_id,))
    count = c.fetchone()[0]
    conn.close()

    rank = get_rank(user_id, clan_id)
    treasury_text = ""
    if has_permission(user_id, clan_id, "view_treasury"):
        treasury_text = f"\n💰  <b>Казна</b>        {clan[4]:,} монет"

    keyboard = get_keyboard(update, rank)
    text = (
        f"<b>[ Семья — {clan[1]} ]</b>\n"
        f"{'─' * 22}\n\n"
        f"💪  <b>Мощь</b>         {clan[3]}\n"
        f"👥  <b>Участников</b>   {count}"
        f"{treasury_text}\n"
        f"🏅  <b>Твоё звание</b>  {get_rank_label(rank)}\n\n"
        f"<i>Семья — это всё.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "clan_info", text, keyboard)

# ══════════════════════════════════════════
#  /top
# ══════════════════════════════════════════
async def top_clans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name, power FROM clans ORDER BY power DESC LIMIT 10")
    clans = c.fetchall()
    conn.close()
    if not clans:
        await update.message.reply_text("Кланов пока нет."); return

    places = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    lines = ""
    for i, (name, power) in enumerate(clans):
        lines += f"  {places[i]}.  {name}  —  {power}\n"

    rank = get_player_rank(update.effective_user.id)
    keyboard = get_keyboard(update, rank)
    text = (
        f"<b>[ Рейтинг семей ]</b>\n"
        f"{'─' * 22}\n\n"
        f"{lines}\n"
        f"<i>Власть определяет место за столом.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "top", text, keyboard)

# ══════════════════════════════════════════
#  /help
# ══════════════════════════════════════════
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rank = get_player_rank(user_id)
    keyboard = get_keyboard(update, rank)

    text = (
        f"<b>[ Инструктаж ]</b>\n"
        f"{'─' * 22}\n\n"
        f"<b>Основные команды:</b>\n"
        f"  /start         — главное меню\n"
        f"  /profile       — твоё досье\n"
        f"  /clan_info     — информация о клане\n"
        f"  /members       — состав семьи\n"
        f"  /stat          — статистика клана\n"
        f"  /top           — рейтинг семей\n"
        f"  /conflicts     — список конфликтов\n"
        f"  /help          — этот инструктаж\n\n"
        f"<b>Вступление:</b>\n"
        f"  /create_clan   — основать клан (20,000)\n"
        f"  /request_join  — подать заявку в клан\n\n"
        f"<b>Управление (Капо+):</b>\n"
        f"  /requests      — входящие заявки\n"
        f"  /promote       — повысить участника\n"
        f"  /kick          — исключить участника\n\n"
        f"<b>Только Крёстный отец:</b>\n"
        f"  /war           — объявить войну\n"
        f"  /conflict      — управлять конфликтами\n\n"
        f"<i>Семья — это закон.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "start", text, keyboard)

# ══════════════════════════════════════════
#  /announce
# ══════════════════════════════════════════
async def announce(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("Недостаточно полномочий."); return
    if not ctx.args:
        await update.message.reply_text("Укажи текст: /announce <текст>"); return

    text_msg = " ".join(ctx.args)
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO announcements (text, created_at, author_id) VALUES (?, ?, ?)",
              (text_msg, datetime.datetime.now().isoformat(), user_id))
    c.execute("SELECT user_id FROM players")
    all_players = c.fetchall()
    conn.commit()
    conn.close()

    text = (
        f"<b>[ Официальное объявление ]</b>\n"
        f"{'─' * 22}\n\n"
        f"{text_msg}\n\n"
        f"<i>— Руководство семьи</i>"
    )
    sent = 0
    for (pid,) in all_players:
        try:
            await send_photo_message(ctx.bot, pid, "announce", text)
            sent += 1
        except: pass
    await update.message.reply_text(f"Отправлено: {sent} адресатам.")

# ══════════════════════════════════════════
#  Запуск
# ══════════════════════════════════════════
def main():
    init_db()
    init_stats_tables()
    init_economy_tables()

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("rob", rob))
    app.add_handler(CommandHandler("work", work))
    app.add_handler(CommandHandler("casino", casino))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("getid", getid))
    app.add_handler(MessageHandler(filters.PHOTO & filters.Caption(["/getid"]), getid))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("create_clan", create_clan))
    app.add_handler(CommandHandler("request_join", request_join))
    app.add_handler(CommandHandler("requests", view_requests))
    app.add_handler(CommandHandler("members", members))
    app.add_handler(CommandHandler("promote", promote))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("clan_info", clan_info))
    app.add_handler(CommandHandler("top", top_clans))
    app.add_handler(CommandHandler("announce", announce))
    app.add_handler(CommandHandler("stat", clan_stat))
    app.add_handler(CommandHandler("conflict", manage_conflict))
    app.add_handler(CommandHandler("conflicts", list_conflicts))
    app.add_handler(CommandHandler("getid", getid))
    app.add_handler(CallbackQueryHandler(handle_request, pattern="^(accept|decline)_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    print("Бот запущен.")
    app.run_polling()

if __name__ == "__main__":
    main()
