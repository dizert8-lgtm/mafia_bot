"""
Дополнительные функции клана:
- Пассивный доход 100 монет каждые 2 дня
- /mf_leave  — выйти из клана (платишь 70% монет в казну)
- /mf_demote — понизить участника в звании
"""

import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, Application
from database import get_conn
from ranks import get_rank, has_permission, get_rank_label, RANK_ORDER
from images import send_photo_message

# ══════════════════════════════════════════
#  Инициализация таблицы пассивного дохода
# ══════════════════════════════════════════
def init_clan_system_tables():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS clan_income (
        clan_id     INTEGER PRIMARY KEY,
        last_income TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS leave_requests (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        clan_id     INTEGER,
        status      TEXT DEFAULT 'pending',
        created_at  TEXT
    )""")
    conn.commit()
    conn.close()

# ══════════════════════════════════════════
#  Пассивный доход — проверка и начисление
# ══════════════════════════════════════════
async def check_passive_income(bot):
    """
    Вызывается при запуске бота и периодически.
    Начисляет 100 монет в казну клана каждые 2 дня.
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name FROM clans")
    clans = c.fetchall()

    for clan_id, clan_name in clans:
        c.execute("SELECT last_income FROM clan_income WHERE clan_id=?", (clan_id,))
        row = c.fetchone()

        now = datetime.datetime.now()

        if not row:
            # Первая запись
            c.execute("INSERT INTO clan_income (clan_id, last_income) VALUES (?,?)",
                      (clan_id, now.isoformat()))
            conn.commit()
            continue

        last = datetime.datetime.fromisoformat(row[0])
        delta = now - last

        if delta >= datetime.timedelta(days=2):
            # Начисляем 100 монет в казну
            income = 100
            c.execute("UPDATE clans SET treasury=treasury+? WHERE id=?", (income, clan_id))
            c.execute("UPDATE clan_income SET last_income=? WHERE clan_id=?",
                      (now.isoformat(), clan_id))
            conn.commit()

            # Уведомляем Крёстного отца
            c.execute("SELECT user_id FROM clan_members WHERE clan_id=? AND rank='godfather'",
                      (clan_id,))
            gf = c.fetchone()
            if gf:
                try:
                    await bot.send_message(
                        gf[0],
                        f"<b>[ Пассивный доход ]</b>\n"
                        f"{'─' * 22}\n\n"
                        f"🏛  Клан «{clan_name}»\n"
                        f"💰  Казна пополнена: <b>+{income} монет</b>\n\n"
                        f"<i>Семья работает даже пока ты спишь.</i>",
                        parse_mode="HTML"
                    )
                except: pass

    conn.close()

# ══════════════════════════════════════════
#  /mf_leave — выйти из клана
# ══════════════════════════════════════════
async def leave_clan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player or not player[2]:
        await update.message.reply_text("Ты не в клане.")
        return

    clan_id  = player[2]
    rank     = get_rank(user_id, clan_id)
    coins    = player[4]

    # Крёстный отец не может просто так выйти
    if rank == "godfather":
        await update.message.reply_text(
            "<b>Крёстный отец не может покинуть клан.</b>\n\n"
            "Сначала передай власть другому:\n"
            "<code>/mf_promote @username</code>\n\n"
            "После того как повысишь кого-то до Крёстного отца — "
            "твоё звание станет 🥃 Правая рука и ты сможешь выйти.",
            parse_mode="HTML"
        )
        return

    # Считаем штраф — 70% монет
    fine = int(coins * 0.70)

    # Кнопки подтверждения
    keyboard = [[
        InlineKeyboardButton("✓ Да, покинуть клан", callback_data=f"leave_confirm_{user_id}"),
        InlineKeyboardButton("✗ Отмена", callback_data="leave_cancel"),
    ]]

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
    clan_name = c.fetchone()[0]
    conn.close()

    await update.message.reply_text(
        f"<b>[ Выход из клана ]</b>\n"
        f"{'─' * 22}\n\n"
        f"🏛  Клан: <b>{clan_name}</b>\n"
        f"🏅  Звание: {get_rank_label(rank)}\n\n"
        f"⚠️  При выходе ты заплатишь:\n"
        f"💰  <b>{fine:,} монет</b> (70% от {coins:,})\n\n"
        f"Эти деньги уйдут в казну клана.\n\n"
        f"<i>Ты уверен?</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_leave(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data    = query.data
    user_id = query.from_user.id

    if data == "leave_cancel":
        await query.edit_message_text("❌ Выход отменён. Ты остаёшься в семье.")
        return

    if data.startswith("leave_confirm_"):
        target_user_id = int(data.split("_")[2])

        # Проверяем что нажал именно тот кто запрашивал
        if user_id != target_user_id:
            await query.answer("Это не твоя кнопка!", show_alert=True)
            return

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
        player = c.fetchone()

        if not player or not player[2]:
            conn.close()
            await query.edit_message_text("Ты уже не в клане.")
            return

        clan_id  = player[2]
        coins    = player[4]
        fine     = int(coins * 0.70)
        rank     = get_rank(user_id, clan_id)

        if rank == "godfather":
            conn.close()
            await query.edit_message_text(
                "Крёстный отец не может покинуть клан.\n"
                "Сначала передай власть: /mf_promote @username"
            )
            return

        c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
        clan_name = c.fetchone()[0]

        # Снимаем деньги и добавляем в казну
        c.execute("UPDATE players SET coins=coins-?, clan_id=NULL WHERE user_id=?",
                  (fine, user_id))
        c.execute("UPDATE clans SET treasury=treasury+? WHERE id=?", (fine, clan_id))
        c.execute("DELETE FROM clan_members WHERE user_id=? AND clan_id=?",
                  (user_id, clan_id))
        conn.commit()

        # Уведомляем Крёстного отца клана
        c.execute("SELECT user_id FROM clan_members WHERE clan_id=? AND rank='godfather'",
                  (clan_id,))
        gf = c.fetchone()
        conn.close()

        await query.edit_message_text(
            f"<b>Ты покинул клан «{clan_name}».</b>\n\n"
            f"💰  Штраф: <b>{fine:,} монет</b> переведено в казну.\n\n"
            f"<i>Дорога одиночки тяжела.</i>",
            parse_mode="HTML"
        )

        # Уведомляем Крёстного отца
        if gf:
            try:
                username = player[1]
                await ctx.bot.send_message(
                    gf[0],
                    f"<b>[ Участник покинул клан ]</b>\n"
                    f"{'─' * 22}\n\n"
                    f"👤  @{username} вышел из семьи.\n"
                    f"💰  В казну поступило: <b>{fine:,} монет</b>",
                    parse_mode="HTML"
                )
            except: pass

# ══════════════════════════════════════════
#  /mf_demote — понизить в звании
# ══════════════════════════════════════════
async def demote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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

    # Только Крёстный отец и Правая рука
    if not has_permission(user_id, clan_id, "promote_member"):
        await update.message.reply_text("Недостаточно полномочий.")
        return

    if not ctx.args:
        await update.message.reply_text(
            "Укажи username:\n<code>/mf_demote @username</code>",
            parse_mode="HTML"
        )
        return

    target_username = ctx.args[0].replace("@", "")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM players WHERE username=?", (target_username,))
    target = c.fetchone()

    if not target:
        conn.close()
        await update.message.reply_text("Игрок не найден.")
        return

    target_id    = target[0]
    current_rank = get_rank(target_id, clan_id)

    if not current_rank:
        conn.close()
        await update.message.reply_text("Этот игрок не в твоём клане.")
        return

    if current_rank == "godfather":
        conn.close()
        await update.message.reply_text("Нельзя понизить Крёстного отца.")
        return

    if current_rank == "associate":
        conn.close()
        await update.message.reply_text(
            f"@{target_username} уже на минимальном звании (♟ Associate)."
        )
        return

    # Понижаем на одно звание
    current_idx = RANK_ORDER.index(current_rank)
    new_rank    = RANK_ORDER[current_idx + 1]  # следующий = ниже

    c.execute("UPDATE clan_members SET rank=? WHERE user_id=? AND clan_id=?",
              (new_rank, target_id, clan_id))
    conn.commit()
    conn.close()

    text = (
        f"<b>[ Понижение ]</b>\n"
        f"{'─' * 22}\n\n"
        f"👤  @{target_username}\n"
        f"⬇️  Новое звание: <b>{get_rank_label(new_rank)}</b>\n\n"
        f"<i>Семья ожидала большего.</i>"
    )
    await send_photo_message(ctx.bot, update.effective_chat.id, "kick", text)

    # Уведомляем понижаемого
    try:
        from menu import build_keyboard
        new_keyboard = build_keyboard(new_rank)
        await ctx.bot.send_message(
            target_id,
            f"<b>Твоё звание понижено.</b>\n\n"
            f"⬇️  Новое звание: {get_rank_label(new_rank)}\n\n"
            f"<i>Докажи что достоин большего.</i>",
            parse_mode="HTML",
            reply_markup=new_keyboard
        )
    except: pass
