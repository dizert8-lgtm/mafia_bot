"""
Картинки для каждого действия бота.
Фото в стиле мафия/нуар.

Распределение по событиям:
1  (мафиози с пистолетом ночью)  → start, help
2  (расстрел в лесу)             → war, conflict
3  (встреча боссов у машин)      → create_clan, truce
4  (совещание за столом)         → clan_info, members
5  (допрос у машин)              → kick, request
6  (Peaky Blinders улица)        → conflicts, stat
7  (босс за столом с охраной)    → profile, promote
8  (перестрелка в баре)          → attack, war
9  (тёмный зал заседаний)        → top, announce
10 (казино с игроками)           → top, business
11 (зал казино)                  → stat, treasury
12 (вокзал перестрелка)          → war, attack
"""

IMAGES = {
    # Главный экран — мафиози с пистолетом ночью
    "start":        "https://i.imgur.com/8JQaoMg.jpeg",

    # Профиль — босс за столом с охраной
    "profile":      "https://i.imgur.com/AI78sgH.jpeg",

    # Создание клана — встреча боссов у машин
    "create_clan":  "https://i.imgur.com/fROXbOL.jpeg",

    # Информация о клане — совещание за столом
    "clan_info":    "https://i.imgur.com/ciGcwbb.jpeg",

    # Состав клана — совещание за столом
    "members":      "https://i.imgur.com/ciGcwbb.jpeg",

    # Топ кланов — тёмный зал заседаний
    "top":          "https://i.imgur.com/a61q4yM.jpeg",

    # Статистика — Peaky Blinders улица
    "stat":         "https://i.imgur.com/tOj0tKV.jpeg",

    # Война — расстрел в лесу
    "war":          "https://i.imgur.com/RtDvNgq.jpeg",

    # Атака — перестрелка в баре
    "attack":       "https://i.imgur.com/WB90XC8.jpeg",

    # Победа — казино с игроками
    "win":          "https://i.imgur.com/goljFZW.jpeg",

    # Поражение — вокзал перестрелка
    "lose":         "https://i.imgur.com/I5tYAjH.jpeg",

    # Вступление — допрос у машин
    "join":         "https://i.imgur.com/s8XKzB9.jpeg",

    # Заявка — допрос у машин
    "request":      "https://i.imgur.com/s8XKzB9.jpeg",

    # Повышение — босс за столом
    "promote":      "https://i.imgur.com/AI78sgH.jpeg",

    # Исключение — расстрел в лесу
    "kick":         "https://i.imgur.com/RtDvNgq.jpeg",

    # Объявление — тёмный зал заседаний
    "announce":     "https://i.imgur.com/a61q4yM.jpeg",

    # Конфликт — Peaky Blinders улица
    "conflict":     "https://i.imgur.com/tOj0tKV.jpeg",

    # Помощь — мафиози с пистолетом
    "help":         "https://i.imgur.com/8JQaoMg.jpeg",

    # Казино/бизнес
    "business":     "https://i.imgur.com/4gH6MSI.jpeg",
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