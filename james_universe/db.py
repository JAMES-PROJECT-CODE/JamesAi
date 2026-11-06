import sqlite3

class Database:
    def __init__(self, path: str):
        self.path = path

    def connect(self):
        con = sqlite3.connect(self.path)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def initialize(self):
        with self.connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS members (
                chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                display_name TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id))""")
            con.execute("""CREATE TABLE IF NOT EXISTS group_settings (
                chat_id INTEGER PRIMARY KEY,
                personality TEXT NOT NULL DEFAULT 'james',
                guardian_enabled INTEGER NOT NULL DEFAULT 0)""")

    def add_xp(self, chat_id, user_id, name, amount):
        with self.connect() as con:
            con.execute("""INSERT INTO members(chat_id,user_id,display_name,xp)
                VALUES(?,?,?,?) ON CONFLICT(chat_id,user_id) DO UPDATE SET
                display_name=excluded.display_name, xp=xp+excluded.xp""",
                (chat_id, user_id, name, amount))

    def get_xp(self, chat_id, user_id):
        with self.connect() as con:
            row = con.execute("SELECT xp FROM members WHERE chat_id=? AND user_id=?",
                              (chat_id, user_id)).fetchone()
            return int(row[0]) if row else 0

    def leaderboard(self, chat_id, limit=10):
        with self.connect() as con:
            return con.execute("""SELECT display_name,xp FROM members
                WHERE chat_id=? ORDER BY xp DESC LIMIT ?""",
                (chat_id, limit)).fetchall()

    def get_settings(self, chat_id):
        with self.connect() as con:
            row = con.execute("SELECT personality,guardian_enabled FROM group_settings WHERE chat_id=?",
                              (chat_id,)).fetchone()
        return {"personality": row[0], "guardian": bool(row[1])} if row else {
            "personality": "james", "guardian": False}

    def set_personality(self, chat_id, personality):
        with self.connect() as con:
            con.execute("""INSERT INTO group_settings(chat_id,personality) VALUES(?,?)
                ON CONFLICT(chat_id) DO UPDATE SET personality=excluded.personality""",
                (chat_id, personality))

    def set_guardian(self, chat_id, enabled):
        with self.connect() as con:
            con.execute("""INSERT INTO group_settings(chat_id,guardian_enabled) VALUES(?,?)
                ON CONFLICT(chat_id) DO UPDATE SET guardian_enabled=excluded.guardian_enabled""",
                (chat_id, int(enabled)))
