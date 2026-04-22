import os
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from database import init_db, get_conn
from ranks import (
    RANKS, RANK_ORDER, get_rank, has_permission,
    get_rank_label, get_next_rank, get_clan_members_by_rank
)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = 0  # <- вставь свой Telegram ID сюда

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO players (user_id, username) VALUES (?, ?)",
              (user.id, user.username or user.first_name))
    conn.commit()
    conn.close()

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT text FROM announcements ORDER BY id DESC LIMIT 1")
    ann = c.fetchone()
    conn.close()
    ann_text = f"\n\n📢 Последнее объявление:\n{ann[0]}" if ann else ""

    await update.message.reply_text(
        f"🎭 Добро пожаловать в мир мафии, {user.first_name}!{ann_text}\n\n"
        "📋 Команды:\n"
        "/profile — профиль\n"
        "/create_clan — создать клан (300 монет)\n"
        "/request_join — подать заявку в клан\n"
        "/clan_info — информация о клане\n"
        "/members — состав клана\n"
        "/promote — повысить участника\n"
        "/kick — выгнать участника\n"
        "/requests — заявки (капо+)\n"
        "/top — топ кланов"
    )

async def profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player:
        await update.message.reply_text("Сначала напиши /start"); return

    uid, username, clan_id, strength, coins, level, exp = player
    clan_text = "Без клана"
    rank_text = ""
    if clan_id:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
        clan = c.fetchone()
        conn.close()
        if clan:
            rank = get_rank(user_id, clan_id)
            rank_text = f"\n🏅 Звание: {get_rank_label(rank)}"
            clan_text = f"🏛 {clan[0]}"

    await update.message.reply_text(
        f"👤 {username}\n"
        f"⭐ Уровень: {level}  |  📊 Опыт: {exp}\n"
        f"⚔️ Сила: {strength}  |  💰 Монеты: {coins}\n"
        f"Клан: {clan_text}{rank_text}"
    )

async def create_clan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player:
        await update.message.reply_text("Сначала напиши /start"); return
    if player[2]:
        await update.message.reply_text("Ты уже в клане!"); return
    if player[4] < 300:
        await update.message.reply_text(f"❌ Нужно 300 монет. У тебя: {player[4]}"); return
    if not ctx.args:
        await update.message.reply_text("Укажи название: /create_clan <название>"); return

    name = " ".join(ctx.args)
    if len(name) < 3 or len(name) > 30:
        await update.message.reply_text("Название: от 3 до 30 символов"); return

    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO clans (name, owner_id, created_at) VALUES (?, ?, ?)",
                  (name, user_id, datetime.datetime.now().isoformat()))
        clan_id = c.lastrowid
        c.execute("UPDATE players SET clan_id=?, coins=coins-300 WHERE user_id=?", (clan_id, user_id))
        c.execute("INSERT INTO clan_members (user_id, clan_id, rank, joined_at) VALUES (?, ?, 'godfather', ?)",
                  (user_id, clan_id, datetime.datetime.now().isoformat()))
        conn.commit()
        await update.message.reply_text(
            f"🏛 Клан «{name}» создан!\n👑 Ты — Крёстный отец\n💰 Списано 300 монет"
        )
    except Exception:
        await update.message.reply_text("❌ Клан с таким названием уже существует!")
    finally:
        conn.close()

async def request_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player:
        await update.message.reply_text("Сначала напиши /start"); return
    if player[2]:
        await update.message.reply_text("Ты уже в клане!"); return
    if not ctx.args:
        await update.message.reply_text("Укажи клан: /request_join <название>"); return

    clan_name = " ".join(ctx.args)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM clans WHERE name=?", (clan_name,))
    clan = c.fetchone()
    if not clan:
        conn.close()
        await update.message.reply_text(f"❌ Клан «{clan_name}» не найден."); return

    c.execute("SELECT * FROM join_requests WHERE user_id=? AND clan_id=? AND status='pending'",
              (user_id, clan[0]))
    if c.fetchone():
        conn.close()
        await update.message.reply_text("Ты уже подал заявку в этот клан!"); return

    c.execute("INSERT INTO join_requests (user_id, clan_id, message, created_at) VALUES (?, ?, ?, ?)",
              (user_id, clan[0], "Хочу вступить в клан", datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Заявка в клан «{clan_name}» отправлена! Ожидай решения.")

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
        await update.message.reply_text("❌ Только Капо и выше могут смотреть заявки."); return

    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT jr.id, p.username, p.strength, p.level
                 FROM join_requests jr JOIN players p ON p.user_id=jr.user_id
                 WHERE jr.clan_id=? AND jr.status='pending'""", (clan_id,))
    requests = c.fetchall()
    conn.close()

    if not requests:
        await update.message.reply_text("📋 Заявок нет."); return

    for req_id, username, strength, level in requests:
        keyboard = [[
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{req_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_{req_id}"),
        ]]
        await update.message.reply_text(
            f"📨 Заявка от @{username}\n⭐ Уровень: {level}  |  ⚔️ Сила: {strength}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

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
        await query.edit_message_text("Заявка уже обработана."); return

    req_user_id, clan_id = req[1], req[2]
    if not has_permission(user_id, clan_id, "accept_member"):
        conn.close()
        await query.answer("❌ Нет прав!", show_alert=True); return

    if action == "accept":
        c.execute("UPDATE join_requests SET status='accepted' WHERE id=?", (req_id,))
        c.execute("UPDATE players SET clan_id=? WHERE user_id=?", (clan_id, req_user_id))
        c.execute("INSERT OR IGNORE INTO clan_members (user_id, clan_id, rank, joined_at) VALUES (?, ?, 'associate', ?)",
                  (req_user_id, clan_id, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ Игрок принят как 🃏 Associate!")
        try:
            await ctx.bot.send_message(req_user_id, "🎉 Заявка одобрена! Ты — 🃏 Associate.")
        except: pass
    else:
        c.execute("UPDATE join_requests SET status='declined' WHERE id=?", (req_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("❌ Заявка отклонена.")
        try:
            await ctx.bot.send_message(req_user_id, "😔 Твоя заявка отклонена.")
        except: pass

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

    text = f"👥 Состав клана «{clan[0]}»:\n\n"
    for username, rank, uid in members_list:
        text += f"{get_rank_label(rank)} — @{username}\n"
    await update.message.reply_text(text)

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
        await update.message.reply_text("❌ Нет прав на повышение."); return
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
        c.execute("UPDATE clan_members SET rank='capo' WHERE clan_id=? AND rank='underboss'", (clan_id,))

    c.execute("UPDATE clan_members SET rank=? WHERE user_id=? AND clan_id=?",
              (next_rank, target_id, clan_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"⬆️ @{target_username} повышен до {get_rank_label(next_rank)}!")
    try:
        await ctx.bot.send_message(target_id, f"🎉 Тебя повысили до {get_rank_label(next_rank)}!")
    except: pass

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
        await update.message.reply_text("❌ Нет прав."); return
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
        await update.message.reply_text("Нельзя выгнать Крёстного отца!"); return

    c.execute("DELETE FROM clan_members WHERE user_id=? AND clan_id=?", (target_id, clan_id))
    c.execute("UPDATE players SET clan_id=NULL WHERE user_id=?", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🚪 @{target_username} выгнан из клана.")
    try:
        await ctx.bot.send_message(target_id, "😔 Тебя выгнали из клана.")
    except: pass

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
    treasury_text = f"\n💰 Казна: {clan[4]} монет" if has_permission(user_id, clan_id, "view_treasury") else ""

    await update.message.reply_text(
        f"🏛 Клан «{clan[1]}»\n"
        f"💪 Мощь: {clan[3]}\n"
        f"👥 Участников: {count}"
        f"{treasury_text}\n"
        f"🏅 Твоё звание: {get_rank_label(rank)}"
    )

async def top_clans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name, power FROM clans ORDER BY power DESC LIMIT 10")
    clans = c.fetchall()
    conn.close()
    if not clans:
        await update.message.reply_text("Кланов пока нет."); return

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 Топ кланов:\n\n"
    for i, (name, power) in enumerate(clans):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} «{name}» — мощь: {power}\n"
    await update.message.reply_text(text)

async def announce(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Нет доступа."); return
    if not ctx.args:
        await update.message.reply_text("Укажи текст: /announce <текст>"); return

    text = " ".join(ctx.args)
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO announcements (text, created_at, author_id) VALUES (?, ?, ?)",
              (text, datetime.datetime.now().isoformat(), user_id))
    c.execute("SELECT user_id FROM players")
    all_players = c.fetchall()
    conn.commit()
    conn.close()

    sent = 0
    for (pid,) in all_players:
        try:
            await ctx.bot.send_message(pid, f"📢 Объявление:\n\n{text}")
            sent += 1
        except: pass
    await update.message.reply_text(f"✅ Отправлено {sent} игрокам!")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("create_clan", create_clan))
    app.add_handler(CommandHandler("request_join", request_join))
    app.add_handler(CommandHandler("requests", view_requests))
    app.add_handler(CommandHandler("members", members))
    app.add_handler(CommandHandler("promote", promote))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("clan_info", clan_info))
    app.add_handler(CommandHandler("top", top_clans))
    app.add_handler(CommandHandler("announce", announce))
    app.add_handler(CallbackQueryHandler(handle_request, pattern="^(accept|decline)_"))
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()