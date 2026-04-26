"""
Система войн между кланами:
/mf_war <название>   — объявить войну (Крёстный отец)
/mf_attack           — атаковать (раз в 1 час, Мафиозо+)
/mf_war_status       — статус войны
/mf_truce            — предложить перемирие (Крёстный отец)

Механика:
- Война длится 12 часов
- Каждый участник атакует раз в 1 час
- Урон = сила игрока + случайное число (1-20)
- Победитель забирает 30% казны проигравшего
- Мощь победителя +15, проигравшего -10
"""

import random
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_conn
from ranks import get_rank, has_permission
from images import send_photo_message
from economy import set_cooldown, check_cooldown

WAR_DURATION_HOURS = 12
TREASURY_PRIZE_PCT = 0.30

def get_active_war(clan_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT w.*, c1.name, c2.name
                 FROM wars w
                 JOIN clans c1 ON c1.id=w.attacker_id
                 JOIN clans c2 ON c2.id=w.defender_id
                 WHERE (w.attacker_id=? OR w.defender_id=?)
                 AND w.status='active'""", (clan_id, clan_id))
    row = c.fetchone()
    conn.close()
    return row

def get_clan_members_ids(clan_id: int) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM clan_members WHERE clan_id=?", (clan_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

async def notify_clan(bot, clan_id: int, text: str, image_key: str = "war"):
    for uid in get_clan_members_ids(clan_id):
        try:
            await send_photo_message(bot, uid, image_key, text)
        except: pass

async def finish_war(bot, war_id: int, war=None):
    conn = get_conn()
    c = conn.cursor()
    if not war:
        c.execute("""SELECT w.*, c1.name, c2.name FROM wars w
                     JOIN clans c1 ON c1.id=w.attacker_id
                     JOIN clans c2 ON c2.id=w.defender_id
                     WHERE w.id=?""", (war_id,))
        war = c.fetchone()
    if not war:
        conn.close()
        return

    att_id, def_id = war[1], war[2]
    att_score, def_score = war[4], war[5]
    att_name, def_name = war[9], war[10]

    if att_score == def_score:
        c.execute("UPDATE wars SET status='draw' WHERE id=?", (war_id,))
        conn.commit()
        conn.close()
        draw_text = (
            f"<b>[ Война завершена — Ничья ]</b>\n"
            f"{'─' * 22}\n\n"
            f"⚔️  «{att_name}»  vs  «{def_name}»\n"
            f"🟥  {att_score}  —  {def_score}  🟦\n\n"
            f"<i>Силы равны. Никто не победил.</i>"
        )
        await notify_clan(bot, att_id, draw_text, "war")
        await notify_clan(bot, def_id, draw_text, "war")
        return

    winner_id   = att_id if att_score > def_score else def_id
    loser_id    = def_id if winner_id == att_id else att_id
    winner_name = att_name if winner_id == att_id else def_name
    loser_name  = def_name if winner_id == att_id else att_name
    w_score     = att_score if winner_id == att_id else def_score
    l_score     = def_score if winner_id == att_id else att_score

    c.execute("SELECT treasury FROM clans WHERE id=?", (loser_id,))
    prize = int((c.fetchone()[0]) * TREASURY_PRIZE_PCT)

    c.execute("UPDATE wars SET status='finished', winner_id=? WHERE id=?", (winner_id, war_id))
    c.execute("UPDATE clans SET treasury=treasury+?, power=power+15 WHERE id=?", (prize, winner_id))
    c.execute("UPDATE clans SET treasury=MAX(0,treasury-?), power=MAX(10,power-10) WHERE id=?",
              (prize, loser_id))
    c.execute("INSERT OR IGNORE INTO clan_stats (clan_id) VALUES (?)", (winner_id,))
    c.execute("INSERT OR IGNORE INTO clan_stats (clan_id) VALUES (?)", (loser_id,))
    c.execute("UPDATE clan_stats SET wins=wins+1 WHERE clan_id=?", (winner_id,))
    c.execute("UPDATE clan_stats SET losses=losses+1 WHERE clan_id=?", (loser_id,))
    conn.commit()
    conn.close()

    await notify_clan(bot, winner_id,
        f"<b>[ Победа! ]</b>\n{'─'*22}\n\n"
        f"🏆  «{winner_name}» победил!\n"
        f"⚔️  Счёт: {w_score} — {l_score}\n\n"
        f"💰  Захвачено: <b>{prize:,} монет</b>\n"
        f"💪  Мощь: <b>+15</b>\n\n"
        f"<i>Семья доказала свою силу.</i>", "win")

    await notify_clan(bot, loser_id,
        f"<b>[ Поражение ]</b>\n{'─'*22}\n\n"
        f"💀  «{loser_name}» потерпел поражение.\n"
        f"⚔️  Счёт: {l_score} — {w_score}\n\n"
        f"💰  Потеряно: <b>{prize:,} монет</b>\n"
        f"💪  Мощь: <b>-10</b>\n\n"
        f"<i>Семья должна стать сильнее.</i>", "lose")

async def declare_war(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане."); return

    clan_id = player[0]
    if not has_permission(user_id, clan_id, "declare_war"):
        await update.message.reply_text("Только 🎩 Крёстный отец может объявлять войну."); return
    if get_active_war(clan_id):
        await update.message.reply_text("Твой клан уже воюет! /mf_war_status"); return
    if not ctx.args:
        await update.message.reply_text(
            "Укажи клан:\n<code>/mf_war Название</code>", parse_mode="HTML"); return

    target_name = " ".join(ctx.args)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM clans WHERE name=?", (target_name,))
    target = c.fetchone()
    c.execute("SELECT * FROM clans WHERE id=?", (clan_id,))
    my_clan = c.fetchone()
    conn.close()

    if not target:
        await update.message.reply_text(f"Клан «{target_name}» не найден."); return
    if target[0] == clan_id:
        await update.message.reply_text("Нельзя воевать с самим собой."); return
    if get_active_war(target[0]):
        await update.message.reply_text(f"Клан «{target_name}» уже воюет."); return

    ends_at = (datetime.datetime.now() + datetime.timedelta(hours=WAR_DURATION_HOURS)).isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO wars (attacker_id, defender_id, status, declared_at, ends_at) VALUES (?,?,'active',?,?)",
              (clan_id, target[0], datetime.datetime.now().isoformat(), ends_at))
    conn.commit()
    conn.close()

    await notify_clan(ctx.bot, clan_id,
        f"<b>[ Война объявлена! ]</b>\n{'─'*22}\n\n"
        f"⚔️  Атакуем «{target[1]}»\n"
        f"⏳  Длительность: <b>{WAR_DURATION_HOURS} часов</b>\n"
        f"💰  Приз: <b>30% казны</b> противника\n\n"
        f"Атакуй: <code>/mf_attack</code>", "war")

    await notify_clan(ctx.bot, target[0],
        f"<b>[ Вас атакуют! ]</b>\n{'─'*22}\n\n"
        f"⚔️  Клан «{my_clan[1]}» объявил войну!\n"
        f"⏳  Длительность: <b>{WAR_DURATION_HOURS} часов</b>\n"
        f"💰  На кону: <b>30% вашей казны</b>\n\n"
        f"Защищайся: <code>/mf_attack</code>", "war")

async def attack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player or not player[2]:
        await update.message.reply_text("Ты не в клане."); return

    clan_id = player[2]
    if not has_permission(user_id, clan_id, "attack"):
        await update.message.reply_text(
            "❌ Associate не может атаковать.\n"
            "Нужно звание 🖤 Мафиозо или выше."
        ); return

    can_act, wait = check_cooldown(user_id, "attack", 1)
    if not can_act:
        await update.message.reply_text(
            f"<b>Следующая атака через: {wait}</b>", parse_mode="HTML"); return

    war = get_active_war(clan_id)
    if not war:
        await update.message.reply_text("Твой клан не участвует в войне."); return

    ends_at = datetime.datetime.fromisoformat(war[7])
    if datetime.datetime.now() > ends_at:
        await finish_war(ctx.bot, war[0], war)
        await update.message.reply_text("Война завершена! Результаты отправлены."); return

    war_id, att_id, def_id = war[0], war[1], war[2]
    att_name, def_name = war[9], war[10]
    strength = player[3]
    roll     = random.randint(1, 20)
    damage   = strength + roll

    conn = get_conn()
    c = conn.cursor()
    if clan_id == att_id:
        c.execute("UPDATE wars SET attacker_score=attacker_score+? WHERE id=?", (damage, war_id))
        side = att_name
    else:
        c.execute("UPDATE wars SET defender_score=defender_score+? WHERE id=?", (damage, war_id))
        side = def_name
    c.execute("UPDATE players SET strength=strength+1 WHERE user_id=?", (user_id,))
    conn.commit()
    c.execute("SELECT attacker_score, defender_score FROM wars WHERE id=?", (war_id,))
    scores = c.fetchone()
    conn.close()

    set_cooldown(user_id, "attack")

    emoji = random.choice(["🔫", "💣", "🗡️", "🔪", "💥", "⚡"])
    text = (
        f"<b>[ Атака ]</b>  {emoji}\n"
        f"{'─' * 22}\n\n"
        f"🎲  Бросок:    <b>{roll}/20</b>\n"
        f"💥  Урон:      <b>+{damage}</b> для «{side}»\n"
        f"💪  Твоя сила: <b>{strength+1}</b>\n\n"
        f"<b>Счёт:</b>\n"
        f"🟥  «{att_name}»: {scores[0]}\n"
        f"🟦  «{def_name}»: {scores[1]}\n\n"
        f"<i>Следующая атака через 1 час.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "attack", text)

async def war_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане."); return

    war = get_active_war(player[0])
    if not war:
        await update.message.reply_text(
            "<b>Активных войн нет.</b>\n\n"
            "Крёстный отец может объявить:\n<code>/mf_war Название</code>",
            parse_mode="HTML"); return

    ends_at = datetime.datetime.fromisoformat(war[7])
    if datetime.datetime.now() > ends_at:
        await finish_war(ctx.bot, war[0], war)
        await update.message.reply_text("Война завершена! Результаты отправлены."); return

    att_score, def_score = war[4], war[5]
    att_name, def_name   = war[9], war[10]
    remaining    = ends_at - datetime.datetime.now()
    hours_left   = int(remaining.total_seconds() // 3600)
    minutes_left = int((remaining.total_seconds() % 3600) // 60)
    total  = att_score + def_score or 1
    att_bar = int(att_score / total * 20)
    bar    = "🟥" * att_bar + "🟦" * (20 - att_bar)
    leading = att_name if att_score >= def_score else def_name

    text = (
        f"<b>[ Идёт война ]</b>\n"
        f"{'─' * 22}\n\n"
        f"⚔️  «{att_name}»  vs  «{def_name}»\n\n"
        f"{bar}\n\n"
        f"🟥  «{att_name}»: <b>{att_score}</b>\n"
        f"🟦  «{def_name}»: <b>{def_score}</b>\n\n"
        f"📊  Лидирует: <b>«{leading}»</b>\n"
        f"⏳  До конца: <b>{hours_left}ч {minutes_left}мин</b>\n\n"
        f"<i>Атакуй: /mf_attack</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "war", text)

async def truce(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане."); return

    clan_id = player[0]
    if not has_permission(user_id, clan_id, "make_truce"):
        await update.message.reply_text("Только 🎩 Крёстный отец может предлагать перемирие."); return

    war = get_active_war(clan_id)
    if not war:
        await update.message.reply_text("Твой клан не воюет."); return

    war_id, att_id, def_id = war[0], war[1], war[2]
    att_name, def_name = war[9], war[10]
    enemy_id   = def_id if clan_id == att_id else att_id
    enemy_name = def_name if clan_id == att_id else att_name

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
    my_name = c.fetchone()[0]
    c.execute("SELECT user_id FROM clan_members WHERE clan_id=? AND rank='godfather'", (enemy_id,))
    gf = c.fetchone()
    conn.close()

    keyboard = [[
        InlineKeyboardButton("✓ Принять", callback_data=f"truce_accept_{war_id}"),
        InlineKeyboardButton("✗ Отклонить", callback_data=f"truce_decline_{war_id}"),
    ]]

    await send_photo_message(ctx.bot, update.effective_chat.id, "create_clan",
        f"<b>Предложение о перемирии отправлено «{enemy_name}».</b>")

    if gf:
        try:
            await ctx.bot.send_photo(
                gf[0],
                photo="https://i.ibb.co/4n9mG14q/photo-2026-04-24-22-32-32.jpg",
                caption=(
                    f"<b>[ Предложение о перемирии ]</b>\n{'─'*22}\n\n"
                    f"Клан «{my_name}» предлагает перемирие.\n\n"
                    f"<i>Война будет остановлена без победителя.</i>"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        except: pass

async def handle_truce(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("truce_accept_"):
        war_id = int(data.split("_")[2])
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM wars WHERE id=?", (war_id,))
        war = c.fetchone()
        if not war or war[3] != "active":
            conn.close()
            await query.edit_message_caption("Война уже завершена."); return
        c.execute("UPDATE wars SET status='truce' WHERE id=?", (war_id,))
        c.execute("INSERT OR IGNORE INTO clan_stats (clan_id) VALUES (?)", (war[1],))
        c.execute("INSERT OR IGNORE INTO clan_stats (clan_id) VALUES (?)", (war[2],))
        c.execute("UPDATE clan_stats SET truces=truces+1 WHERE clan_id IN (?,?)", (war[1], war[2]))
        conn.commit()
        conn.close()
        await query.edit_message_caption("✓ Перемирие принято.")
        peace = "<b>[ Перемирие ]</b>\n\nВойна остановлена по соглашению.\n\n<i>Семья отдыхает.</i>"
        await notify_clan(ctx.bot, war[1], peace, "create_clan")
        await notify_clan(ctx.bot, war[2], peace, "create_clan")

    elif data.startswith("truce_decline_"):
        await query.edit_message_caption("✗ Перемирие отклонено. Война продолжается.")
