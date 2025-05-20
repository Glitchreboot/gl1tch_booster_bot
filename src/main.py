from aiogram import Bot, Dispatcher, executor, types
import sqlite3
import os

API_TOKEN = os.getenv("TG_BOT_TOKEN")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Простая БД SQLite
conn = sqlite3.connect('booster.db')
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    nickname TEXT,
    channel_url TEXT,
    points INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    target_url TEXT,
    done INTEGER DEFAULT 0
)
""")
conn.commit()

@dp.message_handler(commands=['start'])
async def cmd_start(msg: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users (tg_id) VALUES (?)", (msg.from_user.id,))
    conn.commit()
    await msg.answer(
        "Добро пожаловать в GL1TCH.REBOOT Booster!\n"
        "Пришли свою ссылку на канал/YouTube, а я сгенерирую тебе задания."
    )

@dp.message_handler(lambda m: m.text and m.text.startswith("http"))
async def register_channel(msg: types.Message):
    url = msg.text.strip()
    cursor.execute(
        "UPDATE users SET channel_url = ? WHERE tg_id = ?",
        (url, msg.from_user.id)
    )
    conn.commit()
    await msg.answer(
        f"Твой канал сохранён: {url}\n"
        "Сейчас создаю список задач — подпишись на чужие каналы, чтобы получить баллы."
    )
    # Генерируем, например, 3 задания:
    cursor.execute("DELETE FROM tasks WHERE user_id = ?", (msg.from_user.id,))
    # Берём 3 случайных других пользователей:
    cursor.execute("SELECT channel_url FROM users WHERE channel_url IS NOT NULL AND tg_id != ? ORDER BY RANDOM() LIMIT 3", (msg.from_user.id,))
    targets = cursor.fetchall()
    for (target_url,) in targets:
        cursor.execute(
            "INSERT INTO tasks (user_id, target_url) VALUES (?, ?)",
            (msg.from_user.id, target_url)
        )
    conn.commit()
    # Отправляем список:
    keyboard = types.InlineKeyboardMarkup()
    for row in cursor.execute("SELECT id, target_url FROM tasks WHERE user_id = ? AND done = 0", (msg.from_user.id,)):
        task_id, target = row
        keyboard.add(types.InlineKeyboardButton(
            text=f"Проверить {target}",
            callback_data=f"check_{task_id}"
        ))
    await msg.answer("Твои задания:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("check_"))
async def check_subscription(cb: types.CallbackQuery):
    task_id = int(cb.data.split("_")[1])
    cursor.execute("SELECT user_id, target_url FROM tasks WHERE id = ?", (task_id,))
    user_id, target_url = cursor.fetchone()
    # Проверяем подписку в Telegram:
    try:
        member = await bot.get_chat_member(chat_id=target_url, user_id=user_id)
        subscribed = member.is_chat_member()
    except:
        subscribed = False
    if subscribed:
        cursor.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        cursor.execute("UPDATE users SET points = points + 10 WHERE tg_id = ?", (user_id,))
        conn.commit()
        await cb.answer("✅ Подписка подтверждена! +10 баллов")
    else:
        await cb.answer("❌ Ты ещё не подписан.")

@dp.message_handler(commands=['profile'])
async def profile(msg: types.Message):
    cursor.execute("SELECT points, channel_url FROM users WHERE tg_id = ?", (msg.from_user.id,))
    pts, url = cursor.fetchone()
    await msg.answer(f"🔹 Твой канал: {url}\n🔹 Баллы: {pts}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
