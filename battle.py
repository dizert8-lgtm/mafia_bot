"""
Система стычек между кланами:
/mf_battle <клан>   — объявить стычку (Крёстный отец, в чате)
/mf_join_battle     — присоединиться к стычке
/mf_battle_status   — статус текущей стычки
/mf_heir @username  — назначить наследника (Крёстный отец)

Механика:
- Привязана к чату группы
- 6 vs 6 участников
- 30 минут
- Автобой каждые 5 минут
- Смерть: рандомно Ранен или Убит (шанс 20-30%)
- Убитый выкидывается из клана на 15 дней
- Крёстный отец может погибнуть с малым шансом
- После смерти КО — голосование клана
"""

import random
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_conn
from ranks import get_rank, has_permission, get_rank_label, RANK_ORDER
from images import send_photo_message

BATTLE_DURATION_MINUTES = 30
AUTO_FIGHT_INTERVAL     = 5   # минут между автоатаками
MAX_FIGHTERS            = 6   # максимум с каждой стороны
DEATH_CHANCE            = 0.25  # 25% шанс смерти при поражении
GF_DEATH_CHANCE         = 0.08  # 8% шанс смерти Крёстного отца
BAN_DAYS                = 15   # дней бана после смерти

# ══════════════════════════════════════════
#  Инициализация таблиц
# ══════════════════════════════════════════
def init_battle_tables():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS battles (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id      INTEGER,
        attacker_id  INTEGER,
        defender_id  INTEGER,
        status       TEXT DEFAULT 'recruiting',
        att_score    INTEGER DEFAULT 0,
        def_score    INTEGER DEFAULT 0,
        started_at   TEXT,
        ends_at      TEXT,
        winner_id    INTEGER DEFAULT NULL,
        round_num    INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS battle_fighters (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        battle_id  INTEGER,
        user_id    INTEGER,
        clan_id    INTEGER,
        status     TEXT DEFAULT 'alive',
        damage     INTEGER DEFAULT 0,
        joined_at  TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS death_bans (
        user_id    INTEGER,
        clan_id    INTEGER,
        banned_at  TEXT,
        until      TEXT,
        PRIMARY KEY (user_id, clan_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS heir_votes (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        clan_id    INTEGER,
        candidate_id INTEGER,
        voter_id   INTEGER,
        UNIQUE(clan_id, voter_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS clan_heirs (
        clan_id    INTEGER PRIMARY KEY,
        heir_id    INTEGER
    )""")

    conn.commit()
    conn.close()

# ══════════════════════════════════════════
#  Вспомогательные функции
# ══════════════════════════════════════════
def get_active_battle(chat_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT b.*, c1.name, c2.name
                 FROM battles b
                 JOIN clans c1 ON c1.id=b.attacker_id
                 JOIN clans c2 ON c2.id=b.defender_id
                 WHERE b.chat_id=? AND b.status IN ('recruiting','active')""",
              (chat_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_battle_fighters(battle_id: int, clan_id: int = None):
    conn = get_conn()
    c = conn.cursor()
    if clan_id:
        c.execute("""SELECT bf.*, p.username FROM battle_fighters bf
                     JOIN players p ON p.user_id=bf.user_id
                     WHERE bf.battle_id=? AND bf.clan_id=? AND bf.status!='dead'""",
                  (battle_id, clan_id))
    else:
        c.execute("""SELECT bf.*, p.username FROM battle_fighters bf
                     JOIN players p ON p.user_id=bf.user_id
                     WHERE bf.battle_id=?""", (battle_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def is_banned(user_id: int, clan_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT until FROM death_bans WHERE user_id=? AND clan_id=?", (user_id, clan_id))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    return datetime.datetime.now() < datetime.datetime.fromisoformat(row[0])

def add_death_ban(user_id: int, clan_id: int):
    conn = get_conn()
    c = conn.cursor()
    until = (datetime.datetime.now() + datetime.timedelta(days=BAN_DAYS)).isoformat()
    c.execute("INSERT OR REPLACE INTO death_bans (user_id, clan_id, banned_at, until) VALUES (?,?,?,?)",
              (user_id, clan_id, datetime.datetime.now().isoformat(), until))
    conn.commit()
    conn.close()

def get_clan_members_ids(clan_id: int) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM clan_members WHERE clan_id=?", (clan_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_random_fighters(clan_id: int, count: int, exclude: list = None) -> list:
    """Выбирает случайных бойцов из клана."""
    exclude = exclude or []
    members = [m for m in get_clan_members_ids(clan_id) if m not in exclude]
    return random.sample(members, min(count, len(members)))

async def notify_fighters(bot, battle_id: int, text: str, image_key: str = "war"):
    """Уведомить всех живых бойцов стычки."""
    fighters = get_battle_fighters(battle_id)
    for f in fighters:
        try:
            await send_photo_message(bot, f[2], image_key, text)
        except: pass

# ══════════════════════════════════════════
#  /mf_battle — объявить стычку
# ══════════════════════════════════════════
async def declare_battle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Только в группе
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "Стычки можно объявлять только в групповом чате!"
        ); return

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане."); return

    clan_id = player[0]
    if not has_permission(user_id, clan_id, "declare_war"):
        await update.message.reply_text("Только 🎩 Крёстный отец может объявлять стычки."); return

    if get_active_battle(chat_id):
        await update.message.reply_text("В этом чате уже идёт стычка!"); return

    if not ctx.args:
        await update.message.reply_text(
            "Укажи название клана:\n<code>/mf_battle Название</code>",
            parse_mode="HTML"); return

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
        await update.message.reply_text("Нельзя объявить стычку самому себе."); return

    ends_at = (datetime.datetime.now() + datetime.timedelta(minutes=BATTLE_DURATION_MINUTES)).isoformat()

    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO battles (chat_id, attacker_id, defender_id, status, started_at, ends_at)
                 VALUES (?,?,?,'recruiting',?,?)""",
              (chat_id, clan_id, target[0], datetime.datetime.now().isoformat(), ends_at))
    battle_id = c.lastrowid

    # Добавляем объявителя как первого бойца
    c.execute("INSERT INTO battle_fighters (battle_id, user_id, clan_id, joined_at) VALUES (?,?,?,?)",
              (battle_id, user_id, clan_id, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

    # Кнопки присоединения
    keyboard = [[
        InlineKeyboardButton("⚔️ Встать в строй", callback_data=f"battle_join_{battle_id}_{clan_id}"),
        InlineKeyboardButton("🛡 Защищать семью", callback_data=f"battle_join_{battle_id}_{target[0]}"),
    ]]

    text = (
        f"<b>[ Объявлена Стычка! ]</b>\n"
        f"{'─' * 22}\n\n"
        f"⚔️  «{my_clan[1]}»  vs  «{target[1]}»\n\n"
        f"➢  Нужно бойцов: <b>6 vs 6</b>\n"
        f"➢  Длительность: <b>{BATTLE_DURATION_MINUTES} минут</b>\n"
        f"➢  Ставка: <b>30% казны</b> проигравшего\n\n"
        f"⚠️  <b>Смерть в стычке возможна!</b>\n"
        f"Погибший покидает клан на {BAN_DAYS} дней.\n\n"
        f"<i>Кто готов рискнуть — вставай в строй!</i>"
    )
    await ctx.bot.send_photo(
        chat_id=chat_id,
        photo="https://i.ibb.co/nqCx6wZh/photo-2026-04-24-22-32-29.jpg",
        caption=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    # Запускаем авто-подбор через 5 минут если не наберут
    ctx.job_queue.run_once(
        auto_fill_fighters,
        when=300,
        data={"battle_id": battle_id, "chat_id": chat_id},
        name=f"autofill_{battle_id}"
    )

# ══════════════════════════════════════════
#  Авто-подбор бойцов
# ══════════════════════════════════════════
async def auto_fill_fighters(ctx: ContextTypes.DEFAULT_TYPE):
    data      = ctx.job.data
    battle_id = data["battle_id"]
    chat_id   = data["chat_id"]

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM battles WHERE id=?", (battle_id,))
    battle = c.fetchone()
    conn.close()

    if not battle or battle[3] == "finished":
        return

    att_id = battle[2]
    def_id = battle[3]

    att_fighters = get_battle_fighters(battle_id, att_id)
    def_fighters = get_battle_fighters(battle_id, def_id)

    att_existing = [f[2] for f in att_fighters]
    def_existing = [f[2] for f in def_fighters]

    conn = get_conn()
    c = conn.cursor()

    # Дополняем атакующих
    if len(att_fighters) < MAX_FIGHTERS:
        needed   = MAX_FIGHTERS - len(att_fighters)
        randoms  = get_random_fighters(att_id, needed, att_existing)
        for uid in randoms:
            c.execute("INSERT OR IGNORE INTO battle_fighters (battle_id, user_id, clan_id, joined_at) VALUES (?,?,?,?)",
                      (battle_id, uid, att_id, datetime.datetime.now().isoformat()))

    # Дополняем защитников
    if len(def_fighters) < MAX_FIGHTERS:
        needed   = MAX_FIGHTERS - len(def_fighters)
        randoms  = get_random_fighters(def_id, needed, def_existing)
        for uid in randoms:
            c.execute("INSERT OR IGNORE INTO battle_fighters (battle_id, user_id, clan_id, joined_at) VALUES (?,?,?,?)",
                      (battle_id, uid, def_id, datetime.datetime.now().isoformat()))

    # Меняем статус на active
    c.execute("UPDATE battles SET status='active' WHERE id=?", (battle_id,))
    conn.commit()
    conn.close()

    # Получаем имена кланов
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (att_id,))
    att_name = c.fetchone()[0]
    c.execute("SELECT name FROM clans WHERE id=?", (def_id,))
    def_name = c.fetchone()[0]
    conn.close()

    att_f = get_battle_fighters(battle_id, att_id)
    def_f = get_battle_fighters(battle_id, def_id)

    att_list = "".join(f"  ➢ @{f[-1]}\n" for f in att_f)
    def_list = "".join(f"  ➢ @{f[-1]}\n" for f in def_f)

    text = (
        f"<b>[ Стычка начинается! ]</b>\n"
        f"{'─' * 22}\n\n"
        f"⚔️  «{att_name}»  vs  «{def_name}»\n\n"
        f"<b>Бойцы «{att_name}»:</b>\n{att_list}\n"
        f"<b>Бойцы «{def_name}»:</b>\n{def_list}\n"
        f"<i>Бой начался. Следи за результатами!</i>"
    )

    await ctx.bot.send_photo(
        chat_id=chat_id,
        photo="https://i.ibb.co/RtDvNgq/photo-2026-04-24-22-32-29.jpg",
        caption=text,
        parse_mode="HTML"
    )

    # Запускаем автобой каждые 5 минут
    ctx.job_queue.run_repeating(
        auto_fight_round,
        interval=AUTO_FIGHT_INTERVAL * 60,
        first=AUTO_FIGHT_INTERVAL * 60,
        data={"battle_id": battle_id, "chat_id": chat_id},
        name=f"fight_{battle_id}"
    )

    # Завершение через 30 минут
    ctx.job_queue.run_once(
        end_battle,
        when=BATTLE_DURATION_MINUTES * 60,
        data={"battle_id": battle_id, "chat_id": chat_id},
        name=f"end_{battle_id}"
    )

# ══════════════════════════════════════════
#  Автобой — раунд каждые 5 минут
# ══════════════════════════════════════════
async def auto_fight_round(ctx: ContextTypes.DEFAULT_TYPE):
    data      = ctx.job.data
    battle_id = data["battle_id"]
    chat_id   = data["chat_id"]

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM battles WHERE id=?", (battle_id,))
    battle = c.fetchone()
    conn.close()

    if not battle or battle[3] != "active":
        ctx.job.schedule_removal()
        return

    att_id   = battle[2]
    def_id   = battle[3]
    att_fighters = get_battle_fighters(battle_id, att_id)
    def_fighters = get_battle_fighters(battle_id, def_id)

    if not att_fighters or not def_fighters:
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (att_id,))
    att_name = c.fetchone()[0]
    c.execute("SELECT name FROM clans WHERE id=?", (def_id,))
    def_name = c.fetchone()[0]

    # Считаем суммарную силу
    att_power = 0
    for f in att_fighters:
        c.execute("SELECT strength FROM players WHERE user_id=?", (f[2],))
        row = c.fetchone()
        if row:
            att_power += row[0] + random.randint(1, 20)

    def_power = 0
    for f in def_fighters:
        c.execute("SELECT strength FROM players WHERE user_id=?", (f[2],))
        row = c.fetchone()
        if row:
            def_power += row[0] + random.randint(1, 20)

    c.execute("UPDATE battles SET att_score=att_score+?, def_score=def_score+?, round_num=round_num+1 WHERE id=?",
              (att_power, def_power, battle_id))

    c.execute("SELECT att_score, def_score, round_num FROM battles WHERE id=?", (battle_id,))
    scores = c.fetchone()
    conn.commit()
    conn.close()

    winner_round = att_name if att_power >= def_power else def_name

    text = (
        f"<b>[ Раунд {scores[2]} ]</b>\n"
        f"{'─' * 22}\n\n"
        f"⚔️  «{att_name}» — «{def_name}»\n\n"
        f"➢  Атака «{att_name}»: <b>{att_power}</b>\n"
        f"➢  Атака «{def_name}»: <b>{def_power}</b>\n\n"
        f"🏆  Раунд за «{winner_round}»\n\n"
        f"<b>Общий счёт:</b>\n"
        f"➢  «{att_name}»: {scores[0]}\n"
        f"➢  «{def_name}»: {scores[1]}"
    )

    keyboard = [[
        InlineKeyboardButton("⚔️ Поддержать своих", callback_data=f"battle_support_{battle_id}")
    ]]

    await ctx.bot.send_photo(
        chat_id=chat_id,
        photo="https://i.ibb.co/WB90XC8/photo-2026-04-24-22-32-49.jpg",
        caption=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

# ══════════════════════════════════════════
#  Кнопки — присоединиться и поддержать
# ══════════════════════════════════════════
async def battle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data    = query.data

    # Присоединиться к стычке
    if data.startswith("battle_join_"):
        parts     = data.split("_")
        battle_id = int(parts[2])
        clan_id   = int(parts[3])

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
        player = c.fetchone()
        conn.close()

        if not player or player[0] != clan_id:
            await query.answer("Ты не состоишь в этом клане!", show_alert=True); return

        # Проверяем бан
        if is_banned(user_id, clan_id):
            await query.answer("Ты погиб в предыдущей стычке и не можешь участвовать!", show_alert=True); return

        # Проверяем лимит
        fighters = get_battle_fighters(battle_id, clan_id)
        if len(fighters) >= MAX_FIGHTERS:
            await query.answer("Состав уже полный — 6 бойцов!", show_alert=True); return

        # Проверяем не добавлен ли уже
        if any(f[2] == user_id for f in fighters):
            await query.answer("Ты уже в составе!", show_alert=True); return

        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO battle_fighters (battle_id, user_id, clan_id, joined_at) VALUES (?,?,?,?)",
                  (battle_id, user_id, clan_id, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
        clan_name = c.fetchone()[0]
        c.execute("SELECT username FROM players WHERE user_id=?", (user_id,))
        username = c.fetchone()[0]
        conn.close()

        await query.answer(f"✓ Ты встал в строй клана «{clan_name}»!", show_alert=True)

        fighters_now = get_battle_fighters(battle_id, clan_id)
        await ctx.bot.send_message(
            query.message.chat_id,
            f"➢ @{username} встал в строй «{clan_name}» ({len(fighters_now)}/{MAX_FIGHTERS})",
            parse_mode="HTML"
        )

    # Поддержать своих во время боя
    elif data.startswith("battle_support_"):
        battle_id = int(data.split("_")[2])

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
        player = c.fetchone()
        conn.close()

        if not player or not player[0]:
            await query.answer("Ты не в клане!", show_alert=True); return

        clan_id = player[0]

        # Проверяем что этот клан участвует
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM battles WHERE id=? AND (attacker_id=? OR defender_id=?)",
                  (battle_id, clan_id, clan_id))
        battle = c.fetchone()
        conn.close()

        if not battle:
            await query.answer("Твой клан не участвует в этой стычке!", show_alert=True); return

        fighters = get_battle_fighters(battle_id, clan_id)
        if len(fighters) >= MAX_FIGHTERS:
            await query.answer("Состав полный — помочь нельзя!", show_alert=True); return

        if any(f[2] == user_id for f in fighters):
            await query.answer("Ты уже сражаешься!", show_alert=True); return

        if is_banned(user_id, clan_id):
            await query.answer("Ты не можешь участвовать — погиб в прошлой стычке!", show_alert=True); return

        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO battle_fighters (battle_id, user_id, clan_id, joined_at) VALUES (?,?,?,?)",
                  (battle_id, user_id, clan_id, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
        clan_name = c.fetchone()[0]
        c.execute("SELECT username FROM players WHERE user_id=?", (user_id,))
        username = c.fetchone()[0]
        conn.close()

        await query.answer(f"⚔️ Ты вступил в бой за «{clan_name}»!", show_alert=True)
        await ctx.bot.send_message(
            query.message.chat_id,
            f"🔥 @{username} вступает в стычку на стороне «{clan_name}»!",
        )

    # Голосование за наследника
    elif data.startswith("heir_vote_"):
        parts       = data.split("_")
        clan_id     = int(parts[2])
        candidate_id = int(parts[3])

        conn = get_conn()
        c = conn.cursor()
        # Проверяем что голосующий в клане
        c.execute("SELECT user_id FROM clan_members WHERE clan_id=? AND user_id=?", (clan_id, user_id))
        if not c.fetchone():
            conn.close()
            await query.answer("Ты не в этом клане!", show_alert=True); return

        c.execute("INSERT OR REPLACE INTO heir_votes (clan_id, candidate_id, voter_id) VALUES (?,?,?)",
                  (clan_id, candidate_id, user_id))
        conn.commit()

        c.execute("SELECT COUNT(*) FROM heir_votes WHERE clan_id=? AND candidate_id=?", (clan_id, candidate_id))
        votes = c.fetchone()[0]
        c.execute("SELECT username FROM players WHERE user_id=?", (candidate_id,))
        cand_name = c.fetchone()[0]
        conn.close()

        await query.answer(f"✓ Твой голос за @{cand_name} принят! ({votes} голосов)", show_alert=True)

# ══════════════════════════════════════════
#  Завершение стычки
# ══════════════════════════════════════════
async def end_battle(ctx: ContextTypes.DEFAULT_TYPE):
    data      = ctx.job.data
    battle_id = data["battle_id"]
    chat_id   = data["chat_id"]

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM battles WHERE id=?", (battle_id,))
    battle = c.fetchone()
    conn.close()

    if not battle or battle[3] == "finished":
        return

    att_id    = battle[2]
    def_id    = battle[3]
    att_score = battle[5]
    def_score = battle[6]

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (att_id,))
    att_name = c.fetchone()[0]
    c.execute("SELECT name FROM clans WHERE id=?", (def_id,))
    def_name = c.fetchone()[0]
    conn.close()

    # Определяем победителя
    if att_score >= def_score:
        winner_id, loser_id     = att_id, def_id
        winner_name, loser_name = att_name, def_name
    else:
        winner_id, loser_id     = def_id, att_id
        winner_name, loser_name = def_name, att_name

    # Обновляем статус
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE battles SET status='finished', winner_id=? WHERE id=?", (winner_id, battle_id))

    # Приз — 30% казны проигравшего
    c.execute("SELECT treasury FROM clans WHERE id=?", (loser_id,))
    prize = int(c.fetchone()[0] * 0.30)
    c.execute("UPDATE clans SET treasury=treasury+?, power=power+10 WHERE id=?", (prize, winner_id))
    c.execute("UPDATE clans SET treasury=MAX(0,treasury-?), power=MAX(10,power-8) WHERE id=?", (prize, loser_id))
    conn.commit()
    conn.close()

    # Обрабатываем потери
    deaths_text = await process_casualties(ctx.bot, battle_id, winner_id, loser_id, chat_id)

    text = (
        f"<b>[ Стычка завершена! ]</b>\n"
        f"{'─' * 22}\n\n"
        f"🏆  Победитель: <b>«{winner_name}»</b>\n\n"
        f"➢  «{att_name}»: {att_score} очков\n"
        f"➢  «{def_name}»: {def_score} очков\n\n"
        f"💰  Захвачено: <b>{prize:,} монет</b>\n\n"
        f"{deaths_text}"
        f"\n<i>Семья помнит своих павших.</i>"
    )

    await ctx.bot.send_photo(
        chat_id=chat_id,
        photo="https://i.ibb.co/nqCx6wZh/photo-2026-04-24-22-32-29.jpg",
        caption=text,
        parse_mode="HTML"
    )

    # Останавливаем автобой
    current_jobs = ctx.job_queue.get_jobs_by_name(f"fight_{battle_id}")
    for job in current_jobs:
        job.schedule_removal()

# ══════════════════════════════════════════
#  Обработка потерь
# ══════════════════════════════════════════
async def process_casualties(bot, battle_id: int, winner_id: int, loser_id: int, chat_id: int) -> str:
    """Определяет убитых и раненых."""
    deaths_text = ""

    winner_fighters = get_battle_fighters(battle_id, winner_id)
    loser_fighters  = get_battle_fighters(battle_id, loser_id)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (winner_id,))
    winner_name = c.fetchone()[0]
    c.execute("SELECT name FROM clans WHERE id=?", (loser_id,))
    loser_name  = c.fetchone()[0]
    conn.close()

    # У победителей малый шанс потерь
    winner_deaths = []
    for f in winner_fighters:
        if random.random() < 0.10:  # 10% у победителей
            result = random.choice(["wounded", "dead"])
            if result == "dead":
                winner_deaths.append(f)

    # У проигравших гарантированно 2-4 жертвы
    loser_sample  = random.sample(loser_fighters, min(random.randint(2, 4), len(loser_fighters)))
    loser_deaths  = []
    loser_wounded = []

    for f in loser_sample:
        result = random.choice(["wounded", "dead"])
        if result == "dead":
            loser_deaths.append(f)
        else:
            loser_wounded.append(f)

    # Если нет смертей у проигравших — хотя бы 1 убитый
    if not loser_deaths and loser_sample:
        loser_deaths.append(loser_sample[0])
        loser_wounded = [f for f in loser_wounded if f != loser_sample[0]]

    # Обрабатываем убитых победителей
    for f in winner_deaths:
        await kill_fighter(bot, f[2], winner_id, f[-1], chat_id)

    # Обрабатываем убитых проигравших
    for f in loser_deaths:
        await kill_fighter(bot, f[2], loser_id, f[-1], chat_id)

    # Проверяем Крёстного отца (если был в чате)
    gf_check = await check_godfather_death(bot, winner_id, loser_id, battle_id, chat_id)

    # Формируем текст потерь
    if winner_deaths:
        deaths_text += f"💀 <b>Потери «{winner_name}»:</b>\n"
        for f in winner_deaths:
            deaths_text += f"  ➢ @{f[-1]} — убит\n"
        deaths_text += "\n"

    if loser_deaths or loser_wounded:
        deaths_text += f"💀 <b>Потери «{loser_name}»:</b>\n"
        for f in loser_deaths:
            deaths_text += f"  ➢ @{f[-1]} — убит\n"
        for f in loser_wounded:
            deaths_text += f"  ➢ @{f[-1]} — ранен\n"
        deaths_text += "\n"

    return deaths_text

async def kill_fighter(bot, user_id: int, clan_id: int, username: str, chat_id: int):
    """Убивает бойца — выкидывает из клана, добавляет бан."""
    conn = get_conn()
    c = conn.cursor()

    # Проверяем не Крёстный ли отец
    rank = None
    c.execute("SELECT rank FROM clan_members WHERE user_id=? AND clan_id=?", (user_id, clan_id))
    row = c.fetchone()
    if row:
        rank = row[0]

    if rank == "godfather":
        conn.close()
        return  # Крёстный отец обрабатывается отдельно

    # Выкидываем из клана
    c.execute("DELETE FROM clan_members WHERE user_id=? AND clan_id=?", (user_id, clan_id))
    c.execute("UPDATE players SET clan_id=NULL WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

    # Добавляем бан на 15 дней
    add_death_ban(user_id, clan_id)

    try:
        await bot.send_message(
            user_id,
            f"<b>💀 Ты погиб в стычке.</b>\n\n"
            f"Ты исключён из клана.\n"
            f"Вступить в этот клан снова можно через <b>{BAN_DAYS} дней</b>.\n\n"
            f"<i>Семья помнит тебя.</i>",
            parse_mode="HTML"
        )
    except: pass

async def check_godfather_death(bot, winner_id: int, loser_id: int, battle_id: int, chat_id: int) -> str:
    """Проверяет может ли погибнуть Крёстный отец."""
    for clan_id in [winner_id, loser_id]:
        chance = GF_DEATH_CHANCE if clan_id == winner_id else GF_DEATH_CHANCE * 2

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT user_id FROM clan_members WHERE clan_id=? AND rank='godfather'", (clan_id,))
        gf = c.fetchone()
        c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
        clan_name = c.fetchone()[0]
        conn.close()

        if not gf:
            continue

        gf_id = gf[0]

        # Проверяем был ли КО в стычке
        fighters = get_battle_fighters(battle_id, clan_id)
        gf_in_battle = any(f[2] == gf_id for f in fighters)

        if not gf_in_battle:
            continue

        if random.random() < chance:
            # Крёстный отец погибает!
            await handle_godfather_death(bot, gf_id, clan_id, clan_name, chat_id)

    return ""

async def handle_godfather_death(bot, gf_id: int, clan_id: int, clan_name: str, chat_id: int):
    """Обрабатывает смерть Крёстного отца."""
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT username FROM players WHERE user_id=?", (gf_id,))
    gf_name = c.fetchone()[0]

    # Проверяем есть ли назначенный наследник
    c.execute("SELECT heir_id FROM clan_heirs WHERE clan_id=?", (clan_id,))
    heir_row = c.fetchone()

    if heir_row:
        heir_id = heir_row[0]
        c.execute("SELECT username FROM players WHERE user_id=?", (heir_id,))
        heir_name = c.fetchone()[0]

        # Передаём власть наследнику
        c.execute("UPDATE clan_members SET rank='godfather' WHERE user_id=? AND clan_id=?", (heir_id, clan_id))
        c.execute("DELETE FROM clan_members WHERE user_id=? AND clan_id=?", (gf_id, clan_id))
        c.execute("UPDATE players SET clan_id=NULL WHERE user_id=?", (gf_id,))
        c.execute("DELETE FROM clan_heirs WHERE clan_id=?", (clan_id,))
        conn.commit()
        conn.close()

        add_death_ban(gf_id, clan_id)

        text = (
            f"<b>[ 💀 Крёстный отец пал! ]</b>\n"
            f"{'─' * 22}\n\n"
            f"👑 @{gf_name} — погиб в стычке.\n\n"
            f"Власть над «{clan_name}» переходит к\n"
            f"🎩 @{heir_name} — назначенному наследнику.\n\n"
            f"<i>Семья продолжает жить.</i>"
        )
        try:
            await bot.send_message(heir_id,
                f"<b>🎩 Ты — новый Крёстный отец «{clan_name}».</b>\n\n"
                f"Предыдущий босс пал в бою.\n<i>Веди семью с честью.</i>",
                parse_mode="HTML")
        except: pass

    else:
        # Нет наследника — голосование
        conn.commit()

        # Кандидаты: все Правые руки и Капо
        c.execute("""SELECT user_id FROM clan_members
                     WHERE clan_id=? AND rank IN ('underboss','capo')
                     AND user_id != ?""", (clan_id, gf_id))
        candidates = c.fetchall()

        if not candidates:
            # Если никого нет — берём любого члена
            c.execute("SELECT user_id FROM clan_members WHERE clan_id=? AND user_id!=?", (clan_id, gf_id))
            candidates = c.fetchall()

        conn.close()

        # Убираем старого КО
        conn = get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM clan_members WHERE user_id=? AND clan_id=?", (gf_id, clan_id))
        c.execute("UPDATE players SET clan_id=NULL WHERE user_id=?", (gf_id,))
        conn.commit()
        conn.close()
        add_death_ban(gf_id, clan_id)

        if not candidates:
            text = (
                f"<b>[ 💀 Крёстный отец пал! ]</b>\n"
                f"{'─' * 22}\n\n"
                f"👑 @{gf_name} — погиб в стычке.\n"
                f"Клан «{clan_name}» остался без лидера.\n\n"
                f"<i>Семья в смятении...</i>"
            )
        else:
            keyboard = []
            for (cand_id,) in candidates[:5]:
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT username FROM players WHERE user_id=?", (cand_id,))
                cand_name = c.fetchone()[0]
                conn.close()
                keyboard.append([InlineKeyboardButton(
                    f"➢ @{cand_name}",
                    callback_data=f"heir_vote_{clan_id}_{cand_id}"
                )])

            text = (
                f"<b>[ 💀 Крёстный отец пал! ]</b>\n"
                f"{'─' * 22}\n\n"
                f"👑 @{gf_name} — погиб в стычке.\n\n"
                f"<b>Клан «{clan_name}» выбирает нового лидера!</b>\n"
                f"Голосуй за нового Крёстного отца.\n"
                f"Голосование длится 10 минут.\n\n"
                f"<i>Семья должна решить.</i>"
            )
            await bot.send_photo(
                chat_id=chat_id,
                photo="https://i.ibb.co/kgnygtHf/photo-2026-04-24-22-32-36.jpg",
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )

            # Через 10 минут подводим итоги голосования
            from telegram.ext import CallbackContext
            # Сохраняем данные для финального подсчёта
            return

    await bot.send_photo(
        chat_id=chat_id,
        photo="https://i.ibb.co/kgnygtHf/photo-2026-04-24-22-32-36.jpg",
        caption=text,
        parse_mode="HTML"
    )

# ══════════════════════════════════════════
#  /mf_heir — назначить наследника
# ══════════════════════════════════════════
async def set_heir(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане."); return

    clan_id = player[0]
    rank    = get_rank(user_id, clan_id)

    if rank != "godfather":
        await update.message.reply_text("Только 🎩 Крёстный отец может назначать наследника."); return

    if not ctx.args:
        await update.message.reply_text(
            "Укажи username:\n<code>/mf_heir @username</code>",
            parse_mode="HTML"); return

    target_username = ctx.args[0].replace("@", "")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM players WHERE username=?", (target_username,))
    target = c.fetchone()
    conn.close()

    if not target:
        await update.message.reply_text("Игрок не найден."); return

    target_id   = target[0]
    target_rank = get_rank(target_id, clan_id)

    if not target_rank:
        await update.message.reply_text("Этот игрок не в твоём клане."); return

    if target_id == user_id:
        await update.message.reply_text("Нельзя назначить себя наследником."); return

    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO clan_heirs (clan_id, heir_id) VALUES (?,?)",
              (clan_id, target_id))
    conn.commit()
    conn.close()

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
    clan_name = c.fetchone()[0]
    conn.close()

    text = (
        f"<b>[ Наследник назначен ]</b>\n"
        f"{'─' * 22}\n\n"
        f"👑  @{target_username} назначен наследником\n"
        f"    клана «{clan_name}».\n\n"
        f"<i>Если Крёстный отец падёт — власть перейдёт к нему.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "clan_info", text)

    try:
        await ctx.bot.send_message(
            target_id,
            f"<b>Тебя назначили наследником клана «{clan_name}».</b>\n\n"
            f"Если Крёстный отец погибнет — власть перейдёт к тебе.\n\n"
            f"<i>Будь готов взять на себя ответственность.</i>",
            parse_mode="HTML"
        )
    except: pass

# ══════════════════════════════════════════
#  /mf_battle_status
# ══════════════════════════════════════════
async def battle_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    battle  = get_active_battle(chat_id)

    if not battle:
        await update.message.reply_text(
            "<b>Активных стычек нет.</b>\n\n"
            "Крёстный отец может объявить:\n"
            "<code>/mf_battle Название клана</code>",
            parse_mode="HTML"); return

    att_name = battle[11]
    def_name = battle[12]
    att_score = battle[5]
    def_score = battle[6]
    status    = battle[3]
    ends_at   = datetime.datetime.fromisoformat(battle[8])
    remaining = ends_at - datetime.datetime.now()

    if remaining.total_seconds() < 0:
        await update.message.reply_text("Стычка завершается..."); return

    minutes_left = int(remaining.total_seconds() // 60)
    seconds_left = int(remaining.total_seconds() % 60)

    att_f = get_battle_fighters(battle[0], battle[2])
    def_f = get_battle_fighters(battle[0], battle[4] if len(battle) > 4 else 0)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM battles WHERE id=?", (battle[0],))
    b = c.fetchone()
    conn.close()

    att_f = get_battle_fighters(b[0], b[2])
    def_f = get_battle_fighters(b[0], b[3])

    status_text = "📋 Набор бойцов" if b[4] == "recruiting" else "⚔️ Идёт бой"

    text = (
        f"<b>[ Стычка — {status_text} ]</b>\n"
        f"{'─' * 22}\n\n"
        f"⚔️  «{att_name}»  vs  «{def_name}»\n\n"
        f"➢  «{att_name}»: {len(att_f)}/6 бойцов  |  {att_score} очков\n"
        f"➢  «{def_name}»: {len(def_f)}/6 бойцов  |  {def_score} очков\n\n"
        f"⏳  До конца: <b>{minutes_left}мин {seconds_left}сек</b>"
    )
    await send_photo_message(ctx.bot, chat_id, "war", text)