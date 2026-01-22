import sqlite3
import os
import time
import random
import json
from datetime import datetime
from telebot import TeleBot, types
import logging
import subprocess

# Настройка логирования с выводом в файл и консоль
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

# Проверка версии библиотеки


print("🚀 Бот запускается...")

# Конфигурация
BOT_TOKEN1 = '7868348661:AAFCGYN3s2zvj83FJdcwQXlAnkda3QSfaWA'
CHANNEL_ID = '-1002545520626'
ADMIN_ID = 8479289622
MAIN_DB_PATH = 'bot.db'  # Путь к общей базе данных

# Инициализация бота
bot = TeleBot(BOT_TOKEN1)
print(bot.get_me().username)

# Эмодзи для анимации
LOADING_FRAMES = ["⏳", "⌛", "⏳", "⌛"]
PROGRESS_FRAMES = ["▱▱▱▱▱", "▰▱▱▱▱", "▰▰▱▱▱", "▰▰▰▱▱", "▰▰▰▰▱", "▰▰▰▰▰"]

# Глобальные переменные
sending_process_active = False
scan_mode_active = False

# Инициализация SQLite базы данных
def init_db():
    conn = None
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS channels (
                     channel_id TEXT PRIMARY KEY
                     )''')
        c.execute('''CREATE TABLE IF NOT EXISTS videos (
                     file_id TEXT PRIMARY KEY,
                     message_id TEXT,
                     duration INTEGER,
                     date_added TEXT
                     )''')
        c.execute('''CREATE TABLE IF NOT EXISTS videos_full (
                     file_id TEXT PRIMARY KEY,
                     message_id TEXT,
                     date_added TEXT
                     )''')
        c.execute('''CREATE TABLE IF NOT EXISTS sent_videos (
                     channel_id TEXT,
                     file_id TEXT,
                     PRIMARY KEY (channel_id, file_id)
                     )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_videos_file_id ON videos(file_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_videos_full_file_id ON videos_full(file_id)')
        conn.commit()
        print("✅ База данных инициализирована")
    except Exception as e:
        logging.error(f"Ошибка инициализации базы данных: {e}")
        raise
    finally:
        if conn:
            conn.close()

# Проверка, является ли пользователь админом
# Замените текущую функцию на:
def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    try:
        # Если ADMIN_ID - число
        if isinstance(ADMIN_ID, (int, str)):
            return str(user_id) == str(ADMIN_ID)
        # Если ADMIN_ID - список
        elif isinstance(ADMIN_ID, (list, tuple)):
            return str(user_id) in [str(admin_id) for admin_id in ADMIN_ID]
        else:
            return False
    except Exception as e:
        logging.error(f"Ошибка в is_admin: {e}")
        return False

# Работа с токенами доступа к видео
def validate_and_use_token(token):
    """Проверяет токен и помечает его использованным"""
    try:
        conn = sqlite3.connect(MAIN_DB_PATH)
        c = conn.cursor()
        c.execute('SELECT user_id, video_count, used FROM video_access_tokens WHERE token = ?', (token,))
        result = c.fetchone()

        if not result:
            conn.close()
            return None, "❌ Неверный токен доступа!"

        user_id, video_count, used = result

        if used:
            conn.close()
            return None, "❌ Эта ссылка уже была использована!"

        # Помечаем токен как использованный
        c.execute('UPDATE video_access_tokens SET used = 1 WHERE token = ?', (token,))
        conn.commit()
        conn.close()

        return (user_id, video_count), None
    except Exception as e:
        logging.error(f"Ошибка валидации токена: {e}")
        return None, f"❌ Ошибка проверки токена: {e}"

# Проверка прав бота в канале
def check_bot_permissions(chat_id):
    try:
        chat = bot.get_chat(chat_id)
        if chat.type in ['channel', 'supergroup', 'group']:
            member = bot.get_chat_member(chat_id, bot.get_me().id)
            return member.status in ['administrator', 'creator']
        return False
    except Exception as e:
        logging.error(f"Ошибка проверки прав бота в {chat_id}: {e}")
        return False

# Проверка активности каналов
def check_channels_activity():
    while True:
        try:
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("SELECT channel_id FROM channels")
            channels = [row[0] for row in c.fetchall()]
            conn.close()
            for channel_id in channels:
                if not check_bot_permissions(channel_id):
                    try:
                        bot.send_message(ADMIN_ID, f"⚠️ Бот потерял права администратора в канале {channel_id}. Удаляю из списка.")
                        delete_channel(channel_id)
                    except Exception as e:
                        logging.error(f"Ошибка при отправке уведомления об утрате прав: {e}")
        except Exception as e:
            logging.error(f"Ошибка в check_channels_activity: {e}")
        time.sleep(3600)  # Проверка каждые 60 минут

# Инициализация каналов
def initialize_channels():
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT channel_id FROM channels")
        if not c.fetchall():
            c.execute("INSERT OR IGNORE INTO channels (channel_id) VALUES (?)", (CHANNEL_ID,))
            conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Ошибка инициализации каналов: {e}")
        raise

# Работа с каналами
def get_channels():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT channel_id FROM channels")
    channels = [row[0] for row in c.fetchall()]
    conn.close()
    return channels

def add_channel(channel_id):
    if not check_bot_permissions(channel_id):
        return False, f"❌ Бот не имеет прав администратора в канале {channel_id}."
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO channels (channel_id) VALUES (?)", (channel_id,))
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    return success, "🎉 Канал успешно добавлен!" if success else "⚠️ Канал уже существует в списке."

def delete_channel(channel_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    return success, "🗑️ Канал успешно удалён!" if success else "❌ Канал не найден в списке."

# Работа с видео (первая база)
def save_video(file_id, message_id, duration):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT file_id FROM videos WHERE file_id = ?", (file_id,))
    if c.fetchone():
        conn.close()
        return False
    c.execute("INSERT INTO videos (file_id, message_id, duration, date_added) VALUES (?, ?, ?, ?)",
              (file_id, message_id, duration, datetime.now().isoformat()))
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    return success

def get_random_video():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT file_id FROM videos WHERE duration <= 120")
    videos = [row[0] for row in c.fetchall()]
    conn.close()
    return random.choice(videos) if videos else None

def get_video_count():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM videos")
    count = c.fetchone()[0]
    conn.close()
    return count

# Работа с видео (вторая база)
def save_video_full(file_id, message_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT file_id FROM videos_full WHERE file_id = ?", (file_id,))
    if c.fetchone():
        conn.close()
        return False
    c.execute("INSERT INTO videos_full (file_id, message_id, date_added) VALUES (?, ?, ?)",
              (file_id, message_id, datetime.now().isoformat()))
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    return success

def get_all_videos_full():
    """Загружает все видео из таблицы videos_full в базе данных bot_data.db"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT file_id FROM videos_full")
        videos = [row[0] for row in c.fetchall()]
        conn.close()
        print(f"✅ Загружено {len(videos)} видео из bot_data.db (videos_full)")
        return videos
    except Exception as e:
        print(f"❌ Ошибка загрузки видео из базы данных: {e}")
        import traceback
        traceback.print_exc()
        return []

def send_videos_to_user(chat_id, video_count, user_id=None):
    """Отправляет случайные видео пользователю, исключая уже просмотренные"""
    try:
        all_videos = get_all_videos_full()

        if not all_videos:
            bot.send_message(chat_id, "❌ В базе нет видео! Обратитесь в поддержку.")
            return

        # Загружаем просмотренные видео пользователя, если user_id предоставлен
        viewed_videos = set()
        if user_id:
            try:
                conn = sqlite3.connect(MAIN_DB_PATH)
                c = conn.cursor()
                c.execute('SELECT file_id FROM viewed_content WHERE user_id = ?', (user_id,))
                viewed_videos = set(row[0] for row in c.fetchall())
                conn.close()
            except Exception as e:
                logging.error(f"Ошибка загрузки просмотренных видео: {e}")

        # Фильтруем видео, исключая уже просмотренные
        available_videos = [v for v in all_videos if v not in viewed_videos]

        if not available_videos:
            bot.send_message(chat_id, "✅ Вы посмотрели все доступные видео! Скоро будут новые.")
            return

        # Выбираем случайные видео из доступных
        import random
        videos_to_send = random.sample(available_videos, min(video_count, len(available_videos)))

        sending_msg = bot.send_message(
            chat_id,
            f"🎬 <b>Отправляю {len(videos_to_send)} видео...</b>\n\n"
            f"⏳ Пожалуйста, подождите...",
            parse_mode='HTML'
        )

        sent_count = 0
        error_count = 0
        update_interval = 5
        current_delay = 0.5
        min_delay = 0.3
        max_delay = 5

        # Сохраняем просмотренные видео в БД при отправке
        for i, file_id in enumerate(videos_to_send, 1):
            # Сохраняем в viewed_content что пользователь начал смотреть видео
            if user_id:
                try:
                    conn = sqlite3.connect(MAIN_DB_PATH)
                    c = conn.cursor()
                    c.execute(
                        'INSERT OR IGNORE INTO viewed_content (user_id, file_id, category) VALUES (?, ?, ?)',
                        (user_id, file_id, 'private')
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logging.error(f"Ошибка сохранения просмотренного видео: {e}")
            max_retries = 2
            retry_count = 0
            sent_successfully = False

            while retry_count < max_retries and not sent_successfully:
                try:
                    bot.send_video(
                        chat_id=chat_id,
                        video=file_id,
                        has_spoiler=True
                    )
                    sent_count += 1
                    sent_successfully = True
                    current_delay = max(min_delay, current_delay - 0.05)
                except Exception as e:
                    if hasattr(e, 'error_code') and getattr(e, 'error_code', None) == 429:
                        retry_after = min(getattr(getattr(e, 'result_json', {}).get('parameters', {}), 'get', lambda k, d: d)('retry_after', 30), 30)
                        logging.warning(f"Лимит Telegram API. Жду {retry_after} сек...")
                        if i % 3 == 0:
                            try:
                                bot.edit_message_text(
                                    f"⏸️ Telegram лимит! Жду {retry_after} сек...\nОбработано: {i}/{len(videos_to_send)}",
                                    sending_msg.chat.id,
                                    sending_msg.message_id
                                )
                            except:
                                pass
                        time.sleep(retry_after)
                        current_delay = min(max_delay, current_delay + 0.5)
                        retry_count += 1
                    else:
                        logging.error(f"Ошибка отправки видео {file_id}: {e}")
                        error_count += 1
                        break

            if sent_successfully:
                time.sleep(current_delay)

            if i % update_interval == 0 or i == len(videos_to_send):
                try:
                    progress_percent = int((i / len(videos_to_send)) * 100)
                    bot.edit_message_text(
                        f"🎬 <b>Отправка видео</b>\n\n"
                        f"📊 Прогресс: {progress_percent}%\n"
                        f"✅ Отправлено: {sent_count}\n"
                        f"❌ Ошибки: {error_count}\n"
                        f"📈 Обработано: {i}/{len(videos_to_send)}",
                        sending_msg.chat.id,
                        sending_msg.message_id,
                        parse_mode='HTML'
                    )
                except:
                    pass

        bot.edit_message_text(
            f"✅ <b>Отправка завершена!</b>\n\n"
            f"🎬 Отправлено видео: {sent_count}\n"
            f"❌ Ошибки: {error_count}\n\n"
            f"Приятного просмотра! 🍿",
            sending_msg.chat.id,
            sending_msg.message_id,
            parse_mode='HTML'
        )

    except Exception as e:
        logging.error(f"Ошибка в send_videos_to_user: {e}")
        try:
            bot.send_message(chat_id, f"❌ Ошибка отправки видео: {e}")
        except:
            pass

def get_video_count_full():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM videos_full")
    count = c.fetchone()[0]
    conn.close()
    return count

def is_video_sent(channel_id, file_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM sent_videos WHERE channel_id = ? AND file_id = ?", (str(channel_id), file_id))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def mark_video_sent(channel_id, file_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO sent_videos (channel_id, file_id) VALUES (?, ?)", (str(channel_id), file_id))
    conn.commit()
    conn.close()

def clear_full_db():
    conn = None
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("DELETE FROM videos_full")
        c.execute("DELETE FROM sent_videos")
        conn.commit()
        return True, "✅ Вторая база данных и данные об отправленных видео успешно очищены!"
    except Exception as e:
        logging.error(f"Ошибка при очистке второй базы: {e}")
        return False, f"❌ Ошибка при очистке второй базы: {e}"
    finally:
        if conn:
            conn.close()

def clear_first_db():
    conn = None
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("DELETE FROM videos")
        conn.commit()
        return True, "✅ Первая база данных успешно очищена!"
    except Exception as e:
        logging.error(f"Ошибка при очистке первой базы: {e}")
        return False, f"❌ Ошибка при очистке первой базы: {e}"
    finally:
        if conn:
            conn.close()

# Анимация загрузки
def animate_loading(message, text_base, duration=3):
    for i in range(duration * 2):
        frame = LOADING_FRAMES[i % len(LOADING_FRAMES)]
        try:
            bot.edit_message_text(
                f"{frame} {text_base}",
                message.chat.id,
                message.message_id
            )
            time.sleep(0.5)
        except:
            break

# Анимация прогресса
def animate_progress(message, text_base, current, total):
    progress_percent = int((current / total) * 100) if total > 0 else 0
    progress_bar_index = int((current / total) * (len(PROGRESS_FRAMES) - 1)) if total > 0 else 0
    progress_bar = PROGRESS_FRAMES[min(progress_bar_index, len(PROGRESS_FRAMES) - 1)]
    text = f"🔄 {text_base}\n\n"
    text += f"📊 Прогресс: {progress_bar} {progress_percent}%\n"
    text += f"📈 Обработано: {current}/{total}"
    try:
        bot.edit_message_text(text, message.chat.id, message.message_id)
    except:
        pass

# Обработка видео
@bot.message_handler(content_types=['video'])
def handle_video(message):
    try:
        if message.chat.type == 'private' and is_admin(message.from_user.id):
            file_id = message.video.file_id
            message_id = str(message.message_id)
            if scan_mode_active:
                duration = message.video.duration if hasattr(message.video, 'duration') else 0
                saved = save_video(file_id, message_id, duration)
                response = f"{'✅ Видео сохранено в первую базу' if saved else '⚠️ Это видео уже было сохранено в первой базе'}\n\n📊 Статистика:\n• Первая база: {get_video_count()} видео"
            else:
                saved = save_video_full(file_id, message_id)
                response = f"{'✅ Видео сохранено во вторую базу' if saved else '⚠️ Это видео уже было сохранено во второй базе'}\n\n📊 Статистика:\n• Вторая база: {get_video_count_full()} видео"
            bot.reply_to(message, response)
    except Exception as e:
        logging.error(f"Ошибка в handle_video: {e}")
        if message.chat.type == 'private' and is_admin(message.from_user.id):
            bot.reply_to(message, f"❌ Ошибка при сохранении видео: {e}")

# Текст подписи для видео
CAPTION = """🔥 ПОПОЛНЕНИЕ 🔥

💋 <a href="https://t.me/Naturals_Beautybot">Получить приватку</a> 💋
😏 <a href="https://t.me/Naturals_Beautybot">Нажмите на текст</a> 😏

✅ Пароль: 777 ✅

<b>🎯 Следующее видео на 25 реакций</b>"""

# Команды бота
@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id

        # Проверяем параметры start
        if len(message.text.split()) > 1:
            params = message.text.split()[1]

            # Формат: video_{token}
            if params.startswith('video_'):
                token = params.replace('video_', '')
                result, error = validate_and_use_token(token)

                if error or not result:
                    bot.send_message(message.chat.id, error or "❌ Ошибка проверки токена!")
                    return

                target_user_id, video_count = result

                # Проверяем, что это тот же пользователь
                if user_id != target_user_id:
                    bot.send_message(message.chat.id, "❌ Эта ссылка предназначена для другого пользователя!")
                    return

                # Отправляем видео
                send_videos_to_user(message.chat.id, video_count, target_user_id)
                return

        # Стандартное приветствие для админа
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "👋 Привет! Этот бот используется для получения видео по специальным ссылкам.")
            return

        welcome_text = f"""
🤖 <b>УПРАВЛЕНИЕ БОТОМ</b> 🤖

📊 <b>Текущий статус:</b>
• Режим ожидания видео: <code>{'Активен' if scan_mode_active else 'Неактивен'}</code>
• Видео в первой базе: <code>{get_video_count()}</code>
• Видео во второй базе: <code>{get_video_count_full()}</code>
• Каналов подключено: <code>{len(get_channels())}</code>

🔧 <b>ДОСТУПНЫЕ КОМАНДЫ:</b>

📷 <code>/scan</code> - Активировать режим сохранения в первую базу
⏹️ <code>/stop</code> - Остановить режим сканирования
➕ <code>/add [ID канала]</code> - Добавить канал для публикации
➖ <code>/del [ID канала]</code> - Удалить канал из списка
📋 <code>/list</code> - Показать список всех каналов
📊 <code>/stats</code> - Показать статистику бота

📤 <code>/post</code> - Отправить случайное видео в каналы
📦 <code>/full [ID канала] [кол-во]</code> - Массовая публикация (с конца списка)
📬 <code>/me [кол-во]</code> - Отправить видео себе в ЛС (с начала списка)
⏹️ <code>/stop_full</code> - Остановить массовую публикацию

🗑️ <code>/clear_first_db</code> - Очистить первую базу данных
🗑️ <code>/clear_full_db</code> - Очистить вторую базу данных
📂 <code>/list_full_db</code> - Показать статистику второй базы

💡 <i>Отправляйте видео боту для автоматического сохранения</i>
        """

        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Ошибка в /start: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")


# Callback handler удален - теперь используем только команды

@bot.message_handler(commands=['scan'])
def scan_command(message):
    global scan_mode_active
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        scan_mode_active = True
        bot.reply_to(message, "✅ Режим ожидания видео для первой базы активирован. Отправляйте видео, они будут сохранены в первую базу. Для остановки используйте /stop.")
    except Exception as e:
        logging.error(f"Ошибка в /scan: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['stop'])
def stop_command(message):
    global scan_mode_active
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        scan_mode_active = False
        bot.reply_to(message, "✅ Режим ожидания видео остановлен. Теперь видео будут сохраняться во вторую базу.")
    except Exception as e:
        logging.error(f"Ошибка в /stop: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['add'])
def add_channel_cmd(message):
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        if not args:
            bot.reply_to(message, "📝 Укажите ID канала:\n<code>/add @ChannelName</code>\nили\n<code>/add -1001234567890</code>", parse_mode='HTML')
            return
        channel_id = args[0]
        loading_msg = bot.reply_to(message, "⏳ Добавляю канал...")
        success, msg = add_channel(channel_id)
        bot.edit_message_text(f"{'✅' if success else '⚠️'} {msg}", loading_msg.chat.id, loading_msg.message_id)
    except Exception as e:
        logging.error(f"Ошибка в /add: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['post'])
def test_post(message):
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        channels = get_channels()
        if not channels:
            bot.reply_to(message, "❌ Нет добавленных каналов для отправки. Используйте /add.")
            return
        sending_msg = bot.reply_to(message, "🚀 Отправляю посты...")
        animate_progress(sending_msg, "Отправка постов", 1, 1)
        success = send_video_to_channels()
        result_text = f"🎉 Посты отправлены!\n📤 Успешно: {len(channels) if success else 0}/{len(channels)}"
        bot.edit_message_text(result_text, sending_msg.chat.id, sending_msg.message_id)
    except Exception as e:
        logging.error(f"Ошибка в /post: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

def send_video_to_channels():
    try:
        channels = get_channels()
        if not channels:
            logging.warning("Нет каналов для отправки видео")
            return False
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT file_id, message_id FROM videos WHERE duration <= 120")
        videos = c.fetchall()
        conn.close()
        if not videos:
            bot.send_message(ADMIN_ID, f"❌ В первой базе нет видео! Используйте /scan и отправьте видео.")
            logging.warning("Первая база видео пуста")
            return False
        last_message_ids = {}  # Временное хранение для текущей сессии
        for channel_id in channels:
            attempts = 0
            max_attempts = 50
            file_id = None
            while attempts < max_attempts:
                candidate_file_id = random.choice(videos)[0]
                if not is_video_sent(channel_id, candidate_file_id):
                    file_id = candidate_file_id
                    break
                attempts += 1
            if not file_id:
                file_id = random.choice(videos)[0]
            sent_message = bot.send_video(
                chat_id=channel_id,
                video=file_id,
                caption=CAPTION,
                parse_mode='HTML',
                has_spoiler=True
            )
            mark_video_sent(channel_id, file_id)
            last_message_ids[str(channel_id)] = {
                "message_id": sent_message.message_id,
                "caption": CAPTION
            }
        return True
    except Exception as e:
        logging.error(f"Ошибка в send_video_to_channels: {e}")
        return False

@bot.message_handler(commands=['list'])
def list_channels(message):
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        channels = get_channels()
        response = "📋 <b>СПИСОК КАНАЛОВ</b>\n\n"
        if not channels:
            response += "ℹ️ <i>Нет добавленных каналов для публикации</i>\n\n"
        else:
            response += "📤 <b>Каналы для публикации:</b>\n"
            for i, channel in enumerate(channels, 1):
                try:
                    chat = bot.get_chat(channel)
                    channel_name = chat.title or channel
                except:
                    channel_name = channel
                response += f"  {i}. <code>{channel_name}</code>\n"
        bot.reply_to(message, response, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка в /list: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['del'])
def delete_channel_cmd(message):
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        if not args:
            bot.reply_to(message, "📝 Укажите ID канала:\n<code>/del @ChannelName</code>\nили\n<code>/del -1001234567890</code>", parse_mode='HTML')
            return
        channel_id = args[0]
        loading_msg = bot.reply_to(message, "🗑️ Удаляю канал...")
        success, msg = delete_channel(channel_id)
        bot.edit_message_text(f"{'✅' if success else '❌'} {msg}", loading_msg.chat.id, loading_msg.message_id)
    except Exception as e:
        logging.error(f"Ошибка в /del: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['stats'])
def stats(message):
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        video_count = get_video_count()
        video_count_full = get_video_count_full()
        channel_count = len(get_channels())
        stats_text = f"""
📊 <b>СТАТИСТИКА БОТА</b>

🎬 <b>Видео в первой базе (для /post):</b> <code>{video_count}</code>
🎬 <b>Видео во второй базе:</b> <code>{video_count_full}</code>
📤 <b>Каналов для публикации:</b> <code>{channel_count}</code>
🔄 <b>Режим ожидания видео:</b> <code>{'Активен' if scan_mode_active else 'Неактивен'}</code>

🕐 <b>Время обновления:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>

{"🟢 Первая база заполнена" if video_count > 0 else "🔴 Первая база пуста - используйте /scan и отправьте видео"}
{"🟢 Вторая база заполнена" if video_count_full > 0 else "🔴 Вторая база пуста - отправьте видео без активного /scan"}
        """
        bot.reply_to(message, stats_text, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка в /stats: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['full'])
def full_post(message):
    global sending_process_active, scan_mode_active
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        if not args:
            bot.reply_to(message, "📝 Укажите ID канала:\n<code>/full @ChannelName</code>\nили\n<code>/full -1001234567890</code>\n\n📊 Опционально укажите количество или диапазон видео:\n<code>/full @ChannelName 50</code>\n<code>/full @ChannelName 100-200</code>", parse_mode='HTML')
            return
        channel_id = args[0]
        video_limit = None
        range_start = None
        range_end = None

        if len(args) > 1:
            param = args[1]
            if '-' in param:
                try:
                    parts = param.split('-')
                    range_start = int(parts[0])
                    range_end = int(parts[1])
                    if range_start <= 0 or range_end <= 0 or range_start > range_end:
                        bot.reply_to(message, "❌ Диапазон должен быть в формате: начало-конец (оба больше 0, начало ≤ конец)")
                        return
                except (ValueError, IndexError):
                    bot.reply_to(message, "❌ Ошибка в формате диапазона. Используйте: /full @ChannelName 100-200")
                    return
            elif param.isdigit():
                video_limit = int(param)
                if video_limit <= 0:
                    bot.reply_to(message, "❌ Количество видео должно быть больше 0.")
                    return

        if not check_bot_permissions(channel_id):
            bot.reply_to(message, f"❌ Бот не имеет прав администратора в канале {channel_id}.")
            return
        all_videos = get_all_videos_full()
        if not all_videos:
            bot.reply_to(message, "❌ Во второй базе нет видео! Отправьте видео без активного /scan.")
            return

        if range_start is not None and range_end is not None:
            if range_end > len(all_videos):
                bot.reply_to(message, f"❌ В базе только {len(all_videos)} видео, а вы запросили до позиции {range_end}.")
                return
            videos = list(reversed(all_videos[range_start-1:range_end]))
            action_text = f"видео с {range_start} по {range_end}"
        else:
            videos = list(reversed(all_videos[-video_limit:])) if video_limit else list(reversed(all_videos))
            action_text = f"последние {video_limit} видео" if video_limit else "все видео"
        sending_msg = bot.reply_to(message, f"🚀 Отправляю {action_text}...")
        total_videos = len(videos)
        sent_count = 0
        skipped_count = 0
        error_count = 0
        sending_process_active = True
        current_delay = 0.5  # Начальная задержка - 0.5 секунды
        min_delay = 0.3  # Минимальная задержка
        max_delay = 5  # Максимальная задержка при ошибках
        update_interval = 10  # Обновлять прогресс каждые 10 видео

        for i, file_id in enumerate(videos, 1):
            if not sending_process_active:
                break
            if is_video_sent(channel_id, file_id):
                skipped_count += 1
                if i % update_interval == 0 or i == total_videos:
                    animate_progress(sending_msg, f"Отправка {action_text}", i, total_videos)
                continue
            max_retries = 2  # Уменьшили количество попыток
            retry_count = 0
            sent_successfully = False
            while retry_count < max_retries and not sent_successfully:
                try:
                    bot.send_video(
                        chat_id=channel_id,
                        video=file_id,
                        parse_mode='HTML',
                        has_spoiler=True
                    )
                    mark_video_sent(channel_id, file_id)
                    sent_count += 1
                    sent_successfully = True
                    # Уменьшаем задержку после успешной отправки
                    current_delay = max(min_delay, current_delay - 0.05)
                except Exception as e:
                    if hasattr(e, 'error_code') and getattr(e, 'error_code', None) == 429:
                        retry_after = min(getattr(getattr(e, 'parameters', {}), 'get', lambda k, d: d)('retry_after', 30), 30)
                        logging.warning(f"Лимит Telegram API. Жду {retry_after} сек...")
                        if i % 5 == 0:  # Обновляем реже при лимите
                            try:
                                bot.edit_message_text(
                                    f"⏸️ Telegram лимит! Жду {retry_after} сек...\nОбработано: {i}/{total_videos}",
                                    sending_msg.chat.id,
                                    sending_msg.message_id
                                )
                            except:
                                pass  # Игнорируем ошибки обновления сообщения
                        time.sleep(retry_after)
                        current_delay = min(max_delay, current_delay + 0.5)
                        retry_count += 1
                    else:
                        logging.error(f"Ошибка отправки видео {file_id}: {e}")
                        error_count += 1
                        break
            if sent_successfully:
                time.sleep(current_delay)
            # Обновляем прогресс только каждые N видео
            if i % update_interval == 0 or i == total_videos:
                animate_progress(sending_msg, f"Отправка {action_text}", i, total_videos)
        result_text = f"""
🎉 <b>ОТПРАВКА ЗАВЕРШЕНА!</b>
📤 <b>Канал:</b> <code>{channel_id}</code>
✅ <b>Отправлено видео:</b> <code>{sent_count}</code>
⏭️ <b>Пропущено (уже отправлены):</b> <code>{skipped_count}</code>
❌ <b>Ошибки отправки:</b> <code>{error_count}</code>
🎬 <b>Обработано видео:</b> <code>{sent_count + skipped_count + error_count}</code>
📊 <b>Всего видео в базе:</b> <code>{len(all_videos)}</code>
"""
        bot.edit_message_text(
            result_text,
            sending_msg.chat.id,
            sending_msg.message_id,
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Ошибка в /full: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")
    finally:
        sending_process_active = False

@bot.message_handler(commands=['stop_full'])
def stop_full_cmd(message):
    global sending_process_active
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        if sending_process_active:
            sending_process_active = False
            bot.reply_to(message, "⏹️ Процесс отправки видео остановлен.")
        else:
            bot.reply_to(message, "ℹ️ Нет активных процессов отправки.")
    except Exception as e:
        logging.error(f"Ошибка в /stop_full: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['clear_full_db'])
def clear_full_db_cmd(message):
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        loading_msg = bot.reply_to(message, "🗑️ Очищаю вторую базу данных...")
        success, msg = clear_full_db()
        bot.edit_message_text(f"{'✅' if success else '❌'} {msg}", loading_msg.chat.id, loading_msg.message_id)
    except Exception as e:
        logging.error(f"Ошибка в /clear_full_db: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['clear_first_db'])
def clear_first_db_cmd(message):
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        loading_msg = bot.reply_to(message, "🗑️ Очищаю первую базу данных...")
        success, msg = clear_first_db()
        bot.edit_message_text(f"{'✅' if success else '❌'} {msg}", loading_msg.chat.id, loading_msg.message_id)
    except Exception as e:
        logging.error(f"Ошибка в /clear_first_db: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['list_full_db'])
def list_full_db_files(message):
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        video_count = get_video_count_full()
        response = f"📋 <b>ВТОРАЯ БАЗА ДАННЫХ</b>\n\n📊 <b>Всего видео:</b> <code>{video_count}</code>"
        bot.reply_to(message, response, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка в /list_full_db: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['me'])
def send_to_me(message):
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        if not args:
            bot.reply_to(message, "📝 Укажите количество видео или диапазон:\n<code>/me 10</code>\n<code>/me 900-1500</code>", parse_mode='HTML')
            return

        all_videos = get_all_videos_full()
        if not all_videos:
            bot.reply_to(message, "❌ Во второй базе нет видео! Отправьте видео без активного /scan.")
            return

        # Проверка формата диапазона (900-1500) или количества (10)
        arg = args[0]
        if '-' in arg:
            try:
                parts = arg.split('-')
                if len(parts) != 2:
                    bot.reply_to(message, "❌ Неверный формат диапазона. Используйте: /me 900-1500")
                    return
                start_idx = int(parts[0])
                end_idx = int(parts[1])

                if start_idx <= 0 or end_idx <= 0:
                    bot.reply_to(message, "❌ Номера видео должны быть больше 0.")
                    return
                if start_idx > end_idx:
                    bot.reply_to(message, "❌ Начальный номер не может быть больше конечного.")
                    return

                # Преобразуем в индексы (1-based в 0-based)
                start_idx -= 1

                # Берём видео из диапазона
                if start_idx >= len(all_videos):
                    bot.reply_to(message, f"❌ Начальный номер {start_idx + 1} больше количества видео ({len(all_videos)}).")
                    return

                videos = all_videos[start_idx:end_idx]
                if not videos:
                    bot.reply_to(message, "❌ В указанном диапазоне нет видео.")
                    return

                sending_msg = bot.reply_to(message, f"🚀 Отправляю видео с {start_idx + 1} по {end_idx} ({len(videos)} видео) в ЛС...")
            except ValueError:
                bot.reply_to(message, "❌ Неверный формат. Используйте:\n/me 10\nили\n/me 900-1500")
                return
        else:
            # Стандартное количество видео
            if not arg.isdigit():
                bot.reply_to(message, "❌ Неверный формат. Используйте:\n/me 10\nили\n/me 900-1500")
                return
            video_count = int(arg)
            if video_count <= 0:
                bot.reply_to(message, "❌ Количество видео должно быть больше 0.")
                return
            videos = all_videos[:video_count] if video_count <= len(all_videos) else all_videos
            sending_msg = bot.reply_to(message, f"🚀 Отправляю первые {len(videos)} видео в ЛС...")
        total_videos = len(videos)
        sent_count = 0
        error_count = 0
        current_delay = 0.5
        min_delay = 0.3
        max_delay = 5
        update_interval = 5

        for i, file_id in enumerate(videos, 1):
            max_retries = 2
            retry_count = 0
            sent_successfully = False

            while retry_count < max_retries and not sent_successfully:
                try:
                    bot.send_video(
                        chat_id=ADMIN_ID,
                        video=file_id,
                        parse_mode='HTML',
                        has_spoiler=True
                    )
                    sent_count += 1
                    sent_successfully = True
                    current_delay = max(min_delay, current_delay - 0.05)
                except Exception as e:
                    if hasattr(e, 'error_code') and getattr(e, 'error_code', None) == 429:
                        retry_after = min(getattr(getattr(e, 'result_json', {}).get('parameters', {}), 'get', lambda k, d: d)('retry_after', 30), 30)
                        logging.warning(f"Лимит Telegram API при отправке в ЛС. Жду {retry_after} сек...")
                        if i % 3 == 0:
                            try:
                                bot.edit_message_text(
                                    f"⏸️ Telegram лимит! Жду {retry_after} сек...\nОбработано: {i}/{total_videos}",
                                    sending_msg.chat.id,
                                    sending_msg.message_id
                                )
                            except:
                                pass
                        time.sleep(retry_after)
                        current_delay = min(max_delay, current_delay + 0.5)
                        retry_count += 1
                        if retry_count >= max_retries:
                            error_count += 1
                    else:
                        logging.error(f"Ошибка отправки видео {file_id} в ЛС: {e}")
                        error_count += 1
                        break

            if sent_successfully:
                time.sleep(current_delay)

            if i % update_interval == 0 or i == total_videos:
                animate_progress(sending_msg, "Отправка видео в ЛС", i, total_videos)

        result_text = f"""
✅ <b>ОТПРАВКА В ЛС ЗАВЕРШЕНА!</b>
📤 <b>Отправлено видео:</b> <code>{sent_count}</code>
❌ <b>Ошибки отправки:</b> <code>{error_count}</code>
🎬 <b>Обработано видео:</b> <code>{sent_count + error_count}</code>
"""
        bot.edit_message_text(
            result_text,
            sending_msg.chat.id,
            sending_msg.message_id,
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Ошибка в /me: {e}")
        try:
            bot.reply_to(message, f"❌ Ошибка: {e}")
        except:
            pass

@bot.message_handler(commands=['version'])
def version_command(message):
    try:
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Эта команда только для администратора.")
            return
        version_info = getattr(telebot, '__version__', 'unknown')
        try:
            pip_info = subprocess.check_output(['pip', 'show', 'pyTelegramBotAPI']).decode('utf-8')
        except subprocess.CalledProcessError as e:
            pip_info = f"Ошибка при получении информации: {e}"
        bot.reply_to(message, f"📌 Версия pyTelegramBotAPI: {version_info}\n\n{pip_info}", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка в /version: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

# Запуск бота
if __name__ == '__main__':
    import threading
    
    print("🤖 Запуск бота...")
    init_db()
    initialize_channels()
    
    # Фоновая проверка каналов (если нужно)
    threading.Thread(target=check_channels_activity, daemon=True).start()
    
    print("✅ Бот готов к работе!")
    
    while True:
        try:
            print("→ Запуск polling...")
            bot.polling(
                non_stop=True,
                interval=0.5,    
                timeout=15,     
                long_polling_timeout=10
            )
        except Exception as e:
            logging.error(f"Polling упал: {e}", exc_info=True)
            time.sleep(3)  

if __name__ == '__main__':
    main()
