"""
Система иерархии клана:
🎩 Крёстный отец  (godfather)   — абсолютная власть
🥃 Правая рука    (underboss)   — доверенный заместитель
🗂 Капо           (capo)        — старший в группе
🖤 Мафиозо        (mafioso)     — преданный член семьи
♟ Associate       (associate)   — кандидат на доверие
"""

from database import get_conn

# ── Названия и эмодзи ──────────────────────────────
RANKS = {
    "godfather":  "🎩 Крёстный отец",
    "underboss":  "🥃 Правая рука",
    "capo":       "🗂 Капо",
    "mafioso":    "🖤 Мафиозо",
    "associate":  "♟ Associate",
}

RANK_ORDER = ["godfather", "underboss", "capo", "mafioso", "associate"]

# ── Права ──────────────────────────────────────────
PERMISSIONS = {
    "declare_war":       ["godfather"],
    "make_truce":        ["godfather"],
    "set_tax":           ["godfather"],
    "appoint_underboss": ["godfather"],
    "withdraw_treasury": ["godfather", "underboss"],
    "accept_member":     ["godfather", "underboss", "capo"],
    "promote_member":    ["godfather", "underboss"],
    "kick_member":       ["godfather", "underboss"],
    "attack":            ["godfather", "underboss", "capo", "mafioso"],
    "view_treasury":     ["godfather", "underboss", "capo"],
}

def get_rank(user_id: int, clan_id: int) -> str | None:
    """Возвращает звание игрока в клане или None."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT rank FROM clan_members WHERE user_id=? AND clan_id=?",
              (user_id, clan_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def has_permission(user_id: int, clan_id: int, action: str) -> bool:
    """Проверяет есть ли у игрока право на действие."""
    rank = get_rank(user_id, clan_id)
    if not rank:
        return False
    return rank in PERMISSIONS.get(action, [])

def get_rank_label(rank: str) -> str:
    """Возвращает красивое название звания."""
    return RANKS.get(rank, "— Неизвестно")

def get_next_rank(rank: str) -> str | None:
    """Возвращает следующее звание выше."""
    idx = RANK_ORDER.index(rank) if rank in RANK_ORDER else -1
    if idx > 0:
        return RANK_ORDER[idx - 1]
    return None

def get_clan_members_by_rank(clan_id: int) -> list:
    """Возвращает участников клана отсортированных по званию."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT p.username, m.rank, m.user_id
        FROM clan_members m
        JOIN players p ON p.user_id = m.user_id
        WHERE m.clan_id = ?
    """, (clan_id,))
    rows = c.fetchall()
    conn.close()
    return sorted(
        rows,
        key=lambda x: RANK_ORDER.index(x[1]) if x[1] in RANK_ORDER else 99
    )