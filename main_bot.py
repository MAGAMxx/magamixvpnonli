import os
import sqlite3
import time
import json
from datetime import datetime, timedelta
from telebot import TeleBot, types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import threading
import pickle

load_dotenv()

# Конфигурация
BOT_TOKEN = '8557659726:AAGnTU2kTVhtPlF1R8taQWRD5FyzVwBmkPI'
SUPPORT_BOT = 'https://t.me/nejnayatp3'
CONTENT_GROUP_ID = -4955529149  # ID группы с контентом (замените на ваш)

# Цены
PRICE_REGULAR_VIDEO = 3
PRICE_REGULAR_PHOTO = 1
PRICE_VIP_VIDEO = 6
PRICE_PREMIUM_REGULAR = 300
PRICE_PREMIUM_VIP = 500
ADMIN_IDS = [8479289622, 7728306007]
REFERRAL_BONUS = 15
NEW_USER_BONUS = 20
# CONTENT_COOLDOWN = 10 # Убрано ожидание

# Курс Telegram Stars к рублю (1 Star = 1.5 рубля)
STARS_TO_RUB_RATE = 1.4

# Криптовалютные курсы (обновляются автоматически)
CRYPTO_RATES = {}

def update_crypto_rates():
    """Обновление курсов криптовалют через API"""
    try:
        import requests
        
        # CoinGecko API (бесплатный, без ключа)
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': 'bitcoin,ethereum,tron,tether',
            'vs_currencies': 'rub'
        }
        
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            CRYPTO_RATES['btc'] = data.get('bitcoin', {}).get('rub', 5000000)
            CRYPTO_RATES['eth'] = data.get('ethereum', {}).get('rub', 300000)
            CRYPTO_RATES['tron'] = data.get('tron', {}).get('rub', 10)
            CRYPTO_RATES['usdt'] = data.get('tether', {}).get('rub', 95)
            print(f"✅ Курсы криптовалют обновлены: BTC={CRYPTO_RATES['btc']:.0f}₽, ETH={CRYPTO_RATES['eth']:.0f}₽")
        else:
            # Запасные курсы если API недоступен
            set_default_crypto_rates()
    except Exception as e:
        print(f"⚠️ Ошибка обновления курсов: {e}")
        set_default_crypto_rates()

def set_default_crypto_rates():
    """Устанавливаем курсы по умолчанию"""
    CRYPTO_RATES['btc'] = 5000000  # примерно
    CRYPTO_RATES['eth'] = 300000
    CRYPTO_RATES['tron'] = 10
    CRYPTO_RATES['usdt'] = 95

def get_crypto_amount(rub_amount, crypto_type):
    """Конвертирует рубли в криптовалюту"""
    if not CRYPTO_RATES:
        update_crypto_rates()
    
    if crypto_type in ['usdt_ton', 'usdt_eth', 'usdt_sol']:
        rate = CRYPTO_RATES.get('usdt', 95)
    elif crypto_type == 'btc':
        rate = CRYPTO_RATES.get('btc', 5000000)
    elif crypto_type == 'eth':
        rate = CRYPTO_RATES.get('eth', 300000)
    elif crypto_type in ['tron', 'ton']:
        rate = CRYPTO_RATES.get('tron', 10)
    else:
        rate = 1
    
    return round(rub_amount / rate, 8)

# Приватки (теперь с количеством видео вместо channel_id)
PRIVATE_CHANNELS = {
    'probe': {
        'name': 'Пробные 40 видео',
        'price': 20,
        'video_count': 40,
        'description': '40 случайных видео',
        'hidden': False
    },
    'trial': {
        'name': 'ПАК 200 видео',
        'price': 200,
        'video_count': 200,
        'description': '200 случайных видео',
        'hidden': False
    },
    'students': {
        'name': 'ПАК 444 видео',
        'price': 350,
        'video_count': 444,
        'description': '444 случайных видео',
        'hidden': False
    },
    'alt': {
        'name': 'ПАК 600 видео',
        'price': 500,
        'video_count': 600,
        'description': '600 случайных видео',
        'hidden': False
    },
    'all_inclusive': {
        'name': 'ПАК 2000 видео',
        'price': 1000,
        'video_count': 2000,
        'description': '2000 случайных видео',
        'hidden': False
    }
}

# Создание одноразовых токенов для видео
def create_video_access_token(private_type, user_id):
    """Создает одноразовый токен для доступа к видео"""
    conn = None
    try:
        # Проверяем, не скрыта ли приватка
        if PRIVATE_CHANNELS[private_type].get('hidden', False):
            return None

        private_data = PRIVATE_CHANNELS[private_type]
        video_count = private_data.get('video_count', 10)
        
        # Генерируем уникальный токен
        import secrets
        token = secrets.token_urlsafe(32)
        
        # Сохраняем токен в БД (используем отдельное соединение)
        conn = sqlite3.connect('bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO video_access_tokens (token, user_id, video_count) VALUES (?, ?, ?)',
            (token, user_id, video_count)
        )
        conn.commit()
        conn.close()
        
        # Формируем ссылку на видео бота
        video_bot_username = "GiveBonusTG_bot"
        video_link = f"https://t.me/{video_bot_username}?start=video_{token}"
        
        print(f"✅ Создан токен доступа для {private_data['name']}: {token}")
        return video_link
    except Exception as e:
        if conn:
            try:
                conn.close()
            except:
                pass
        private_data = PRIVATE_CHANNELS.get(private_type, {})
        print(f"❌ Ошибка создания токена для {private_data.get('name', private_type)}: {e}")
        return None

def init_private_links():
    """Заглушка для совместимости (ссылки теперь создаются при покупке)"""
    print("✅ Инициализация приваток: используются одноразовые ссылки")

def get_payment_settings(payment_type):
    """Получить настройки способа оплаты"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT is_active, phone_number, wallet_number, payment_name, bank_name FROM payment_settings WHERE payment_type = ?', (payment_type,))
    result = cursor.fetchone()
    if result:
        return {
            'is_active': bool(result[0]),
            'phone_number': result[1],
            'wallet_number': result[2],
            'payment_name': result[3],
            'bank_name': result[4]
        }
    return None

def get_active_payment_methods():
    """Получить список активных способов оплаты"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT payment_type, phone_number, wallet_number, payment_name, bank_name FROM payment_settings WHERE is_active = 1')
    return cursor.fetchall()

# Категории (загружаются из БД)
REGULAR_CATEGORIES = {}
VIP_CATEGORIES = {}

def load_categories_from_db():
    """Загрузка категорий из базы данных"""
    global REGULAR_CATEGORIES, VIP_CATEGORIES
    cursor = db_conn.cursor()

    # Получаем все активные категории
    cursor.execute('SELECT category_key, category_name, is_vip FROM categories WHERE is_active = 1')
    categories = cursor.fetchall()

    REGULAR_CATEGORIES = {}
    VIP_CATEGORIES = {}

    for key, name, is_vip in categories:
        if is_vip:
            VIP_CATEGORIES[key] = name
        else:
            REGULAR_CATEGORIES[key] = name

def init_default_categories():
    """Инициализация стандартных категорий если БД пуста"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM categories')
    count = cursor.fetchone()[0]

    if count == 0:
        # Добавляем стандартные категории
        default_categories = [
            ('students', '🎓 Студентки', 0),
            ('solo', '💃 Соло', 0),
            ('lesbian', '👭 Лecбиянkи', 1),
            ('gay', '👬 Гeи', 1),
            ('special', '🔥 Тo сaмoe', 1),
            ('younger', '😇 Пoмoлoжe', 1),
            ('alt', '🖤 Альтyшkи', 1),
            ('darknet', '🌑 ДAPКNЕT', 1)
        ]

        for key, name, is_vip in default_categories:
            cursor.execute(
                'INSERT INTO categories (category_key, category_name, is_vip) VALUES (?, ?, ?)',
                (key, name, is_vip)
            )
        db_conn.commit()

# Состояния пользователей
user_states = {}

bot = TeleBot(BOT_TOKEN)

# Инициализация БД
def init_db():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 20,
            referrer_id INTEGER,
            premium_regular_until TIMESTAMP,
            premium_vip_until TIMESTAMP,
            last_content_request TIMESTAMP,
            channel1_subscribed BOOLEAN DEFAULT 0,
            channel2_subscribed BOOLEAN DEFAULT 0,
            channel3_subscribed BOOLEAN DEFAULT 0,
            last_daily_claim TIMESTAMP,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Добавляем колонку last_daily_claim если её нет
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN last_daily_claim TIMESTAMP')
        conn.commit()
    except:
        pass

    # Добавляем колонку username если её нет
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN username TEXT')
        conn.commit()
    except:
        pass

    # Добавляем колонку channel3_subscribed если её нет
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN channel3_subscribed BOOLEAN DEFAULT 0')
        conn.commit()
    except:
        pass

    # Добавляем колонку channel4_subscribed если её нет
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN channel4_subscribed BOOLEAN DEFAULT 0')
        conn.commit()
    except:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            bonus_paid BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Пересоздаем таблицу viewed_content если структура неправильная
    cursor.execute('DROP TABLE IF EXISTS viewed_content')
    cursor.execute('''
        CREATE TABLE viewed_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            category TEXT NOT NULL,
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, file_id, category)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            premium_type TEXT,
            screenshot_file_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS private_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            private_type TEXT,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, private_type)
        )
    ''')

    # Добавляем таблицу для ролей пользователей (рекламщик)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER PRIMARY KEY,
            is_advertiser BOOLEAN DEFAULT 0
        )
    ''')

    # Добавляем таблицу для заданий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            task_key TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            reward REAL NOT NULL,
            condition_value INTEGER,
            is_active BOOLEAN DEFAULT 1,
            callback_data TEXT,
            icon TEXT DEFAULT '🎁',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Добавляем таблицу для отслеживания выполненных заданий пользователями
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_key TEXT NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, task_key)
        )
    ''')

    # Добавляем таблицу для категорий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_key TEXT UNIQUE NOT NULL,
            category_name TEXT NOT NULL,
            is_vip BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Добавляем колонку channel_link если её нет
    try:
        cursor.execute('ALTER TABLE tasks ADD COLUMN channel_link TEXT')
        conn.commit()
    except:
        pass

    # Добавляем колонку channel_id если её нет
    try:
        cursor.execute('ALTER TABLE tasks ADD COLUMN channel_id TEXT')
        conn.commit()
    except:
        pass

    # Таблица для контента
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_key TEXT UNIQUE,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            categories TEXT NOT NULL, -- JSON-строка или через запятую
            number INTEGER,
            timestamp_ms REAL,
            file_size INTEGER,
            file_unique_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица для избранного (уже есть, но убедимся)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            content_type TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, file_id)
        )
    ''')

    # Таблица для избранного
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            content_type TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, file_id)
        )
    ''')

    # Таблица для исключения из рассылки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcast_excluded (
            user_id INTEGER PRIMARY KEY,
            excluded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица для отслеживания ежедневного спина
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_spins (
            user_id INTEGER PRIMARY KEY,
            last_spin TIMESTAMP,
            spins_count INTEGER DEFAULT 0
        )
    ''')

    # Таблица для одноразовых токенов доступа к видео
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_access_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            video_count INTEGER NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Добавляем стандартные способы оплаты если их нет
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='payment_settings'
    """)
    table_exists = cursor.fetchone() is not None

    if not table_exists:
        print("Таблица payment_settings не найдена → создаём и заполняем")

        cursor.execute('''
            CREATE TABLE payment_settings (
                payment_type    TEXT PRIMARY KEY,
                is_active       INTEGER DEFAULT 1,
                phone_number    TEXT,
                wallet_number   TEXT,
                payment_name    TEXT,
                bank_name       TEXT
            )
        ''')

        default_payments = [
            ('card', 1, '79931437679', None, 'Карта (СБП)', None),
            ('yoomoney', 1, None, '4100118856603360', 'ЮMoney', None),
            ('stars', 1, None, None, 'Telegram Stars', None),
            ('ton', 1, None, 'UQC1ITG7ZNBXEfLgR0cR8W0_RgDd4dPNboRJNgsZayGrlpU4', 'TON', None),
            ('usdt_ton', 1, None, 'UQC1ITG7ZNBXEfLgR0cR8W0_RgDd4dPNboRJNgsZayGrlpU4', 'USDT (TON)', None),
            ('tron', 1, None, 'TQFjw8wKR1EkEwxQun25QpcshaxaDEh7j3', 'TRON (TRX)', None),
            ('btc', 1, None, '1GPV83jNWWFVGGFHUGo7UKSkp1wsz1BedD', 'Bitcoin (BTC)', None),
            ('eth', 1, None, '0x3323527454230b7c8406e01eefb3cd6c94eeebc0', 'Ethereum (ETH)', None),
            ('usdt_eth', 1, None, '0x3323527454230b7c8406e01eefb3cd6c94eeebc0', 'USDT (ERC20)', None),
            ('usdt_sol', 1, None, 'BPgE91GNB4ymdTfvMHgN8Si4MCSiWjLbCa6T68hhApuN', 'USDT (Solana)', None)
        ]

        for payment in default_payments:
            cursor.execute('''
                INSERT INTO payment_settings 
                (payment_type, is_active, phone_number, wallet_number, payment_name, bank_name)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', payment)

        print("Таблица payment_settings создана + добавлены 10 дефолтных способов оплаты")
    else:
        print("Таблица payment_settings уже существует, пропускаем создание")

    conn.commit()
    return conn

db_conn = init_db()
init_default_categories()
load_categories_from_db()

# Функции работы с контентом
def load_content():
    """Загрузка контента из БД"""
    try:
        conn = sqlite3.connect('bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT item_key, file_id, file_type, categories, number, timestamp_ms, file_size, file_unique_id FROM content')
        rows = cursor.fetchall()
        conn.close()
        
        content = {}
        for row in rows:
            content[row[0]] = {
                'file_id': row[1],
                'type': row[2],
                'categories': json.loads(row[3]) if row[3].startswith('[') else row[3].split(','),
                'number': row[4],
                'timestamp_ms': row[5],
                'file_size': row[6],
                'file_unique_id': row[7]
            }
        return content
    except Exception as e:
        print(f"❌ Ошибка загрузки контента из БД: {e}")
        return {}

def save_content(content_dict):
    """Сохранение контента в БД (синхронизация)"""
    try:
        conn = sqlite3.connect('bot.db', check_same_thread=False)
        cursor = conn.cursor()
        for key, data in content_dict.items():
            cats = json.dumps(data['categories'], ensure_ascii=False)
            cursor.execute('''
                INSERT OR REPLACE INTO content 
                (item_key, file_id, file_type, categories, number, timestamp_ms, file_size, file_unique_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (key, data['file_id'], data['type'], cats, data.get('number'), 
                  data.get('timestamp_ms'), data.get('file_size'), data.get('file_unique_id')))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка сохранения контента в БД: {e}")

def add_content_to_storage(file_id, categories, file_type, file_size=None, file_unique_id=None):
    """Добавление контента напрямую в БД"""
    try:
        conn = sqlite3.connect('bot.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT MAX(number) FROM content')
        max_num = cursor.fetchone()[0] or 0
        next_num = max_num + 1
        item_key = f"item_{next_num}"
        timestamp_ms = time.time()
        cats = json.dumps(categories, ensure_ascii=False)
        
        cursor.execute('''
            INSERT INTO content 
            (item_key, file_id, file_type, categories, number, timestamp_ms, file_size, file_unique_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (item_key, str(file_id), file_type, cats, next_num, timestamp_ms, file_size, file_unique_id))
        
        conn.commit()
        conn.close()
        print(f"✅ Сохранен {file_type} #{next_num} в БД")
        return True
    except Exception as e:
        print(f"❌ Ошибка добавления контента в БД: {e}")
        return False

def load_viewed_content_from_db(user_id, category):
    """Загрузка списка просмотренных file_id для пользователя и категории из БД"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT file_id FROM viewed_content WHERE user_id = ? AND category = ?', (user_id, category))
    return [row[0] for row in cursor.fetchall()]

def save_viewed_content_to_db(user_id, file_id, category):
    """Сохранение просмотренного контента в БД"""
    try:
        cursor = db_conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO viewed_content (user_id, file_id, category) VALUES (?, ?, ?)',
            (user_id, file_id, category)
        )
        db_conn.commit()
    except Exception as e:
        print(f"❌ Ошибка сохранения просмотренного контента в БД: {e}")

def clear_viewed_content_for_category(user_id, category):
    """Очистка просмотренного контента для категории"""
    try:
        cursor = db_conn.cursor()
        cursor.execute('DELETE FROM viewed_content WHERE user_id = ? AND category = ?', (user_id, category))
        db_conn.commit()
    except Exception as e:
        print(f"❌ Ошибка очистки просмотренного контента: {e}")

def load_favorites():
    """Загрузка избранного из БД"""
    try:
        conn = sqlite3.connect('bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, file_id, content_type FROM favorites')
        rows = cursor.fetchall()
        conn.close()
        
        favorites = {}
        for user_id, file_id, content_type in rows:
            u_key = str(user_id)
            if u_key not in favorites:
                favorites[u_key] = []
            favorites[u_key].append({'file_id': file_id, 'type': content_type})
        return favorites
    except Exception as e:
        print(f"❌ Ошибка загрузки избранного из БД: {e}")
        return {}

def save_favorites(favorites_dict):
    """Заглушка (теперь сохраняется сразу в БД)"""
    pass

def add_to_favorites(user_id, file_id, content_type):
    """Добавить контент в избранное в БД"""
    try:
        conn = sqlite3.connect('bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO favorites (user_id, file_id, content_type)
            VALUES (?, ?, ?)
        ''', (user_id, file_id, content_type))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка добавления в избранное в БД: {e}")
        return False

def remove_from_favorites(user_id, file_id):
    """Удалить контент из избранного в БД"""
    try:
        conn = sqlite3.connect('bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM favorites WHERE user_id = ? AND file_id = ?', (user_id, file_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка удаления из избранного в БД: {e}")
        return False

def get_user_favorites(user_id):
    """Получить список избранного пользователя из БД"""
    try:
        conn = sqlite3.connect('bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT file_id, content_type FROM favorites WHERE user_id = ?', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{'file_id': row[0], 'type': row[1]} for row in rows]
    except Exception as e:
        print(f"❌ Ошибка получения избранного из БД: {e}")
        return []

def get_total_content_count():
    """Получить общее количество контента из БД"""
    try:
        conn = sqlite3.connect('bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM content')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0

def get_random_favorite(user_id):
    """Получить случайное видео из избранного"""
    import random
    favorites = get_user_favorites(user_id)
    if not favorites:
        return None
    return random.choice(favorites)

def exclude_from_broadcast(user_id):
    """Исключить пользователя из рассылки"""
    cursor = db_conn.cursor()
    try:
        cursor.execute('INSERT OR IGNORE INTO broadcast_excluded (user_id) VALUES (?)', (user_id,))
        db_conn.commit()
        return True
    except:
        return False

def is_excluded_from_broadcast(user_id):
    """Проверить, исключён ли пользователь из рассылки"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT user_id FROM broadcast_excluded WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None

def can_spin_daily(user_id):
    """Проверить, может ли пользователь сделать ежедневный спин"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT last_spin FROM daily_spins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result or not result[0]:
        return True
    
    try:
        last_spin_date = datetime.fromisoformat(result[0]).date()
        today = datetime.now().date()
        return last_spin_date < today
    except:
        return True

def perform_daily_spin(user_id):
    """Выполнить ежедневный спин и вернуть размер выигрыша"""
    import random
    
    slots = [1, 2, 3, 4, 5, 6, 7]
    spin_result = [random.choice(slots) for _ in range(3)]
    
    if spin_result == [7, 7, 7]:
        reward = 100
    elif spin_result[0] == spin_result[1] == spin_result[2]:
        reward = 50
    else:
        reward = random.randint(10, 15)
    
    cursor = db_conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        'INSERT OR REPLACE INTO daily_spins (user_id, last_spin, spins_count) VALUES (?, ?, (SELECT COALESCE(spins_count, 0) + 1 FROM daily_spins WHERE user_id = ?))',
        (user_id, now, user_id)
    )
    
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (reward, user_id))
    cursor.execute(
        'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
        (user_id, reward, f"Ежедневный спин 🎰")
    )
    db_conn.commit()
    
    return spin_result, reward

def get_random_content(category, content_type, user_id):
    """Получение случайного контента по категории и типу, исключая просмотренное"""
    content_dict = load_content()
    
    # Получаем список просмотренных file_id из БД
    viewed_ids = load_viewed_content_from_db(user_id, category)

    # Фильтруем контент, исключая просмотренный
    matching = []
    for key, data in content_dict.items():
        if isinstance(data, dict) and 'file_id' in data:
            file_id = data.get('file_id')
            if category in data.get('categories', []) and data.get('type') == content_type:
                if str(file_id) not in viewed_ids:
                    matching.append((key, data))

    # Если нет непросмотренного контента - возвращаем None
    if not matching:
        return None

    import random
    key, data = random.choice(matching)
    file_id = data.get('file_id')

    # Добавляем file_id в просмотренные
    save_viewed_content_to_db(user_id, str(file_id), category)

    # Возвращаем file_id напрямую
    return {'file_id': str(file_id), 'file_type': content_type, 'file_id_key': str(file_id)}



# Обработчик новых сообщений в группе с контентом (не используется при новой логике)
# Контент добавляется через команду /scan

# Получение или создание пользователя
def get_user(user_id, referrer_id=None, username=None):
    cursor = db_conn.cursor()

    # 1. Пытаемся найти пользователя
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()

    if user is None:
        # 2. Создаём нового пользователя
        cursor.execute(
            '''
            INSERT INTO users 
            (user_id, balance, referrer_id, username, created_at) 
            VALUES (?, 20.0, ?, ?, CURRENT_TIMESTAMP)
            ''',
            (user_id, referrer_id, username)
        )
        db_conn.commit()

        # 3. Сразу берём свежесозданную запись
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()

        # На всякий случай — защита от крайне редкой ситуации
        if user is None:
            raise RuntimeError(f"Не удалось создать пользователя {user_id} — критическая ошибка БД")

        # 4. Реферальная логика (только для новых пользователей)
        if referrer_id and referrer_id != user_id:  # защита от саморефералов
            try:
                cursor.execute(
                    'UPDATE users SET balance = balance + ? WHERE user_id = ?',
                    (REFERRAL_BONUS, referrer_id)
                )
                cursor.execute(
                    'INSERT INTO referrals (referrer_id, referred_id, bonus_paid) '
                    'VALUES (?, ?, 1)',
                    (referrer_id, user_id)
                )
                cursor.execute(
                    'INSERT INTO transactions (user_id, amount, description) '
                    'VALUES (?, ?, ?)',
                    (referrer_id, REFERRAL_BONUS, 'Реферальный бонус за регистрацию')
                )
                db_conn.commit()

                # Уведомление рефереру
                bot.send_message(
                    referrer_id,
                    f"👥 <b>Новый реферал!</b>\n\n"
                    f"Приглашённый вами пользователь присоединился.\n"
                    f"💰 Вы получили: +{REFERRAL_BONUS}₽",
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f"Ошибка начисления реферального бонуса для {referrer_id} → {user_id}: {e}")
                # можно откатить транзакцию, но в большинстве случаев лучше оставить как есть

    else:
        # 5. Обновляем username, если он изменился
        # Важно: индекс 10 может сломаться при изменении структуры таблицы!
        # Лучше использовать имя колонки или именованный доступ
        current_username = user[10] if len(user) > 10 else None

        if username and username != current_username:
            cursor.execute(
                'UPDATE users SET username = ? WHERE user_id = ?',
                (username, user_id)
            )
            db_conn.commit()

            # Обновляем объект user
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()

    return user

# Проверка подписки
def check_subscription(user_id, channel_id):
    try:
        member = bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        # Логируем ошибку для отладки
        print(f"Ошибка проверки подписки для {user_id} в канале {channel_id}: {e}")
        # Пытаемся еще раз через секунду
        time.sleep(1)
        try:
            member = bot.get_chat_member(channel_id, user_id)
            return member.status in ['member', 'administrator', 'creator']
        except:
            return False

# Проверка премиума
def has_premium(user_id):
    user = get_user(user_id)

    if user[3]:
        try:
            premium_until = datetime.fromisoformat(user[3])
            if premium_until > datetime.now():
                return True, 'regular', premium_until
        except:
            pass # Игнорируем ошибки парсинга даты

    if user[4]:
        try:
            premium_until = datetime.fromisoformat(user[4])
            if premium_until > datetime.now():
                return True, 'vip', premium_until
        except:
            pass # Игнорируем ошибки парсинга даты

    return False, None, None

# Главное меню
def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        #InlineKeyboardButton("📂 Обычные категории", callback_data='regular_categories'),
        #InlineKeyboardButton("⭐ VIP категории", callback_data='vip_categories'),
        InlineKeyboardButton("🔐 Приватки", callback_data='private_channels'),
        #InlineKeyboardButton("💖 Избранное", callback_data='favorites'),
        InlineKeyboardButton("👤 Профиль", callback_data='profile')
    )
    return keyboard

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ Доступ запрещен!")
        return

    text = (
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите действие:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("👤 Управление пользователем", callback_data='admin_user_manage'),
        InlineKeyboardButton("📊 Статистика", callback_data='admin_stats'),
        #InlineKeyboardButton("📂 Управление категориями", callback_data='admin_categories'),
        InlineKeyboardButton("🔐 Управление приватками", callback_data='admin_privates'),
        InlineKeyboardButton("🎁 Управление заданиями", callback_data='admin_tasks'),
        InlineKeyboardButton("💳 Управление оплатой", callback_data='admin_payments'),
        InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast'),
        #InlineKeyboardButton("🗑️ Удалить все видео", callback_data='admin_delete_all_videos')
    )

    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')

@bot.message_handler(commands=['stat'])
def show_stats(message):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ Доступ запрещен!")
        return

    cursor = db_conn.cursor()

    # Общая статистика
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE created_at >= datetime("now", "-1 day")')
    new_users_today = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE premium_regular_until > datetime("now") OR premium_vip_until > datetime("now")')
    active_premium = cursor.fetchone()[0]

    # Считаем доход от пополнений баланса
    cursor.execute('''
        SELECT SUM(amount) FROM transactions 
        WHERE (description LIKE "%Пополнение баланса%" OR description LIKE "%Оплата подтверждена%") 
        AND amount > 0
    ''')
    topup_income = cursor.fetchone()[0] or 0

    # Считаем доход от премиумов (через payment_requests с подтвержденным статусом)
    cursor.execute('''
        SELECT COUNT(*) FROM payment_requests 
        WHERE status = 'confirmed' AND premium_type IN ('regular', 'vip')
    ''')
    premium_sales = cursor.fetchone()[0]

    cursor.execute('''
        SELECT 
            SUM(CASE WHEN premium_type = 'regular' THEN ? ELSE ? END)
        FROM payment_requests 
        WHERE status = 'confirmed' AND premium_type IN ('regular', 'vip')
    ''', (PRICE_PREMIUM_REGULAR, PRICE_PREMIUM_VIP))
    premium_income = cursor.fetchone()[0] or 0

    # Общий доход
    total_income = topup_income + premium_income

    # Статистика по контенту
    total_content = get_total_content_count()

    # Реферальная статистика
    cursor.execute('SELECT COUNT(*) FROM referrals')
    total_referrals = cursor.fetchone()[0]

    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n"
        f"• Новых за сутки: {new_users_today}\n"
        f"• Активных премиум: {active_premium}\n\n"
        f"💰 <b>Доход:</b>\n"
        f"• Общий: {total_income:.2f}₽\n"
        f"• От пополнений: {topup_income:.2f}₽\n"
        f"• От премиумов: {premium_income:.2f}₽ ({premium_sales} шт)\n\n"
        f"📂 <b>Контент:</b>\n"
        f"• Всего материалов: {total_content}\n\n"
        f"👥 <b>Рефералы:</b>\n"
        f"• Всего приглашений: {total_referrals}\n"
    )

    bot.send_message(message.chat.id, text, parse_mode='HTML')

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Проверка блокировки
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT reason FROM blocked_users WHERE user_id = ?', (user_id,))
    blocked = cursor.fetchone()
    if blocked:
        bot.send_message(
            message.chat.id,
            f"🚫 <b>Доступ заблокирован</b>\n\n"
            f"Причина: {blocked[0]}\n\n"
            f"Для разблокировки обратитесь в поддержку: {SUPPORT_BOT}",
            parse_mode='HTML'
        )
        conn.close()
        return

    # Проверка, новый ли пользователь
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    existing_user = cursor.fetchone()
    is_new_user = existing_user is None

    # Проверка реферальной ссылки
    referrer_id = None
    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1]
        if ref_code.startswith('ref'):
            try:
                referrer_id = int(ref_code[3:])
                if referrer_id == user_id:
                    referrer_id = None
            except:
                pass

    user = get_user(user_id, referrer_id, username)

    # Уведомление новому пользователю о реферере
    if is_new_user and referrer_id:
        try:
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (referrer_id,))
            referrer = cursor.fetchone()
            referrer_name = "Пользователь"
            try:
                referrer_info = bot.get_chat(referrer_id)
                referrer_name = referrer_info.first_name or "Пользователь"
            except:
                pass

            bot.send_message(
                user_id,
                f"👋 <b>Вас пригласил:</b> {referrer_name}\n\n"
                f"💰 Вы получили приветственный бонус {NEW_USER_BONUS}₽!",
                parse_mode='HTML'
            )
        except:
            pass
    
    conn.close()

    # Формируем текст в зависимости от того, новый ли пользователь
    if is_new_user:
        text = (
            "🔥 <b>Добро пожаловать!</b>\n\n"
            f"💰 Новым пользователям +{NEW_USER_BONUS}₽ на баланс!\n"
            f"👥 Пригласи друга и получи +{REFERRAL_BONUS}₽\n\n"
            "📋 Переходи в приватки и наслаждайся:)"
        )
    else:
        text = (
            "🔥 <b>С возвращением!</b>\n\n"
            f"👥 Пригласи друга и получи +{REFERRAL_BONUS}₽\n\n"
            "📋 Переходи в приватки и наслаждайся)"
        )

    bot.send_message(message.chat.id, text, reply_markup=main_menu_keyboard(), parse_mode='HTML')

@bot.message_handler(commands=['scan'])
def scan_command(message):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ Доступ запрещен!")
        return

    user_states[user_id] = {'scanning_mode': True}
    bot.send_message(
        message.chat.id,
        "📤 <b>Режим добавления контента активирован</b>\n\n"
        "Отправляйте видео или фото для добавления в базу.\n"
        "Когда закончите, отправьте команду /stop_scan",
        parse_mode='HTML'
    )

@bot.message_handler(commands=['stop_scan'])
def stop_scan_command(message):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ Доступ запрещен!")
        return

    if user_id in user_states and user_states[user_id].get('scanning_mode'):
        user_states.pop(user_id, None)
        bot.send_message(
            message.chat.id,
            "✅ <b>Режим добавления контента завершен</b>\n\n"
            "Все контент успешно добавлен в базу!",
            parse_mode='HTML'
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ Режим добавления контента не был активирован.\n"
            "Сначала используйте /scan",
            parse_mode='HTML'
        )

# Функции для работы с приватками
def show_private_channels_menu(call):
    """Показать меню приваток"""
    text = (
        "🔐 <b>Приватные каналы</b>\n\n"
        "Приватка - это закрытый канал с эксклюзивным контентом.\n"
        "Доступ выдается навсегда!\n\n"
        "Выберите канал:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    for key, data in PRIVATE_CHANNELS.items():
        if not data.get('hidden', False):
            keyboard.add(InlineKeyboardButton(f"{data['name']} - {data['price']}₽", callback_data=f'private_{key}'))
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def show_private_channel_info(call):
    """Показать информацию о приватке"""
    # Извлекаем тип приватки из callback_data (формат: private_KEY)
    private_type = call.data.replace('private_', '')

    # Проверяем существование ключа и что приватка не скрыта
    if private_type not in PRIVATE_CHANNELS or PRIVATE_CHANNELS[private_type].get('hidden', False):
        bot.answer_callback_query(call.id, "❌ Ошибка: приватка не найдена или скрыта", show_alert=True)
        return

    private_data = PRIVATE_CHANNELS[private_type]

    # Убрана проверка на уже купленную приватку - теперь можно покупать бесконечно
    text = (
        f"🔐 <b>{private_data['name']}</b>\n\n"
        f"📝 Контент: {private_data['description']}\n"
        f"💰 Цена: <b>{private_data['price']}₽</b>\n\n"
        f"✨ <b>Что вы получите:</b>\n"
        f"• Одноразовая ссылка для доступа\n"
        f"• Эксклюзивный контент\n"
        f"• Закрытый канал\n\n"
        f"💡 <b>Важно:</b> При каждой покупке вы получаете новую ссылку\n\n"
        f"Нажмите 'Купить' для оплаты:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("💳 Купить", callback_data=f'buy_private_{private_type}')
    )
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='private_channels'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def show_private_payment_options(call):
    """Показать способы оплаты приватки"""
    user_id = call.from_user.id
    callback_parts = call.data.split('_')
    if len(callback_parts) > 3:
        private_type = '_'.join(callback_parts[2:])
    else:
        private_type = callback_parts[2]

    private_data = PRIVATE_CHANNELS[private_type]
    price = private_data['price']

    user = get_user(user_id)
    user_balance = user[1]

    text = (
        f"💳 <b>Оплата: {private_data['name']}</b>\n\n"
        f"💰 Стоимость: <b>{price}₽</b>\n"
        f"💵 Ваш баланс: <b>{user_balance:.2f}₽</b>\n\n"
        "Выберите способ оплаты:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)

    if user_balance >= price:
        keyboard.add(
            InlineKeyboardButton(f"💰 Оплатить балансом ({price}₽)", 
                               callback_data=f'pay_balance_private_{private_type}')
        )

    # Получаем активные способы оплаты
    active_payments = get_active_payment_methods()

    for payment_type, phone, wallet, name, bank_name in active_payments:
        if payment_type == 'stars':
            stars_amount = int(price / STARS_TO_RUB_RATE)
            keyboard.add(InlineKeyboardButton(f"⭐ {name} ({stars_amount} Stars)", callback_data=f'pay_stars_private_{private_type}'))
        elif payment_type == 'card':
            bank_info = f" (Банк: {bank_name})" if bank_name else ""
            keyboard.add(InlineKeyboardButton(f"💳 {name}{bank_info}", callback_data=f'card_private_{private_type}'))
        elif payment_type == 'yoomoney':
            keyboard.add(InlineKeyboardButton(f"💰 {name}", callback_data=f'yoomoney_private_{private_type}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data=f'private_{private_type}'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def process_balance_private_payment(call):
    """Оплата приватки балансом"""
    user_id = call.from_user.id
    callback_parts = call.data.split('_')
    if len(callback_parts) > 4:
        private_type = '_'.join(callback_parts[3:])
    else:
        private_type = callback_parts[3]

    private_data = PRIVATE_CHANNELS[private_type]
    price = private_data['price']

    user = get_user(user_id)
    user_balance = user[1]

    if user_balance < price:
        bot.answer_callback_query(
            call.id,
            f"❌ Недостаточно средств! Нужно {price}₽, у вас {user_balance:.2f}₽",
            show_alert=True
        )
        return

    # Списываем средства и выдаем доступ
    cursor = db_conn.cursor()
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (price, user_id))
    cursor.execute(
        'INSERT OR IGNORE INTO private_access (user_id, private_type) VALUES (?, ?)',
        (user_id, private_type)
    )
    cursor.execute(
        'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
        (user_id, -price, f"Покупка приватки {private_data['name']}")
    )
    db_conn.commit()

    # Создаем одноразовую ссылку для видео
    video_link = create_video_access_token(private_type, user_id)

    if video_link:
        text = (
            f"🎉 <b>Оплата успешна!</b>\n\n"
            f"✅ Вы получили доступ к {private_data['name']}\n"
            f"📦 Количество видео: {private_data['video_count']}\n\n"
            f"🔗 Ссылка для получения видео:\n{video_link}\n\n"
            f"💰 Списано с баланса: {price}₽\n"
            f"📝 Нажмите на ссылку, чтобы получить видео!\n\n"
            f"⚠️ Это одноразовая ссылка только для вас!"
        )
    else:
        text = (
            f"🎉 <b>Оплата успешна!</b>\n\n"
            f"✅ Вы получили доступ к {private_data['name']}\n\n"
            f"💰 Списано с баланса: {price}₽\n\n"
            f"❌ Ошибка создания ссылки. Обратитесь в поддержку."
        )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def process_stars_private_payment(call):
    """Оплата приватки через Stars"""
    user_id = call.from_user.id
    callback_parts = call.data.split('_')
    if len(callback_parts) > 4:
        private_type = '_'.join(callback_parts[3:])
    else:
        private_type = callback_parts[3]

    private_data = PRIVATE_CHANNELS[private_type]
    price = private_data['price']

    stars_amount = int(price / STARS_TO_RUB_RATE)

    payment_bot_username = "Zvezdapizd_bot"
    payment_link = f"https://t.me/{payment_bot_username}?start=private_{user_id}_{private_type}_{price}"

    text = (
        f"⭐ <b>Оплата через Telegram Stars</b>\n\n"
        f"📦 Товар: {private_data['name']}\n"
        f"💰 Стоимость: {price}₽\n"
        f"⭐ К оплате: {stars_amount} Stars\n\n"
        f"💱 Курс: 1 Star = {STARS_TO_RUB_RATE}₽\n\n"
        f"Для оплаты перейдите в платежного бота:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("💳 Перейти к оплате", url=payment_link),
        InlineKeyboardButton("◀️ Назад", callback_data=f'buy_private_{private_type}')
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

    bot.answer_callback_query(call.id)

def process_card_private_payment(call):
    """Оплата приватки картой"""
    user_id = call.from_user.id
    callback_parts = call.data.split('_')
    if len(callback_parts) > 3:
        private_type = '_'.join(callback_parts[2:-1])
    else:
        private_type = callback_parts[2]

    private_data = PRIVATE_CHANNELS[private_type]
    price = private_data['price']

    payment_settings = get_payment_settings('card')
    if not payment_settings or not payment_settings['is_active']:
        bot.answer_callback_query(call.id, "❌ Этот способ оплаты временно недоступен", show_alert=True)
        return

    phone = payment_settings['phone_number']
    bank_name = payment_settings.get('bank_name', '')
    bank_info = f" (Банк: {bank_name})" if bank_name else ""
    text = (
        f"💳 <b>Пополнение через {payment_settings['payment_name']}</b>\n\n"
        f"💰 Сумма: <b>{price}₽</b>\n"
        f"📱 Номер телефона: <code>{phone}</code>{bank_info}\n\n"
        "Переведите указанную сумму по СБП на этот номер.\n"
        "После оплаты нажмите 'Я оплатил' и отправьте скриншот."
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✅ Я оплатил", callback_data=f'paid_private_{private_type}_card'),
        InlineKeyboardButton("◀️ Назад", callback_data=f'buy_private_{private_type}')
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

def process_yoomoney_private_payment(call):
    """Оплата приватки ЮMoney"""
    user_id = call.from_user.id
    callback_parts = call.data.split('_')
    if len(callback_parts) > 3:
        private_type = '_'.join(callback_parts[2:-1])
    else:
        private_type = callback_parts[2]

    private_data = PRIVATE_CHANNELS[private_type]
    price = private_data['price']

    payment_settings = get_payment_settings('yoomoney')
    if not payment_settings or not payment_settings['is_active']:
        bot.answer_callback_query(call.id, "❌ Этот способ оплаты временно недоступен", show_alert=True)
        return

    wallet = payment_settings['wallet_number']
    text = (
        f"💰 <b>Пополнение через {payment_settings['payment_name']}</b>\n\n"
        f"💰 Сумма: <b>{price}₽</b>\n"
        f"💳 Номер кошелька: <code>{wallet}</code>\n\n"
        "После оплаты нажмите 'Я оплатил' и отправьте скриншот."
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✅ Я оплатил", callback_data=f'paid_private_{private_type}_yoomoney'),
        InlineKeyboardButton("◀️ Назад", callback_data=f'buy_private_{private_type}')
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

def handle_paid_private(call):
    """Пользователь оплатил приватку"""
    user_id = call.from_user.id
    callback_parts = call.data.split('_')

    # Извлекаем тип приватки и способ оплаты
    payment_method = callback_parts[-1] if callback_parts[-1] in ['card', 'yoomoney'] else 'card'
    if payment_method in ['card', 'yoomoney']:
        private_type = '_'.join(callback_parts[2:-1])
    else:
        private_type = '_'.join(callback_parts[2:])

    user_states[user_id] = {
        'waiting_screenshot_private': True,
        'private_type': private_type,
        'private_payment_method': payment_method
    }

    bot.edit_message_text(
        "📸 <b>Отлично!</b>\n\n"
        "Теперь отправьте скриншот оплаты.\n"
        "Просто пришлите фото чека в этот чат.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML'
    )

def confirm_private_payment(call):
    """Подтверждение оплаты приватки админом"""
    parts = call.data.split('_')
    request_id = int(parts[2])

    cursor = db_conn.cursor()
    cursor.execute('SELECT user_id, premium_type FROM payment_requests WHERE id = ?', (request_id,))
    request = cursor.fetchone()

    if request:
        user_id, private_type_full = request
        # Извлекаем тип приватки из строки вида 'private_trial_card' или 'private_students_yoomoney'
        private_type_parts = private_type_full.replace('private_', '').split('_')
        # Убираем метод оплаты (последний элемент, если это card или yoomoney)
        if private_type_parts[-1] in ['card', 'yoomoney']:
            private_type = '_'.join(private_type_parts[:-1])
        else:
            private_type = '_'.join(private_type_parts)

        private_data = PRIVATE_CHANNELS[private_type]

        cursor.execute('UPDATE payment_requests SET status = ? WHERE id = ?', ('confirmed', request_id))
        cursor.execute(
            'INSERT OR IGNORE INTO private_access (user_id, private_type) VALUES (?, ?)',
            (user_id, private_type)
        )
        db_conn.commit()

        # Создаем одноразовую ссылку для видео
        video_link = create_video_access_token(private_type, user_id)

        if video_link:
            text = (
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"🎉 Вы получили доступ к {private_data['name']}\n"
                f"📦 Количество видео: {private_data['video_count']}\n\n"
                f"🔗 Ссылка для получения видео:\n{video_link}\n\n"
                f"📝 Нажмите на ссылку, чтобы получить видео!\n\n"
                f"⚠️ Это одноразовая ссылка только для вас!"
            )
        else:
            text = (
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"🎉 Вы получили доступ к {private_data['name']}\n\n"
                f"❌ Ошибка создания ссылки. Обратитесь в поддержку."
            )

        try:
            bot.send_message(user_id, text, parse_mode='HTML')
        except:
            pass

        bot.edit_message_caption(
            caption=call.message.caption + f"\n\n✅ <b>Подтверждено администратором</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )

def reject_private_payment(call):
    """Отклонение оплаты приватки админом"""
    request_id = int(call.data.split('_')[2])

    cursor = db_conn.cursor()
    cursor.execute('SELECT user_id FROM payment_requests WHERE id = ?', (request_id,))
    request = cursor.fetchone()

    if request:
        user_id = request[0]

        cursor.execute('UPDATE payment_requests SET status = ? WHERE id = ?', ('rejected', request_id))
        db_conn.commit()

        try:
            bot.send_message(
                user_id,
                "❌ <b>Оплата отклонена</b>\n\n"
                "К сожалению, ваша заявка была отклонена.\n"
                "Обратитесь в поддержку для уточнения деталей.",
                parse_mode='HTML'
            )
        except:
            pass

        bot.edit_message_caption(
            caption=call.message.caption + f"\n\n❌ <b>Отклонено администратором</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )

# Получение контента с проверками
def get_content(call, content_type, category):
    user_id = call.from_user.id
    user = get_user(user_id)

    # Проверка премиума
    is_premium, premium_type, premium_until = has_premium(user_id)

    # Определяем цену
    is_vip = category in VIP_CATEGORIES
    if content_type == 'video':
        price = PRICE_VIP_VIDEO if is_vip else PRICE_REGULAR_VIDEO
    else:
        price = PRICE_REGULAR_PHOTO

    # Проверка баланса (если нет премиума)
    if not is_premium:
        if user[1] < price:
            try:
                bot.answer_callback_query(
                    call.id,
                    f"❌ Недостаточно баланса! Нужно {price}₽, у вас {user[1]:.2f}₽",
                    show_alert=True
                )
            except:
                pass
            return

    # Попытка отправить контент (до 3 попыток с разными видео)
    max_attempts = 3
    for attempt in range(max_attempts):
        # Получение контента
        content = get_random_content(category, content_type, user_id)

        if not content:
            try:
                # Проверяем, есть ли вообще контент в этой категории
                content_dict = load_content()
                has_content = False
                for key, data in content_dict.items():
                    if isinstance(data, dict) and 'file_id' in data:
                        if category in data.get('categories', []) and data.get('type') == content_type:
                            has_content = True
                            break

                if has_content:
                    bot.answer_callback_query(
                        call.id,
                        f"✅ Вы просмотрели весь контент в этой категории!",
                        show_alert=True
                    )
                else:
                    bot.answer_callback_query(
                        call.id,
                        f"❌ Контент временно недоступен. Попробуйте позже.",
                        show_alert=True
                    )
            except:
                pass
            return

        file_id = content['file_id']
        file_id_key = content['file_id_key']

        # Отправка контента
        try:
            # Создаем клавиатуру с кнопками
            content_keyboard = InlineKeyboardMarkup(row_width=2)
            content_keyboard.add(
                InlineKeyboardButton("🏠 Гл меню", callback_data='back_to_menu'),
                InlineKeyboardButton("🔄 Ещё раз", callback_data=f'get_{content_type}_{category}')
            )
            content_keyboard.add(
                InlineKeyboardButton("⭐ В избранное", callback_data=f'add_fav_{file_id[:30]}')
            )

            if content_type == 'video':
                bot.send_video(call.message.chat.id, file_id, reply_markup=content_keyboard)
            else:
                bot.send_photo(call.message.chat.id, file_id, reply_markup=content_keyboard)

            # Списание средств ПОСЛЕ успешной отправки (если нет премиума)
            cursor = db_conn.cursor()
            if not is_premium:
                cursor.execute(
                    'UPDATE users SET balance = balance - ?, last_content_request = ? WHERE user_id = ?',
                    (price, datetime.now().isoformat(), user_id)
                )
                cursor.execute(
                    'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
                    (user_id, -price, f"Покупка {content_type} из категории {category}")
                )
            else:
                cursor.execute(
                    'UPDATE users SET last_content_request = ? WHERE user_id = ?',
                    (datetime.now().isoformat(), user_id)
                )
            db_conn.commit()

            try:
                bot.answer_callback_query(call.id, "✅ Контент отправлен!")
            except:
                pass
            
            # Успешная отправка - выходим из цикла
            return
            
        except Exception as e:
            print(f"Ошибка отправки контента (попытка {attempt + 1}/{max_attempts}): {e}")
            
            # Если это последняя попытка - показываем ошибку
            if attempt == max_attempts - 1:
                try:
                    bot.answer_callback_query(
                        call.id,
                        "❌ Не удалось отправить контент. Попробуйте ещё раз.",
                        show_alert=True
                    )
                except:
                    pass
            # Иначе продолжаем цикл и пробуем другое видео

# ============= АДМИН-ПАНЕЛЬ =============

def admin_user_manage_start(call):
    """Начало управления пользователем"""
    user_id = call.from_user.id

    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Доступ запрещен!")
        return

    user_states[user_id] = {'admin_waiting_user_id': True}

    text = (
        "👤 <b>Управление пользователем</b>\n\n"
        "Отправьте ID пользователя или его @username:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def admin_show_stats(call):
    """Показать статистику в админ-панели"""
    user_id = call.from_user.id

    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Доступ запрещен!")
        return

    cursor = db_conn.cursor()

    # Общая статистика
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE created_at >= datetime("now", "-1 day")')
    new_users_today = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE premium_regular_until > datetime("now") OR premium_vip_until > datetime("now")')
    active_premium = cursor.fetchone()[0]

    # Считаем доход от пополнений баланса
    cursor.execute('''
        SELECT SUM(amount) FROM transactions 
        WHERE (description LIKE "%Пополнение баланса%" OR description LIKE "%Оплата подтверждена%") 
        AND amount > 0
    ''')
    topup_income = cursor.fetchone()[0] or 0

    # Считаем доход от премиумов
    cursor.execute('''
        SELECT COUNT(*) FROM payment_requests 
        WHERE status = 'confirmed' AND premium_type IN ('regular', 'vip')
    ''')
    premium_sales = cursor.fetchone()[0]

    cursor.execute('''
        SELECT 
            SUM(CASE WHEN premium_type = 'regular' THEN ? ELSE ? END)
        FROM payment_requests 
        WHERE status = 'confirmed' AND premium_type IN ('regular', 'vip')
    ''', (PRICE_PREMIUM_REGULAR, PRICE_PREMIUM_VIP))
    premium_income = cursor.fetchone()[0] or 0

    # Общий доход
    total_income = topup_income + premium_income

    cursor.execute('SELECT COUNT(*) FROM blocked_users')
    blocked_count = cursor.fetchone()[0]

    # Статистика по контенту
    content_list = load_content()
    total_content = len(content_list)

    # Реферальная статистика
    cursor.execute('SELECT COUNT(*) FROM referrals')
    total_referrals = cursor.fetchone()[0]

    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n"
        f"• Новых за сутки: {new_users_today}\n"
        f"• Активных премиум: {active_premium}\n"
        f"• Заблокировано: {blocked_count}\n\n"
        f"💰 <b>Доход:</b>\n"
        f"• Общий: {total_income:.2f}₽\n"
        f"• От пополнений: {topup_income:.2f}₽\n"
        f"• От премиумов: {premium_income:.2f}₽ ({premium_sales} шт)\n\n"
        f"📂 <b>Контент:</b>\n"
        f"• Всего материалов: {total_content}\n\n"
        f"👥 <b>Рефералы:</b>\n"
        f"• Всего приглашений: {total_referrals}\n"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def admin_broadcast_start(call):
    """Начало рассылки"""
    user_id = call.from_user.id

    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Доступ запрещен!")
        return

    user_states[user_id] = {'admin_waiting_broadcast': True}

    text = (
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Отправьте сообщение, которое будет разослано всем пользователям.\n\n"
        "⚠️ Используйте с осторожностью!"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data='back_to_admin'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def admin_user_actions(call):
    """Показать действия с пользователем"""
    user_id = call.from_user.id

    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Доступ запрещен!")
        return

    target_user_id = int(call.data.split('_')[2])

    cursor = db_conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (target_user_id,))
    user = cursor.fetchone()

    if not user:
        bot.answer_callback_query(call.id, "❌ Пользователь не найден!", show_alert=True)
        return

    # Проверка блокировки
    cursor.execute('SELECT reason FROM blocked_users WHERE user_id = ?', (target_user_id,))
    blocked = cursor.fetchone()
    is_blocked = blocked is not None

    # Информация о премиуме
    is_premium, premium_type, premium_until = has_premium(target_user_id)

    # Информация о рефералах
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (target_user_id,))
    total_referrals = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND bonus_paid = 1', (target_user_id,))
    paid_referrals = cursor.fetchone()[0]

    # Информация о покупках
    cursor.execute('''
        SELECT COUNT(*), SUM(ABS(amount)) FROM transactions 
        WHERE user_id = ? AND amount < 0 AND description LIKE "%Покупка%"
    ''', (target_user_id,))
    purchase_data = cursor.fetchone()
    total_purchases = purchase_data[0] or 0
    total_spent = purchase_data[1] or 0

    # Информация о пополнениях
    cursor.execute('''
        SELECT SUM(amount) FROM transactions 
        WHERE user_id = ? AND amount > 0 AND (description LIKE "%Пополнение%" OR description LIKE "%бонус%")
    ''', (target_user_id,))
    total_topups = cursor.fetchone()[0] or 0

    # Дата регистрации
    reg_date = datetime.fromisoformat(user[9]).strftime('%d.%m.%Y %H:%M') if user[9] else "Неизвестно"

    # Проверка роли рекламщика
    cursor.execute('SELECT is_advertiser FROM user_roles WHERE user_id = ?', (target_user_id,))
    role_data = cursor.fetchone()
    is_advertiser = role_data[0] if role_data else False

    text = (
        f"👤 <b>Пользователь ID: {target_user_id}</b>\n\n"
        f"💰 Баланс: <b>{user[1]:.2f}₽</b>\n"
        f"🚫 Статус: {'Заблокирован' if is_blocked else 'Активен'}\n"
        f"📢 Роль: {'Рекламщик' if is_advertiser else 'Обычный пользователь'}\n"
        f"📅 Регистрация: {reg_date}\n\n"
    )

    if is_premium and premium_until:
        premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"
        text += f"⭐ Премиум: {premium_name} до {premium_until.strftime('%d.%m %H:%M')}\n\n"

    text += (
        f"👥 <b>Рефералы:</b>\n"
        f"• Всего: {total_referrals}\n"
        f"• Активных: {paid_referrals}\n\n"
        f"💳 <b>Активность:</b>\n"
        f"• Покупок: {total_purchases} ({total_spent:.2f}₽)\n"
        f"• Пополнений: {total_topups:.2f}₽\n\n"
        "Выберите действие:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("💰 Установить баланс", callback_data=f'admin_set_balance_{target_user_id}'),
        InlineKeyboardButton("➕ Добавить баланс", callback_data=f'admin_add_balance_{target_user_id}'),
        InlineKeyboardButton("⭐ Выдать премиум", callback_data=f'admin_give_premium_{target_user_id}')
    )

    if is_advertiser:
        keyboard.add(InlineKeyboardButton("📢 Убрать роль рекламщика", callback_data=f'admin_remove_adv_{target_user_id}'))
    else:
        keyboard.add(InlineKeyboardButton("📢 Выдать роль рекламщика", callback_data=f'admin_give_adv_{target_user_id}'))

    if is_blocked:
        keyboard.add(InlineKeyboardButton("✅ Разблокировать", callback_data=f'admin_unblock_{target_user_id}'))
    else:
        keyboard.add(InlineKeyboardButton("🚫 Заблокировать", callback_data=f'admin_block_{target_user_id}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def admin_set_balance(call):
    """Установить баланс пользователя"""
    user_id = call.from_user.id
    target_user_id = int(call.data.split('_')[3])

    user_states[user_id] = {
        'admin_set_balance_for': target_user_id,
        'admin_waiting_balance': True
    }

    text = (
        f"💰 <b>Установка баланса</b>\n\n"
        f"👤 Пользователь ID: {target_user_id}\n\n"
        f"Введите новую сумму баланса:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data=f'admin_user_{target_user_id}'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def admin_add_balance(call):
    """Добавить баланс пользователю"""
    user_id = call.from_user.id
    target_user_id = int(call.data.split('_')[3])

    user_states[user_id] = {
        'admin_add_balance_for': target_user_id,
        'admin_waiting_add_balance': True
    }

    text = (
        f"➕ <b>Добавление баланса</b>\n\n"
        f"👤 Пользователь ID: {target_user_id}\n\n"
        f"Введите сумму для добавления:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data=f'admin_user_{target_user_id}'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def admin_give_premium(call):
    """Выдать премиум пользователю"""
    user_id = call.from_user.id
    target_user_id = int(call.data.split('_')[3])

    text = (
        f"⭐ <b>Выдача премиума</b>\n\n"
        f"👤 Пользователь ID: {target_user_id}\n\n"
        f"Выберите тип премиума:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("⭐ Премиум (обычные) 24ч", callback_data=f'admin_prem_reg_{target_user_id}'),
        InlineKeyboardButton("💎 VIP Премиум 24ч", callback_data=f'admin_prem_vip_{target_user_id}'),
        InlineKeyboardButton("◀️ Отмена", callback_data=f'admin_user_{target_user_id}')
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def admin_block_user(call):
    """Заблокировать пользователя"""
    user_id = call.from_user.id
    target_user_id = int(call.data.split('_')[2])

    user_states[user_id] = {
        'admin_block_user': target_user_id,
        'admin_waiting_block_reason': True
    }

    text = (
        f"🚫 <b>Блокировка пользователя</b>\n\n"
        f"👤 Пользователь ID: {target_user_id}\n\n"
        f"Введите причину блокировки:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data=f'admin_user_{target_user_id}'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

def admin_unblock_user(call):
    """Разблокировать пользователя"""
    user_id = call.from_user.id
    target_user_id = int(call.data.split('_')[2])

    cursor = db_conn.cursor()
    cursor.execute('DELETE FROM blocked_users WHERE user_id = ?', (target_user_id,))
    db_conn.commit()

    try:
        bot.send_message(
            target_user_id,
            "✅ <b>Вы разблокированы!</b>\n\n"
            "Теперь вы можете пользоваться ботом.",
            parse_mode='HTML'
        )
    except:
        pass

    bot.answer_callback_query(call.id, "✅ Пользователь разблокирован!", show_alert=True)

    # Возвращаемся к карточке пользователя
    call.data = f'admin_user_{target_user_id}'
    admin_user_actions(call)

def admin_delete_all_videos(call):
    """Удалить все видео из базы данных"""
    user_id = call.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Доступ запрещен!")
        return
    
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("DELETE FROM viewed_content")
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ История просмотров очищена!", show_alert=True)
        back_to_admin_panel(call)
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}", show_alert=True)

def back_to_admin_panel(call):
    """Вернуться в главное меню админ-панели"""
    user_id = call.from_user.id

    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Доступ запрещен!")
        return

    # Очищаем состояние
    user_states.pop(user_id, None)

    text = (
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите действие:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("👤 Управление пользователем", callback_data='admin_user_manage'),
        InlineKeyboardButton("📊 Статистика", callback_data='admin_stats'),
        #InlineKeyboardButton("📂 Управление категориями", callback_data='admin_categories'),
        InlineKeyboardButton("🔐 Управление приватками", callback_data='admin_privates'),
        InlineKeyboardButton("🎁 Управление заданиями", callback_data='admin_tasks'),
        InlineKeyboardButton("💳 Управление оплатой", callback_data='admin_payments'),
        InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast'),
        #InlineKeyboardButton("🗑️ Удалить все видео", callback_data='admin_delete_all_videos')
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Обработка callback запросов
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id

    if call.data.startswith('get_video_'):
        category = call.data.split('_')[2]
        get_content(call, 'video', category)

    elif call.data.startswith('get_photo_'):
        category = call.data.split('_')[2]
        get_content(call, 'photo', category)

    elif call.data.startswith('add_cat_'):
        handle_category_selection(call)

    elif call.data == 'finish_adding':
        finish_content_adding(call)

    elif call.data == 'daily_bonus':
        claim_daily_bonus(call)

    elif call.data == 'daily_spin_info':
        show_daily_spin_info(call)

    elif call.data == 'daily_spin_execute':
        do_daily_spin(call)

    # Универсальная обработка заданий подписки из БД
    elif call.data.startswith('task_'):
        task_key = call.data.replace('task_', '')
        show_task_subscription(call, task_key)

    elif call.data.startswith('check_task_'):
        task_key = call.data.replace('check_task_', '')
        check_task_subscription(call, task_key)

    elif call.data == 'check_achievements':
        check_achievements(call)

    elif call.data.startswith('confirm_topup_'):
        confirm_topup(call)

    elif call.data.startswith('reject_topup_'):
        reject_topup(call)

    elif call.data == 'admin_user_manage':
        admin_user_manage_start(call)

    elif call.data == 'admin_stats':
        admin_show_stats(call)

    elif call.data == 'admin_broadcast':
        admin_broadcast_start(call)

    elif call.data.startswith('admin_user_'):
        admin_user_actions(call)

    elif call.data.startswith('admin_set_balance_'):
        admin_set_balance(call)

    elif call.data.startswith('admin_add_balance_'):
        admin_add_balance(call)

    elif call.data.startswith('admin_give_premium_'):
        admin_give_premium(call)

    elif call.data.startswith('admin_block_'):
        admin_block_user(call)

    elif call.data.startswith('admin_unblock_'):
        admin_unblock_user(call)

    elif call.data == 'back_to_admin':
        back_to_admin_panel(call)

    elif call.data == 'admin_delete_all_videos':
        admin_delete_all_videos(call)

    # Управление приватками
    elif call.data == 'admin_privates':
        show_admin_privates_menu(call)

    elif call.data == 'admin_priv_list':
        show_privates_list(call)

    elif call.data == 'admin_priv_edit_select':
        admin_priv_edit_select(call)

    elif call.data.startswith('admin_priv_edit_'):
        admin_priv_edit_menu(call)

    elif call.data == 'admin_priv_hide_select':
        admin_priv_hide_select(call)

    elif call.data.startswith('admin_priv_hide_'):
        admin_priv_hide(call)

    elif call.data == 'admin_priv_show_select':
        admin_priv_show_select(call)

    elif call.data.startswith('admin_priv_show_'):
        admin_priv_show(call)

    elif call.data.startswith('admin_priv_vidcount_'):
        priv_key = '_'.join(call.data.split('_')[3:])
        user_states[user_id] = {'admin_edit_priv_vidcount': priv_key}
        text = f"🎬 <b>Изменение количества видео</b>\n\nВведите новое количество видео для приватки:"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data=f'admin_priv_edit_{priv_key}'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    elif call.data.startswith('admin_priv_price_'):
        priv_key = '_'.join(call.data.split('_')[3:])
        user_states[user_id] = {'admin_edit_priv_price': priv_key}
        text = f"💵 <b>Изменение цены</b>\n\nВведите новую цену для приватки (в рублях):"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data=f'admin_priv_edit_{priv_key}'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    elif call.data.startswith('admin_priv_desc_'):
        priv_key = '_'.join(call.data.split('_')[3:])
        user_states[user_id] = {'admin_edit_priv_desc': priv_key}
        text = f"📝 <b>Изменение описания</b>\n\nВведите новое описание для приватки:"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data=f'admin_priv_edit_{priv_key}'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    elif call.data.startswith('admin_priv_name_'):
        priv_key = '_'.join(call.data.split('_')[3:])
        user_states[user_id] = {'admin_edit_priv_name': priv_key}
        text = f"🏷️ <b>Изменение названия</b>\n\nВведите новое название для приватки:"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data=f'admin_priv_edit_{priv_key}'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    elif call.data.startswith('admin_give_adv_'):
        target_user_id = int(call.data.split('_')[3])
        cursor = db_conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO user_roles (user_id, is_advertiser) VALUES (?, ?)', (target_user_id, 1))
        db_conn.commit()
        bot.answer_callback_query(call.id, "✅ Роль рекламщика выдана!", show_alert=True)
        try:
            bot.send_message(target_user_id, "📢 <b>Вам выдана роль Рекламщика!</b>\n\nТеперь вы будете получать бонусы за рефералов без обязательных подписок.", parse_mode='HTML')
        except:
            pass
        call.data = f'admin_user_{target_user_id}'
        admin_user_actions(call)

    elif call.data.startswith('admin_remove_adv_'):
        target_user_id = int(call.data.split('_')[3])
        cursor = db_conn.cursor()
        cursor.execute('UPDATE user_roles SET is_advertiser = 0 WHERE user_id = ?', (target_user_id,))
        db_conn.commit()
        bot.answer_callback_query(call.id, "✅ Роль рекламщика убрана!", show_alert=True)
        try:
            bot.send_message(target_user_id, "😔 <b>Роль Рекламщика снята.</b>\n\nБонусы за рефералов будут начисляться только при выполнении условий.", parse_mode='HTML')
        except:
            pass
        call.data = f'admin_user_{target_user_id}'
        admin_user_actions(call)

    elif call.data.startswith('admin_prem_'):
        parts = call.data.split('_')
        prem_type = parts[2]
        target_user_id = int(parts[3])

        cursor = db_conn.cursor()
        premium_until = datetime.now() + timedelta(hours=24)

        if prem_type == 'reg':
            cursor.execute('UPDATE users SET premium_regular_until = ? WHERE user_id = ?', 
                         (premium_until.isoformat(), target_user_id))
            premium_name = "Премиум (обычные)"
        else:
            cursor.execute('UPDATE users SET premium_vip_until = ? WHERE user_id = ?', 
                         (premium_until.isoformat(), target_user_id))
            premium_name = "VIP Премиум"

        db_conn.commit()

        bot.answer_callback_query(call.id, f"✅ Выдан {premium_name}!", show_alert=True)

        try:
            bot.send_message(
                target_user_id,
                f"🎉 <b>Вам выдан {premium_name}!</b>\n\n"
                f"⏰ Действует до: {premium_until.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"Контент теперь бесплатный для вас!",
                parse_mode='HTML'
            )
        except:
            pass

        call.data = f'admin_user_{target_user_id}'
        admin_user_actions(call)

    elif call.data == 'back_to_menu':
        text = (
            "🔥 <b>Главное меню</b>\n\n"
            f"💰 Новым пользователям +{NEW_USER_BONUS}₽ на баланс!\n"
            f"👥 Пригласи друга и получи +{REFERRAL_BONUS}₽\n\n"
            "📋 Переходи в приватки и наслаждайся:)"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=main_menu_keyboard(), parse_mode='HTML')
        except:
            # Если не получается отредактировать (например, сообщение с фото/видео), отправляем новое
            bot.send_message(call.message.chat.id, text, 
                           reply_markup=main_menu_keyboard(), parse_mode='HTML')
        bot.answer_callback_query(call.id)

    elif call.data == 'profile':
        show_profile(call)

    elif call.data == 'tasks':
        show_tasks(call)

    elif call.data == 'referral_system':
        show_referral_system(call)

    elif call.data == 'favorites':
        show_favorites(call)

    elif call.data == 'fav_next':
        send_favorite_content(call, user_id)

    elif call.data.startswith('add_fav_'):
        handle_add_to_favorites(call)

    elif call.data.startswith('del_fav_'):
        handle_delete_from_favorites(call)

    elif call.data.startswith('del_content_'):
        handle_delete_content(call)

    elif call.data == 'regular_categories':
        show_categories(call, is_vip=False)

    elif call.data == 'vip_categories':
        show_categories(call, is_vip=True)

    elif call.data == 'private_channels':
        show_private_channels_menu(call)

    elif call.data.startswith('private_') and not call.data.startswith('private_channels'):
        show_private_channel_info(call)

    elif call.data.startswith('buy_private_'):
        show_private_payment_options(call)

    elif call.data.startswith('pay_balance_private_'):
        process_balance_private_payment(call)

    elif call.data.startswith('card_private_'):
        process_card_private_payment(call)

    elif call.data.startswith('yoomoney_private_'):
        process_yoomoney_private_payment(call)

    elif call.data.startswith('pay_stars_private_'):
        process_stars_private_payment(call)

    elif call.data.startswith('paid_private_'):
        handle_paid_private(call)

    elif call.data.startswith('confirm_private_'):
        confirm_private_payment(call)

    elif call.data.startswith('reject_private_'):
        reject_private_payment(call)

    elif call.data.startswith('cat_'):
        show_content_type(call)

    elif call.data == 'buy_premium':
        buy_premium_menu(call)

    elif call.data == 'topup':
        topup_menu(call)

    elif call.data == 'topup_card':
        topup_card_menu(call)

    elif call.data == 'topup_yoomoney':
        topup_yoomoney_menu(call)

    elif call.data == 'topup_stars':
        topup_stars_menu(call)

    elif call.data == 'topup_crypto_menu':
        topup_crypto_select_menu(call)

    elif call.data.startswith('topup_ton') or call.data.startswith('topup_usdt_') or call.data.startswith('topup_tron') or call.data.startswith('topup_btc') or call.data.startswith('topup_eth'):
        crypto_type = call.data.replace('topup_', '')
        topup_crypto_menu(call, crypto_type)

    elif call.data.startswith('buy_prem_'):
        process_premium_purchase(call)

    elif call.data.startswith('pay_balance_premium_'):
        process_balance_premium_payment(call)

    elif call.data.startswith('pay_stars_premium_'):
        process_stars_premium_payment(call)

    elif call.data.startswith('card_premium_'):
        premium_type = call.data.split('_')[2]
        price = PRICE_PREMIUM_REGULAR if premium_type == 'regular' else PRICE_PREMIUM_VIP
        premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"

        payment_settings = get_payment_settings('card')
        if not payment_settings or not payment_settings['is_active']:
            bot.answer_callback_query(call.id, "❌ Этот способ оплаты временно недоступен", show_alert=True)
            return

        phone = payment_settings['phone_number']
        bank_name = payment_settings.get('bank_name', '')
        bank_info = f" (Банк: {bank_name})" if bank_name else ""
        text = (
            f"💳 <b>Пополнение через {payment_settings['payment_name']}</b>\n\n"
            f"💰 Сумма: <b>{price}₽</b>\n"
            f"📱 Номер телефона: <code>{phone}</code>{bank_info}\n\n"
            "Переведите указанную сумму по СБП на этот номер.\n"
            "После оплаты нажмите 'Я оплатил' и отправьте скриншот."
        )

        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("✅ Я оплатил", callback_data=f'paid_premium_{premium_type}_card'),
            InlineKeyboardButton("◀️ Назад", callback_data=f'buy_prem_{premium_type}')
        )

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=keyboard, parse_mode='HTML')
        bot.answer_callback_query(call.id)

    elif call.data.startswith('yoomoney_premium_'):
        premium_type = call.data.split('_')[2]
        price = PRICE_PREMIUM_REGULAR if premium_type == 'regular' else PRICE_PREMIUM_VIP
        premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"

        payment_settings = get_payment_settings('yoomoney')
        if not payment_settings or not payment_settings['is_active']:
            bot.answer_callback_query(call.id, "❌ Этот способ оплаты временно недоступен", show_alert=True)
            return

        wallet = payment_settings['wallet_number']
        text = (
            f"💰 <b>Пополнение через {payment_settings['payment_name']}</b>\n\n"
            f"💰 Сумма: <b>{price}₽</b>\n"
            f"💳 Номер кошелька: <code>{wallet}</code>\n\n"
            "После оплаты нажмите 'Я оплатил' и отправьте скриншот."
        )

        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("✅ Я оплатил", callback_data=f'paid_premium_{premium_type}_yoomoney'),
            InlineKeyboardButton("◀️ Назад", callback_data=f'buy_prem_{premium_type}')
        )

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=keyboard, parse_mode='HTML')
        bot.answer_callback_query(call.id)

    elif call.data.startswith('paid_premium_'):
        bot.answer_callback_query(call.id)
        parts = call.data.split('_')
        premium_type = parts[2]
        payment_method = parts[3] if len(parts) > 3 else 'card'
        user_states[user_id] = {
            'waiting_screenshot_premium': True, 
            'premium_type': premium_type,
            'premium_payment_method': payment_method
        }
        bot.edit_message_text(
            "📸 <b>Отлично!</b>\n\n"
            "Теперь отправьте скриншот оплаты.\n"
            "Просто пришлите фото чека в этот чат.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )

    elif call.data.startswith('paid_topup_'):
        bot.answer_callback_query(call.id)
        parts = call.data.split('_')
        amount = int(parts[2])
        payment_method = parts[3] if len(parts) > 3 else 'card'
        user_states[user_id] = {
            'waiting_screenshot_topup': True, 
            'topup_amount': amount,
            'topup_payment_method': payment_method
        }
        bot.edit_message_text(
            "📸 <b>Отлично!</b>\n\n"
            "Теперь отправьте скриншот оплаты.\n"
            "Просто пришлите фото чека в этот чат.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )

    elif call.data.startswith('confirm_payment_'):
        confirm_payment(call)

    elif call.data.startswith('reject_payment_'):
        reject_payment(call)

    elif call.data == 'admin_categories':
        show_admin_categories_menu(call)

    elif call.data == 'admin_cat_add_start':
        admin_add_category(call)

    elif call.data == 'admin_cat_add_regular':
        user_id = call.from_user.id
        user_states[user_id] = {'admin_waiting_new_cat_name': True, 'cat_is_vip': 0}
        text = "✍️ <b>Добавление обычной категории</b>\n\nВведите название категории:"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data='admin_categories'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    elif call.data == 'admin_cat_add_vip':
        user_id = call.from_user.id
        user_states[user_id] = {'admin_waiting_new_cat_name': True, 'cat_is_vip': 1}
        text = "✍️ <b>Добавление VIP категории</b>\n\nВведите название категории:"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data='admin_categories'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    elif call.data == 'admin_cat_del_start':
        admin_delete_category(call)

    elif call.data == 'admin_cat_hide_start':
        admin_hide_category(call)

    elif call.data == 'admin_cat_show_start':
        admin_show_category(call)

    elif call.data == 'admin_payments':
        show_admin_payments_menu(call)

    elif call.data == 'admin_pay_list':
        show_payments_list(call)

    elif call.data == 'admin_pay_edit_select':
        admin_pay_edit_select(call)

    elif call.data.startswith('admin_pay_edit_') and not call.data.startswith('admin_pay_edit_select'):
        admin_pay_edit_menu(call)

    elif call.data.startswith('admin_pay_phone_'):
        payment_type = call.data.split('_')[-1]
        user_states[user_id] = {'admin_edit_pay_phone': payment_type}
        text = "📱 <b>Изменение номера телефона</b>\n\nВведите новый номер телефона (например: 79001234567):"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data=f'admin_pay_edit_{payment_type}'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    elif call.data.startswith('admin_pay_wallet_'):
        payment_type = call.data.split('_')[-1]
        user_states[user_id] = {'admin_edit_pay_wallet': payment_type}
        text = "💳 <b>Изменение номера кошелька</b>\n\nВведите новый номер кошелька:"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data=f'admin_pay_edit_{payment_type}'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    elif call.data == 'admin_pay_toggle_select':
        admin_pay_toggle_select(call)

    elif call.data.startswith('admin_pay_toggle_'):
        admin_pay_toggle(call)

    elif call.data == 'admin_pay_select_bank':
        admin_select_bank_payment(call)

    elif call.data.startswith('admin_pay_bank_select_'):
        payment_type = call.data.split('_')[-1]
        user_states[user_id] = {'admin_select_bank_type': payment_type}
        payment_settings = get_payment_settings(payment_type)
        payment_name = payment_settings.get('payment_name', 'этого способа оплаты') if payment_settings else 'этого способа оплаты'
        text = "🏦 <b>Выберите банк для {}</b>\n\nДоступные банки:".format(payment_name)
        keyboard = InlineKeyboardMarkup(row_width=1)
        banks = [
            ('Альфа-Банк', 'alfa'),
            ('Сбербанк', 'sber'),
            ('ВТБ', 'vtb'),
            ('Тинькофф', 'tinkoff'),
            ('Райффайзен', 'raiffeisen'),
            ('УралСиб', 'uralsib'),
            ('Газпромбанк', 'gazprom'),
            ('БЦ-Финанс', 'bcf'),
            ('Озон Банк', 'ozon'),
            ('Другой банк', 'other')
        ]
        for bank_name, bank_code in banks:
            keyboard.add(InlineKeyboardButton(bank_name, callback_data=f'admin_pay_bank_set_{payment_type}_{bank_code}'))
        keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_pay_select_bank'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    elif call.data.startswith('admin_pay_bank_set_'):
        parts = call.data.split('_')
        payment_type = parts[4]
        bank_code = parts[5]
        
        banks = {
            'alfa': 'Альфа-Банк',
            'sber': 'Сбербанк',
            'vtb': 'ВТБ',
            'tinkoff': 'Тинькофф',
            'raiffeisen': 'Райффайзен',
            'uralsib': 'УралСиб',
            'gazprom': 'Газпромбанк',
            'bcf': 'БЦ-Финанс',
            'ozon': 'Озон Банк',
            'other': 'Другой банк'
        }
        
        bank_name = banks.get(bank_code, 'Неизвестный банк')
        cursor = db_conn.cursor()
        cursor.execute('UPDATE payment_settings SET bank_name = ? WHERE payment_type = ?', (bank_name, payment_type))
        db_conn.commit()
        
        payment_settings = get_payment_settings(payment_type)
        payment_name = payment_settings.get('payment_name', 'способа оплаты') if payment_settings else 'способа оплаты'
        bot.answer_callback_query(call.id, f"✅ Банк '{bank_name}' выбран для {payment_name}", show_alert=True)
        admin_select_bank_payment(call)

    elif call.data == 'admin_tasks':
        show_admin_tasks_menu(call)

    elif call.data == 'admin_tasks_list':
        show_tasks_list(call)

    elif call.data == 'admin_tasks_add':
        admin_add_task_start(call)

    elif call.data.startswith('admin_tasks_add_type_'):
        admin_add_task_type(call)

    elif call.data == 'admin_tasks_edit_select':
        admin_edit_task_select(call)

    elif call.data.startswith('admin_tasks_edit_') and not call.data.startswith('admin_tasks_edit_title_') and not call.data.startswith('admin_tasks_edit_reward_') and not call.data.startswith('admin_tasks_edit_condition_') and not call.data.startswith('admin_tasks_edit_callback_') and not call.data.startswith('admin_tasks_edit_icon_'):
        admin_edit_task_menu(call)

    elif call.data == 'admin_tasks_delete_select':
        admin_delete_task_select(call)

    elif call.data.startswith('admin_tasks_delete_confirm_'):
        admin_delete_task_confirm(call)

    elif call.data.startswith('admin_tasks_delete_yes_'):
        admin_delete_task_execute(call)

    elif call.data.startswith('admin_tasks_toggle_'):
        admin_toggle_task(call)

    elif call.data.startswith('admin_tasks_edit_title_'):
        task_id = int(call.data.split('_')[-1])
        user_states[user_id] = {'admin_edit_task_title': True, 'task_id': task_id}
        bot.edit_message_text("📝 Введите новое название задания:", call.message.chat.id, call.message.message_id, parse_mode='HTML')

    elif call.data.startswith('admin_tasks_edit_reward_'):
        task_id = int(call.data.split('_')[-1])
        user_states[user_id] = {'admin_edit_task_reward': True, 'task_id': task_id}
        bot.edit_message_text("💰 Введите новую награду (в рублях):", call.message.chat.id, call.message.message_id, parse_mode='HTML')

    elif call.data.startswith('admin_tasks_edit_condition_'):
        task_id = int(call.data.split('_')[-1])
        user_states[user_id] = {'admin_edit_task_condition': True, 'task_id': task_id}
        bot.edit_message_text("🔢 Введите новое условие (число) или '-' для удаления:", call.message.chat.id, call.message.message_id, parse_mode='HTML')

    elif call.data.startswith('admin_tasks_edit_callback_'):
        task_id = int(call.data.split('_')[-1])
        user_states[user_id] = {'admin_edit_task_callback': True, 'task_id': task_id}
        bot.edit_message_text("🔘 Введите новый callback_data или '-' для удаления:", call.message.chat.id, call.message.message_id, parse_mode='HTML')

    elif call.data.startswith('admin_tasks_edit_icon_'):
        task_id = int(call.data.split('_')[-1])
        user_states[user_id] = {'admin_edit_task_icon': True, 'task_id': task_id}
        bot.edit_message_text("😀 Введите новую иконку (эмодзи):", call.message.chat.id, call.message.message_id, parse_mode='HTML')

# Проверка достижений
def check_achievements(call):
    user_id = call.from_user.id
    cursor = db_conn.cursor()

    # Получаем статистику
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND bonus_paid = 1', (user_id,))
    referral_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = ? AND amount < 0 AND description LIKE "%Покупка%"', (user_id,))
    content_purchased = cursor.fetchone()[0]

    # Проверяем какие бонусы уже получены
    cursor.execute('SELECT description FROM transactions WHERE user_id = ? AND description LIKE "%Достижение:%"', (user_id,))
    received_achievements = [row[0] for row in cursor.fetchall()]

    bonuses_to_give = []

    # Проверяем достижения по рефералам
    if referral_count >= 1 and "Достижение: 1 реферал" not in received_achievements:
        bonuses_to_give.append(("Достижение: 1 реферал", 10))

    if referral_count >= 3 and "Достижение: 3 реферала" not in received_achievements:
        bonuses_to_give.append(("Достижение: 3 реферала", 25))

    if referral_count >= 5 and "Достижение: 5 рефералов" not in received_achievements:
        bonuses_to_give.append(("Достижение: 5 рефералов", 50))

    # Проверяем достижение по покупкам
    if content_purchased >= 10 and "Достижение: 10 покупок" not in received_achievements:
        bonuses_to_give.append(("Достижение: 10 покупок", 15))

    if bonuses_to_give:
        total_bonus = sum([amount for _, amount in bonuses_to_give])

        # Начисляем все бонусы
        for description, amount in bonuses_to_give:
            cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
            cursor.execute(
                'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
                (user_id, amount, description)
            )

        db_conn.commit()

        # Получаем новый баланс
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        new_balance = cursor.fetchone()[0]

        achievements_text = "\n".join([f"• {desc} (+{amt}₽)" for desc, amt in bonuses_to_give])

        text = (
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"Вы получили новые достижения:\n\n"
            f"{achievements_text}\n\n"
            f"💰 Начислено: {total_bonus}₽\n"
            f"💵 Новый баланс: {new_balance:.2f}₽"
        )

        bot.answer_callback_query(call.id, f"🎉 Получено {total_bonus}₽!", show_alert=True)
    else:
        text = (
            "ℹ️ <b>Достижения</b>\n\n"
            "У вас пока нет новых достижений для получения.\n\n"
            "Продолжайте приглашать друзей и покупать контент!"
        )
        bot.answer_callback_query(call.id, "Новых достижений нет", show_alert=True)

    bot.send_message(call.message.chat.id, text, parse_mode='HTML')
    show_tasks(call)

# Профиль пользователя
def show_profile(call):
    user_id = call.from_user.id
    user = get_user(user_id)

    if user is None:
        # Можно либо создать пользователя, либо показать ошибку
        bot.answer_callback_query(call.id, "Профиль не найден. Попробуйте /start", show_alert=True)
        # или автоматически создать
        # get_user(user_id)  # вызовет создание
        # user = get_user(user_id)
        return

    is_premium, premium_type, premium_until = has_premium(user_id)

    text = f"👤 <b>Твой профиль</b>\n\n💰 Баланс: <b>{user[1]:.2f}₽</b>\n\n"

    if is_premium and premium_until:
        premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"
        remaining_time = premium_until - datetime.now()
        hours = int(remaining_time.total_seconds() // 3600)
        minutes = int((remaining_time.total_seconds() % 3600) // 60)
        text += f"⭐ У вас активный {premium_name}\n⏰ Осталось: {hours}ч {minutes}мин\n\n"

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("👥 Реферальная система", callback_data='referral_system'),
        InlineKeyboardButton("🎁 Задания", callback_data='tasks'),
        InlineKeyboardButton("💳 Пополнить баланс", callback_data='topup'),
        #InlineKeyboardButton("🛒 Купить премиум", callback_data='buy_premium'),
        InlineKeyboardButton("💬 Тех. поддержка", url=SUPPORT_BOT),
        InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Реферальная система
def show_referral_system(call):
    user_id = call.from_user.id

    cursor = db_conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
    referral_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND bonus_paid = 1', (user_id,))
    active_referrals = cursor.fetchone()[0]

    cursor.execute(
        'SELECT SUM(amount) FROM transactions WHERE user_id = ? AND description LIKE "%Реферальный бонус%"',
        (user_id,)
    )
    total_earned = cursor.fetchone()[0] or 0

    ref_link = f"https://t.me/{bot.get_me().username}?start=ref{user_id}"

    text = (
        f"👥 <b>Реферальная система</b>\n\n"
        f"🔗 Ваша реферальная ссылка:\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 Статистика:\n"
        f"👤 Приглашено друзей: <b>{referral_count}</b>\n"
        f"✅ Активных рефералов: <b>{active_referrals}</b>\n"
        f"💰 Заработано: <b>{total_earned:.2f}₽</b>\n\n"
        f"💡 <b>Как работает:</b>\n"
        f"1. Пригласите друга по вашей ссылке\n"
        f"2. Друг должен выполнить задание с подпиской на канал\n"
        f"3. После этого вы получаете <b>{REFERRAL_BONUS}₽</b>!"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='profile'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Задания
def show_tasks(call):
    user_id = call.from_user.id
    cursor = db_conn.cursor()

    # Получаем все активные задания из БД
    cursor.execute('SELECT id, task_type, task_key, title, description, reward, condition_value, is_active, callback_data, icon, created_at, channel_link, channel_id FROM tasks WHERE is_active = 1 ORDER BY task_type, id')
    tasks = cursor.fetchall()

    # Получаем выполненные задания пользователя
    cursor.execute('SELECT task_key FROM user_tasks WHERE user_id = ?', (user_id,))
    completed_task_keys = [row[0] for row in cursor.fetchall()]

    # Получаем статистику пользователя для проверки условий
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND bonus_paid = 1', (user_id,))
    referral_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id = ? AND amount < 0 AND description LIKE "%Покупка%"', (user_id,))
    content_purchased = cursor.fetchone()[0]

    # Проверяем ежедневный вход
    cursor.execute('SELECT last_daily_claim FROM users WHERE user_id = ?', (user_id,))
    last_claim = cursor.fetchone()
    daily_available = True
    if last_claim and last_claim[0]:
        try:
            last_claim_date = datetime.fromisoformat(last_claim[0]).date()
            today = datetime.now().date()
            daily_available = last_claim_date < today
        except:
            daily_available = True

    # Формируем текст с заданиями
    text = "🎁 <b>Задания и награды</b>\n\n"

    task_types = {'daily': '📅 Ежедневные', 'subscription': '📢 Подписки', 'achievement': '🏆 Достижения'}
    current_type = None
    keyboard = InlineKeyboardMarkup(row_width=1)

    for task in tasks:
        task_id, task_type, task_key, title, description, reward, condition_value, is_active, callback_data, icon, created_at, channel_link, channel_id = task

        # Добавляем заголовок типа заданий
        if task_type != current_type:
            current_type = task_type
            text += f"\n<b>{task_types.get(task_type, task_type)}</b>\n"

        # Проверяем выполнено ли задание
        is_completed = task_key in completed_task_keys

        # Проверяем условия для достижений
        if task_type == 'achievement' and condition_value:
            if 'реферал' in title.lower() or 'друг' in title.lower():
                if referral_count < condition_value:
                    is_completed = False
            elif 'покуп' in title.lower() or 'материал' in title.lower():
                if content_purchased < condition_value:
                    is_completed = False

        # Проверяем ежедневные задания
        if task_type == 'daily' and 'ежедневн' in title.lower():
            is_completed = not daily_available

        status_icon = '✅' if is_completed else '❌'
        text += f"{status_icon} {icon} {title} (+{reward}₽)\n"

        # Добавляем кнопку если задание не выполнено
        if not is_completed:
            # Для заданий подписки используем универсальный callback
            if task_type == 'subscription':
                keyboard.add(InlineKeyboardButton(f"{icon} {title}", callback_data=f'task_{task_key}'))
            # Для остальных используем callback_data из БД
            elif callback_data:
                keyboard.add(InlineKeyboardButton(f"{icon} {title} (+{reward}₽)", callback_data=callback_data))

    text += "\n💡 Выполняй задания и получай бонусы!"

    # Создаем новую клавиатуру с кнопкой спина вверху
    top_keyboard = InlineKeyboardMarkup(row_width=1)
    if can_spin_daily(user_id):
        top_keyboard.add(InlineKeyboardButton("🎰 Ежедневный спин", callback_data='daily_spin_info'))
    
    # Добавляем остальные кнопки
    top_keyboard.row_width = 1
    for row in keyboard.keyboard:
        for btn in row:
            top_keyboard.add(btn)
    
    # Кнопка для проверки достижений
    if referral_count >= 1:
        top_keyboard.add(InlineKeyboardButton("🔄 Проверить достижения", callback_data='check_achievements'))

    top_keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='profile'))
    keyboard = top_keyboard

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Категории
def show_categories(call, is_vip=False):
    categories = VIP_CATEGORIES if is_vip else REGULAR_CATEGORIES
    category_type = "VIP" if is_vip else "Обычные"

    keyboard = InlineKeyboardMarkup(row_width=1)
    for key, name in categories.items():
        keyboard.add(InlineKeyboardButton(name, callback_data=f'cat_{key}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu'))

    text = f"📂 {category_type} категории\n\nВыберите категорию:"

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Выбор типа контента
def show_content_type(call):
    category = call.data.split('_')[1]
    is_vip = category in VIP_CATEGORIES

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🎥 Видео", callback_data=f'get_video_{category}'))

    if not is_vip:
        keyboard.add(InlineKeyboardButton("📷 Фото", callback_data=f'get_photo_{category}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='vip_categories' if is_vip else 'regular_categories'))

    category_name = VIP_CATEGORIES.get(category) or REGULAR_CATEGORIES.get(category)
    text = f"📂 {category_name}\n\nВыберите тип контента:"

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Показ избранного
def show_favorites(call):
    user_id = call.from_user.id
    favorites = get_user_favorites(user_id)
    
    if not favorites:
        text = (
            "💖 <b>Избранное</b>\n\n"
            "У вас пока нет избранного контента.\n\n"
            "Добавляйте видео в избранное при просмотре!"
        )
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu'))
        
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                 reply_markup=keyboard, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, text,
                           reply_markup=keyboard, parse_mode='HTML')
        try:
            bot.answer_callback_query(call.id)
        except:
            pass
        return
    
    # Отправляем случайное видео из избранного
    send_favorite_content(call, user_id)

def send_favorite_content(call, user_id):
    """Отправить контент из избранного"""
    favorite = get_random_favorite(user_id)
    
    if not favorite:
        text = (
            "💖 <b>Избранное</b>\n\n"
            "У вас пока нет избранного контента."
        )
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu'))
        
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                 reply_markup=keyboard, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
        return
    
    file_id = favorite.get('file_id')
    content_type = favorite.get('type', 'video')
    
    try:
        # Создаем клавиатуру: "ещё" "гл меню" и "удалить"
        fav_keyboard = InlineKeyboardMarkup(row_width=2)
        fav_keyboard.add(
            InlineKeyboardButton("🔄 Ещё", callback_data='fav_next'),
            InlineKeyboardButton("🏠 Гл меню", callback_data='back_to_menu')
        )
        fav_keyboard.add(
            InlineKeyboardButton("🗑 Удалить", callback_data=f'del_fav_{file_id[:50]}')
        )
        
        if content_type == 'video':
            bot.send_video(call.message.chat.id, file_id, reply_markup=fav_keyboard)
        else:
            bot.send_photo(call.message.chat.id, file_id, reply_markup=fav_keyboard)
        
        try:
            bot.answer_callback_query(call.id)
        except:
            pass
    except Exception as e:
        print(f"Ошибка отправки избранного: {e}")
        # Если файл недоступен, удаляем из избранного
        remove_from_favorites(user_id, file_id)
        # Пробуем отправить следующее
        send_favorite_content(call, user_id)

def handle_add_to_favorites(call):
    """Добавить контент в избранное"""
    user_id = call.from_user.id
    # callback: add_fav_{content_type}_{file_id}
    parts = call.data.split('_')
    content_type = parts[2]
    file_id = '_'.join(parts[3:])
    
    # Ищем полный file_id
    content_dict = load_content()
    full_file_id = None
    for key, data in content_dict.items():
        if isinstance(data, dict) and 'file_id' in data:
            if data['file_id'].startswith(file_id):
                full_file_id = data['file_id']
                break
    
    if full_file_id:
        if add_to_favorites(user_id, full_file_id, content_type):
            try:
                bot.answer_callback_query(call.id, "⭐ Добавлено в избранное!", show_alert=False)
            except:
                pass
        else:
            try:
                bot.answer_callback_query(call.id, "Уже в избранном", show_alert=False)
            except:
                pass
    else:
        # Если не нашли в content_dict, используем file_id как есть
        if add_to_favorites(user_id, file_id, content_type):
            try:
                bot.answer_callback_query(call.id, "⭐ Добавлено в избранное!", show_alert=False)
            except:
                pass
        else:
            try:
                bot.answer_callback_query(call.id, "Уже в избранном", show_alert=False)
            except:
                pass

def handle_delete_from_favorites(call):
    """Удалить контент из избранного"""
    user_id = call.from_user.id
    # callback: del_fav_{file_id}
    parts = call.data.split('_')
    file_id_partial = '_'.join(parts[2:])
    
    # Ищем полный file_id в избранном
    favorites = get_user_favorites(user_id)
    for fav in favorites:
        if fav.get('file_id', '').startswith(file_id_partial):
            remove_from_favorites(user_id, fav['file_id'])
            break
    
    try:
        bot.answer_callback_query(call.id, "🗑 Удалено из избранного!", show_alert=False)
    except:
        pass
    
    # Отправляем следующее видео из избранного
    send_favorite_content(call, user_id)

def handle_delete_content(call):
    """Удалить контент из базы данных (только для админа)"""
    user_id = call.from_user.id
    
    # Проверяем права админа
    if user_id not in ADMIN_IDS:
        try:
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
        except:
            pass
        return
    
    # callback: del_content_{content_type}_{category}_{file_id_partial}
    parts = call.data.split('_')
    content_type = parts[2]
    category = parts[3]
    file_id_partial = '_'.join(parts[4:])
    
    # Загружаем контент
    content_dict = load_content()
    
    # Ищем и удаляем файл по частичному file_id
    deleted = False
    deleted_key = None
    for key, data in list(content_dict.items()):
        if isinstance(data, dict) and 'file_id' in data:
            if data['file_id'].startswith(file_id_partial):
                deleted_key = key
                del content_dict[key]
                deleted = True
                break
    
    if deleted:
        # Сохраняем обновленный контент
        save_content(content_dict)
        
        try:
            bot.answer_callback_query(call.id, "✅ Контент удален из базы!", show_alert=True)
        except:
            pass
        
        # Отправляем сообщение об успешном удалении
        text = (
            f"🗑️ <b>Контент удален!</b>\n\n"
            f"📁 Тип: {content_type}\n"
            f"📂 Категория: {category}\n"
            f"🔑 Ключ: {deleted_key}\n\n"
            f"✅ Файл успешно удален из базы данных."
        )
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("🔄 Ещё контент", callback_data=f'get_{content_type}_{category}'),
            InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu')
        )
        
        try:
            bot.send_message(call.message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
        except:
            pass
    else:
        try:
            bot.answer_callback_query(call.id, "❌ Контент не найден в базе!", show_alert=True)
        except:
            pass

# Оплата премиума через Stars
def process_stars_premium_payment(call):
    user_id = call.from_user.id
    premium_type = call.data.split('_')[3]
    price = PRICE_PREMIUM_REGULAR if premium_type == 'regular' else PRICE_PREMIUM_VIP
    premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"

    # Рассчитываем стоимость в Stars
    stars_amount = int(price / STARS_TO_RUB_RATE)

    # Генерируем ссылку на платежного бота
    payment_bot_username = "Zvezdapizd_bot"
    payment_link = f"https://t.me/{payment_bot_username}?start=premium_{user_id}_{premium_type}_{price}"

    text = (
        f"⭐ <b>Оплата премиума через Telegram Stars</b>\n\n"
        f"📦 Товар: {premium_name}\n"
        f"💰 Стоимость: {price}₽\n"
        f"⭐ К оплате: {stars_amount} Stars\n\n"
        f"💱 Курс: 1 Star = {STARS_TO_RUB_RATE}₽\n\n"
        f"Для оплаты перейдите в платежного бота:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("💳 Перейти к оплате", url=payment_link),
        InlineKeyboardButton("◀️ Назад", callback_data='buy_premium')
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

    bot.answer_callback_query(call.id)

# Оплата премиума балансом
def process_balance_premium_payment(call):
    user_id = call.from_user.id
    premium_type = call.data.split('_')[3]
    price = PRICE_PREMIUM_REGULAR if premium_type == 'regular' else PRICE_PREMIUM_VIP
    premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"

    user = get_user(user_id)
    user_balance = user[1]

    # Проверяем баланс
    if user_balance < price:
        bot.answer_callback_query(
            call.id,
            f"❌ Недостаточно средств! Нужно {price}₽, у вас {user_balance:.2f}₽",
            show_alert=True
        )
        return

    # Списываем средства и выдаем премиум
    cursor = db_conn.cursor()
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (price, user_id))

    premium_until = datetime.now() + timedelta(hours=24)

    if premium_type == 'regular':
        cursor.execute('UPDATE users SET premium_regular_until = ? WHERE user_id = ?', 
                     (premium_until.isoformat(), user_id))
    else:
        cursor.execute('UPDATE users SET premium_vip_until = ? WHERE user_id = ?', 
                     (premium_until.isoformat(), user_id))

    cursor.execute(
        'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
        (user_id, -price, f"Покупка {premium_name}")
    )
    db_conn.commit()

    # Получаем новый баланс
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    new_balance = cursor.fetchone()[0]

    text = (
        f"🎉 <b>Премиум успешно активирован!</b>\n\n"
        f"⭐ Тип: {premium_name}\n"
        f"⏰ Действует до: {premium_until.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"💰 Списано с баланса: {price}₽\n"
        f"💵 Остаток: {new_balance:.2f}₽\n\n"
        f"Контент теперь бесплатный для вас!\n"
        f"Приятного использования!"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

    bot.answer_callback_query(call.id, "✅ Премиум активирован!")

# Покупка премиума
def buy_premium_menu(call):
    text = (
        "⭐ <b>Премиум подписки</b>\n\n"
        f"1️⃣ <b>Премиум (обычные)</b> - {PRICE_PREMIUM_REGULAR}₽\n"
        "• Безлимитный доступ к обычным категориям на 24ч\n"
        "• Контент становится бесплатным\n"
        "• Задержка 10 сек между запросами\n\n"
        f"2️⃣ <b>VIP Премиум</b> - {PRICE_PREMIUM_VIP}₽\n"
        "• Безлимитный доступ ко ВСЕМ категориям на 24ч\n"
        "• Контент становится бесплатным\n"
        "• Задержка 10 сек между запросами\n\n"
        "Выберите тип премиума:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f"⭐ Премиум ({PRICE_PREMIUM_REGULAR}₽)", callback_data='buy_prem_regular'),
        InlineKeyboardButton(f"💎 VIP ({PRICE_PREMIUM_VIP}₽)", callback_data='buy_prem_vip'),
        InlineKeyboardButton("◀️ Назад", callback_data='profile')
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Меню пополнения
def topup_menu(call):
    text = (
        "💳 <b>Пополнение баланса</b>\n\n"
        "Выберите способ оплаты:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)

    # Получаем активные способы оплаты
    active_payments = get_active_payment_methods()

    # Проверяем наличие активных криптовалют
    has_crypto = False
    for payment_type, phone, wallet, name, bank_name in active_payments:
        if payment_type in ['ton', 'usdt_ton', 'tron', 'btc', 'eth', 'usdt_eth', 'usdt_sol']:
            has_crypto = True
            break

    for payment_type, phone, wallet, name, bank_name in active_payments:
        if payment_type == 'card':
            bank_info = f" (Банк: {bank_name})" if bank_name else ""
            keyboard.add(InlineKeyboardButton(f"💳 {name}{bank_info}", callback_data='topup_card'))
        elif payment_type == 'yoomoney':
            keyboard.add(InlineKeyboardButton(f"💰 {name}", callback_data='topup_yoomoney'))
        elif payment_type == 'stars':
            keyboard.add(InlineKeyboardButton(f"⭐ {name}", callback_data='topup_stars'))

    # Добавляем одну кнопку для всех криптовалют
    if has_crypto:
        keyboard.add(InlineKeyboardButton("₿ Криптовалюта", callback_data='topup_crypto_menu'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='profile'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Пополнение картой
def topup_card_menu(call):
    user_id = call.from_user.id
    user_states[user_id] = {'waiting_topup_amount': True, 'payment_method': 'card'}

    text = (
        "💳 <b>Пополнение картой</b>\n\n"
        "Введите сумму пополнения от 10₽ до 5000₽:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='topup'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Пополнение ЮMoney
def topup_yoomoney_menu(call):
    user_id = call.from_user.id
    user_states[user_id] = {'waiting_topup_amount': True, 'payment_method': 'yoomoney'}

    text = (
        "💰 <b>Пополнение через ЮMoney</b>\n\n"
        "Введите сумму пополнения от 10₽ до 5000₽:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='topup'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Пополнение звездами
def topup_stars_menu(call):
    user_id = call.from_user.id
    user_states[user_id] = {'waiting_stars_amount': True}

    text = (
        f"⭐ <b>Пополнение через Telegram Stars</b>\n\n"
        f"💱 Курс: 1 Star = {STARS_TO_RUB_RATE}₽\n\n"
        f"Введите сумму пополнения в рублях (от 5₽ до 3000₽):"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='topup'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Меню выбора криптовалюты
def topup_crypto_select_menu(call):
    text = (
        "₿ <b>Пополнение криптовалютой</b>\n\n"
        "Выберите криптовалюту:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)

    # Получаем активные криптовалюты
    active_payments = get_active_payment_methods()

    for payment_type, phone, wallet, name, bank_name in active_payments:
        if payment_type in ['ton', 'usdt_ton', 'tron', 'btc', 'eth', 'usdt_eth', 'usdt_sol']:
            keyboard.add(InlineKeyboardButton(f"₿ {name}", callback_data=f'topup_{payment_type}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='topup'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Пополнение криптовалютой
def topup_crypto_menu(call, crypto_type):
    user_id = call.from_user.id
    user_states[user_id] = {'waiting_crypto_amount': True, 'crypto_type': crypto_type}

    payment_settings = get_payment_settings(crypto_type)
    if not payment_settings or not payment_settings['is_active']:
        bot.answer_callback_query(call.id, "❌ Этот способ оплаты временно недоступен", show_alert=True)
        return

    text = (
        f"₿ <b>Пополнение через {payment_settings['payment_name']}</b>\n\n"
        f"Введите сумму пополнения в рублях (от 100₽ до 50000₽):"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='topup'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Обработка покупки премиума
def process_premium_purchase(call):
    user_id = call.from_user.id
    premium_type = 'regular' if 'regular' in call.data else 'vip'
    price = PRICE_PREMIUM_REGULAR if premium_type == 'regular' else PRICE_PREMIUM_VIP
    premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"

    user = get_user(user_id)
    user_balance = user[1]

    user_states[user_id] = {'buying_premium_type': premium_type, 'buying_premium_price': price}

    text = (
        f"💳 <b>Оплата: {premium_name}</b>\n\n"
        f"💰 Стоимость: <b>{price}₽</b>\n"
        f"💵 Ваш баланс: <b>{user_balance:.2f}₽</b>\n\n"
        "Выберите способ оплаты:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)

    # Если хватает баланса, добавляем кнопку оплаты балансом
    if user_balance >= price:
        keyboard.add(
            InlineKeyboardButton(f"💰 Оплатить балансом ({price}₽)", callback_data=f'pay_balance_premium_{premium_type}')
        )

    # Получаем активные способы оплаты
    active_payments = get_active_payment_methods()

    for payment_type, phone, wallet, name, bank_name in active_payments:
        if payment_type == 'stars':
            stars_amount = int(price / STARS_TO_RUB_RATE)
            keyboard.add(InlineKeyboardButton(f"⭐ {name} ({stars_amount} Stars)", callback_data=f'pay_stars_premium_{premium_type}'))
        elif payment_type == 'card':
            bank_info = f" (Банк: {bank_name})" if bank_name else ""
            keyboard.add(InlineKeyboardButton(f"💳 {name}{bank_info}", callback_data=f'card_premium_{premium_type}'))
        elif payment_type == 'yoomoney':
            keyboard.add(InlineKeyboardButton(f"💰 {name}", callback_data=f'yoomoney_premium_{premium_type}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='buy_premium'))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=keyboard, parse_mode='HTML')

# Обработка сообщений
@bot.message_handler(content_types=['photo', 'video', 'text'])
def handle_message(message):
    user_id = message.from_user.id

    # Админ вводит ID пользователя для управления
    if user_id in user_states and user_states[user_id].get('admin_waiting_user_id'):
        if message.content_type == 'text':
            target_user_id = None

            # Проверяем, это username или ID
            if message.text.startswith('@'):
                # Пытаемся найти пользователя по username
                username_search = message.text[1:]
                cursor = db_conn.cursor()
                # Ищем по username в таблице users
                cursor.execute('SELECT user_id FROM users WHERE username = ?', (username_search,))
                result = cursor.fetchone()
                if result:
                    target_user_id = result[0]
            else:
                try:
                    target_user_id = int(message.text)
                except:
                    pass

            if target_user_id:
                user_states.pop(user_id, None)

                # Проверяем, существует ли пользователь
                cursor = db_conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (target_user_id,))
                user = cursor.fetchone()

                if not user:
                    bot.send_message(message.chat.id, "❌ Пользователь не найден в базе данных! Попробуйте еще раз:")
                    user_states[user_id] = {'admin_waiting_user_id': True}
                    return

                # Проверка блокировки
                cursor.execute('SELECT reason FROM blocked_users WHERE user_id = ?', (target_user_id,))
                blocked = cursor.fetchone()
                is_blocked = blocked is not None

                # Информация о премиуме
                is_premium, premium_type, premium_until = has_premium(target_user_id)

                # Информация о рефералах
                cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (target_user_id,))
                total_referrals = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND bonus_paid = 1', (target_user_id,))
                paid_referrals = cursor.fetchone()[0]

                # Информация о покупках
                cursor.execute('''
                    SELECT COUNT(*), SUM(ABS(amount)) FROM transactions 
                    WHERE user_id = ? AND amount < 0 AND description LIKE "%Покупка%"
                ''', (target_user_id,))
                purchase_data = cursor.fetchone()
                total_purchases = purchase_data[0] or 0
                total_spent = purchase_data[1] or 0

                # Информация о пополнениях
                cursor.execute('''
                    SELECT SUM(amount) FROM transactions 
                    WHERE user_id = ? AND amount > 0 AND (description LIKE "%Пополнение%" OR description LIKE "%бонус%")
                ''', (target_user_id,))
                total_topups = cursor.fetchone()[0] or 0

                # Дата регистрации
                reg_date = datetime.fromisoformat(user[9]).strftime('%d.%m.%Y %H:%M') if user[9] else "Неизвестно"

                # Проверка роли рекламщика
                cursor.execute('SELECT is_advertiser FROM user_roles WHERE user_id = ?', (target_user_id,))
                role_data = cursor.fetchone()
                is_advertiser = role_data[0] if role_data else False

                text = (
                    f"👤 <b>Пользователь ID: {target_user_id}</b>\n\n"
                    f"💰 Баланс: <b>{user[1]:.2f}₽</b>\n"
                    f"🚫 Статус: {'Заблокирован' if is_blocked else 'Активен'}\n"
                    f"📢 Роль: {'Рекламщик' if is_advertiser else 'Обычный пользователь'}\n"
                    f"📅 Регистрация: {reg_date}\n\n"
                )

                if is_premium and premium_until:
                    premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"
                    text += f"⭐ Премиум: {premium_name} до {premium_until.strftime('%d.%m %H:%M')}\n\n"

                text += (
                    f"👥 <b>Рефералы:</b>\n"
                    f"• Всего: {total_referrals}\n"
                    f"• Активных: {paid_referrals}\n\n"
                    f"💳 <b>Активность:</b>\n"
                    f"• Покупок: {total_purchases} ({total_spent:.2f}₽)\n"
                    f"• Пополнений: {total_topups:.2f}₽\n\n"
                    "Выберите действие:"
                )

                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    InlineKeyboardButton("💰 Установить баланс", callback_data=f'admin_set_balance_{target_user_id}'),
                    InlineKeyboardButton("➕ Добавить баланс", callback_data=f'admin_add_balance_{target_user_id}'),
                    InlineKeyboardButton("⭐ Выдать премиум", callback_data=f'admin_give_premium_{target_user_id}')
                )

                if is_advertiser:
                    keyboard.add(InlineKeyboardButton("📢 Убрать роль рекламщика", callback_data=f'admin_remove_adv_{target_user_id}'))
                else:
                    keyboard.add(InlineKeyboardButton("📢 Выдать роль рекламщика", callback_data=f'admin_give_adv_{target_user_id}'))

                if is_blocked:
                    keyboard.add(InlineKeyboardButton("✅ Разблокировать", callback_data=f'admin_unblock_{target_user_id}'))
                else:
                    keyboard.add(InlineKeyboardButton("🚫 Заблокировать", callback_data=f'admin_block_{target_user_id}'))

                keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin'))

                bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
            else:
                bot.send_message(message.chat.id, "❌ Пользователь не найден! Попробуйте еще раз:")
                user_states[user_id] = {'admin_waiting_user_id': True}
        return

    # Админ вводит сумму для установки баланса
    elif user_id in user_states and user_states[user_id].get('admin_waiting_balance'):
        if message.content_type == 'text':
            try:
                amount = float(message.text)
                target_user_id = user_states[user_id]['admin_set_balance_for']

                cursor = db_conn.cursor()
                cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (amount, target_user_id))
                cursor.execute(
                    'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
                    (target_user_id, amount, f"Установка баланса администратором")
                )
                db_conn.commit()

                user_states.pop(user_id, None)

                bot.send_message(
                    message.chat.id,
                    f"✅ Баланс пользователя {target_user_id} установлен на {amount}₽",
                    parse_mode='HTML'
                )

                # Уведомляем пользователя
                try:
                    bot.send_message(
                        target_user_id,
                        f"💰 <b>Баланс изменен</b>\n\nВаш баланс установлен на {amount}₽",
                        parse_mode='HTML'
                    )
                except:
                    pass
            except ValueError:
                bot.send_message(message.chat.id, "❌ Введите корректную сумму!")
        return

    # Админ вводит сумму для добавления баланса
    elif user_id in user_states and user_states[user_id].get('admin_waiting_add_balance'):
        if message.content_type == 'text':
            try:
                amount = float(message.text)
                target_user_id = user_states[user_id]['admin_add_balance_for']

                cursor = db_conn.cursor()
                cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, target_user_id))
                cursor.execute(
                    'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
                    (target_user_id, amount, f"Добавление баланса администратором")
                )
                db_conn.commit()

                # Получаем новый баланс
                cursor.execute('SELECT balance FROM users WHERE user_id = ?', (target_user_id,))
                new_balance = cursor.fetchone()[0]

                user_states.pop(user_id, None)

                bot.send_message(
                    message.chat.id,
                    f"✅ Пользователю {target_user_id} добавлено {amount}₽\nНовый баланс: {new_balance}₽",
                    parse_mode='HTML'
                )

                # Уведомляем пользователя
                try:
                    bot.send_message(
                        target_user_id,
                        f"💰 <b>Пополнение баланса</b>\n\nВам добавлено {amount}₽\nНовый баланс: {new_balance}₽",
                        parse_mode='HTML'
                    )
                except:
                    pass
            except ValueError:
                bot.send_message(message.chat.id, "❌ Введите корректную сумму!")
        return

    # Админ вводит причину блокировки
    elif user_id in user_states and user_states[user_id].get('admin_waiting_block_reason'):
        if message.content_type == 'text':
            reason = message.text
            target_user_id = user_states[user_id]['admin_block_user']

            cursor = db_conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO blocked_users (user_id, reason) VALUES (?, ?)',
                (target_user_id, reason)
            )
            db_conn.commit()

            user_states.pop(user_id, None)

            bot.send_message(
                message.chat.id,
                f"✅ Пользователь {target_user_id} заблокирован!\nПричина: {reason}",
                parse_mode='HTML'
            )

            # Уведомляем пользователя
            try:
                bot.send_message(
                    target_user_id,
                    f"🚫 <b>Вы заблокированы</b>\n\nПричина: {reason}\n\nДля разблокировки обратитесь в поддержку: {SUPPORT_BOT}",
                    parse_mode='HTML'
                )
            except:
                pass
        return

    # Админ изменяет количество видео приватки
    elif user_id in user_states and user_states[user_id].get('admin_edit_priv_vidcount'):
        if message.content_type == 'text':
            try:
                new_video_count = int(message.text)
                priv_key = user_states[user_id]['admin_edit_priv_vidcount']

                if priv_key in PRIVATE_CHANNELS:
                    PRIVATE_CHANNELS[priv_key]['video_count'] = new_video_count
                    user_states.pop(user_id, None)

                    bot.send_message(
                        message.chat.id,
                        f"✅ Количество видео обновлено!\n\n"
                        f"Приватка: {PRIVATE_CHANNELS[priv_key]['name']}\n"
                        f"Новое количество: {new_video_count} видео",
                        parse_mode='HTML'
                    )
                else:
                    bot.send_message(message.chat.id, "❌ Приватка не найдена!")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Введите корректное количество видео (число)!")
        return

    # Админ изменяет цену приватки
    elif user_id in user_states and user_states[user_id].get('admin_edit_priv_price'):
        if message.content_type == 'text':
            try:
                new_price = int(message.text)
                priv_key = user_states[user_id]['admin_edit_priv_price']

                if priv_key in PRIVATE_CHANNELS:
                    PRIVATE_CHANNELS[priv_key]['price'] = new_price
                    user_states.pop(user_id, None)

                    bot.send_message(
                        message.chat.id,
                        f"✅ Цена обновлена!\n\n"
                        f"Приватка: {PRIVATE_CHANNELS[priv_key]['name']}\n"
                        f"Новая цена: {new_price}₽",
                        parse_mode='HTML'
                    )
                else:
                    bot.send_message(message.chat.id, "❌ Приватка не найдена!")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Введите корректную цену (число)!")
        return

    # Админ изменяет описание приватки
    elif user_id in user_states and user_states[user_id].get('admin_edit_priv_desc'):
        if message.content_type == 'text':
            new_desc = message.text
            priv_key = user_states[user_id]['admin_edit_priv_desc']

            if priv_key in PRIVATE_CHANNELS:
                PRIVATE_CHANNELS[priv_key]['description'] = new_desc
                user_states.pop(user_id, None)

                bot.send_message(
                    message.chat.id,
                    f"✅ Описание обновлено!\n\n"
                    f"Приватка: {PRIVATE_CHANNELS[priv_key]['name']}\n"
                    f"Новое описание: {new_desc}",
                    parse_mode='HTML'
                )
            else:
                bot.send_message(message.chat.id, "❌ Приватка не найдена!")
        return

    # Админ изменяет название приватки
    elif user_id in user_states and user_states[user_id].get('admin_edit_priv_name'):
        if message.content_type == 'text':
            new_name = message.text
            priv_key = user_states[user_id]['admin_edit_priv_name']

            if priv_key in PRIVATE_CHANNELS:
                old_name = PRIVATE_CHANNELS[priv_key]['name']
                PRIVATE_CHANNELS[priv_key]['name'] = new_name
                user_states.pop(user_id, None)

                bot.send_message(
                    message.chat.id,
                    f"✅ Название обновлено!\n\n"
                    f"Старое: {old_name}\n"
                    f"Новое: {new_name}",
                    parse_mode='HTML'
                )
            else:
                bot.send_message(message.chat.id, "❌ Приватка не найдена!")
        return

    # Админ добавляет новую категорию
    elif user_id in user_states and user_states[user_id].get('admin_waiting_new_cat_name'):
        if message.content_type == 'text':
            cat_name = message.text
            cat_key = cat_name.lower().replace(' ', '_').replace('🎓', '').replace('💃', '').replace('👭', '').replace('👬', '').replace('🔥', '').replace('😇', '').replace('🖤', '').replace('🌑', '').strip()
            is_vip = user_states[user_id].get('cat_is_vip', 0)

            cursor = db_conn.cursor()

            # Проверяем, не существует ли уже
            cursor.execute('SELECT id FROM categories WHERE category_key = ?', (cat_key,))
            if cursor.fetchone():
                bot.send_message(message.chat.id, "❌ Категория с таким ключом уже существует!")
                return

            # Добавляем в БД
            cursor.execute(
                'INSERT INTO categories (category_key, category_name, is_vip) VALUES (?, ?, ?)',
                (cat_key, cat_name, is_vip)
            )
            db_conn.commit()

            # Перезагружаем категории
            load_categories_from_db()

            user_states.pop(user_id, None)

            cat_type = "VIP" if is_vip else "Обычная"
            bot.send_message(
                message.chat.id,
                f"✅ Категория добавлена!\n\n"
                f"Название: {cat_name}\n"
                f"Ключ: <code>{cat_key}</code>\n"
                f"Тип: {cat_type}",
                parse_mode='HTML'
            )
        return

    # Админ удаляет категорию
    elif user_id in user_states and user_states[user_id].get('admin_waiting_del_cat_name'):
        if message.content_type == 'text':
            cat_key = message.text

            cursor = db_conn.cursor()
            cursor.execute('SELECT category_name FROM categories WHERE category_key = ?', (cat_key,))
            result = cursor.fetchone()

            if result:
                cat_name = result[0]
                # Удаляем из БД
                cursor.execute('DELETE FROM categories WHERE category_key = ?', (cat_key,))
                db_conn.commit()

                # Перезагружаем категории
                load_categories_from_db()

                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, f"✅ Категория '{cat_name}' удалена!", parse_mode='HTML')
            else:
                bot.send_message(message.chat.id, "❌ Категория не найдена! Введите ключ категории (например: students)")
        return

    # Админ скрывает категорию
    elif user_id in user_states and user_states[user_id].get('admin_waiting_hide_cat_name'):
        if message.content_type == 'text':
            cat_key = message.text

            cursor = db_conn.cursor()
            cursor.execute('SELECT category_name FROM categories WHERE category_key = ?', (cat_key,))
            result = cursor.fetchone()

            if result:
                cat_name = result[0]
                cursor.execute('UPDATE categories SET is_active = 0 WHERE category_key = ?', (cat_key,))
                db_conn.commit()
                load_categories_from_db()

                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, f"✅ Категория '{cat_name}' скрыта!", parse_mode='HTML')
            else:
                bot.send_message(message.chat.id, "❌ Категория не найдена!")
        return

    # Админ показывает категорию
    elif user_id in user_states and user_states[user_id].get('admin_waiting_show_cat_name'):
        if message.content_type == 'text':
            cat_key = message.text

            cursor = db_conn.cursor()
            cursor.execute('SELECT category_name FROM categories WHERE category_key = ?', (cat_key,))
            result = cursor.fetchone()

            if result:
                cat_name = result[0]
                cursor.execute('UPDATE categories SET is_active = 1 WHERE category_key = ?', (cat_key,))
                db_conn.commit()
                load_categories_from_db()

                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, f"✅ Категория '{cat_name}' теперь видна!", parse_mode='HTML')
            else:
                bot.send_message(message.chat.id, "❌ Категория не найдена!")
        return

    # Админ отправляет сообщение для рассылки
    elif user_id in user_states and user_states[user_id].get('admin_waiting_broadcast'):
        cursor = db_conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        all_users = cursor.fetchall()

        total_users = len(all_users)
        success_count = 0
        fail_count = 0
        excluded_count = 0

        # Отправляем стартовое сообщение о прогрессе
        progress_msg = bot.send_message(
            message.chat.id,
            f"📢 <b>Рассылка началась...</b>\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"✅ Отправлено: 0\n"
            f"❌ Не доставлено: 0\n"
            f"⏭️ Исключено: 0\n"
            f"📊 Прогресс: 0%",
            parse_mode='HTML'
        )

        # Рассылка с обновлением прогресса
        for idx, user in enumerate(all_users, 1):
            target_id = user[0]
            
            # Проверяем, не исключён ли пользователь
            if is_excluded_from_broadcast(target_id):
                excluded_count += 1
                time.sleep(0.01)
            else:
                try:
                    bot.copy_message(target_id, message.chat.id, message.message_id)
                    success_count += 1
                    time.sleep(0.03)  # Уменьшена задержка для ускорения
                except Exception as e:
                    fail_count += 1
                    # Исключаем пользователя при ошибке отправки
                    exclude_from_broadcast(target_id)

            # Обновляем прогресс каждые 10 пользователей или в конце
            if idx % 10 == 0 or idx == total_users:
                progress_percent = int((idx / total_users) * 100)
                try:
                    bot.edit_message_text(
                        f"📢 <b>Рассылка в процессе...</b>\n\n"
                        f"👥 Всего пользователей: {total_users}\n"
                        f"✅ Отправлено: {success_count}\n"
                        f"❌ Не доставлено: {fail_count}\n"
                        f"⏭️ Исключено: {excluded_count}\n"
                        f"📊 Прогресс: {progress_percent}%",
                        message.chat.id,
                        progress_msg.message_id,
                        parse_mode='HTML'
                    )
                except:
                    pass

        user_states.pop(user_id, None)

        # Финальное сообщение
        bot.edit_message_text(
            f"📢 <b>Рассылка завершена!</b>\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"✅ Отправлено: {success_count}\n"
            f"❌ Не доставлено: {fail_count}\n"
            f"⏭️ Исключено: {excluded_count}\n"
            f"📊 Прогресс: 100%",
            message.chat.id,
            progress_msg.message_id,
            parse_mode='HTML'
        )
        return

    # Админ добавляет задание - ввод данных по шагам
    elif user_id in user_states and user_states[user_id].get('admin_adding_task'):
        if message.content_type == 'text':
            state = user_states[user_id]
            step = state.get('step')
            task_type = state.get('task_type')

            if step == 'key':
                state['task_key'] = message.text
                state['step'] = 'title'
                bot.send_message(message.chat.id, "📝 Введите название задания:")
            elif step == 'title':
                state['title'] = message.text
                state['step'] = 'reward'
                bot.send_message(message.chat.id, "💰 Введите награду (в рублях):")
            elif step == 'reward':
                try:
                    reward = float(message.text)
                    state['reward'] = reward
                    # Для подписки следующий шаг - иконка
                    if task_type == 'subscription':
                        state['step'] = 'icon'
                        bot.send_message(message.chat.id, "😀 Введите иконку (эмодзи):")
                    else:
                        state['step'] = 'condition'
                        bot.send_message(message.chat.id, "🔢 Введите условие (число) или '-' если не нужно:")
                except ValueError:
                    bot.send_message(message.chat.id, "❌ Введите корректное число для награды:")
            elif step == 'condition':
                condition_value = None if message.text == '-' else int(message.text) if message.text.isdigit() else None
                state['condition_value'] = condition_value
                state['step'] = 'callback'
                bot.send_message(message.chat.id, "🔘 Введите callback_data или '-' если не нужно:")
            elif step == 'callback':
                callback_data = None if message.text == '-' else message.text
                state['callback_data'] = callback_data
                state['step'] = 'icon'
                bot.send_message(message.chat.id, "😀 Введите иконку (эмодзи):")
            elif step == 'icon':
                icon = message.text
                state['icon'] = icon

                # Для подписки следующий шаг - ссылка на канал
                if task_type == 'subscription':
                    state['step'] = 'channel_link'
                    bot.send_message(message.chat.id, "🔗 Введите ссылку на канал (она отобразится в виде кнопки 'Подписаться'):")
                else:
                    # Для других типов заданий сохраняем сразу
                    cursor = db_conn.cursor()
                    try:
                        cursor.execute(
                            'INSERT INTO tasks (task_type, task_key, title, reward, condition_value, callback_data, icon) VALUES (?, ?, ?, ?, ?, ?, ?)',
                            (state['task_type'], state['task_key'], state['title'], state['reward'], 
                             state.get('condition_value'), state.get('callback_data'), icon)
                        )
                        db_conn.commit()
                        bot.send_message(message.chat.id, f"✅ Задание '{state['title']}' успешно добавлено!", parse_mode='HTML')
                    except sqlite3.IntegrityError:
                        bot.send_message(message.chat.id, "❌ Задание с таким ключом уже существует!")

                    user_states.pop(user_id, None)
            elif step == 'channel_link':
                state['channel_link'] = message.text
                state['step'] = 'channel_id'
                bot.send_message(message.chat.id, "🆔 Введите ID канала (например: -1002345678901):")
            elif step == 'channel_id':
                state['channel_id'] = message.text

                # Сохраняем задание подписки
                cursor = db_conn.cursor()
                try:
                    cursor.execute(
                        'INSERT INTO tasks (task_type, task_key, title, reward, icon, channel_link, channel_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (state['task_type'], state['task_key'], state['title'], state['reward'], 
                         state['icon'], state['channel_link'], state['channel_id'])
                    )
                    db_conn.commit()
                    bot.send_message(message.chat.id, f"✅ Задание '{state['title']}' успешно добавлено!", parse_mode='HTML')
                except sqlite3.IntegrityError:
                    bot.send_message(message.chat.id, "❌ Задание с таким ключом уже существует!")

                user_states.pop(user_id, None)
        return

    # Админ редактирует название задания
    elif user_id in user_states and user_states[user_id].get('admin_edit_task_title'):
        if message.content_type == 'text':
            task_id = user_states[user_id]['task_id']
            new_title = message.text
            cursor = db_conn.cursor()
            cursor.execute('UPDATE tasks SET title = ? WHERE id = ?', (new_title, task_id))
            db_conn.commit()
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id, "✅ Название обновлено!")
        return

    # Админ редактирует награду задания
    elif user_id in user_states and user_states[user_id].get('admin_edit_task_reward'):
        if message.content_type == 'text':
            try:
                task_id = user_states[user_id]['task_id']
                new_reward = float(message.text)
                cursor = db_conn.cursor()
                cursor.execute('UPDATE tasks SET reward = ? WHERE id = ?', (new_reward, task_id))
                db_conn.commit()
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, "✅ Награда обновлена!")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Введите корректное число:")
        return

    # Админ редактирует условие задания
    elif user_id in user_states and user_states[user_id].get('admin_edit_task_condition'):
        if message.content_type == 'text':
            task_id = user_states[user_id]['task_id']
            condition_value = None if message.text == '-' else int(message.text) if message.text.isdigit() else None
            cursor = db_conn.cursor()
            cursor.execute('UPDATE tasks SET condition_value = ? WHERE id = ?', (condition_value, task_id))
            db_conn.commit()
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id, "✅ Условие обновлено!")
        return

    # Админ редактирует callback задания
    elif user_id in user_states and user_states[user_id].get('admin_edit_task_callback'):
        if message.content_type == 'text':
            task_id = user_states[user_id]['task_id']
            callback_data = None if message.text == '-' else message.text
            cursor = db_conn.cursor()
            cursor.execute('UPDATE tasks SET callback_data = ? WHERE id = ?', (callback_data, task_id))
            db_conn.commit()
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id, "✅ Callback обновлен!")
        return

    # Админ редактирует иконку задания
    elif user_id in user_states and user_states[user_id].get('admin_edit_task_icon'):
        if message.content_type == 'text':
            task_id = user_states[user_id]['task_id']
            new_icon = message.text
            cursor = db_conn.cursor()
            cursor.execute('UPDATE tasks SET icon = ? WHERE id = ?', (new_icon, task_id))
            db_conn.commit()
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id, "✅ Иконка обновлена!")
        return

    # Админ изменяет номер телефона для оплаты
    elif user_id in user_states and user_states[user_id].get('admin_edit_pay_phone'):
        if message.content_type == 'text':
            payment_type = user_states[user_id]['admin_edit_pay_phone']
            new_phone = message.text
            cursor = db_conn.cursor()
            cursor.execute('UPDATE payment_settings SET phone_number = ? WHERE payment_type = ?', (new_phone, payment_type))
            db_conn.commit()
            user_states.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                f"✅ Номер телефона обновлен!\n\n"
                f"Новый номер: <code>{new_phone}</code>",
                parse_mode='HTML'
            )
        return

    # Админ изменяет номер кошелька для оплаты
    elif user_id in user_states and user_states[user_id].get('admin_edit_pay_wallet'):
        if message.content_type == 'text':
            payment_type = user_states[user_id]['admin_edit_pay_wallet']
            new_wallet = message.text
            cursor = db_conn.cursor()
            cursor.execute('UPDATE payment_settings SET wallet_number = ? WHERE payment_type = ?', (new_wallet, payment_type))
            db_conn.commit()
            user_states.pop(user_id, None)
            bot.send_message(
                message.chat.id,
                f"✅ Номер кошелька обновлен!\n\nНовый номер: <code>{new_wallet}</code>",
                parse_mode='HTML'
            )
        return

    # Админ добавляет контент в режиме сканирования
    elif user_id in user_states and user_states[user_id].get('scanning_mode'):
        if message.content_type in ['photo', 'video']:
            file_type = 'photo' if message.content_type == 'photo' else 'video'

            user_states[user_id]['current_file_type'] = file_type
            user_states[user_id]['current_message'] = message
            user_states[user_id]['selected_categories'] = []

            # Показываем категории для выбора
            all_categories = {**REGULAR_CATEGORIES, **VIP_CATEGORIES}
            keyboard = InlineKeyboardMarkup(row_width=2)

            for key, name in all_categories.items():
                keyboard.add(InlineKeyboardButton(name, callback_data=f'add_cat_{key}'))

            keyboard.add(InlineKeyboardButton("✅ Добавить в выбранные", callback_data='finish_adding'))

            bot.send_message(
                message.chat.id,
                f"📂 <b>Выберите категории для {file_type}</b>\n\n"
                "Нажмите на категории, в которые нужно добавить контент.\n"
                "Затем нажмите 'Добавить в выбранные'.",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте видео или фото.")

    # Пользователь вводит сумму пополнения картой или ЮMoney
    elif user_id in user_states and user_states[user_id].get('waiting_topup_amount'):
        if message.content_type == 'text':
            try:
                amount = int(message.text)
                if 10 <= amount <= 5000:
                    payment_method = user_states[user_id].get('payment_method', 'card')
                    user_states[user_id]['waiting_topup_amount'] = False

                    # Получаем настройки способа оплаты
                    payment_settings = get_payment_settings(payment_method)

                    if not payment_settings or not payment_settings['is_active']:
                        bot.send_message(message.chat.id, "❌ Этот способ оплаты временно недоступен.")
                        return

                    if payment_method == 'yoomoney':
                        wallet = payment_settings['wallet_number']
                        text = (
                            f"💰 <b>Пополнение через {payment_settings['payment_name']}</b>\n\n"
                            f"💰 Сумма: <b>{amount}₽</b>\n"
                            f"💳 Номер кошелька: <code>{wallet}</code>\n\n"
                            "После оплаты нажмите 'Я оплатил' и отправьте скриншот."
                        )
                        payment_emoji = "💰"
                    else:
                        phone = payment_settings['phone_number']
                        bank_name = payment_settings.get('bank_name', '')
                        bank_info = f" (Банк: {bank_name})" if bank_name else ""
                        text = (
                            f"💳 <b>Пополнение через {payment_settings['payment_name']}</b>\n\n"
                            f"💰 Сумма: <b>{amount}₽</b>\n"
                            f"📱 Номер телефона: <code>{phone}</code>{bank_info}\n\n"
                            "Переведите указанную сумму по СБП на этот номер.\n"
                            "После оплаты нажмите 'Я оплатил' и отправьте скриншот."
                        )
                        payment_emoji = "💳"

                    keyboard = InlineKeyboardMarkup(row_width=1)
                    keyboard.add(
                        InlineKeyboardButton("✅ Я оплатил", callback_data=f'paid_topup_{amount}_{payment_method}'),
                        InlineKeyboardButton("◀️ Назад", callback_data='topup')
                    )

                    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
                else:
                    bot.send_message(message.chat.id, "❌ Сумма должна быть от 10₽ до 5000₽. Попробуйте снова:")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Введите корректную сумму числом (например, 100):")
        else:
            bot.send_message(message.chat.id, "❌ Пожалуйста, введите сумму числом.")

    # Пользователь вводит сумму пополнения звездами
    elif user_id in user_states and user_states[user_id].get('waiting_stars_amount'):
        if message.content_type == 'text':
            try:
                amount_rub = int(message.text)
                if 5 <= amount_rub <= 3000:
                    user_states.pop(user_id, None)

                    # Генерируем ссылку на платежного бота
                    payment_bot_username = "Zvezdapizd_bot"
                    payment_link = f"https://t.me/{payment_bot_username}?start=pay_{user_id}_{amount_rub}"

                    text = (
                        f"⭐ <b>Пополнение через Telegram Stars</b>\n\n"
                        f"💰 Сумма: <b>{amount_rub}₽</b>\n\n"
                        f"Для оплаты перейдите в платежного бота:"
                    )

                    keyboard = InlineKeyboardMarkup(row_width=1)
                    keyboard.add(
                        InlineKeyboardButton("💳 Перейти к оплате", url=payment_link),
                        InlineKeyboardButton("◀️ Назад", callback_data='topup')
                    )

                    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
                else:
                    bot.send_message(message.chat.id, "❌ Сумма должна быть от 5₽ до 3000₽. Попробуйте снова:")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Введите корректную сумму числом (например, 100):")
        else:
            bot.send_message(message.chat.id, "❌ Пожалуйста, введите сумму числом.")

    # Пользователь вводит сумму пополнения криптовалютой
    elif user_id in user_states and user_states[user_id].get('waiting_crypto_amount'):
        if message.content_type == 'text':
            try:
                amount_rub = int(message.text)
                if 100 <= amount_rub <= 50000:
                    crypto_type = user_states[user_id].get('crypto_type')
                    user_states.pop(user_id, None)

                    payment_settings = get_payment_settings(crypto_type)
                    if not payment_settings:
                        bot.send_message(message.chat.id, "❌ Ошибка получения данных оплаты.")
                        return

                    wallet = payment_settings['wallet_number']
                    crypto_amount = get_crypto_amount(amount_rub, crypto_type)
                    
                    # Обновляем курсы перед показом
                    update_crypto_rates()
                    
                    text = (
                        f"₿ <b>Пополнение через {payment_settings['payment_name']}</b>\n\n"
                        f"💰 Сумма: <b>{amount_rub}₽</b>\n"
                        f"₿ К оплате: <b>{crypto_amount}</b>\n"
                        f"💳 Адрес кошелька:\n<code>{wallet}</code>\n\n"
                        f"⚠️ <b>Важно:</b>\n"
                        f"1. Отправьте точную сумму на указанный адрес\n"
                        f"2. После оплаты нажмите 'Я оплатил' и отправьте скриншот транзакции\n"
                        f"3. Курс актуален в течение 15 минут"
                    )

                    keyboard = InlineKeyboardMarkup(row_width=1)
                    keyboard.add(
                        InlineKeyboardButton("✅ Я оплатил", callback_data=f'paid_topup_{amount_rub}_{crypto_type}'),
                        InlineKeyboardButton("◀️ Назад", callback_data='topup')
                    )

                    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
                else:
                    bot.send_message(message.chat.id, "❌ Сумма должна быть от 100₽ до 50000₽. Попробуйте снова:")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Введите корректную сумму числом (например, 500):")
        else:
            bot.send_message(message.chat.id, "❌ Пожалуйста, введите сумму числом.")

    # Пользователь отправляет скриншот оплаты премиума
    elif user_id in user_states and user_states[user_id].get('waiting_screenshot_premium'):
        if message.content_type == 'photo':
            photo = message.photo[-1]
            screenshot_file_id = photo.file_id

            premium_type = user_states[user_id].get('premium_type')
            payment_method = user_states[user_id].get('premium_payment_method', 'card')
            price = PRICE_PREMIUM_REGULAR if premium_type == 'regular' else PRICE_PREMIUM_VIP
            username = message.from_user.username or "Нет username"

            # Определяем название метода оплаты
            if payment_method == 'yoomoney':
                payment_method_name = "ЮMoney"
                payment_emoji = "💰"
            else:
                payment_method_name = "Карта"
                payment_emoji = "💳"

            cursor = db_conn.cursor()
            cursor.execute(
                'INSERT INTO payment_requests (user_id, username, premium_type, screenshot_file_id) VALUES (?, ?, ?, ?)',
                (user_id, username, f'{premium_type}_{payment_method}', screenshot_file_id)
            )
            db_conn.commit()
            request_id = cursor.lastrowid

            bot.send_message(
                message.chat.id,
                "⏳ <b>Ваша заявка отправлена на проверку!</b>\n\n"
                "Ожидайте подтверждения от администратора.\n"
                "Обычно это занимает 5-15 минут.",
                parse_mode='HTML'
            )

            premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"
            admin_text = (
                f"{payment_emoji} <b>Новая заявка на оплату премиума #{request_id}</b>\n\n"
                f"👤 Пользователь: @{username}\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📦 Товар: {premium_name}\n"
                f"💰 Сумма: {price}₽\n"
                f"💳 Способ оплаты: {payment_method_name}\n\n"
                f"📸 Скриншот оплаты:"
            )

            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("✅ Подтвердить", callback_data=f'confirm_payment_{request_id}'),
                InlineKeyboardButton("❌ Отклонить", callback_data=f'reject_payment_{request_id}')
            )

            for admin_id in ADMIN_IDS:
                try:
                    bot.send_photo(admin_id, screenshot_file_id, caption=admin_text, 
                                 reply_markup=keyboard, parse_mode='HTML')
                except:
                    pass

            user_states.pop(user_id, None)
        else:
            bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте скриншот оплаты (фото).")

    # Пользователь отправляет скриншот оплаты приватки
    elif user_id in user_states and user_states[user_id].get('waiting_screenshot_private'):
        if message.content_type == 'photo':
            photo = message.photo[-1]
            screenshot_file_id = photo.file_id

            private_type = user_states[user_id].get('private_type')
            payment_method = user_states[user_id].get('private_payment_method', 'card')
            private_data = PRIVATE_CHANNELS[private_type]
            price = private_data['price']
            username = message.from_user.username or "Нет username"

            # Определяем название метода оплаты
            if payment_method == 'yoomoney':
                payment_method_name = "ЮMoney"
                payment_emoji = "💰"
            else:
                payment_method_name = "Карта"
                payment_emoji = "💳"

            cursor = db_conn.cursor()
            cursor.execute(
                'INSERT INTO payment_requests (user_id, username, premium_type, screenshot_file_id) VALUES (?, ?, ?, ?)',
                (user_id, username, f'private_{private_type}_{payment_method}', screenshot_file_id)
            )
            db_conn.commit()
            request_id = cursor.lastrowid

            bot.send_message(
                message.chat.id,
                "⏳ <b>Ваша заявка отправлена на проверку!</b>\n\n"
                "Ожидайте подтверждения от администратора.\n"
                "Обычно это занимает 5-15 минут.",
                parse_mode='HTML'
            )

            admin_text = (
                f"{payment_emoji} <b>Новая заявка на приватку #{request_id}</b>\n\n"
                f"👤 Пользователь: @{username}\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📦 Товар: {private_data['name']}\n"
                f"💰 Сумма: {price}₽\n"
                f"💳 Способ оплаты: {payment_method_name}\n\n"
                f"📸 Скриншот оплаты:"
            )

            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("✅ Подтвердить", callback_data=f'confirm_private_{request_id}'),
                InlineKeyboardButton("❌ Отклонить", callback_data=f'reject_private_{request_id}')
            )

            for admin_id in ADMIN_IDS:
                try:
                    bot.send_photo(admin_id, screenshot_file_id, caption=admin_text, 
                                 reply_markup=keyboard, parse_mode='HTML')
                except:
                    pass

            user_states.pop(user_id, None)
        else:
            bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте скриншот оплаты (фото).")

    # Пользователь отправляет скриншот пополнения баланса
    elif user_id in user_states and user_states[user_id].get('waiting_screenshot_topup'):
        if message.content_type == 'photo':
            photo = message.photo[-1]
            screenshot_file_id = photo.file_id

            amount = user_states[user_id].get('topup_amount')
            payment_method = user_states[user_id].get('topup_payment_method', 'card')
            username = message.from_user.username or "Нет username"

            # Определяем название метода оплаты
            if payment_method == 'yoomoney':
                payment_method_name = "ЮMoney"
                payment_emoji = "💰"
            else:
                payment_method_name = "Карта"
                payment_emoji = "💳"

            cursor = db_conn.cursor()
            cursor.execute(
                'INSERT INTO payment_requests (user_id, username, premium_type, screenshot_file_id) VALUES (?, ?, ?, ?)',
                (user_id, username, f'topup_{amount}_{payment_method}', screenshot_file_id)
            )
            db_conn.commit()
            request_id = cursor.lastrowid

            bot.send_message(
                message.chat.id,
                "⏳ <b>Ваша заявка отправлена на проверку!</b>\n\n"
                "Ожидайте подтверждения от администратора.\n"
                "Обычно это занимает 5-15 минут.",
                parse_mode='HTML'
            )

            admin_text = (
                f"{payment_emoji} <b>Новая заявка на пополнение #{request_id}</b>\n\n"
                f"👤 Пользователь: @{username}\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"💰 Сумма пополнения: {amount}₽\n"
                f"💳 Способ оплаты: {payment_method_name}\n\n"
                f"📸 Скриншот оплаты:"
            )

            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("✅ Выдать", callback_data=f'confirm_topup_{request_id}_{amount}'),
                InlineKeyboardButton("❌ Отклонить", callback_data=f'reject_topup_{request_id}')
            )

            for admin_id in ADMIN_IDS:
                try:
                    bot.send_photo(admin_id, screenshot_file_id, caption=admin_text, 
                                 reply_markup=keyboard, parse_mode='HTML')
                except:
                    pass

            user_states.pop(user_id, None)
        else:
            bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте скриншот оплаты (фото).")

# Подтверждение оплаты
def confirm_payment(call):
    request_id = int(call.data.split('_')[2])

    cursor = db_conn.cursor()
    cursor.execute('SELECT user_id, premium_type FROM payment_requests WHERE id = ?', (request_id,))
    request = cursor.fetchone()

    if request:
        user_id, premium_type_full = request

        # Извлекаем тип премиума (regular или vip) из строки вида 'regular_card' или 'vip_yoomoney'
        premium_type = premium_type_full.split('_')[0]

        cursor.execute('UPDATE payment_requests SET status = ? WHERE id = ?', ('confirmed', request_id))

        premium_until = datetime.now() + timedelta(hours=24)

        if premium_type == 'regular':
            cursor.execute('UPDATE users SET premium_regular_until = ? WHERE user_id = ?', 
                         (premium_until.isoformat(), user_id))
        else:
            cursor.execute('UPDATE users SET premium_vip_until = ? WHERE user_id = ?', 
                         (premium_until.isoformat(), user_id))

        db_conn.commit()

        premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"
        try:
            bot.send_message(
                user_id,
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"🎉 Вам выдан {premium_name} на 24 часа!\n"
                f"⏰ Действует до: {premium_until.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"Контент теперь бесплатный для вас!\n"
                f"Приятного использования!",
                parse_mode='HTML'
            )
        except:
            pass

        bot.edit_message_caption(
            caption=call.message.caption + f"\n\n✅ <b>Подтверждено администратором</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )

# Отклонение оплаты
def reject_payment(call):
    request_id = int(call.data.split('_')[2])

    cursor = db_conn.cursor()
    cursor.execute('SELECT user_id FROM payment_requests WHERE id = ?', (request_id,))
    request = cursor.fetchone()

    if request:
        user_id = request[0]

        cursor.execute('UPDATE payment_requests SET status = ? WHERE id = ?', ('rejected', request_id))
        db_conn.commit()

        try:
            bot.send_message(
                user_id,
                "❌ <b>Оплата отклонена</b>\n\n"
                "К сожалению, ваша заявка была отклонена.\n"
                "Возможные причины:\n"
                "• Неверная сумма\n"
                "• Некорректный скриншот\n\n"
                "Обратитесь в поддержку для уточнения деталей.",
                parse_mode='HTML'
            )
        except:
            pass

        bot.edit_message_caption(
            caption=call.message.caption + f"\n\n❌ <b>Отклонено администратором</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )

# Обработка выбора категории для контента
def handle_category_selection(call):
    user_id = call.from_user.id
    category = call.data.split('_')[2]

    if user_id in user_states:
        selected = user_states[user_id].get('selected_categories', [])

        if category in selected:
            selected.remove(category)
            bot.answer_callback_query(call.id, f"❌ {category} убрана")
        else:
            selected.append(category)
            bot.answer_callback_query(call.id, f"✅ {category} добавлена")

        user_states[user_id]['selected_categories'] = selected

        # Обновляем клавиатуру с отметками
        all_categories = {**REGULAR_CATEGORIES, **VIP_CATEGORIES}
        keyboard = InlineKeyboardMarkup(row_width=2)

        for key, name in all_categories.items():
            prefix = "✅ " if key in selected else ""
            keyboard.add(InlineKeyboardButton(prefix + name, callback_data=f'add_cat_{key}'))

        keyboard.add(InlineKeyboardButton("✅ Добавить в выбранные", callback_data='finish_adding'))

        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
        except:
            pass

# Завершение добавления контента
def finish_content_adding(call):
    user_id = call.from_user.id

    if user_id in user_states:
        file_type = user_states[user_id].get('current_file_type')
        selected_categories = user_states[user_id].get('selected_categories', [])
        original_message = user_states[user_id].get('current_message')

        if not selected_categories:
            bot.answer_callback_query(call.id, "❌ Выберите хотя бы одну категорию!", show_alert=True)
            return

        try:
            # Получаем file_id и метаданные напрямую из оригинального сообщения
            if file_type == 'video':
                file_id = original_message.video.file_id
                file_unique_id = original_message.video.file_unique_id
                file_size = original_message.video.file_size
            else:
                file_id = original_message.photo[-1].file_id
                file_unique_id = original_message.photo[-1].file_unique_id
                file_size = original_message.photo[-1].file_size

            # Проверяем, существует ли уже этот файл в базе (усиленная защита)
            content_dict = load_content()
            file_exists = False
            existing_item = None

            for key, data in content_dict.items():
                if isinstance(data, dict):
                    # Проверка 1: по file_id (основная)
                    if data.get('file_id') == str(file_id):
                        file_exists = True
                        existing_item = data
                        break
                    # Проверка 2: по file_unique_id (защита от переотправки)
                    if file_unique_id and data.get('file_unique_id') == str(file_unique_id):
                        file_exists = True
                        existing_item = data
                        break
                    # Проверка 3: по размеру файла и времени (защита от быстрого добавления)
                    if file_size and data.get('file_size') == file_size and data.get('type') == file_type:
                        timestamp_diff = abs(time.time() - data.get('timestamp_ms', 0))
                        if timestamp_diff < 2:  # Если файл того же размера добавлен менее 2 секунд назад
                            file_exists = True
                            existing_item = data
                            break

            if file_exists and existing_item:
                existing_categories = existing_item.get('categories', [])
                all_categories = {**REGULAR_CATEGORIES, **VIP_CATEGORIES}
                existing_cat_names = [all_categories.get(c, c) for c in existing_categories]

                bot.answer_callback_query(call.id, "⚠️ Этот файл уже есть в базе!", show_alert=True)
                bot.edit_message_text(
                    f"⚠️ <b>Файл уже существует в базе!</b>\n\n"
                    f"📁 Тип: {file_type}\n"
                    f"📂 Текущие категории: {', '.join(existing_cat_names)}\n"
                    f"🆔 File ID: {file_id[:30]}...\n"
                    f"📏 Размер: {file_size} байт\n\n"
                    f"📤 Отправьте другой контент или /stop_scan для завершения",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode='HTML'
                )

                # Очищаем данные о текущем файле
                user_states[user_id].pop('current_file_type', None)
                user_states[user_id].pop('selected_categories', None)
                user_states[user_id].pop('current_message', None)
                return

            # Сохраняем file_id в JSON с метаданными
            if add_content_to_storage(file_id, selected_categories, file_type, file_size, file_unique_id):
                pass
            else:
                bot.answer_callback_query(call.id, "❌ Ошибка сохранения!", show_alert=True)
                return

            all_categories = {**REGULAR_CATEGORIES, **VIP_CATEGORIES}
            category_names = [all_categories.get(c, c) for c in selected_categories]

            bot.edit_message_text(
                f"✅ <b>Контент успешно добавлен в JSON!</b>\n\n"
                f"📁 Тип: {file_type}\n"
                f"📂 Категории ({len(selected_categories)}): {', '.join(category_names)}\n"
                f"🆔 File ID: {file_id[:30]}...\n\n"
                f"📤 Отправьте следующий контент или /stop_scan для завершения",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='HTML'
            )

            # Очищаем только данные о текущем файле, но оставляем режим сканирования
            user_states[user_id].pop('current_file_type', None)
            user_states[user_id].pop('selected_categories', None)
            user_states[user_id].pop('current_message', None)

        except Exception as e:
            print(f"Ошибка сохранения контента: {e}")
            bot.answer_callback_query(call.id, f"❌ Ошибка сохранения: {str(e)}", show_alert=True)

def show_daily_spin_info(call):
    """Показать информацию о ежедневном спине"""
    user_id = call.from_user.id
    
    if not can_spin_daily(user_id):
        bot.answer_callback_query(call.id, "❌ Вы уже крутили спин сегодня!", show_alert=True)
        return
    
    text = (
        "🎰 <b>Испытай удачу!</b>\n\n"
        "Получи от 10 до 100₽ на баланс!\n\n"
        "<b>Результаты:</b>\n"
        "⭐ ⭐ ⭐ (777) = <b>100₽ ДЖЕКПОТ!</b>\n"
        "🍎 🍎 🍎 (3 одинаковых) = <b>50₽</b>\n"
        "🍎 🍊 🍋 (рандомные) = <b>10-15₽</b>\n\n"
        "Жми кнопку ниже и смотри, что выпадет!"
    )
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🎰 Испытать удачу", callback_data='daily_spin_execute'))
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='tasks'))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=keyboard, parse_mode='HTML')
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
    
    bot.answer_callback_query(call.id)

def do_daily_spin(call):
    """Выполнить ежедневный спин и показать результат"""
    user_id = call.from_user.id
   
    # Проверка, можно ли крутить сегодня
    if not can_spin_daily(user_id):
        bot.answer_callback_query(call.id, "❌ Вы уже крутили спин сегодня!", show_alert=True)
        return
   
    # Выполняем спин и получаем результат + награду
    spin_result, reward = perform_daily_spin(user_id)
   
    # Эмодзи для слотов
    slots_emoji = {1: '🍎', 2: '🍊', 3: '🍋', 4: '🍌', 5: '🍉', 6: '🍓', 7: '⭐'}
    spin_display = ' '.join([slots_emoji.get(s, str(s)) for s in spin_result])
   
    # Формируем заголовок и сообщение в зависимости от результата
    if spin_result == [7, 7, 7]:
        title = "🎉 ДЖЕКПОТ! 777!"
        msg = f"Невероятно! Вы выбросили 777!\n\n{spin_display}\n\n💰 Ваш выигрыш: <b>100₽</b>"
    elif spin_result[0] == spin_result[1] == spin_result[2]:
        title = "🎊 ВЫИГРЫШ!"
        emoji = slots_emoji.get(spin_result[0], str(spin_result[0]))
        msg = f"Три одинаковых символа!\n\n{spin_display}\n\n💰 Ваш выигрыш: <b>50₽</b>"
    else:
        title = "🎰 Спин"
        msg = f"{spin_display}\n\n💰 Ваш выигрыш: <b>{reward}₽</b>"
   
    # Получаем актуальный баланс
    cursor = db_conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    if row is None:
        bot.answer_callback_query(call.id, "Профиль не найден. Нажмите /start", show_alert=True)
        return
    
    new_balance = row[0]  # здесь уже безопасно берём значение
   
    # Финальное сообщение
    text = f"{title}\n\n{msg}\n\n💵 Ваш баланс: <b>{new_balance:.2f}₽</b>\n\nВернитесь завтра за новым спином!"
   
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🏠 К заданиям", callback_data='tasks'))
   
    # Пытаемся отредактировать сообщение, если не получается — отправляем новое
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    except Exception:
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
   
    # Уведомление о выигрыше (без алерта, чтобы не раздражать)
    bot.answer_callback_query(call.id, f"✅ +{reward}₽!", show_alert=False)

# Функция получения ежедневного бонуса
def claim_daily_bonus(call):
    user_id = call.from_user.id
    cursor = db_conn.cursor()

    # Проверяем, можно ли получить бонус
    cursor.execute('SELECT last_daily_claim FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    can_claim = True
    if result and result[0]:
        try:
            last_claim_date = datetime.fromisoformat(result[0]).date()
            today = datetime.now().date()
            can_claim = last_claim_date < today
        except:
            can_claim = True

    if not can_claim:
        bot.answer_callback_query(call.id, "❌ Вы уже получили ежедневный бонус сегодня!", show_alert=True)
        return

    # Начисляем бонус
    cursor.execute('UPDATE users SET balance = balance + 10, last_daily_claim = ? WHERE user_id = ?', 
                  (datetime.now().isoformat(), user_id))
    cursor.execute(
        'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
        (user_id, 10, "Ежедневный бонус")
    )
    db_conn.commit()

    # Получаем новый баланс
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    new_balance = cursor.fetchone()[0]

    text = (
        f"🎁 <b>Ежедневный бонус получен!</b>\n\n"
        f"💰 Ваш баланс пополнен на 10₽\n"
        f"💵 Текущий баланс: {new_balance:.2f}₽\n\n"
        f"Возвращайтесь завтра за новым бонусом!"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu'))

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=keyboard, parse_mode='HTML')
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')

    bot.answer_callback_query(call.id, "✅ +10₽ начислено!", show_alert=True)

# Показ задания на подписку
def show_channel_subscription_task(call, channel_id, channel_link, channel_num):
    user_id = call.from_user.id

    text = (
        f"📢 <b>Подписка на канал {channel_num}</b>\n\n"
        f"💰 Награда: +10₽\n\n"
        f"1️⃣ Нажмите кнопку 'Подписаться'\n"
        f"2️⃣ Подпишитесь на канал\n"
        f"3️⃣ Вернитесь и нажмите 'Проверить'\n\n"
        f"После проверки подписки вы получите бонус!"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📢 Подписаться", url=channel_link),
        InlineKeyboardButton("✅ Проверить", callback_data=f'check_ch{channel_num}'),
        InlineKeyboardButton("◀️ Назад", callback_data='tasks')
    )

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=keyboard, parse_mode='HTML')
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')

# Универсальная функция для показа задания подписки (из БД)
def show_task_subscription(call, task_key):
    user_id = call.from_user.id
    cursor = db_conn.cursor()

    # Получаем данные задания из БД
    cursor.execute('SELECT title, reward, icon, channel_link, channel_id FROM tasks WHERE task_key = ? AND is_active = 1', (task_key,))
    task_data = cursor.fetchone()

    if not task_data:
        bot.answer_callback_query(call.id, "❌ Задание не найдено!", show_alert=True)
        return

    title, reward, icon, channel_link, channel_id = task_data

    text = (
        f"{icon} <b>{title}</b>\n\n"
        f"💰 Награда: +{reward}₽\n\n"
        f"1️⃣ Нажмите кнопку 'Подписаться'\n"
        f"2️⃣ Подпишитесь на канал\n"
        f"3️⃣ Вернитесь и нажмите 'Проверить'\n\n"
        f"После проверки подписки вы получите бонус!"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📢 Подписаться", url=channel_link),
        InlineKeyboardButton("✅ Проверить", callback_data=f'check_task_{task_key}'),
        InlineKeyboardButton("◀️ Назад", callback_data='tasks')
    )

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=keyboard, parse_mode='HTML')
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')

# Универсальная функция для проверки подписки (из БД)
def check_task_subscription(call, task_key):
    user_id = call.from_user.id
    cursor = db_conn.cursor()

    # Получаем данные задания из БД
    cursor.execute('SELECT title, reward, channel_id FROM tasks WHERE task_key = ? AND is_active = 1', (task_key,))
    task_data = cursor.fetchone()

    if not task_data:
        bot.answer_callback_query(call.id, "❌ Задание не найдено!", show_alert=True)
        return

    title, reward, channel_id = task_data

    # Проверяем, не выполнено ли уже задание
    cursor.execute('SELECT id FROM user_tasks WHERE user_id = ? AND task_key = ?', (user_id, task_key))
    if cursor.fetchone():
        bot.answer_callback_query(call.id, "✅ Вы уже получили бонус за это задание!", show_alert=True)
        show_tasks(call)
        return

    # Проверяем подписку
    is_subscribed = check_subscription(user_id, channel_id)

    if is_subscribed:
        # Начисляем награду
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (reward, user_id))
        cursor.execute(
            'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
            (user_id, reward, f"Бонус за задание: {title}")
        )
        # Отмечаем задание как выполненное
        cursor.execute(
            'INSERT INTO user_tasks (user_id, task_key) VALUES (?, ?)',
            (user_id, task_key)
        )
        db_conn.commit()

        # Проверяем количество выполненных заданий подписки
        cursor.execute('''
            SELECT COUNT(*) FROM user_tasks ut
            JOIN tasks t ON ut.task_key = t.task_key
            WHERE ut.user_id = ? AND t.task_type = 'subscription'
        ''', (user_id,))
        subscription_tasks_count = cursor.fetchone()[0]

        # Проверяем реферальный бонус
        cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
        referrer_data = cursor.fetchone()

        if referrer_data and referrer_data[0]:
            referrer_id = referrer_data[0]

            # Проверяем, рекламщик ли реферер
            cursor.execute('SELECT is_advertiser FROM user_roles WHERE user_id = ?', (referrer_id,))
            advertiser_data = cursor.fetchone()
            is_advertiser = advertiser_data[0] if advertiser_data else False

            # Проверяем, не был ли уже начислен бонус
            cursor.execute('SELECT bonus_paid FROM referrals WHERE referred_id = ?', (user_id,))
            referral_record = cursor.fetchone()

            # Рекламщик получает бонус сразу, обычный реферер - после 2 заданий
            can_pay = False
            if is_advertiser and subscription_tasks_count == 1:
                can_pay = True
            elif not is_advertiser and subscription_tasks_count >= 2:
                can_pay = True

            if can_pay and referral_record and not referral_record[0]:
                # Начисляем реферальный бонус
                cursor.execute('UPDATE referrals SET bonus_paid = 1 WHERE referrer_id = ? AND referred_id = ?', (referrer_id, user_id))
                cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (REFERRAL_BONUS, referrer_id))
                cursor.execute(
                    'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
                    (referrer_id, REFERRAL_BONUS, f"Реферальный бонус за пользователя {user_id}")
                )

                # Уведомляем реферера
                try:
                    if is_advertiser:
                        msg = f"🎉 <b>Реферальный бонус!</b>\n\n" \
                              f"Ваш реферал выполнил первое задание подписки!\n" \
                              f"💰 Вы получили: +{REFERRAL_BONUS}₽"
                    else:
                        msg = f"🎉 <b>Реферальный бонус!</b>\n\n" \
                              f"Ваш друг выполнил 2 задания подписки!\n" \
                              f"💰 Вы получили: +{REFERRAL_BONUS}₽"
                    bot.send_message(referrer_id, msg, parse_mode='HTML')
                except:
                    pass

        db_conn.commit()

        # Получаем новый баланс
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        new_balance = cursor.fetchone()[0]

        bot.answer_callback_query(call.id, f"✅ +{reward}₽ начислено!", show_alert=True)

        text = (
            f"✅ <b>Задание выполнено!</b>\n\n"
            f"🎁 {title}\n"
            f"💰 Награда: +{reward}₽\n"
            f"💵 Ваш баланс: {new_balance:.2f}₽"
        )


        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("◀️ К заданиям", callback_data='tasks'))

        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                 reply_markup=keyboard, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
    else:
        bot.answer_callback_query(call.id, "❌ Вы еще не подписались на канал!", show_alert=True)

# Проверка подписки на канал
def check_channel_subscription(call, channel_id, channel_num):
    user_id = call.from_user.id

    # Проверяем подписку
    is_subscribed = check_subscription(user_id, channel_id)

    if is_subscribed:
        cursor = db_conn.cursor()

        # Проверяем, получал ли уже бонус
        cursor.execute('SELECT channel1_subscribed, channel2_subscribed, channel3_subscribed, channel4_subscribed, referrer_id FROM users WHERE user_id = ?', (user_id,))
        user_data = cursor.fetchone()

        already_received = False
        if channel_num == 1 and user_data[0] == 1:
            already_received = True
        elif channel_num == 2 and user_data[1] == 1:
            already_received = True
        elif channel_num == 3 and user_data[2] == 1:
            already_received = True
        elif channel_num == 4 and user_data[3] == 1:
            already_received = True

        if already_received:
            bot.answer_callback_query(call.id, "✅ Вы уже получили бонус за эту подписку!", show_alert=True)
            show_tasks(call)
            return

        # Начисляем бонус
        if channel_num == 1:
            cursor.execute('UPDATE users SET channel1_subscribed = 1, balance = balance + 10 WHERE user_id = ?', (user_id,))
        elif channel_num == 2:
            cursor.execute('UPDATE users SET channel2_subscribed = 1, balance = balance + 10 WHERE user_id = ?', (user_id,))
        elif channel_num == 3:
            cursor.execute('UPDATE users SET channel3_subscribed = 1, balance = balance + 10 WHERE user_id = ?', (user_id,))
        elif channel_num == 4:
            cursor.execute('UPDATE users SET channel4_subscribed = 1, balance = balance + 10 WHERE user_id = ?', (user_id,))

        cursor.execute(
            'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
            (user_id, 10, f"Бонус за подписку на канал {channel_num}")
        )

        # Проверяем все каналы
        cursor.execute('SELECT channel1_subscribed, channel2_subscribed, channel3_subscribed, channel4_subscribed FROM users WHERE user_id = ?', (user_id,))
        channels_status = cursor.fetchone()
        all_channels_done = channels_status[0] == 1 and channels_status[1] == 1 and channels_status[2] == 1 and channels_status[3] == 1

        # Начисляем реферальный бонус
        referrer_id = user_data[4]
        if referrer_id:
            # Проверяем, рекламщик ли реферер
            cursor.execute('SELECT is_advertiser FROM user_roles WHERE user_id = ?', (referrer_id,))
            advertiser_data = cursor.fetchone()
            is_advertiser = advertiser_data[0] if advertiser_data else False

            # Проверяем, не был ли уже начислен бонус
            cursor.execute('SELECT bonus_paid FROM referrals WHERE referrer_id = ? AND referred_id = ?', (referrer_id, user_id))
            referral_data = cursor.fetchone()

            # Если реферер рекламщик - начисляем сразу, иначе только после всех подписок
            can_pay = False
            if is_advertiser:
                can_pay = True
            elif all_channels_done:
                can_pay = True

            if referral_data and referral_data[0] == 0 and can_pay:
                # Начисляем реферальный бонус
                cursor.execute('UPDATE referrals SET bonus_paid = 1 WHERE referrer_id = ? AND referred_id = ?', (referrer_id, user_id))
                cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (REFERRAL_BONUS, referrer_id))
                cursor.execute(
                    'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
                    (referrer_id, REFERRAL_BONUS, f"Реферальный бонус за пользователя {user_id}")
                )

                # Уведомление рефереру
                try:
                    if is_advertiser:
                        msg = f"🎉 <b>Реферальный бонус!</b>\n\n" \
                              f"Ваш реферал присоединился к боту.\n" \
                              f"💰 Ваш баланс пополнен на {REFERRAL_BONUS}₽"
                    else:
                        msg = f"🎉 <b>Реферальный бонус!</b>\n\n" \
                              f"Ваш друг выполнил все задания с подписками.\n" \
                              f"💰 Ваш баланс пополнен на {REFERRAL_BONUS}₽"
                    bot.send_message(referrer_id, msg, parse_mode='HTML')
                except:
                    pass

        db_conn.commit()

        # Получаем новый баланс
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        new_balance = cursor.fetchone()[0]

        # Проверяем статус реферального бонуса
        bonus_msg = ""
        if referrer_id and all_channels_done:
            cursor.execute('SELECT bonus_paid FROM referrals WHERE referrer_id = ? AND referred_id = ?', (referrer_id, user_id))
            ref_data = cursor.fetchone()
            if ref_data and ref_data[0] == 1:
                bonus_msg = f"\n\n🎁 Ваш пригласивший получил {REFERRAL_BONUS}₽ за то, что вы выполнили все задания!"

        text = (
            f"🎉 <b>Подписка подтверждена!</b>\n\n"
            f"✅ Спасибо за подписку на канал {channel_num}!\n"
            f"💰 Ваш баланс пополнен на 10₽\n\n"
            f"💵 Текущий баланс: {new_balance:.2f}₽{bonus_msg}"
        )

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu'))

        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                 reply_markup=keyboard, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')

        bot.answer_callback_query(call.id, "✅ +10₽ начислено!", show_alert=True)
    else:
        bot.answer_callback_query(
            call.id, 
            "❌ Подписка не найдена!\n\nУбедитесь, что вы подписались на канал и попробуйте снова.", 
            show_alert=True
        )

# Подтверждение пополнения баланса
def confirm_topup(call):
    parts = call.data.split('_')
    request_id = int(parts[2])
    amount = int(parts[3])

    cursor = db_conn.cursor()
    cursor.execute('SELECT user_id FROM payment_requests WHERE id = ?', (request_id,))
    request = cursor.fetchone()

    if request:
        user_id = request[0]

        cursor.execute('UPDATE payment_requests SET status = ? WHERE id = ?', ('confirmed', request_id))
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        cursor.execute(
            'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
            (user_id, amount, f"Пополнение баланса на {amount}₽")
        )
        db_conn.commit()

        try:
            bot.send_message(
                user_id,
                f"✅ <b>Пополнение подтверждено!</b>\n\n"
                f"💰 На ваш баланс зачислено {amount}₽\n\n"
                f"Спасибо за пополнение!",
                parse_mode='HTML'
            )
        except:
            pass

        bot.edit_message_caption(
            caption=call.message.caption + f"\n\n✅ <b>Подтверждено администратором</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )

# Отклонение пополнения баланса
def reject_topup(call):
    request_id = int(call.data.split('_')[2])

    cursor = db_conn.cursor()
    cursor.execute('SELECT user_id FROM payment_requests WHERE id = ?', (request_id,))
    request = cursor.fetchone()

    if request:
        user_id = request[0]

        cursor.execute('UPDATE payment_requests SET status = ? WHERE id = ?', ('rejected', request_id))
        db_conn.commit()

        try:
            bot.send_message(
                user_id,
                "❌ <b>Пополнение отклонено</b>\n\n"
                "К сожалению, ваша заявка была отклонена.\n"
                "Возможные причины:\n"
                "• Неверная сумма\n"
                "• Некорректный скриншот\n\n"
                "Обратитесь в поддержку для уточнения деталей.",
                parse_mode='HTML'
            )
        except:
            pass

        bot.edit_message_caption(
            caption=call.message.caption + f"\n\n❌ <b>Отклонено администратором</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )


# Функции для админ-панели управления категориями
def show_admin_categories_menu(call):
    """Показывает меню управления категориями"""
    text = "📂 <b>Управление категориями</b>\n\nВыберите действие:"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("➕ Добавить категорию", callback_data='admin_cat_add_start'),
        InlineKeyboardButton("➖ Удалить категорию", callback_data='admin_cat_del_start'),
        InlineKeyboardButton("🙈 Скрыть категорию", callback_data='admin_cat_hide_start'),
        InlineKeyboardButton("👀 Показать категорию", callback_data='admin_cat_show_start'),
        InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin')
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_add_category(call):
    """Обработка добавления категории - выбор типа"""
    text = "✍️ <b>Добавление категории</b>\n\nВыберите тип категории:"
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📂 Обычная", callback_data='admin_cat_add_regular'),
        InlineKeyboardButton("⭐ VIP", callback_data='admin_cat_add_vip')
    )
    keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data='admin_categories'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_delete_category(call):
    """Обработка удаления категории"""
    user_id = call.from_user.id
    user_states[user_id] = {'admin_waiting_del_cat_name': True}
    text = "🗑️ Введите название категории для удаления:"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data='admin_categories'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_hide_category(call):
    """Обработка скрытия категории"""
    user_id = call.from_user.id
    user_states[user_id] = {'admin_waiting_hide_cat_name': True}
    text = "🙈 Введите название категории для скрытия:"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data='admin_categories'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_show_category(call):
    """Обработка показа категории"""
    user_id = call.from_user.id
    user_states[user_id] = {'admin_waiting_show_cat_name': True}
    text = "👀 Введите название категории для показа:"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data='admin_categories'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

# Функции для админ-панели управления приватками
def show_admin_privates_menu(call):
    """Показывает меню управления приватками"""
    text = "🔐 <b>Управление приватками</b>\n\nВыберите действие:"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📋 Список приваток", callback_data='admin_priv_list'),
        InlineKeyboardButton("✏️ Изменить приватку", callback_data='admin_priv_edit_select'),
        InlineKeyboardButton("🙈 Скрыть приватку", callback_data='admin_priv_hide_select'),
        InlineKeyboardButton("👀 Показать приватку", callback_data='admin_priv_show_select'),
        InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin')
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def show_privates_list(call):
    """Показывает список всех приваток"""
    text = "📋 <b>Список приваток</b>\n\n"

    for key, data in PRIVATE_CHANNELS.items():
        status = "🙈 Скрыта" if data.get('hidden', False) else "👀 Видна"
        text += (
            f"<b>{data['name']}</b>\n"
            f"• Ключ: <code>{key}</code>\n"
            f"• Количество видео: <code>{data['video_count']}</code>\n"
            f"• Цена: {data['price']}₽\n"
            f"• Описание: {data['description']}\n"
            f"• Статус: {status}\n\n"
        )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_privates'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_priv_edit_select(call):
    """Выбор приватки для редактирования"""
    text = "✏️ <b>Выберите приватку для редактирования:</b>"
    keyboard = InlineKeyboardMarkup(row_width=1)

    for key, data in PRIVATE_CHANNELS.items():
        keyboard.add(InlineKeyboardButton(data['name'], callback_data=f'admin_priv_edit_{key}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_privates'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_priv_edit_menu(call):
    """Меню редактирования конкретной приватки"""
    priv_key = '_'.join(call.data.split('_')[3:])
    priv_data = PRIVATE_CHANNELS.get(priv_key)

    if not priv_data:
        bot.answer_callback_query(call.id, "❌ Приватка не найдена!", show_alert=True)
        return

    text = (
        f"✏️ <b>Редактирование: {priv_data['name']}</b>\n\n"
        f"📦 Количество видео: <code>{priv_data['video_count']}</code>\n"
        f"💰 Цена: {priv_data['price']}₽\n"
        f"📝 Описание: {priv_data['description']}\n\n"
        "Выберите, что хотите изменить:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🎬 Изменить количество видео", callback_data=f'admin_priv_vidcount_{priv_key}'),
        InlineKeyboardButton("💵 Изменить цену", callback_data=f'admin_priv_price_{priv_key}'),
        InlineKeyboardButton("📝 Изменить описание", callback_data=f'admin_priv_desc_{priv_key}'),
        InlineKeyboardButton("🏷️ Изменить название", callback_data=f'admin_priv_name_{priv_key}'),
        InlineKeyboardButton("◀️ Назад", callback_data='admin_priv_edit_select')
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_priv_hide_select(call):
    """Выбор приватки для скрытия"""
    text = "🙈 <b>Выберите приватку для скрытия:</b>"
    keyboard = InlineKeyboardMarkup(row_width=1)

    has_visible = False
    for key, data in PRIVATE_CHANNELS.items():
        if not data.get('hidden', False):
            keyboard.add(InlineKeyboardButton(data['name'], callback_data=f'admin_priv_hide_{key}'))
            has_visible = True

    if not has_visible:
        text += "\n\n❌ Все приватки уже скрыты"

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_privates'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_priv_show_select(call):
    """Выбор приватки для показа"""
    text = "👀 <b>Выберите приватку для показа:</b>"
    keyboard = InlineKeyboardMarkup(row_width=1)

    has_hidden = False
    for key, data in PRIVATE_CHANNELS.items():
        if data.get('hidden', False):
            keyboard.add(InlineKeyboardButton(data['name'], callback_data=f'admin_priv_show_{key}'))
            has_hidden = True

    if not has_hidden:
        text += "\n\n❌ Все приватки уже видны"

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_privates'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_priv_hide(call):
    """Скрыть приватку"""
    priv_key = '_'.join(call.data.split('_')[3:])
    if priv_key in PRIVATE_CHANNELS:
        PRIVATE_CHANNELS[priv_key]['hidden'] = True
        bot.answer_callback_query(call.id, f"✅ Приватка {PRIVATE_CHANNELS[priv_key]['name']} скрыта!", show_alert=True)
    admin_priv_hide_select(call)

def admin_priv_show(call):
    """Показать приватку"""
    priv_key = '_'.join(call.data.split('_')[3:])
    if priv_key in PRIVATE_CHANNELS:
        PRIVATE_CHANNELS[priv_key]['hidden'] = False
        bot.answer_callback_query(call.id, f"✅ Приватка {PRIVATE_CHANNELS[priv_key]['name']} теперь видна!", show_alert=True)
    admin_priv_show_select(call)

# Функции для админ-панели управления заданиями
def show_admin_tasks_menu(call):
    """Показывает меню управления заданиями"""
    text = "🎁 <b>Управление заданиями</b>\n\nВыберите действие:"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📋 Список заданий", callback_data='admin_tasks_list'),
        InlineKeyboardButton("➕ Добавить задание", callback_data='admin_tasks_add'),
        InlineKeyboardButton("✏️ Редактировать задание", callback_data='admin_tasks_edit_select'),
        InlineKeyboardButton("🗑️ Удалить задание", callback_data='admin_tasks_delete_select'),
        InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin')
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def show_tasks_list(call):
    """Показывает список всех заданий"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT * FROM tasks ORDER BY task_type, id')
    tasks = cursor.fetchall()

    if not tasks:
        text = "📋 <b>Список заданий</b>\n\n❌ Заданий пока нет"
    else:
        text = "📋 <b>Список заданий</b>\n\n"

        task_types = {'daily': '📅 Ежедневные', 'subscription': '📢 Подписки', 'achievement': '🏆 Достижения'}
        current_type = None

        for task in tasks:
            task_id, task_type, task_key, title, description, reward, condition_value, is_active, callback_data, icon, created_at = task

            if task_type != current_type:
                current_type = task_type
                text += f"\n<b>{task_types.get(task_type, task_type)}</b>\n"

            status = "✅ Активно" if is_active else "❌ Неактивно"
            text += f"{icon} <b>{title}</b>\n"
            text += f"  • ID: <code>{task_id}</code>\n"
            text += f"  • Ключ: <code>{task_key}</code>\n"
            text += f"  • Награда: {reward}₽\n"
            if condition_value:
                text += f"  • Условие: {condition_value}\n"
            text += f"  • Статус: {status}\n\n"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_tasks'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_add_task_start(call):
    """Начать добавление задания"""
    user_id = call.from_user.id

    text = "➕ <b>Добавление задания</b>\n\nВыберите тип задания:"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📅 Ежедневное", callback_data='admin_tasks_add_type_daily'),
        InlineKeyboardButton("📢 Подписка", callback_data='admin_tasks_add_type_subscription'),
        InlineKeyboardButton("🏆 Достижение", callback_data='admin_tasks_add_type_achievement'),
        InlineKeyboardButton("◀️ Отмена", callback_data='admin_tasks')
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_add_task_type(call):
    """Обработка выбора типа задания"""
    user_id = call.from_user.id
    task_type = call.data.split('_')[-1]

    user_states[user_id] = {
        'admin_adding_task': True,
        'task_type': task_type,
        'step': 'key'
    }

    text = (
        f"➕ <b>Добавление задания ({task_type})</b>\n\n"
        f"Введите уникальный ключ задания (например: daily_bonus, channel5_sub):"
    )
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Отмена", callback_data='admin_tasks'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_edit_task_select(call):
    """Выбор задания для редактирования"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT id, icon, title, task_type FROM tasks ORDER BY task_type, id')
    tasks = cursor.fetchall()

    text = "✏️ <b>Выберите задание для редактирования:</b>"
    keyboard = InlineKeyboardMarkup(row_width=1)

    if not tasks:
        text += "\n\n❌ Заданий пока нет"
    else:
        for task_id, icon, title, task_type in tasks:
            keyboard.add(InlineKeyboardButton(f"{icon} {title}", callback_data=f'admin_tasks_edit_{task_id}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_tasks'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_edit_task_menu(call):
    """Меню редактирования конкретного задания"""
    task_id = int(call.data.split('_')[-1])
    cursor = db_conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()

    if not task:
        bot.answer_callback_query(call.id, "❌ Задание не найдено!", show_alert=True)
        return

    task_id, task_type, task_key, title, description, reward, condition_value, is_active, callback_data, icon, created_at = task

    text = (
        f"✏️ <b>Редактирование: {title}</b>\n\n"
        f"{icon} <b>Информация:</b>\n"
        f"• ID: <code>{task_id}</code>\n"
        f"• Тип: {task_type}\n"
        f"• Ключ: <code>{task_key}</code>\n"
        f"• Название: {title}\n"
        f"• Описание: {description or 'Нет'}\n"
        f"• Награда: {reward}₽\n"
        f"• Условие: {condition_value or 'Нет'}\n"
        f"• Callback: {callback_data or 'Нет'}\n"
        f"• Иконка: {icon}\n"
        f"• Статус: {'✅ Активно' if is_active else '❌ Неактивно'}\n\n"
        "Выберите, что хотите изменить:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📝 Изменить название", callback_data=f'admin_tasks_edit_title_{task_id}'),
        InlineKeyboardButton("💰 Изменить награду", callback_data=f'admin_tasks_edit_reward_{task_id}'),
        InlineKeyboardButton("🔢 Изменить условие", callback_data=f'admin_tasks_edit_condition_{task_id}'),
        InlineKeyboardButton("🔘 Изменить callback", callback_data=f'admin_tasks_edit_callback_{task_id}'),
        InlineKeyboardButton("😀 Изменить иконку", callback_data=f'admin_tasks_edit_icon_{task_id}'),
        InlineKeyboardButton("🔄 Переключить статус", callback_data=f'admin_tasks_toggle_{task_id}'),
        InlineKeyboardButton("◀️ Назад", callback_data='admin_tasks_edit_select')
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_delete_task_select(call):
    """Выбор задания для удаления"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT id, icon, title FROM tasks ORDER BY id')
    tasks = cursor.fetchall()

    text = "🗑️ <b>Выберите задание для удаления:</b>"
    keyboard = InlineKeyboardMarkup(row_width=1)

    if not tasks:
        text += "\n\n❌ Заданий пока нет"
    else:
        for task_id, icon, title in tasks:
            keyboard.add(InlineKeyboardButton(f"{icon} {title}", callback_data=f'admin_tasks_delete_confirm_{task_id}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_tasks'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_delete_task_confirm(call):
    """Подтверждение удаления задания"""
    task_id = int(call.data.split('_')[-1])
    cursor = db_conn.cursor()
    cursor.execute('SELECT icon, title FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()

    if not task:
        bot.answer_callback_query(call.id, "❌ Задание не найдено!", show_alert=True)
        return

    icon, title = task

    text = f"🗑️ <b>Удаление задания</b>\n\n{icon} {title}\n\nВы уверены?"
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да", callback_data=f'admin_tasks_delete_yes_{task_id}'),
        InlineKeyboardButton("❌ Нет", callback_data='admin_tasks_delete_select')
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_delete_task_execute(call):
    """Выполнение удаления задания"""
    task_id = int(call.data.split('_')[-1])
    cursor = db_conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    db_conn.commit()

    bot.answer_callback_query(call.id, "✅ Задание удалено!", show_alert=True)
    admin_delete_task_select(call)

def admin_toggle_task(call):
    """Переключение статуса задания (активно/неактивно)"""
    task_id = int(call.data.split('_')[-1])
    cursor = db_conn.cursor()
    cursor.execute('SELECT is_active FROM tasks WHERE id = ?', (task_id,))
    result = cursor.fetchone()

    if not result:
        bot.answer_callback_query(call.id, "❌ Задание не найдено!", show_alert=True)
        return

    new_status = 0 if result[0] else 1
    cursor.execute('UPDATE tasks SET is_active = ? WHERE id = ?', (new_status, task_id))
    db_conn.commit()

    status_text = "активировано" if new_status else "деактивировано"
    bot.answer_callback_query(call.id, f"✅ Задание {status_text}!", show_alert=True)

    call.data = f'admin_tasks_edit_{task_id}'
    admin_edit_task_menu(call)

# Функции для управления способами оплаты
def show_admin_payments_menu(call):
    """Показывает меню управления способами оплаты"""
    text = "💳 <b>Управление способами оплаты</b>\n\nВыберите действие:"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📋 Список способов оплаты", callback_data='admin_pay_list'),
        InlineKeyboardButton("✏️ Изменить номер/кошелек", callback_data='admin_pay_edit_select'),
        InlineKeyboardButton("🏦 Выбрать банк", callback_data='admin_pay_select_bank'),
        InlineKeyboardButton("🔄 Переключить статус", callback_data='admin_pay_toggle_select'),
        InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin')
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def show_payments_list(call):
    """Показывает список всех способов оплаты"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT payment_type, payment_name, is_active, phone_number, wallet_number FROM payment_settings')
    payments = cursor.fetchall()

    text = "📋 <b>Список способов оплаты</b>\n\n"

    for payment_type, name, is_active, phone, wallet in payments:
        status = "✅ Активен" if is_active else "❌ Отключен"
        text += f"<b>{name}</b>\n"
        text += f"• Тип: <code>{payment_type}</code>\n"
        text += f"• Статус: {status}\n"
        if phone:
            text += f"• Номер телефона: <code>{phone}</code>\n"
        if wallet:
            text += f"• Номер кошелька: <code>{wallet}</code>\n"
        text += "\n"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_payments'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_pay_edit_select(call):
    """Выбор способа оплаты для редактирования"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT payment_type, payment_name FROM payment_settings')
    payments = cursor.fetchall()

    text = "✏️ <b>Выберите способ оплаты для редактирования:</b>"
    keyboard = InlineKeyboardMarkup(row_width=1)

    for payment_type, name in payments:
        keyboard.add(InlineKeyboardButton(name, callback_data=f'admin_pay_edit_{payment_type}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_payments'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_pay_edit_menu(call):
    """Меню редактирования способа оплаты"""
    payment_type = call.data.split('_')[-1]
    cursor = db_conn.cursor()
    cursor.execute('SELECT payment_name, phone_number, wallet_number, is_active FROM payment_settings WHERE payment_type = ?', (payment_type,))
    result = cursor.fetchone()

    if not result:
        bot.answer_callback_query(call.id, "❌ Способ оплаты не найден!", show_alert=True)
        return

    name, phone, wallet, is_active = result

    text = (
        f"✏️ <b>Редактирование: {name}</b>\n\n"
        f"📱 Номер телефона: <code>{phone or 'Не указан'}</code>\n"
        f"💳 Номер кошелька: <code>{wallet or 'Не указан'}</code>\n"
        f"📊 Статус: {'✅ Активен' if is_active else '❌ Отключен'}\n\n"
        "Выберите, что хотите изменить:"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)

    if payment_type == 'card':
        keyboard.add(InlineKeyboardButton("📱 Изменить номер телефона", callback_data=f'admin_pay_phone_{payment_type}'))
    elif payment_type == 'yoomoney':
        keyboard.add(InlineKeyboardButton("💳 Изменить номер кошелька", callback_data=f'admin_pay_wallet_{payment_type}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_pay_edit_select'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_pay_toggle_select(call):
    """Выбор способа оплаты для переключения статуса"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT payment_type, payment_name, is_active FROM payment_settings')
    payments = cursor.fetchall()

    text = "🔄 <b>Выберите способ оплаты для переключения статуса:</b>"
    keyboard = InlineKeyboardMarkup(row_width=1)

    for payment_type, name, is_active in payments:
        status = "✅" if is_active else "❌"
        keyboard.add(InlineKeyboardButton(f"{status} {name}", callback_data=f'admin_pay_toggle_{payment_type}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_payments'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

def admin_pay_toggle(call):
    """Переключение статуса способа оплаты"""
    payment_type = call.data.split('_')[-1]
    cursor = db_conn.cursor()
    cursor.execute('SELECT is_active FROM payment_settings WHERE payment_type = ?', (payment_type,))
    result = cursor.fetchone()

    if not result:
        bot.answer_callback_query(call.id, "❌ Способ оплаты не найден!", show_alert=True)
        return

    new_status = 0 if result[0] else 1
    cursor.execute('UPDATE payment_settings SET is_active = ? WHERE payment_type = ?', (new_status, payment_type))
    db_conn.commit()

    status_text = "активирован" if new_status else "отключен"
    bot.answer_callback_query(call.id, f"✅ Способ оплаты {status_text}!", show_alert=True)
    admin_pay_toggle_select(call)

def admin_select_bank_payment(call):
    """Выбор способа оплаты для установки банка"""
    cursor = db_conn.cursor()
    cursor.execute('SELECT payment_type, payment_name, bank_name FROM payment_settings')
    payments = cursor.fetchall()

    text = "🏦 <b>Выберите способ оплаты для установки банка:</b>"
    keyboard = InlineKeyboardMarkup(row_width=1)

    for payment_type, name, current_bank in payments:
        bank_info = f" ({current_bank})" if current_bank else " (не выбран)"
        keyboard.add(InlineKeyboardButton(f"{name}{bank_info}", callback_data=f'admin_pay_bank_select_{payment_type}'))

    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data='admin_payments'))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')


if __name__ == '__main__':
    print("🤖 Бот запускается...")
    print("🔗 Создание ссылок для приваток...")
    init_private_links()
    print("💱 Обновление курсов криптовалют...")
    update_crypto_rates()
    print("✅ Бот запущен!")
    bot.infinity_polling()
