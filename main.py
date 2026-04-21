from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from database import init_db, get_conn
import datetime

TOKEN = "8774923034:AAExqkuYW1NV7wIbzmR04eKye6KS_0AitbU"  # <-- вставь свой токен сюда

# ══════════════════════════════════════════
#  /start — регистрация
# ══════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO players (user_id, username) VALUES (?, ?)",
              (user.id, user.username or user.first_name))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🎭 Добро пожаловать в мир мафии, {user.first_name}!\n\n"
        "📋 Команды:\n"
        "/profile — твой профиль\n"
        "/create_clan — создать клан\n"
        "/join_clan — вступить в клан\n"
        "/clan_info — информация о клане\n"
        "/top — топ кланов"
    )

# ══════════════════════════════════════════
#  /profile — профиль игрока
# ══════════════════════════════════════════
async def profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player:
        await update.message.reply_text("Сначала напиши /start")
        return

    uid, username, clan_id, strength, coins, level, exp = player

    clan_text = "Без клана"
    if clan_id:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT name FROM clans WHERE id=?", (clan_id,))
        clan = c.fetchone()
        conn.close()
        if clan:
            clan_text = f"🏛 {clan[0]}"

    await update.message.reply_text(
        f"👤 Профиль: {username}\n"
        f"⭐ Уровень: {level}\n"
        f"📊 Опыт: {exp}\n"
        f"⚔️ Сила: {strength}\n"
        f"💰 Монеты: {coins}\n"
        f"🏛 Клан: {clan_text}"
    )

# ══════════════════════════════════════════
#  /create_clan — создать клан
# ══════════════════════════════════════════
async def create_clan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player:
        await update.message.reply_text("Сначала напиши /start")
        return

    if player[2]:
        await update.message.reply_text("Ты уже в клане! Сначала выйди из него.")
        return

    if player[4] < 300:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\n"
            f"Нужно: 300 монет\n"
            f"У тебя: {player[4]} монет"
        )
        return

    if not ctx.args:
        await update.message.reply_text(
            "Укажи название клана:\n"
            "/create_clan <название>\n\n"
            "Пример: /create_clan Черная роза"
        )
        return

    name = " ".join(ctx.args)

    if len(name) < 3:
        await update.message.reply_text("Название слишком короткое (минимум 3 символа)")
        return

    if len(name) > 30:
        await update.message.reply_text("Название слишком длинное (максимум 30 символов)")
        return

    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO clans (name, owner_id, created_at) VALUES (?, ?, ?)",
            (name, user_id, datetime.datetime.now().isoformat())
        )
        clan_id = c.lastrowid
        c.execute(
            "UPDATE players SET clan_id=?, coins=coins-300 WHERE user_id=?",
            (clan_id, user_id)
        )
        conn.commit()
        await update.message.reply_text(
            f"🏛 Клан «{name}» создан!\n\n"
            f"👑 Ты — Босс клана\n"
            f"💰 Списано 300 монет за создание\n\n"
            f"Пригласи друзей командой /join_clan {name}"
        )
    except Exception:
        await update.message.reply_text("❌ Клан с таким названием уже существует!")
    finally:
        conn.close()

# ══════════════════════════════════════════
#  /join_clan — вступить в клан
# ══════════════════════════════════════════
async def join_clan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()

    if not player:
        await update.message.reply_text("Сначала напиши /start")
        return

    if player[2]:
        await update.message.reply_text("Ты уже в клане!")
        return

    if not ctx.args:
        await update.message.reply_text(
            "Укажи название клана:\n"
            "/join_clan <название>\n\n"
            "Пример: /join_clan Черная роза"
        )
        return

    name = " ".join(ctx.args)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM clans WHERE name=?", (name,))
    clan = c.fetchone()

    if not clan:
        conn.close()
        await update.message.reply_text(f"❌ Клан «{name}» не найден.")
        return

    c.execute("UPDATE players SET clan_id=? WHERE user_id=?", (clan[0], user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Ты вступил в клан «{clan[1]}»!\n"
        f"💪 Мощь клана: {clan[3]}\n"
        f"💰 Казна: {clan[4]} монет"
    )

# ══════════════════════════════════════════
#  /clan_info — информация о клане
# ══════════════════════════════════════════
async def clan_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT clan_id FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()

    if not player or not player[0]:
        conn.close()
        await update.message.reply_text("Ты не в клане. Создай: /create_clan или вступи: /join_clan")
        return

    clan_id = player[0]
    c.execute("SELECT * FROM clans WHERE id=?", (clan_id,))
    clan = c.fetchone()
    c.execute("SELECT username FROM players WHERE clan_id=?", (clan_id,))
    members = c.fetchall()
    conn.close()

    members_text = "\n".join([f"  • {m[0]}" for m in members]) or "  • никого"

    await update.message.reply_text(
        f"🏛 Клан «{clan[1]}»\n\n"
        f"💪 Мощь: {clan[3]}\n"
        f"💰 Казна: {clan[4]} монет\n"
        f"👥 Участники ({len(members)}):\n{members_text}"
    )

# ══════════════════════════════════════════
#  /top — топ кланов
# ══════════════════════════════════════════
async def top_clans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name, power, treasury FROM clans ORDER BY power DESC LIMIT 10")
    clans = c.fetchall()
    conn.close()

    if not clans:
        await update.message.reply_text("Кланов пока нет. Создай первый: /create_clan")
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 Топ кланов:\n\n"
    for i, (name, power, treasury) in enumerate(clans):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} «{name}» — мощь: {power}\n"

    await update.message.reply_text(text)

# ══════════════════════════════════════════
#  Запуск
# ══════════════════════════════════════════
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("create_clan", create_clan))
    app.add_handler(CommandHandler("join_clan", join_clan))
    app.add_handler(CommandHandler("clan_info", clan_info))
    app.add_handler(CommandHandler("top", top_clans))

    print("✅ Бот запущен! Нажми Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()