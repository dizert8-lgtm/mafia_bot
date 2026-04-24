"""
Картинки для каждого действия бота.
Все фото в стиле нуар/мафия с Unsplash и других бесплатных сервисов.
"""

IMAGES = {
    # Главный экран
    "start":        "https://images.unsplash.com/photo-1509822929464-92b183d4fe93?w=800&q=80",
    # Досье / профиль
    "profile":      "https://images.unsplash.com/photo-1521587760476-6c12a4b040da?w=800&q=80",
    # Создание клана
    "create_clan":  "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&q=80",
    # Информация о клане
    "clan_info":    "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=800&q=80",
    # Состав клана
    "members":      "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=800&q=80",
    # Топ кланов
    "top":          "https://images.unsplash.com/photo-1565728744382-61accd4aa148?w=800&q=80",
    # Статистика
    "stat":         "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=800&q=80",
    # Война объявлена
    "war":          "https://images.unsplash.com/photo-1509822929464-92b183d4fe93?w=800&q=80",
    # Победа в войне
    "win":          "https://images.unsplash.com/photo-1533227268428-f9ed0900fb3b?w=800&q=80",
    # Поражение
    "lose":         "https://images.unsplash.com/photo-1516274626895-055a99214f08?w=800&q=80",
    # Вступление в клан
    "join":         "https://images.unsplash.com/photo-1521737852567-6949f3f9f2b5?w=800&q=80",
    # Повышение звания
    "promote":      "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=800&q=80",
    # Исключение
    "kick":         "https://images.unsplash.com/photo-1516534775068-ba3e7458af70?w=800&q=80",
    # Объявление
    "announce":     "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&q=80",
    # Конфликт
    "conflict":     "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800&q=80",
    # Заявка
    "request":      "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=800&q=80",
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
        # Если фото не загрузилось — отправляем текст
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception:
            pass
