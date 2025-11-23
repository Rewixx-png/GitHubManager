import aiosqlite
import logging

DB_NAME = "bot_storage.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                github_token TEXT,
                github_username TEXT,
                ignore_own_pushes BOOLEAN DEFAULT 0,
                repo_filter TEXT DEFAULT 'all'
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                repo_full_name TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                UNIQUE(user_id, repo_full_name)
            )
        """)
        
        # NEW: Таблица серверов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                user_id INTEGER PRIMARY KEY,
                host TEXT,
                port INTEGER DEFAULT 22,
                username TEXT,
                auth_type TEXT, -- 'password' or 'key'
                auth_data TEXT, -- зашифрованный пароль или ключ
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()
    logging.info("💾 Database initialized.")

# ... (Остальные функции без изменений: set_user_data, get_user и т.д.) ...
# Вставь сюда старые функции get_user, toggle_ignore_own и т.д. чтобы файл был полным
# Я напишу только НОВЫЕ методы для краткости, но ты должен сохранить старые!
# ----------------------------------------------------------------------------

async def set_user_data(user_id: int, token: str, username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO users (user_id, github_token, github_username) 
            VALUES (?, ?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET 
                github_token=excluded.github_token,
                github_username=excluded.github_username
        """, (user_id, token, username))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def toggle_ignore_own(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT ignore_own_pushes FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row: return False
            new_val = not row[0]
        await db.execute("UPDATE users SET ignore_own_pushes = ? WHERE user_id = ?", (new_val, user_id))
        await db.commit()
        return new_val

async def toggle_repo_filter(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT repo_filter FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            current = row[0] if row else 'all'
        new_val = 'owner' if current == 'all' else 'all'
        await db.execute("UPDATE users SET repo_filter = ? WHERE user_id = ?", (new_val, user_id))
        await db.commit()
        return new_val

async def add_subscription(user_id: int, repo_full_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR IGNORE INTO subscriptions (user_id, repo_full_name)
            VALUES (?, ?)
        """, (user_id, repo_full_name))
        await db.commit()

async def get_subscribers(repo_full_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM subscriptions WHERE repo_full_name = ?", (repo_full_name,)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

# --- НОВЫЕ МЕТОДЫ ДЛЯ СЕРВЕРОВ ---

async def set_server(user_id: int, host: str, port: int, username: str, auth_type: str, auth_data: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO servers (user_id, host, port, username, auth_type, auth_data) 
            VALUES (?, ?, ?, ?, ?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET 
                host=excluded.host,
                port=excluded.port,
                username=excluded.username,
                auth_type=excluded.auth_type,
                auth_data=excluded.auth_data
        """, (user_id, host, port, username, auth_type, auth_data))
        await db.commit()

async def get_server(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM servers WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def delete_server(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM servers WHERE user_id = ?", (user_id,))
        await db.commit()