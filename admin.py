"""
Админские команды — только для создателя бота.
ADMIN_ID = 6353819309
"""

from database import get_conn

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

from telegram import Update
from telegram.ext import ContextTypes

async def adminhelp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text(
        "<b>[ Панель администратора ]</b>\n"
        "──────────────────────\n\n"
        "/addcoins @user 1000\n"
        "/removecoins @user 500\n"
        "/setlevel @user 10\n"
        "/resetcd — сброс своих кулдаунов\n"
        "/resetcd @user\n"
        "/ban @user  |  /unban @user\n"
        "/players — все игроки\n"
        "/clans — все кланы\n"
        "/godmode — режим бога\n"
        "/announce текст — рассылка с фото\n"
        "/msg текст — рассылка без фото",
        parse_mode="HTML"
    )

async def godmode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET coins=?, level=50, experience=0 WHERE user_id=?",
              (GODMODE_COINS, ADMIN_ID))
    c.execute("DELETE FROM cooldowns WHERE user_id=?", (ADMIN_ID,))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        "<b>[ Режим бога активирован ]</b>\n\n"
        "💰 Монеты: <b>999,999,999</b>\n"
        "⭐ Уровень: <b>50</b>\n"
        "⏱ Кулдауны: <b>сброшены</b>",
        parse_mode="HTML"
    )

async def addcoins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text("Использование: /addcoins @username 1000"); return
    username = ctx.args[0].replace("@", "")
    try: amount = int(ctx.args[1])
    except: await update.message.reply_text("Укажи число."); return
    player = get_player_by_username(username)
    if not player:
        await update.message.reply_text(f"Игрок @{username} не найден."); return
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET coins=coins+? WHERE username=?", (amount, username))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✓ @{username} + <b>{amount:,} монет</b>", parse_mode="HTML")
    try:
        await ctx.bot.send_message(player[0],
            f"<b>💰 Пополнение счёта</b>\n\nЗачислено <b>{amount:,} монет</b>.\n\n<i>— Администрация</i>",
            parse_mode="HTML")
    except: pass

async def removecoins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text("Использование: /removecoins @username 500"); return
    username = ctx.args[0].replace("@", "")
    try: amount = int(ctx.args[1])
    except: await update.message.reply_text("Укажи число."); return
    player = get_player_by_username(username)
    if not player:
        await update.message.reply_text(f"Игрок @{username} не найден."); return
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET coins=MAX(0, coins-?) WHERE username=?", (amount, username))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✓ @{username} - <b>{amount:,} монет</b>", parse_mode="HTML")

async def setlevel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text("Использование: /setlevel @username 10"); return
    username = ctx.args[0].replace("@", "")
    try: level = int(ctx.args[1])
    except: await update.message.reply_text("Укажи число."); return
    if level < 1 or level > 100:
        await update.message.reply_text("Уровень: от 1 до 100."); return
    player = get_player_by_username(username)
    if not player:
        await update.message.reply_text(f"Игрок @{username} не найден."); return
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET level=?, experience=0 WHERE username=?", (level, username))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✓ @{username} уровень → <b>{level}</b>", parse_mode="HTML")

async def resetcd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not ctx.args:
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
    await update.message.reply_text(f"✓ Кулдауны @{username} сброшены.")

async def players_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username, coins, level, clan_id FROM players ORDER BY coins DESC")
    players = c.fetchall()
    conn.close()
    if not players:
        await update.message.reply_text("Игроков нет."); return
    text = f"<b>[ Все игроки — {len(players)} ]</b>\n──────────────────────\n\n"
    for username, coins, level, clan_id in players[:20]:
        clan_mark = "🏛" if clan_id else "—"
        text += f"@{username}  ⭐{level}  💰{coins:,}  {clan_mark}\n"
    if len(players) > 20:
        text += f"\n<i>... и ещё {len(players) - 20}</i>"
    await update.message.reply_text(text, parse_mode="HTML")

async def clans_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT cl.name, cl.power, cl.treasury, COUNT(cm.user_id) as members
                 FROM clans cl LEFT JOIN clan_members cm ON cm.clan_id=cl.id
                 GROUP BY cl.id ORDER BY cl.power DESC""")
    clans = c.fetchall()
    conn.close()
    if not clans:
        await update.message.reply_text("Кланов нет."); return
    text = f"<b>[ Все кланы — {len(clans)} ]</b>\n──────────────────────\n\n"
    for name, power, treasury, members in clans:
        text += f"🏛 <b>{name}</b>  💪{power}  💰{treasury:,}  👥{members}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def ban_player(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not ctx.args:
        await update.message.reply_text("Использование: /ban @username"); return
    username = ctx.args[0].replace("@", "")
    player = get_player_by_username(username)
    if not player:
        await update.message.reply_text(f"Игрок @{username} не найден."); return
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE players SET coins=-1 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🚫 @{username} заблокирован.")
    try:
        await ctx.bot.send_message(player[0], "<b>Ты заблокирован.</b>", parse_mode="HTML")
    except: pass

async def unban_player(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
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
    if not is_admin(update.effective_user.id): return
    if not ctx.args:
        await update.message.reply_text(
            "Использование: /msg твой текст\n\nОтправит всем игрокам без фото."
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
            await ctx.bot.send_message(pid, f"📢 {text}", parse_mode="HTML")
            sent += 1
        except: pass
    await update.message.reply_text(f"✓ Отправлено {sent} игрокам.")