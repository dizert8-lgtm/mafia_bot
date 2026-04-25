"""
Картинки для каждого действия бота (ibb.co).

1  мафиози с пистолетом ночью   → start, help
2  расстрел в лесу               → war, kick
3  встреча боссов у машин        → create_clan
4  совещание за столом           → clan_info, members
5  допрос у машин                → request, join
6  Peaky Blinders улица          → conflict, stat
7  босс за столом с охраной      → profile, promote
8  перестрелка в баре            → attack
9  тёмный зал заседаний          → top, announce
10 казино с игроками             → win, business
11 зал казино                    → treasury
12 вокзал перестрелка            → lose
"""

IMAGES = {
    "start":        "https://i.ibb.co/mVsP7dt7/photo-2026-04-24-22-32-14.jpg",
    "help":         "https://i.ibb.co/mVsP7dt7/photo-2026-04-24-22-32-14.jpg",
    "war":          "https://i.ibb.co/nqCx6wZh/photo-2026-04-24-22-32-29.jpg",
    "kick":         "https://i.ibb.co/nqCx6wZh/photo-2026-04-24-22-32-29.jpg",
    "create_clan":  "https://i.ibb.co/4n9mG14q/photo-2026-04-24-22-32-32.jpg",
    "clan_info":    "https://i.ibb.co/kgnygtHf/photo-2026-04-24-22-32-36.jpg",
    "members":      "https://i.ibb.co/kgnygtHf/photo-2026-04-24-22-32-36.jpg",
    "request":      "https://i.ibb.co/bg19pRLf/photo-2026-04-24-22-32-39.jpg",
    "join":         "https://i.ibb.co/bg19pRLf/photo-2026-04-24-22-32-39.jpg",
    "conflict":     "https://i.ibb.co/7NC0tRtL/photo-2026-04-24-22-32-42.jpg",
    "stat":         "https://i.ibb.co/7NC0tRtL/photo-2026-04-24-22-32-42.jpg",
    "profile":      "https://i.ibb.co/Jw5PjVds/photo-2026-04-24-22-32-45.jpg",
    "promote":      "https://i.ibb.co/Jw5PjVds/photo-2026-04-24-22-32-45.jpg",
    "attack":       "https://i.ibb.co/JwYsKh2B/photo-2026-04-24-22-32-49.jpg",
    "top":          "https://i.ibb.co/SDhCgghJ/photo-2026-04-24-22-32-52.jpg",
    "announce":     "https://i.ibb.co/SDhCgghJ/photo-2026-04-24-22-32-52.jpg",
    "win":          "https://i.ibb.co/ZzvnYmrW/photo-2026-04-24-22-32-55.jpg",
    "business":     "https://i.ibb.co/ZzvnYmrW/photo-2026-04-24-22-32-55.jpg",
    "treasury":     "https://i.ibb.co/zhFQTcVp/photo-2026-04-24-22-33-00.jpg",
    "conflicts":    "https://i.ibb.co/7NC0tRtL/photo-2026-04-24-22-32-42.jpg",
    "lose":         "https://i.ibb.co/s9FytjLM/photo-2026-04-24-22-33-03.jpg",
}

async def send_photo_message(bot, chat_id: int, image_key: str, text: str, reply_markup=None):
    """
    Отправляет сообщение с фото и подписью.
    Если фото недоступно — отправляет просто текст.
    """
    url = IMAGES.get(image_key)
    try:
        if url:
            await bot.send_photo(
                chat_id=chat_id,
                photo=url,
                caption=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
    except Exception:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception:
            pass