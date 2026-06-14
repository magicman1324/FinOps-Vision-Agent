"""SQLite 用户宠物数据库"""
import aiosqlite
import os
import random

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
PETS = ["robot", "cat", "dog", "alien"]


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                pet_type TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.commit()


async def get_or_create_user(username: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT username, pet_type FROM users WHERE username = ?",
            (username,),
        )
        row = await cursor.fetchone()
        if row:
            return {"username": row[0], "pet_type": row[1]}

        pet = random.choice(PETS)
        await db.execute(
            "INSERT INTO users (username, pet_type) VALUES (?, ?)",
            (username, pet),
        )
        await db.commit()
        return {"username": username, "pet_type": pet}
