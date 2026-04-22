"""
Система статистики кланов и конфликтов.
Команды:
  /stat <название>     — статистика клана
  /conflict <название> — добавить/убрать конфликт (лимит 6)
  /conflicts           — список своих конфликтов
"""

import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database import get_conn
from ranks import get_rank, has_permission, get_rank_label

# ══════════════════════════════════════════
#  Инициализация таблиц статистики
# ══════════════════════════════════════════
def init_stats_tables():
    conn = get_conn()
    c = conn.cursor()

    # Статистика войн клана
    c.execute("""CREATE TABLE IF NOT EXISTS clan_stats (
        clan_id     INTEGER PRIMARY KEY,
        wins        INTEGER DEFAULT 0,
        losses      INTEGER DEFAULT 0,
        truces      INTEGER DEFAULT 0,
        total_damage INTEGER DEFAULT 0
    )""")

    # Список конфликтов (холодная война, лимит 6)
    c.execute("""CREATE TABLE IF NOT EXISTS conflicts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        clan_id     INTEGER,
        target_id   INTEGER,
        created_at  TEXT,
        UNIQUE(clan_id, target_id)
    )""")

    conn.commit()
    conn.close()

# ══════════════════════════════════════════
#  Вспомогательные функции
# ══════════════════════════════════════════
def get_clan_by_name(name: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM clans WHERE name=?", (name,))
    clan = c.fetchone()
    conn.close()
    return clan

def get_clan_stats(clan_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM clan_stats WHERE clan_id=?", (clan_id,))
    stats = c.fetchone()
    conn.close()
    return stats

def ensure_stats(clan_id: int):
    """Создаёт запись статистики если её нет."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO clan_stats (clan_id) VALUES (?)", (clan_id,))
    conn.commit()
    conn.close()

def get_conflicts(clan_id: int):
    """Возвращает список конфликтов клана."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT cl.name, co.created_at
                 FROM conflicts co
                 JOIN clans cl ON cl.id = co.target_id
                 WHERE co.clan_id = ?
                 ORDER BY co.created_at DESC""", (clan_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_best_fighter(clan_id: int):
    """Возвращает самого сильного бойца клана."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT p.username, p.strength
                 FROM players p
                 JOIN clan_members cm ON cm.user_id = p.user_id
                 WHERE cm.clan_id = ?
                 ORDER BY p.strength DESC LIMIT 1""", (clan_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_active_war(clan_id: int):
    """Возвращает активную войну клана если есть."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT w.*, 
                 c1.name as att_name, c2.name as def_name
                 FROM wars w
                 JOIN clans c1 ON c1.id = w.attacker_id
                 JOIN clans c2 ON c2.id = w.defender_id
                 WHERE (w.attacker_id=? OR w.defender_id=?)
                 AND w.status='active'""", (clan_id, clan_id))
    row = c.fetchone()
    conn.close()
    return row

# ══════════════════════════════════════════
#  /stat — статистика клана
# ══════════════════════════════════════════
async def clan_stat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Определяем какой клан смотреть
    if ctx.args:
        clan_name = " ".join(ctx.args)
        clan = get_clan_by_name(clan_name)
        if not clan:
            await update.message.reply_text(f"❌ Клан «{clan_name}» не найден.")
            return
    else:
        # Смотрим свой клан
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
        player = c.fetchone()
        conn.close()
        if not player or not player[0]:
            await update.message.reply_text(
                "Укажи название клана: /stat <название>\n"
                "Или вступи в клан чтобы смотреть свой."
            )
            return
        clan = get_clan_by_name("")
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM clans WHERE id=?", (player[0],))
        clan = c.fetchone()
        conn.close()

    clan_id = clan[0]
    ensure_stats(clan_id)

    # Собираем данные
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id=?", (clan_id,))
    member_count = c.fetchone()[0]
    c.execute("SELECT * FROM clan_stats WHERE clan_id=?", (clan_id,))
    stats = c.fetchone()
    conn.close()

    wins    = stats[1] if stats else 0
    losses  = stats[2] if stats else 0
    truces  = stats[3] if stats else 0

    # Конфликты
    conflicts = get_conflicts(clan_id)

    # Активная война
    war = get_active_war(clan_id)

    # Лучший боец
    best = get_best_fighter(clan_id)

    # Дата основания
    created = clan[6][:10] if clan[6] else "неизвестно"
    try:
        dt = datetime.datetime.fromisoformat(clan[6])
        created = dt.strftime("%d.%m.%Y")
    except:
        pass

    # Формируем текст
    text = (
        f"🏛 Клан «{clan[1]}»\n"
        f"{'━' * 22}\n"
        f"👥 Участников: {member_count}\n"
        f"💪 Мощь: {clan[3]}\n"
        f"📅 Основан: {created}\n\n"
    )

    # Казна — только для своего клана и капо+
    my_rank = get_rank(user_id, clan_id)
    if my_rank and has_permission(user_id, clan_id, "view_treasury"):
        text += f"💰 Казна: {clan[4]:,} монет\n\n"

    # Боевая история
    text += (
        f"⚔️ Боевая история:\n"
        f"  🏆 Побед: {wins}\n"
        f"  💀 Поражений: {losses}\n"
        f"  🤝 Перемирий: {truces}\n\n"
    )

    # Активная война
    if war:
        enemy_name = war[10] if war[1] == clan_id else war[9]
        text += f"🔥 Активная война:\n  ⚔️ vs «{enemy_name}»\n\n"
    else:
        text += "☮️ Активных войн нет\n\n"

    # Конфликты
    if conflicts:
        text += f"😤 Конфликты ({len(conflicts)}/6):\n"
        for cname, _ in conflicts:
            text += f"  • «{cname}»\n"
        text += "\n"
    else:
        text += "😤 Конфликтов нет\n\n"

    # Лучший боец
    if best:
        text += f"🏅 Лучший боец: @{best[0]} (сила: {best[1]})"

    await update.message.reply_text(text)


# ══════════════════════════════════════════
#  /conflict — добавить/убрать конфликт
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

    # Только крёстный отец
    if not has_permission(user_id, clan_id, "declare_war"):
        await update.message.reply_text(
            "❌ Только 👑 Крёстный отец может управлять конфликтами."
        )
        return

    if not ctx.args:
        await update.message.reply_text(
            "Укажи название клана:\n"
            "/conflict <название>\n\n"
            "Если конфликт уже есть — он будет удалён.\n"
            "Лимит: 6 конфликтов."
        )
        return

    target_name = " ".join(ctx.args)
    target = get_clan_by_name(target_name)

    if not target:
        await update.message.reply_text(f"❌ Клан «{target_name}» не найден.")
        return

    if target[0] == clan_id:
        await update.message.reply_text("Нельзя конфликтовать с самим собой!")
        return

    conn = get_conn()
    c = conn.cursor()

    # Проверяем существующий конфликт
    c.execute("SELECT id FROM conflicts WHERE clan_id=? AND target_id=?",
              (clan_id, target[0]))
    existing = c.fetchone()

    if existing:
        # Убираем конфликт
        c.execute("DELETE FROM conflicts WHERE clan_id=? AND target_id=?",
                  (clan_id, target[0]))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Конфликт с кланом «{target[1]}» снят."
        )
    else:
        # Проверяем лимит
        c.execute("SELECT COUNT(*) FROM conflicts WHERE clan_id=?", (clan_id,))
        count = c.fetchone()[0]
        if count >= 6:
            conn.close()
            await update.message.reply_text(
                f"❌ Лимит конфликтов достигнут (6/6)!\n"
                f"Сначала сними один: /conflict <название>"
            )
            return

        c.execute("INSERT INTO conflicts (clan_id, target_id, created_at) VALUES (?, ?, ?)",
                  (clan_id, target[0], datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"😤 Клан «{target[1]}» добавлен в список конфликтов!\n"
            f"Всего конфликтов: {count + 1}/6"
        )


# ══════════════════════════════════════════
#  /conflicts — список своих конфликтов
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
    conflicts = get_conflicts(clan_id)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
    clan = c.fetchone()
    conn.close()

    if not conflicts:
        await update.message.reply_text(
            f"😤 Конфликты клана «{clan[0]}»:\n\nКонфликтов нет."
        )
        return

    text = f"😤 Конфликты клана «{clan[0]}» ({len(conflicts)}/6):\n\n"
    for i, (cname, created_at) in enumerate(conflicts, 1):
        try:
            dt = datetime.datetime.fromisoformat(created_at)
            date_str = dt.strftime("%d.%m.%Y")
        except:
            date_str = "?"
        text += f"{i}. «{cname}» — с {date_str}\n"

    text += "\nЧтобы снять конфликт: /conflict <название>"
    await update.message.reply_text(text)
