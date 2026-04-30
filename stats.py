"""
Статистика кланов и конфликты.
"""

import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database import get_conn
from ranks import get_rank, has_permission
from images import send_photo_message

def init_stats_tables():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS clan_stats (
        clan_id      INTEGER PRIMARY KEY,
        wins         INTEGER DEFAULT 0,
        losses       INTEGER DEFAULT 0,
        truces       INTEGER DEFAULT 0,
        total_damage INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS conflicts (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        clan_id    INTEGER,
        target_id  INTEGER,
        created_at TEXT,
        UNIQUE(clan_id, target_id)
    )""")
    conn.commit()
    conn.close()

def get_clan_by_name(name: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM clans WHERE name=?", (name,))
    clan = c.fetchone()
    conn.close()
    return clan

def ensure_stats(clan_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO clan_stats (clan_id) VALUES (?)", (clan_id,))
    conn.commit()
    conn.close()

def get_conflicts_list(clan_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT cl.name, co.created_at
                 FROM conflicts co
                 JOIN clans cl ON cl.id=co.target_id
                 WHERE co.clan_id=?
                 ORDER BY co.created_at DESC""", (clan_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_best_fighter(clan_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT p.username, p.strength
                 FROM players p
                 JOIN clan_members cm ON cm.user_id=p.user_id
                 WHERE cm.clan_id=?
                 ORDER BY p.strength DESC LIMIT 1""", (clan_id,))
    row = c.fetchone()
    conn.close()
    return row

# ══════════════════════════════════════════
#  /mf_stat — статистика клана
# ══════════════════════════════════════════
async def clan_stat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Определяем клан
    if ctx.args:
        clan_name = " ".join(ctx.args)
        clan = get_clan_by_name(clan_name)
        if not clan:
            await update.message.reply_text(f"Клан «{clan_name}» не найден.")
            return
    else:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
        player = c.fetchone()
        conn.close()
        if not player or not player[0]:
            await update.message.reply_text(
                "Ты не в клане.\n"
                "Укажи название: <code>/mf_stat Название клана</code>",
                parse_mode="HTML"
            )
            return
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM clans WHERE id=?", (player[0],))
        clan = c.fetchone()
        conn.close()

    if not clan:
        await update.message.reply_text("Клан не найден.")
        return

    clan_id = clan[0]
    ensure_stats(clan_id)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id=?", (clan_id,))
    member_count = c.fetchone()[0]
    c.execute("SELECT * FROM clan_stats WHERE clan_id=?", (clan_id,))
    stats = c.fetchone()
    conn.close()

    wins   = stats[1] if stats else 0
    losses = stats[2] if stats else 0
    truces = stats[3] if stats else 0

    conflicts = get_conflicts_list(clan_id)
    best      = get_best_fighter(clan_id)

    # Активная война
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT w.*, c1.name, c2.name FROM wars w
                 JOIN clans c1 ON c1.id=w.attacker_id
                 JOIN clans c2 ON c2.id=w.defender_id
                 WHERE (w.attacker_id=? OR w.defender_id=?)
                 AND w.status='active'""", (clan_id, clan_id))
    war = c.fetchone()
    conn.close()

    # Дата основания
    try:
        dt = datetime.datetime.fromisoformat(clan[6])
        created = dt.strftime("%d.%m.%Y")
    except:
        created = "—"

    text = (
        f"<b>[ Досье клана — {clan[1]} ]</b>\n"
        f"{'─' * 22}\n\n"
        f"👥  <b>Участников:</b>  {member_count}\n"
        f"💪  <b>Мощь:</b>        {clan[3]}\n"
        f"📅  <b>Основан:</b>     {created}\n\n"
        f"<b>⚔️ Боевая история:</b>\n"
        f"  🏆  Побед:      {wins}\n"
        f"  💀  Поражений:  {losses}\n"
        f"  🤝  Перемирий:  {truces}\n\n"
    )

    if war:
        enemy = war[10] if war[1] == clan_id else war[9]
        text += f"🔥  <b>Активная война:</b>  vs «{enemy}»\n\n"
    else:
        text += "☮️  <b>Активных войн нет</b>\n\n"

    if conflicts:
        text += f"😤  <b>Конфликты ({len(conflicts)}/6):</b>\n"
        for cname, _ in conflicts:
            text += f"  • «{cname}»\n"
        text += "\n"
    else:
        text += "😤  <b>Конфликтов нет</b>\n\n"

    if best:
        text += f"🏅  <b>Лучший боец:</b>  @{best[0]} (сила: {best[1]})"

    await send_photo_message(ctx.bot, update.effective_chat.id, "stat", text)

# ══════════════════════════════════════════
#  /mf_conflict — добавить/убрать конфликт
# ══════════════════════════════════════════
async def manage_conflict(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане.")
        return

    clan_id = player[0]
    if not has_permission(user_id, clan_id, "declare_war"):
        await update.message.reply_text(
            "❌ Только 🎩 Крёстный отец управляет конфликтами."
        )
        return

    if not ctx.args:
        await update.message.reply_text(
            "Укажи название клана:\n"
            "<code>/mf_conflict Название клана</code>\n\n"
            "Повторный ввод — снимет конфликт.\n"
            "Лимит: 6 конфликтов.",
            parse_mode="HTML"
        )
        return

    target_name = " ".join(ctx.args)
    target = get_clan_by_name(target_name)

    if not target:
        await update.message.reply_text(f"Клан «{target_name}» не найден.")
        return
    if target[0] == clan_id:
        await update.message.reply_text("Нельзя конфликтовать с самим собой.")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM conflicts WHERE clan_id=? AND target_id=?",
              (clan_id, target[0]))
    existing = c.fetchone()

    if existing:
        c.execute("DELETE FROM conflicts WHERE clan_id=? AND target_id=?",
                  (clan_id, target[0]))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Конфликт с «{target[1]}» снят."
        )
    else:
        c.execute("SELECT COUNT(*) FROM conflicts WHERE clan_id=?", (clan_id,))
        count = c.fetchone()[0]
        if count >= 6:
            conn.close()
            await update.message.reply_text(
                "❌ Лимит конфликтов (6/6)!\n"
                "Сначала сними один: /mf_conflict <название>"
            )
            return
        c.execute("INSERT INTO conflicts (clan_id, target_id, created_at) VALUES (?,?,?)",
                  (clan_id, target[0], datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"😤 Клан «{target[1]}» добавлен в конфликты!\n"
            f"Всего конфликтов: {count+1}/6"
        )

# ══════════════════════════════════════════
#  /mf_conflicts — список конфликтов
# ══════════════════════════════════════════
async def list_conflicts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане.")
        return

    clan_id = player[0]
    conflicts = get_conflicts_list(clan_id)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
    clan = c.fetchone()
    conn.close()

    if not conflicts:
        await update.message.reply_text(
            f"<b>[ Конфликты клана «{clan[0]}» ]</b>\n\n"
            f"Конфликтов нет.\n\n"
            f"Добавить: <code>/mf_conflict Название клана</code>",
            parse_mode="HTML"
        )
        return

    text = f"<b>[ Конфликты «{clan[0]}» — {len(conflicts)}/6 ]</b>\n{'─'*22}\n\n"
    for i, (cname, created_at) in enumerate(conflicts, 1):
        try:
            dt = datetime.datetime.fromisoformat(created_at)
            date_str = dt.strftime("%d.%m.%Y")
        except:
            date_str = "—"
        text += f"{i}.  «{cname}»  —  с {date_str}\n"

    text += f"\n<i>Снять конфликт: /mf_conflict Название</i>"
    await send_photo_message(ctx.bot, update.effective_chat.id, "conflict", text)

# ══════════════════════════════════════════
#  /mf_clan_announce — объявление от Крёстного отца
# ══════════════════════════════════════════
async def clan_announce(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player or not player[0]:
        await update.message.reply_text("Ты не в клане.")
        return

    clan_id = player[0]
    if not has_permission(user_id, clan_id, "declare_war"):
        await update.message.reply_text(
            "❌ Только 🎩 Крёстный отец может делать объявления клану."
        )
        return

    if not ctx.args:
        await update.message.reply_text(
            "Укажи текст:\n<code>/mf_clan_announce Текст объявления</code>",
            parse_mode="HTML"
        )
        return

    msg_text = " ".join(ctx.args)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
    clan_name = c.fetchone()[0]
    c.execute("SELECT user_id FROM clan_members WHERE clan_id=?", (clan_id,))
    members = c.fetchall()
    conn.close()

    text = (
        f"<b>[ Объявление семьи «{clan_name}» ]</b>\n"
        f"{'─' * 22}\n\n"
        f"{msg_text}\n\n"
        f"<i>— 🎩 Крёстный отец</i>"
    )

    sent = 0
    for (uid,) in members:
        try:
            await send_photo_message(ctx.bot, uid, "announce", text)
            sent += 1
        except:
            pass

    await update.message.reply_text(f"✅ Объявление отправлено {sent} участникам клана.")