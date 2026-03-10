import aiosqlite
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: aiosqlite.Connection = None

    async def connect(self):
        """Встановлює стабільне з'єднання з БД та ініціалізує таблиці"""
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()
        # Автоматично додаємо колонки, якщо їх ще немає в існуючій базі
        await self._migrate_db()
        logger.info("Database connection established and migrated.")

    async def _create_tables(self):
        """Створення структури таблиць"""
        # 1. Таблиця користувачів
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id BIGINT PRIMARY KEY,
                gender TEXT,
                age INTEGER,
                current_weight TEXT,
                height INTEGER DEFAULT 170,
                activity REAL DEFAULT 1.2,
                daily_kcal_limit INTEGER DEFAULT 2000,
                goal TEXT,
                target_weight TEXT,
                daily_budget INTEGER,
                registration_date TEXT,
                premium_until TEXT,
                gift_received INTEGER DEFAULT 0,
                morning_motivation INTEGER DEFAULT 1,
                evening_motivation INTEGER DEFAULT 1
            )
        """)

        # 2. Таблиця логів
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT,
                action_type TEXT,
                created_at DATETIME DEFAULT (DATETIME('now', 'localtime'))
            )
        """)

        # 3. Таблиця страв (З ДОДАНИМ confirmed)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT,
                calories INTEGER,
                proteins REAL DEFAULT 0,
                fats REAL DEFAULT 0,
                carbs REAL DEFAULT 0,
                dish_name TEXT,
                confirmed INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT (DATETIME('now', 'localtime'))
            )
        """)

        # 4. Таблиця донатів
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS used_donations (
                donation_id TEXT PRIMARY KEY
            )
        """)
        await self.conn.commit()

    async def _migrate_db(self):
        """Додає відсутні колонки в існуючі бази"""
        # Міграція для users
        user_columns = {
            "gift_received": "INTEGER DEFAULT 0",
            "morning_motivation": "INTEGER DEFAULT 1",
            "evening_motivation": "INTEGER DEFAULT 1",
            "height": "INTEGER DEFAULT 170",
            "activity": "REAL DEFAULT 1.2",
            "daily_kcal_limit": "INTEGER DEFAULT 2000"
        }
        async with self.conn.execute("PRAGMA table_info(users)") as cursor:
            existing_users = [row['name'] for row in await cursor.fetchall()]
        for col, col_type in user_columns.items():
            if col not in existing_users:
                await self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

        # Міграція для meals
        meal_columns = {
            "proteins": "REAL DEFAULT 0",
            "fats": "REAL DEFAULT 0",
            "carbs": "REAL DEFAULT 0",
            "confirmed": "INTEGER DEFAULT 1"
        }
        async with self.conn.execute("PRAGMA table_info(meals)") as cursor:
            existing_meals = [row['name'] for row in await cursor.fetchall()]
        for col, col_type in meal_columns.items():
            if col not in existing_meals:
                await self.conn.execute(f"ALTER TABLE meals ADD COLUMN {col} {col_type}")

        await self.conn.commit()

    # --- Харчування та статистика (ОНОВЛЕНО) ---

    async def add_meal(self, user_id: int, calories: int, proteins: float, fats: float, carbs: float, dish_name: str, confirmed: int = 1):
        """Зберігає страву. Повертає ID запису."""
        cursor = await self.conn.execute("""
            INSERT INTO meals (user_id, calories, proteins, fats, carbs, dish_name, confirmed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, calories, proteins, fats, carbs, dish_name, confirmed))
        await self.conn.commit()
        return cursor.lastrowid

    async def confirm_meal(self, meal_id: int):
        """Підтверджує страву (confirmed = 1)"""
        await self.conn.execute("UPDATE meals SET confirmed = 1 WHERE id = ?", (meal_id,))
        await self.conn.commit()

    async def delete_meal(self, meal_id: int):
        """Видаляє непідтверджену або помилкову страву"""
        await self.conn.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
        await self.conn.commit()

    async def get_stats_for_period(self, user_id: int, days: int):
        """Статистика тільки за ПІДТВЕРДЖЕНІ страви"""
        start_date = (datetime.now() - timedelta(days=days - 1)).strftime('%Y-%m-%d 00:00:00')
        async with self.conn.execute("""
            SELECT SUM(calories) as total_cal,
                   SUM(proteins) as total_prot,
                   SUM(fats)     as total_fats,
                   SUM(carbs)    as total_carbs,
                   COUNT(*) as count
            FROM meals
            WHERE user_id = ? AND created_at >= ? AND confirmed = 1
        """, (user_id, start_date)) as cursor:
            res = await cursor.fetchone()
            return {
                "total_calories": res['total_cal'] if res['total_cal'] else 0,
                "total_proteins": round(res['total_prot'], 1) if res['total_prot'] else 0,
                "total_fats": round(res['total_fats'], 1) if res['total_fats'] else 0,
                "total_carbs": round(res['total_carbs'], 1) if res['total_carbs'] else 0,
                "meals_count": res['count'] if res['count'] else 0
            }

    # --- Решта методів без змін ---

    async def add_user(self, user_id, gender, age, weight, height, activity, goal, target_weight, budget):
        user = await self.get_user(user_id)
        now = datetime.now()
        w, h, a = float(weight), int(height), int(age)
        if gender == "Чоловік":
            bmr = (10 * w) + (6.25 * h) - (5 * a) + 5
        else:
            bmr = (10 * w) + (6.25 * h) - (5 * a) - 161
        kcal_limit = int(bmr * float(activity))
        if goal == "Схуднути": kcal_limit -= 300
        elif goal == "Набрати масу": kcal_limit += 300

        if not user:
            premium_until = (now + timedelta(days=7)).isoformat()
            reg_date = now.isoformat()
        else:
            premium_until = user['premium_until']
            reg_date = user['registration_date']

        await self.conn.execute("""
            INSERT OR REPLACE INTO users 
            (user_id, gender, age, current_weight, height, activity, daily_kcal_limit, goal, target_weight, daily_budget, registration_date, premium_until) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, gender, age, weight, height, activity, kcal_limit, goal, target_weight, budget, reg_date, premium_until))
        await self.conn.commit()

    async def get_user(self, user_id: int):
        async with self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

    async def set_premium(self, user_id: int, days: int):
        user = await self.get_user(user_id)
        now, start_date = datetime.now(), datetime.now()
        if user and user['premium_until']:
            try:
                current_premium = datetime.fromisoformat(user['premium_until'])
                if current_premium > now: start_date = current_premium
            except: pass
        new_until = (start_date + timedelta(days=days)).isoformat()
        await self.conn.execute("UPDATE users SET premium_until = ? WHERE user_id = ?", (new_until, user_id))
        await self.conn.commit()

    async def is_donation_used(self, donation_id: str):
        async with self.conn.execute("SELECT 1 FROM used_donations WHERE donation_id = ?", (donation_id,)) as c:
            return await c.fetchone() is not None

    async def mark_donation_used(self, donation_id: str):
        await self.conn.execute("INSERT INTO used_donations (donation_id) VALUES (?)", (donation_id,))
        await self.conn.commit()

    async def log_action(self, user_id: int, action_type: str):
        await self.conn.execute("INSERT INTO logs (user_id, action_type) VALUES (?, ?)", (user_id, action_type))
        await self.conn.commit()

    async def get_all_users_ids(self):
        async with self.conn.execute("SELECT user_id FROM users") as c:
            rows = await c.fetchall()
            return [row[0] for row in rows]

    async def get_advanced_stats(self):
        today = datetime.now().date().isoformat()
        now = datetime.now().isoformat()
        async with self.conn.execute("SELECT COUNT(*) FROM users") as c: total_users = (await c.fetchone())[0]
        async with self.conn.execute("SELECT COUNT(DISTINCT user_id) FROM logs WHERE created_at LIKE ?", (f"{today}%",)) as c: active_today = (await c.fetchone())[0]
        async with self.conn.execute("SELECT COUNT(*) FROM logs WHERE action_type='photo'") as c: total_photos = (await c.fetchone())[0]
        async with self.conn.execute("SELECT COUNT(*) FROM logs WHERE action_type='message'") as c: total_messages = (await c.fetchone())[0]
        async with self.conn.execute("SELECT COUNT(*) FROM users WHERE premium_until > ?", (now,)) as c: active_premium = (await c.fetchone())[0]
        return {"total_users": total_users, "active_today": active_today, "total_photos": total_photos, "total_messages": total_messages, "active_premium": active_premium}

    async def close(self):
        if self.conn: await self.conn.close()

    async def update_notification_setting(self, user_id: int, setting: str, value: int):
        await self.conn.execute(f"UPDATE users SET {setting} = ? WHERE user_id = ?", (value, user_id))
        await self.conn.commit()