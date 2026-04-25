"""
Админские команды — только для создателя бота.
ADMIN_ID = 6353819309

Команды:
/addcoins @username 10000  — добавить монеты
/removecoins @username 500 — убрать монеты
/setlevel @username 10     — установить уровень
/godmode                   — бесконечные монеты себе
/players                   — список всех игроков
/resetcd @username         — сбросить кулдауны
/ban @username             — заблокировать игрока
/unban @username           — разблокировать
/adminhelp                 — список команд
"""

import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database import get_conn
from images import send_photo_message

ADMIN_ID = 6353819309
GODMODE_COINS = 999_999_999

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def get_player_by_username(username: str):
    username = username.replace("@", "")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE username=?", (username,))
    player = c.fetchone()
    conn.close()
    return player

# ══════════════════════════════════════════
#  /adminhelp — список команд
# ══════════════════════════════════════════
async def adminhelp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    text = (
        f"<b>[ Панель администратора ]</b>\n"
        f"{'─' * 22}\n\n"
        f"<b>Управление игроками:</b>\n"
        f"  /addcoins @user 1000\n"
        f"  /removecoins @user 500\n"
        f"  /setlevel @user 10\n"
        f"  /resetcd @user\n"
        f"  /ban @user\n"
        f"  /unban @user\n\n"
        f"<b>Информация:</b>\n"
        f"  /players — все игроки\n"
        f"  /clans — все кланы\n\n"
        f"<b>Для себя:</b>\n"
        f"  /godmode — бесконечные монеты\n\n"
        f"<b>Рассылка:</b>\n"
        f"  /announce текст\n\n"
        f"<i>Доступно только тебе.</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ══════════════════════════════════════════
#  /godmode — бесконечные монеты себе
# ══════════════════════════════════════════
async def godmode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET coins=?, level=50, experience=0 WHERE user_id=?",
              (GODMODE_COINS, ADMIN_ID))
    # Сбрасываем все кулдауны
    c.execute("DELETE FROM cooldowns WHERE user_id=?", (ADMIN_ID,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"<b>[ Режим бога активирован ]</b>\n"
        f"{'─' * 22}\n\n"
        f"💰  Монеты:   <b>999,999,999</b>\n"
        f"⭐  Уровень:  <b>50</b>\n"
        f"⏱  Кулдауны: <b>сброшены</b>\n\n"
        f"<i>Тест без ограничений.</i>",
        parse_mode="HTML"
    )

# ══════════════════════════════════════════
#  /addcoins @username amount
# ══════════════════════════════════════════
async def addcoins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Использование: /addcoins @username 1000"
        ); return

    username = ctx.args[0].replace("@", "")
    try:
        amount = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("Укажи число. Пример: /addcoins @user 1000"); return

    player = get_player_by_username(username)
    if not player:
        await update.message.reply_text(f"Игрок @{username} не найден."); return

    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET coins=coins+? WHERE username=?", (amount, username))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"<b>✓ Готово</b>\n\n"
        f"👤  @{username}\n"
        f"💰  Добавлено: <b>+{amount:,} монет</b>",
        parse_mode="HTML"
    )
    # Уведомляем игрока
    try:
        await ctx.bot.send_message(
            player[0],
            f"<b>💰 Пополнение счёта</b>\n\n"
            f"На твой счёт зачислено <b>{amount:,} монет</b>.\n\n"
            f"<i>— Администрация</i>",
            parse_mode="HTML"
        )
    except: pass

# ══════════════════════════════════════════
#  /removecoins @username amount
# ══════════════════════════════════════════
async def removecoins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Использование: /removecoins @username 500"
        ); return

    username = ctx.args[0].replace("@", "")
    try:
        amount = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("Укажи число."); return

    player = get_player_by_username(username)
    if not player:
        await update.message.reply_text(f"Игрок @{username} не найден."); return

    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET coins=MAX(0, coins-?) WHERE username=?", (amount, username))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"<b>✓ Готово</b>\n\n"
        f"👤  @{username}\n"
        f"💰  Снято: <b>-{amount:,} монет</b>",
        parse_mode="HTML"
    )

# ══════════════════════════════════════════
#  /setlevel @username level
# ══════════════════════════════════════════
async def setlevel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Использование: /setlevel @username 10"
        ); return

    username = ctx.args[0].replace("@", "")
    try:
        level = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("Укажи число."); return

    if level < 1 or level > 100:
        await update.message.reply_text("Уровень: от 1 до 100."); return

    player = get_player_by_username(username)
    if not player:
        await update.message.reply_text(f"Игрок @{username} не найден."); return

    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET level=?, experience=0 WHERE username=?",
              (level, username))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"<b>✓ Готово</b>\n\n"
        f"👤  @{username}\n"
        f"⭐  Уровень установлен: <b>{level}</b>",
        parse_mode="HTML"
    )

# ══════════════════════════════════════════
#  /resetcd @username
# ══════════════════════════════════════════
async def resetcd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not ctx.args:
        # Сброс своих кулдаунов
        conn = get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM cooldowns WHERE user_id=?", (ADMIN_ID,))
        conn.commit()
        conn.close()
        await update.message.reply_text("✓ Твои кулдауны сброшены."); return

    username = ctx.args[0].replace("@", "")
    player = get_player_by_username(username)
    if not player:
        await update.message.reply_text(f"Игрок @{username} не найден."); return

    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM cooldowns WHERE user_id=?", (player[0],))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✓ Кулдауны @{username} сброшены."
    )

# ══════════════════════════════════════════
#  /players — список всех игроков
# ══════════════════════════════════════════
async def players_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username, coins, level, clan_id FROM players ORDER BY coins DESC")
    players = c.fetchall()
    conn.close()

    if not players:
        await update.message.reply_text("Игроков нет."); return

    text = f"<b>[ Все игроки — {len(players)} ]</b>\n{'─' * 22}\n\n"
    for username, coins, level, clan_id in players[:20]:
        clan_mark = "🏛" if clan_id else "—"
        text += f"@{username}  |  ⭐{level}  |  💰{coins:,}  {clan_mark}\n"

    if len(players) > 20:
        text += f"\n<i>... и ещё {len(players) - 20} игроков</i>"

    await update.message.reply_text(text, parse_mode="HTML")

# ══════════════════════════════════════════
#  /clans — список всех кланов
# ══════════════════════════════════════════
async def clans_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT cl.name, cl.power, cl.treasury,
                 COUNT(cm.user_id) as members
                 FROM clans cl
                 LEFT JOIN clan_members cm ON cm.clan_id = cl.id
                 GROUP BY cl.id
                 ORDER BY cl.power DESC""")
    clans = c.fetchall()
    conn.close()

    if not clans:
        await update.message.reply_text("Кланов нет."); return

    text = f"<b>[ Все кланы — {len(clans)} ]</b>\n{'─' * 22}\n\n"
    for name, power, treasury, members in clans:
        text += (
            f"🏛 <b>{name}</b>\n"
            f"   💪{power}  💰{treasury:,}  👥{members}\n\n"
        )

    await update.message.reply_text(text, parse_mode="HTML")

# ══════════════════════════════════════════
#  /ban и /unban
# ══════════════════════════════════════════
async def ban_player(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not ctx.args:
        await update.message.reply_text("Использование: /ban @username"); return

    username = ctx.args[0].replace("@", "")
    player = get_player_by_username(username)
    if not player:
        await update.message.reply_text(f"Игрок @{username} не найден."); return

    conn = get_conn()
    c = conn.cursor()
    # Помечаем как заблокированного через отрицательные монеты
    c.execute("UPDATE players SET coins=-1 WHERE username=?", (username,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"🚫 @{username} заблокирован.")
    try:
        await ctx.bot.send_message(
            player[0],
            "<b>Ты заблокирован администратором.</b>",
            parse_mode="HTML"
        )
    except: pass

async def unban_player(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not ctx.args:
        await update.message.reply_text("Использование: /unban @username"); return

    username = ctx.args[0].replace("@", "")
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET coins=500 WHERE username=?", (username,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✓ @{username} разблокирован.")
    async def msg_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
     if not is_admin(update.effective_user.id):
        return

    if not ctx.args:
        await update.message.reply_text(
            "Использование: /msg твой текст здесь\n\n"
            "Отправит чистый текст всем игрокам без фото."
        ); return

    text = " ".join(ctx.args)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM players")
    all_players = c.fetchall()
    conn.close()

    sent = 0
    for (pid,) in all_players:
        try:
            await ctx.bot.send_message(pid, text)
            sent += 1
        except: pass

    await update.message.reply_text(f"✓ Отправлено {sent} игрокам.")
