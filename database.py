import sqlite3

DB_NAME = "mafia.db"

def get_conn():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Игроки
    c.execute("""CREATE TABLE IF NOT EXISTS players (
        user_id     INTEGER PRIMARY KEY,
        username    TEXT,
        clan_id     INTEGER DEFAULT NULL,
        strength    INTEGER DEFAULT 10,
        coins       INTEGER DEFAULT 500,
        level       INTEGER DEFAULT 1,
        experience  INTEGER DEFAULT 0
    )""")

    # Кланы
    c.execute("""CREATE TABLE IF NOT EXISTS clans (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT UNIQUE,
        owner_id    INTEGER,
        power       INTEGER DEFAULT 100,
        treasury    INTEGER DEFAULT 0,
        tax_rate    INTEGER DEFAULT 0,
        created_at  TEXT
    )""")

    # Участники клана с званиями
    c.execute("""CREATE TABLE IF NOT EXISTS clan_members (
        user_id     INTEGER,
        clan_id     INTEGER,
        rank        TEXT DEFAULT 'associate',
        joined_at   TEXT,
        PRIMARY KEY (user_id, clan_id)
    )""")

    # Заявки на вступление
    c.execute("""CREATE TABLE IF NOT EXISTS join_requests (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        clan_id     INTEGER,
        message     TEXT,
        status      TEXT DEFAULT 'pending',
        created_at  TEXT
    )""")

    # Войны
    c.execute("""CREATE TABLE IF NOT EXISTS wars (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        attacker_id     INTEGER,
        defender_id     INTEGER,
        status          TEXT DEFAULT 'active',
        attacker_score  INTEGER DEFAULT 0,
        defender_score  INTEGER DEFAULT 0,
        declared_at     TEXT,
        ends_at         TEXT,
        winner_id       INTEGER DEFAULT NULL
    )""")

    # Бизнесы
    c.execute("""CREATE TABLE IF NOT EXISTS businesses (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        clan_id      INTEGER,
        name         TEXT,
        income       INTEGER DEFAULT 50,
        last_collect TEXT
    )""")

    # Объявления от администрации
    c.execute("""CREATE TABLE IF NOT EXISTS announcements (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        text        TEXT,
        created_at  TEXT,
        author_id   INTEGER
    )""")

    conn.commit()
    conn.close()
    print("База данных успешно создана!")

if __name__ == "__main__":
    init_db()