"""
Магазин мафии:
/mf_shop      — главное меню магазина
/mf_inventory — коллекция игрока
"""

import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from database import get_conn
from images import send_photo_message

def init_shop_tables():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS inventory (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        item_id   TEXT,
        bought_at TEXT,
        UNIQUE(user_id, item_id)
    )""")
    conn.commit()
    conn.close()

WEAPONS = [
    {"id":"w1",  "name":"Кастет",               "price":500,      "desc":"Простое оружие ближнего боя. Первый шаг в мире насилия.",          "photo":"https://i.ibb.co/XH57xfh/photo-2-2026-05-14-20-24-58.jpg"},
    {"id":"w2",  "name":"Складной нож",          "price":1000,     "desc":"Тихое и надёжное оружие. Всегда при себе.",                       "photo":"https://i.ibb.co/xqT6zBfF/photo-14-2026-05-14-20-24-58.jpg"},
    {"id":"w3",  "name":"Стилет",                "price":2000,     "desc":"Элегантный итальянский кинжал. Оружие настоящего мафиози.",       "photo":"https://i.ibb.co/mV162VNB/photo-3-2026-05-14-20-24-58.jpg"},
    {"id":"w4",  "name":"Наган",                 "price":3500,     "desc":"Классический револьвер. Проверен десятилетиями.",                 "photo":"https://i.ibb.co/5gRgH8yy/photo-1-2026-05-14-20-24-58.jpg"},
    {"id":"w5",  "name":"Beretta 92",            "price":5000,     "desc":"Итальянский пистолет. Любимое оружие боссов.",                   "photo":"https://i.ibb.co/ymmtg9sG/photo-12-2026-05-14-20-24-58.jpg"},
    {"id":"w6",  "name":"Colt 1911",             "price":8000,     "desc":"Легендарный американский пистолет. Символ эпохи.",               "photo":"https://i.ibb.co/twQWCPDK/photo-10-2026-05-14-20-24-58.jpg"},
    {"id":"w7",  "name":"Desert Eagle",          "price":12000,    "desc":"Мощь в каждом выстреле. Оружие для серьёзных людей.",            "photo":"https://i.ibb.co/VYhQFfC2/photo-5-2026-05-14-20-24-58.jpg"},
    {"id":"w8",  "name":"Дробовик",              "price":18000,    "desc":"Незаменим при разборках. Один выстрел — один разговор.",         "photo":"https://i.ibb.co/PzmrLTp3/photo-9-2026-05-14-20-24-58.jpg"},
    {"id":"w9",  "name":"Узи",                   "price":25000,    "desc":"Израильский пистолет-пулемёт. Скорострельный и смертоносный.",   "photo":"https://i.ibb.co/gCJ9t3n/photo-8-2026-05-14-20-24-58.jpg"},
    {"id":"w10", "name":"Thompson M1",           "price":35000,    "desc":"Tommy Gun. Оружие чикагской мафии 1920-х.",                     "photo":"https://i.ibb.co/xktZ1K1/photo-6-2026-05-14-20-24-58.jpg"},
    {"id":"w11", "name":"AK-47",                 "price":50000,    "desc":"Самый известный автомат в мире. Надёжен в любых условиях.",     "photo":"https://i.ibb.co/fGyfB53G/photo-15-2026-05-14-20-24-58.jpg"},
    {"id":"w12", "name":"Снайперская винтовка",  "price":75000,    "desc":"Работа на расстоянии. Чисто. Тихо. Профессионально.",           "photo":"https://i.ibb.co/MkjrYw5R/photo-11-2026-05-14-20-24-58.jpg"},
    {"id":"w13", "name":"Золотой пистолет",      "price":100000,   "desc":"Позолоченный ручной работы. Статус и смерть в одном.",          "photo":"https://i.ibb.co/5gFnhG8d/photo-4-2026-05-14-20-24-58.jpg"},
    {"id":"w14", "name":"Коллекционный Luger",   "price":150000,   "desc":"Редкий немецкий пистолет. Музейная ценность в руках босса.",    "photo":"https://i.ibb.co/Gv5fwJ5d/photo-7-2026-05-14-20-24-58.jpg"},
    {"id":"w15", "name":"Алмазный Desert Eagle", "price":250000,   "desc":"Инкрустирован бриллиантами. Единственный в мире.",             "photo":"https://i.ibb.co/hJr4VtKm/photo-13-2026-05-14-20-24-58.jpg"},
]

CARS = [
    {"id":"c1",  "name":"Ford Model A",          "price":1000,     "desc":"Старенький Форд. Скромно, но надёжно.",                         "photo":"https://i.ibb.co/mVydtx97/photo-2026-05-14-20-49-07.jpg"},
    {"id":"c2",  "name":"Chevrolet 1948",         "price":3000,     "desc":"Классика американского автопрома. Широкая и солидная.",         "photo":"https://i.ibb.co/1Dkw6wv/photo-2026-05-14-20-49-13.jpg"},
    {"id":"c3",  "name":"Cadillac Series 62",     "price":7000,     "desc":"Кадиллак — автомобиль боссов. Плавный и мощный.",              "photo":"https://i.ibb.co/LHPF6Gn/photo-2026-05-14-20-49-16.jpg"},
    {"id":"c4",  "name":"Lincoln Continental",    "price":15000,    "desc":"Президентский автомобиль. Роскошь и сила.",                    "photo":"https://i.ibb.co/Q7VPHp5Z/photo-2026-05-14-20-49-20.jpg"},
    {"id":"c5",  "name":"Buick Roadmaster",       "price":25000,    "desc":"Дорожный мастер. Едет быстро, выглядит богато.",               "photo":"https://i.ibb.co/PZWhnyyn/photo-2026-05-14-20-49-23.jpg"},
    {"id":"c6",  "name":"Chrysler Imperial",      "price":40000,    "desc":"Имперский Крайслер. Настоящий американский монстр.",           "photo":"https://i.ibb.co/WW9jRgH8/photo-2026-05-14-20-49-28.jpg"},
    {"id":"c7",  "name":"Mercedes 600",           "price":60000,    "desc":"Автомобиль диктаторов и боссов. Немецкое совершенство.",       "photo":"https://i.ibb.co/s9KtYF1m/photo-2026-05-14-20-49-32.jpg"},
    {"id":"c8",  "name":"Rolls-Royce Silver",     "price":85000,    "desc":"Серебряный Роллс. Едет бесшумно как смерть.",                  "photo":"https://i.ibb.co/Df3P3qXn/photo-2026-05-14-20-49-35.jpg"},
    {"id":"c9",  "name":"Bentley Mulsanne",       "price":120000,   "desc":"Британская роскошь. Кожа, дерево, золото.",                   "photo":"https://i.ibb.co/jZ84H87H/photo-2026-05-14-20-49-38.jpg"},
    {"id":"c10", "name":"Ferrari 250 GTO",        "price":175000,   "desc":"Красный Ferrari. Самый желанный автомобиль в мире.",           "photo":"https://i.ibb.co/XfK3gTXY/photo-2026-05-14-20-49-41.jpg"},
    {"id":"c11", "name":"Lamborghini Miura",      "price":230000,   "desc":"Итальянский зверь. Быстрый как пуля.",                        "photo":"https://i.ibb.co/tP2g55PN/photo-2026-05-14-20-49-45.jpg"},
    {"id":"c12", "name":"Maybach 62",             "price":300000,   "desc":"Мобильный офис босса. Броня, бар и телефон.",                  "photo":"https://i.ibb.co/mw7yVYm/photo-2026-05-14-20-49-49.jpg"},
    {"id":"c13", "name":"Rolls-Royce Phantom",    "price":400000,   "desc":"Фантом. Призрак дороги. Лучший автомобиль в мире.",            "photo":"https://i.ibb.co/MD6RXv6f/photo-2026-05-14-20-49-52.jpg"},
    {"id":"c14", "name":"Золотой Rolls-Royce",    "price":1000000,  "desc":"Покрыт золотом 24 карата. Один в мире.",                      "photo":"https://i.ibb.co/B5g5cvtg/photo-2026-05-14-20-49-54.jpg"},
]

WATCHES = [
    {"id":"wt1",  "name":"Советские часы",        "price":500,      "desc":"Простые и надёжные. Показывают только время.",                 "photo":"https://i.ibb.co/vvK8s2VM/photo-2026-05-14-19-52-20.jpg"},
    {"id":"wt2",  "name":"Seiko классика",         "price":2000,     "desc":"Японская точность. Скромно и достойно.",                      "photo":"https://i.ibb.co/39WKTHZZ/photo-2026-05-14-19-52-44.jpg"},
    {"id":"wt3",  "name":"Tissot",                 "price":5000,     "desc":"Швейцарское качество по доступной цене.",                     "photo":"https://i.ibb.co/nq29QMDK/photo-2026-05-14-19-52-48.jpg"},
    {"id":"wt4",  "name":"TAG Heuer",              "price":10000,    "desc":"Часы гонщиков и победителей.",                               "photo":"https://i.ibb.co/NXffCWt/photo-2026-05-14-19-52-51.jpg"},
    {"id":"wt5",  "name":"Omega Seamaster",        "price":20000,    "desc":"Часы Джеймса Бонда. Стиль и функциональность.",              "photo":"https://i.ibb.co/DPR9wvD1/photo-2026-05-14-19-52-56.jpg"},
    {"id":"wt6",  "name":"Rolex Submariner",       "price":35000,    "desc":"Подводные Ролекс. Символ успеха.",                           "photo":"https://i.ibb.co/b52rG2M3/photo-2026-05-14-19-52-59.jpg"},
    {"id":"wt7",  "name":"Rolex Daytona",          "price":55000,    "desc":"Дейтона. Самые желанные часы в мире.",                       "photo":"https://i.ibb.co/Nn9ycN0k/photo-2026-05-14-19-53-04.jpg"},
    {"id":"wt8",  "name":"Audemars Piguet",        "price":80000,    "desc":"Часы для тех кто разбирается. Редкость и класс.",            "photo":"https://i.ibb.co/8448YYC9/photo-2026-05-14-19-53-08.jpg"},
    {"id":"wt9",  "name":"Patek Philippe",         "price":120000,   "desc":"Ты не владеешь Патеком — ты хранишь его для следующего поколения.", "photo":"https://i.ibb.co/1YLLR9JT/photo-2026-05-14-19-53-13.jpg"},
    {"id":"wt10", "name":"Vacheron Constantin",    "price":180000,   "desc":"Старейшая часовая мануфактура. Безупречное мастерство.",     "photo":"https://i.ibb.co/d4kNVFsG/photo-2026-05-14-19-53-21.jpg"},
    {"id":"wt11", "name":"A. Lange & Söhne",       "price":250000,   "desc":"Немецкая точность до микрона. Часы перфекциониста.",         "photo":"https://i.ibb.co/qYr70QXc/photo-2026-05-14-19-53-27.jpg"},
    {"id":"wt12", "name":"Richard Mille",          "price":350000,   "desc":"Формула 1 на запястье. Для тех кто живёт на скорости.",      "photo":"https://i.ibb.co/yr1Y1M3/photo-2026-05-14-19-53-30.jpg"},
    {"id":"wt13", "name":"Золотой Rolex",          "price":500000,   "desc":"Ролекс из чистого золота. Тяжёлый как власть.",             "photo":"https://i.ibb.co/r2sp1hc1/photo-2026-05-14-19-53-32.jpg"},
    {"id":"wt14", "name":"Patek с бриллиантами",   "price":750000,   "desc":"Усыпан бриллиантами. Носить страшно — не носить невозможно.", "photo":"https://i.ibb.co/whYYdXbS/photo-2026-05-14-19-53-36.jpg"},
    {"id":"wt15", "name":"Алмазные часы",          "price":1500000,  "desc":"Корпус полностью из алмазов. Единственные в мире.",         "photo":"https://i.ibb.co/YBH5BrGM/photo-2026-05-14-19-53-40.jpg"},
]

HOUSES = [
    {"id":"h1",  "name":"Комната в трущобах",     "price":2000,     "desc":"Начало пути. Крыша над головой — уже что-то.",               "photo":"https://i.ibb.co/K4bFLr7/aiease-1778257860668.jpg"},
    {"id":"h2",  "name":"Квартира",               "price":8000,     "desc":"Своя квартира. Маленькая, но своя.",                         "photo":"https://i.ibb.co/0RymjWQs/aiease-1778257944560.jpg"},
    {"id":"h3",  "name":"Таунхаус",               "price":20000,    "desc":"Городской дом. Соседи сверху больше не топают.",              "photo":"https://i.ibb.co/Q3znTk3w/aiease-1778257985602.jpg"},
    {"id":"h4",  "name":"Пентхаус",               "price":45000,    "desc":"Верхний этаж небоскрёба. Весь город у твоих ног.",           "photo":"https://i.ibb.co/RpgVZkwm/aiease-1778258035683.jpg"},
    {"id":"h5",  "name":"Загородный дом",         "price":80000,    "desc":"Тихое место за городом. Бассейн и охрана по периметру.",     "photo":"https://i.ibb.co/4ZSHm4JV/aiease-1778258080816.jpg"},
    {"id":"h6",  "name":"Особняк",                "price":150000,   "desc":"Настоящий особняк. 20 комнат, парк, гараж на 10 машин.",     "photo":"https://i.ibb.co/CpyGzCr0/aiease-1778258789370.jpg"},
    {"id":"h7",  "name":"Особняк с бассейном",    "price":250000,   "desc":"Олимпийский бассейн и вертолётная площадка.",                "photo":"https://i.ibb.co/GQFBTTQk/aiease-1778258889406.jpg"},
    {"id":"h8",  "name":"Вилла в Италии",         "price":400000,   "desc":"Тоскана. Виноградники, оливки и закаты над морем.",          "photo":"https://i.ibb.co/r2hHRBJH/aiease-1778259299706.jpg"},
    {"id":"h9",  "name":"Замок в Европе",         "price":600000,   "desc":"Средневековый замок. Толстые стены, глубокий ров.",          "photo":"https://i.ibb.co/1tNPp8Tn/aiease-1778259754726.jpg"},
    {"id":"h10", "name":"Остров",                 "price":900000,   "desc":"Частный остров в тёплом море. Никаких соседей.",             "photo":"https://i.ibb.co/793v26H/aiease-1778260395968.jpg"},
    {"id":"h11", "name":"Дворец",                 "price":1500000,  "desc":"Настоящий дворец. 100 комнат, 500 слуг.",                    "photo":"https://i.ibb.co/gM5bt93Z/aiease-1778260465327.jpg"},
    {"id":"h12", "name":"Небоскрёб",              "price":2500000,  "desc":"Твоё имя на каждом этаже. Весь город знает кто ты.",         "photo":"https://i.ibb.co/hR3p1r9d/aiease-1778260510568.jpg"},
    {"id":"h13", "name":"Казино",                 "price":4000000,  "desc":"Собственное казино. Деньги текут рекой круглосуточно.",      "photo":"https://i.ibb.co/F4Ny4Ks1/aiease-1778260557595.jpg"},
    {"id":"h14", "name":"Целый город",            "price":7500000,  "desc":"Ты не живёшь в городе — ты и есть этот город.",             "photo":"https://i.ibb.co/SX5ry9C1/Gemini-Generated-Image-u8ptb5u8ptb5u8pt.png"},
    {"id":"h15", "name":"Страна",                 "price":15000000, "desc":"Высшая форма власти. Твои законы. Твоя территория.",         "photo":"https://i.ibb.co/CKgJ4cn9/Gemini-Generated-Image-js2wpgjs2wpgjs2w.png"},
]

CATEGORIES = {
    "weapons": {"name":"Оружие",       "items":WEAPONS},
    "cars":    {"name":"Машины",       "items":CARS},
    "watches": {"name":"Часы",         "items":WATCHES},
    "houses":  {"name":"Недвижимость", "items":HOUSES},
}

ALL_ITEMS = {item["id"]: item for cat in CATEGORIES.values() for item in cat["items"]}

def get_owned_items(user_id: int) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT item_id FROM inventory WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def owns_item(user_id: int, item_id: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM inventory WHERE user_id=? AND item_id=?", (user_id, item_id))
    row = c.fetchone()
    conn.close()
    return row is not None

def get_inventory_text(user_id: int) -> str:
    """Краткая строка коллекции для профиля."""
    owned = get_owned_items(user_id)
    if not owned:
        return ""
    total = sum(ALL_ITEMS[i]["price"] for i in owned if i in ALL_ITEMS)

    w  = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("w") and not i.startswith("wt")]
    c  = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("c")]
    wt = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("wt")]
    h  = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("h")]

    text = f"\n\n<b>[ Коллекция — {len(owned)} пред. | {total:,} монет ]</b>\n"
    if w:  text += f"➢  <b>Оружие:</b>  {w[-1]}\n"        # показываем последнее (самое дорогое)
    if c:  text += f"➢  <b>Машина:</b>  {c[-1]}\n"
    if wt: text += f"➢  <b>Часы:</b>    {wt[-1]}\n"
    if h:  text += f"➢  <b>Дом:</b>     {h[-1]}\n"
    text += f"<i>Полный список: /mf_inventory</i>"
    return text

async def shop_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT coins FROM players WHERE user_id=?", (user_id,))
    player = c.fetchone()
    conn.close()
    if not player:
        await update.message.reply_text("Напиши /mf_start"); return

    owned = get_owned_items(user_id)
    coins = player[0]

    keyboard = [[
        InlineKeyboardButton("➢ Оружие",       callback_data="shop_cat_weapons"),
        InlineKeyboardButton("➢ Машины",        callback_data="shop_cat_cars"),
    ],[
        InlineKeyboardButton("➢ Часы",          callback_data="shop_cat_watches"),
        InlineKeyboardButton("➢ Недвижимость",  callback_data="shop_cat_houses"),
    ],[
        InlineKeyboardButton("➢ Моя коллекция", callback_data="shop_inventory"),
    ]]

    text = (
        f"<b>[ Магазин семьи ]</b>\n"
        f"{'─' * 22}\n\n"
        f"➢  Монеты:    <b>{coins:,}</b>\n"
        f"➢  Предметов: <b>{len(owned)}</b>\n\n"
        f"<i>Выбери категорию:</i>"
    )
    await ctx.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo="https://i.ibb.co/Jw5PjVds/photo-2026-04-24-22-32-45.jpg",
        caption=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def _show_category(query, user_id: int, cat_key: str, page: int = 0):
    cat      = CATEGORIES[cat_key]
    items    = cat["items"]
    owned    = get_owned_items(user_id)
    per_page = 5
    total_pages = (len(items) + per_page - 1) // per_page
    start    = page * per_page
    end      = min(start + per_page, len(items))

    rows = []
    for item in items[start:end]:
        is_owned = item["id"] in owned
        label    = f"✓ {item['name']}" if is_owned else f"➢ {item['name']} — {item['price']:,}"
        rows.append([InlineKeyboardButton(label, callback_data=f"shop_item_{item['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Назад", callback_data=f"shop_page_{cat_key}_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Вперёд ▶", callback_data=f"shop_page_{cat_key}_{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("↩ В магазин", callback_data="shop_back")])

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT coins FROM players WHERE user_id=?", (user_id,))
    coins = c.fetchone()[0]
    conn.close()

    text = (
        f"<b>[ {cat['name']} ]</b>\n"
        f"{'─' * 22}\n\n"
        f"➢  Монеты: <b>{coins:,}</b>\n"
        f"➢  Стр. {page+1}/{total_pages}\n\n"
        f"<i>Выбери предмет:</i>"
    )
    try:
        await query.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
    except: pass

async def _show_item(query, user_id: int, item_id: str):
    item = ALL_ITEMS.get(item_id)
    if not item:
        await query.answer("Предмет не найден.", show_alert=True); return

    is_owned = owns_item(user_id, item_id)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT coins FROM players WHERE user_id=?", (user_id,))
    coins = c.fetchone()[0]
    conn.close()

    cat_key = "weapons"
    page    = 0
    for ck, cat in CATEGORIES.items():
        ids = [i["id"] for i in cat["items"]]
        if item_id in ids:
            cat_key = ck
            page    = ids.index(item_id) // 5
            break

    if is_owned:
        buy_btn = InlineKeyboardButton("✓ Уже куплено", callback_data="shop_owned")
    elif coins >= item["price"]:
        buy_btn = InlineKeyboardButton(f"➢ Купить — {item['price']:,}", callback_data=f"shop_buy_{item_id}")
    else:
        buy_btn = InlineKeyboardButton("❌ Мало монет", callback_data="shop_no_money")

    keyboard = [[buy_btn], [InlineKeyboardButton("↩ Назад", callback_data=f"shop_page_{cat_key}_{page}")]]
    status   = "✓ В коллекции" if is_owned else f"➢ Цена: {item['price']:,} монет"
    text = (
        f"<b>{item['name']}</b>\n"
        f"{'─' * 22}\n\n"
        f"{item['desc']}\n\n"
        f"{status}\n"
        f"➢ Твои монеты: <b>{coins:,}</b>"
    )
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(media=item["photo"], caption=text, parse_mode="HTML"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        try:
            await query.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except: pass

async def _show_inventory_inline(query, user_id: int):
    owned    = get_owned_items(user_id)
    keyboard = [[InlineKeyboardButton("↩ В магазин", callback_data="shop_back")]]

    if not owned:
        try:
            await query.edit_message_caption(
                caption="<b>[ Коллекция пуста ]</b>\n\nНачни покупать в /mf_shop",
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except: pass
        return

    w  = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("w") and not i.startswith("wt")]
    c  = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("c")]
    wt = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("wt")]
    h  = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("h")]
    total = sum(ALL_ITEMS[i]["price"] for i in owned if i in ALL_ITEMS)

    text = f"<b>[ Коллекция ]</b>\n{'─'*22}\n\n➢ <b>{len(owned)}</b> предм. | <b>{total:,}</b> монет\n\n"
    if w:  text += "<b>Оружие:</b>\n"       + "".join(f"  ➢ {n}\n" for n in w)  + "\n"
    if c:  text += "<b>Машины:</b>\n"       + "".join(f"  ➢ {n}\n" for n in c)  + "\n"
    if wt: text += "<b>Часы:</b>\n"         + "".join(f"  ➢ {n}\n" for n in wt) + "\n"
    if h:  text += "<b>Недвижимость:</b>\n" + "".join(f"  ➢ {n}\n" for n in h)

    try:
        await query.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except: pass

async def shop_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data    = query.data

    if data == "shop_back":
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT coins FROM players WHERE user_id=?", (user_id,))
        player = c.fetchone()
        conn.close()
        owned  = get_owned_items(user_id)
        coins  = player[0] if player else 0
        keyboard = [[
            InlineKeyboardButton("➢ Оружие",       callback_data="shop_cat_weapons"),
            InlineKeyboardButton("➢ Машины",        callback_data="shop_cat_cars"),
        ],[
            InlineKeyboardButton("➢ Часы",          callback_data="shop_cat_watches"),
            InlineKeyboardButton("➢ Недвижимость",  callback_data="shop_cat_houses"),
        ],[
            InlineKeyboardButton("➢ Моя коллекция", callback_data="shop_inventory"),
        ]]
        try:
            await query.edit_message_caption(
                caption=(
                    f"<b>[ Магазин семьи ]</b>\n{'─'*22}\n\n"
                    f"➢  Монеты: <b>{coins:,}</b>\n"
                    f"➢  Предметов: <b>{len(owned)}</b>\n\n"
                    f"<i>Выбери категорию:</i>"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        except: pass

    elif data.startswith("shop_cat_"):
        await _show_category(query, user_id, data.replace("shop_cat_", ""), 0)

    elif data.startswith("shop_page_"):
        parts = data.split("_")
        await _show_category(query, user_id, parts[2], int(parts[3]))

    elif data.startswith("shop_item_"):
        await _show_item(query, user_id, data.replace("shop_item_", ""))

    elif data == "shop_inventory":
        await _show_inventory_inline(query, user_id)

    elif data.startswith("shop_buy_"):
        item_id = data.replace("shop_buy_", "")
        item    = ALL_ITEMS.get(item_id)
        if not item:
            await query.answer("Предмет не найден.", show_alert=True); return
        if owns_item(user_id, item_id):
            await query.answer("Уже куплено!", show_alert=True); return

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT coins FROM players WHERE user_id=?", (user_id,))
        player = c.fetchone()
        if not player or player[0] < item["price"]:
            conn.close()
            await query.answer("Недостаточно монет!", show_alert=True); return

        c.execute("UPDATE players SET coins=coins-? WHERE user_id=?", (item["price"], user_id))
        c.execute("INSERT OR IGNORE INTO inventory (user_id, item_id, bought_at) VALUES (?,?,?)",
                  (user_id, item_id, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        await query.answer(f"✓ Куплено: {item['name']}!", show_alert=True)
        await _show_item(query, user_id, item_id)

    elif data in ("shop_owned", "shop_no_money"):
        msg = "Уже в коллекции!" if data == "shop_owned" else "Недостаточно монет!"
        await query.answer(msg, show_alert=True)

async def inventory_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    owned   = get_owned_items(user_id)
    if not owned:
        await update.message.reply_text("<b>Коллекция пуста.</b>\n\nЗагляни: /mf_shop", parse_mode="HTML"); return

    w  = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("w") and not i.startswith("wt")]
    c  = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("c")]
    wt = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("wt")]
    h  = [ALL_ITEMS[i]["name"] for i in owned if i in ALL_ITEMS and i.startswith("h")]
    total = sum(ALL_ITEMS[i]["price"] for i in owned if i in ALL_ITEMS)

    text = f"<b>[ Коллекция ]</b>\n{'─'*22}\n\n➢ <b>{len(owned)}</b> предм. | <b>{total:,}</b> монет\n\n"
    if w:  text += "<b>Оружие:</b>\n"       + "".join(f"  ➢ {n}\n" for n in w)  + "\n"
    if c:  text += "<b>Машины:</b>\n"       + "".join(f"  ➢ {n}\n" for n in c)  + "\n"
    if wt: text += "<b>Часы:</b>\n"         + "".join(f"  ➢ {n}\n" for n in wt) + "\n"
    if h:  text += "<b>Недвижимость:</b>\n" + "".join(f"  ➢ {n}\n" for n in h)

    await send_photo_message(ctx.bot, update.effective_chat.id, "treasury", text)
