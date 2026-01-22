
import os
import sqlite3
from datetime import datetime
from telebot import TeleBot, types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import sys

# Конфигурация
PAYMENT_BOT_TOKEN = '8587070004:AAGi1FrPy85qXtHsUfXrrq4qGQvL89YsBU4'
MAIN_BOT_USERNAME = 'bot'  # Замените на username основного бота
ADMIN_IDS = [8122934151, 1811665749]

# Курс Stars к рублям
STARS_TO_RUB_RATE = 1.3

payment_bot = TeleBot(PAYMENT_BOT_TOKEN)

# Подключение к общей БД
def get_db():
    return sqlite3.connect('bot.db', check_same_thread=False)

# Хранение временных данных о платежах
payment_states = {}

@payment_bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    # Проверяем параметры start
    if len(message.text.split()) > 1:
        params = message.text.split()[1]
        
        # Формат оплаты приватки: private_{user_id}_{private_type}_{price}
        if params.startswith('private_'):
            try:
                parts = params.split('_')
                original_user_id = int(parts[1])
                private_type = parts[2]
                price = int(parts[3])
                
                # Проверяем, что это тот же пользователь
                if user_id != original_user_id:
                    payment_bot.send_message(
                        message.chat.id,
                        "❌ <b>Ошибка</b>\n\nЭта ссылка предназначена для другого пользователя.",
                        parse_mode='HTML'
                    )
                    return
                
                # Конвертируем в Stars
                stars_amount = int(price / STARS_TO_RUB_RATE)
                
                # Название приватки
                private_names = {
                    'trial': '🔍 Пробник',
                    'students': '👩‍🎓 Студентки',
                    'alt': '👯 Альтушки',
                    'all_inclusive': '💫 Все включено'
                }
                private_name = private_names.get(private_type, 'Приватка')
                
                text = (
                    f"⭐ <b>Оплата приватки через Telegram Stars</b>\n\n"
                    f"📦 Товар: {private_name}\n"
                    f"💰 Стоимость: <b>{price}₽</b>\n"
                    f"⭐ К оплате: <b>{stars_amount} Stars</b>\n\n"
                    f"💱 Курс: 1 Star = {STARS_TO_RUB_RATE}₽\n\n"
                    f"Нажмите кнопку ниже для оплаты:"
                )
                
                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton("⭐ Оплатить", callback_data=f'pay_private_{private_type}_{price}_{stars_amount}')
                )
                
                payment_bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
                
            except Exception as e:
                payment_bot.send_message(
                    message.chat.id,
                    "❌ <b>Ошибка</b>\n\nНеверная ссылка для оплаты.",
                    parse_mode='HTML'
                )
        
        # Формат пополнения: pay_{user_id}_{amount}
        elif params.startswith('pay_'):
            try:
                parts = params.split('_')
                original_user_id = int(parts[1])
                amount_rub = int(parts[2])
                
                # Проверяем, что это тот же пользователь
                if user_id != original_user_id:
                    payment_bot.send_message(
                        message.chat.id,
                        "❌ <b>Ошибка</b>\n\nЭта ссылка предназначена для другого пользователя.",
                        parse_mode='HTML'
                    )
                    return
                
                # Конвертируем в Stars
                stars_amount = int(amount_rub / STARS_TO_RUB_RATE)
                
                text = (
                    f"⭐ <b>Пополнение через Telegram Stars</b>\n\n"
                    f"💰 Сумма: <b>{amount_rub}₽</b>\n"
                    f"⭐ К оплате: <b>{stars_amount} Stars</b>\n\n"
                    f"💱 Курс: 1 Star = {STARS_TO_RUB_RATE}₽\n\n"
                    f"Нажмите кнопку ниже для оплаты:"
                )
                
                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton("⭐ Оплатить", callback_data=f'pay_{amount_rub}_{stars_amount}')
                )
                
                payment_bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
                
            except Exception as e:
                payment_bot.send_message(
                    message.chat.id,
                    "❌ <b>Ошибка</b>\n\nНеверная ссылка для оплаты.",
                    parse_mode='HTML'
                )
        
        # Формат премиума: premium_{user_id}_{premium_type}_{price}
        elif params.startswith('premium_'):
            try:
                parts = params.split('_')
                original_user_id = int(parts[1])
                premium_type = parts[2]
                price = int(parts[3])
                
                # Проверяем, что это тот же пользователь
                if user_id != original_user_id:
                    payment_bot.send_message(
                        message.chat.id,
                        "❌ <b>Ошибка</b>\n\nЭта ссылка предназначена для другого пользователя.",
                        parse_mode='HTML'
                    )
                    return
                
                # Конвертируем в Stars
                stars_amount = int(price / STARS_TO_RUB_RATE)
                premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"
                
                text = (
                    f"⭐ <b>Оплата премиума через Telegram Stars</b>\n\n"
                    f"📦 Товар: {premium_name}\n"
                    f"💰 Стоимость: <b>{price}₽</b>\n"
                    f"⭐ К оплате: <b>{stars_amount} Stars</b>\n\n"
                    f"💱 Курс: 1 Star = {STARS_TO_RUB_RATE}₽\n\n"
                    f"Нажмите кнопку ниже для оплаты:"
                )
                
                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton("⭐ Оплатить", callback_data=f'pay_premium_{premium_type}_{price}_{stars_amount}')
                )
                
                payment_bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')
                
            except Exception as e:
                payment_bot.send_message(
                    message.chat.id,
                    "❌ <b>Ошибка</b>\n\nНеверная ссылка для оплаты.",
                    parse_mode='HTML'
                )
        else:
            show_welcome(message)
    else:
        show_welcome(message)

def show_welcome(message):
    text = (
        "💳 <b>Платежный бот</b>\n\n"
        "Этот бот используется для пополнения баланса через Telegram Stars.\n\n"
        "Для пополнения вернитесь в основного бота и выберите способ оплаты."
    )
    payment_bot.send_message(message.chat.id, text, parse_mode='HTML')

@payment_bot.callback_query_handler(func=lambda call: call.data.startswith('pay_'))
def process_payment(call):
    parts = call.data.split('_')
    user_id = call.from_user.id
    
    # Обработка оплаты приватки
    if parts[0] == 'pay' and parts[1] == 'private':
        private_type = parts[2]
        price = int(parts[3])
        stars_amount = int(parts[4])
        
        private_names = {
            'trial': '🔍 Пробник',
            'students': '👩‍🎓 Студентки',
            'alt': '👯 Альтушки',
            'all_inclusive': '💫 Все включено'
        }
        private_name = private_names.get(private_type, 'Приватка')
        
        # Создаем инвойс для приватки
        prices = [LabeledPrice(label=private_name, amount=stars_amount)]
        
        payment_bot.send_invoice(
            chat_id=user_id,
            title=f'Покупка {private_name}',
            description=f'{private_name} ({stars_amount} Stars)',
            invoice_payload=f'private_{private_type}_{user_id}',
            provider_token='',
            currency='XTR',
            prices=prices
        )
        
        payment_bot.answer_callback_query(call.id, "Счет на оплату отправлен!")
    
    # Обработка пополнения баланса
    elif parts[0] == 'pay' and parts[1] != 'premium':
        amount_rub = int(parts[1])
        stars_amount = int(parts[2])
        
        # Создаем инвойс для пополнения
        prices = [LabeledPrice(label=f'Пополнение на {amount_rub}₽', amount=stars_amount)]
        
        payment_bot.send_invoice(
            chat_id=user_id,
            title='Пополнение баланса',
            description=f'Пополнение баланса на {amount_rub}₽ ({stars_amount} Stars)',
            invoice_payload=f'topup_{amount_rub}_{user_id}',
            provider_token='',
            currency='XTR',
            prices=prices
        )
        
        payment_bot.answer_callback_query(call.id, "Счет на оплату отправлен!")
    
    # Обработка покупки премиума
    elif parts[0] == 'pay' and parts[1] == 'premium':
        premium_type = parts[2]
        price = int(parts[3])
        stars_amount = int(parts[4])
        premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"
        
        # Создаем инвойс для премиума
        prices = [LabeledPrice(label=premium_name, amount=stars_amount)]
        
        payment_bot.send_invoice(
            chat_id=user_id,
            title=f'Покупка {premium_name}',
            description=f'{premium_name} на 24 часа ({stars_amount} Stars)',
            invoice_payload=f'premium_{premium_type}_{user_id}',
            provider_token='',
            currency='XTR',
            prices=prices
        )
        
        payment_bot.answer_callback_query(call.id, "Счет на оплату отправлен!")

@payment_bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_handler(pre_checkout_query):
    payment_bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@payment_bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Нет username"
    
    # Получаем данные из payload
    payload = message.successful_payment.invoice_payload
    parts = payload.split('_')
    payment_type = parts[0]
    
    conn = get_db()
    cursor = conn.cursor()
    
    from telebot import TeleBot
    MAIN_BOT_TOKEN = '8392524849:AAHGfM2_HbNKORgWl67eNcYoDmSm-Og9aq4'
    main_bot = TeleBot(MAIN_BOT_TOKEN)
    
    ADMIN_IDS = [8122934151, 1811665749]
    
    # Обработка пополнения баланса
    if payment_type == 'topup':
        amount_rub = int(parts[1])
        original_user_id = int(parts[2])
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount_rub, user_id))
        cursor.execute(
            'INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)',
            (user_id, amount_rub, f"Пополнение баланса на {amount_rub}₽ через Telegram Stars")
        )
        conn.commit()
        
        # Получаем новый баланс
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        new_balance = result[0] if result else amount_rub
        
        # Отправляем подтверждение в платежном боте
        text = (
            f"✅ <b>Оплата успешно завершена!</b>\n\n"
            f"💰 На ваш баланс зачислено {amount_rub}₽\n"
            f"💵 Текущий баланс: {new_balance:.2f}₽\n\n"
            f"Вернитесь в основного бота для использования баланса!"
        )
        
        payment_bot.send_message(user_id, text, parse_mode='HTML')
        
        # Отправляем уведомление в основного бота
        try:
            notification_text = (
                f"✅ <b>Пополнение баланса подтверждено!</b>\n\n"
                f"💰 Зачислено: {amount_rub}₽\n"
                f"💵 Новый баланс: {new_balance:.2f}₽\n\n"
                f"Спасибо за пополнение!"
            )
            main_bot.send_message(user_id, notification_text, parse_mode='HTML')
        except Exception as e:
            print(f"Ошибка отправки уведомления в основного бота: {e}")
        
        # Уведомление админу
        admin_text = (
            f"⭐ <b>Оплата через Telegram Stars</b>\n\n"
            f"💰 Тип: Пополнение баланса\n"
            f"👤 Пользователь: @{username}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💵 Сумма: {amount_rub}₽\n"
            f"⭐ Способ оплаты: Telegram Stars"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                main_bot.send_message(admin_id, admin_text, parse_mode='HTML')
            except:
                pass
    
    # Обработка покупки приватки
    elif payment_type == 'private':
        private_type = parts[1]
        original_user_id = int(parts[2])
        
        # Добавляем доступ к приватке
        cursor.execute(
            'INSERT OR IGNORE INTO private_access (user_id, private_type) VALUES (?, ?)',
            (user_id, private_type)
        )
        conn.commit()
        
        # Создаем одноразовую ссылку для видео
        # Прямой импорт функции создания токена для корректной работы
        def create_token_internal(p_type, u_id):
            import secrets
            token = secrets.token_urlsafe(32)
            c = sqlite3.connect('bot.db', check_same_thread=False)
            cur = c.cursor()
            
            # Получаем количество видео
            v_counts = {'trial': 200, 'students': 444, 'alt': 600, 'all_inclusive': 2000}
            v_count = v_counts.get(p_type, 10)
            
            cur.execute(
                'INSERT INTO video_access_tokens (token, user_id, video_count) VALUES (?, ?, ?)',
                (token, u_id, v_count)
            )
            c.commit()
            c.close()
            return f"https://t.me/GiveBonusTG_bot?start=video_{token}"

        video_link = create_token_internal(private_type, user_id)
        
        private_names = {
            'trial': '🔍 Пробник',
            'students': '👩‍🎓 Студентки',
            'alt': '👯 Альтушки',
            'all_inclusive': '💫 Все включено'
        }
        private_name = private_names.get(private_type, 'Приватка')
        
        # Отправляем подтверждение в платежном боте
        if video_link:
            text = (
                f"✅ <b>Оплата успешно завершена!</b>\n\n"
                f"🎉 Вы получили доступ к {private_name}\n\n"
                f"🔗 Ссылка для получения видео:\n{video_link}\n\n"
                f"📝 Нажмите на ссылку, чтобы получить видео!\n\n"
                f"⚠️ Это одноразовая ссылка только для вас!"
            )
        else:
            text = (
                f"✅ <b>Оплата успешно завершена!</b>\n\n"
                f"🎉 Вы получили доступ к {private_name}\n\n"
                f"❌ Ошибка создания ссылки. Обратитесь в поддержку."
            )
        
        payment_bot.send_message(user_id, text, parse_mode='HTML')
        
        # Отправляем уведомление в основного бота
        try:
            if video_link:
                notification_text = (
                    f"🎉 <b>Приватка успешно активирована!</b>\n\n"
                    f"📱 {private_name}\n\n"
                    f"🔗 Ссылка для получения видео:\n{video_link}\n\n"
                    f"⚠️ Это одноразовая ссылка только для вас!"
                )
            else:
                notification_text = (
                    f"🎉 <b>Приватка успешно активирована!</b>\n\n"
                    f"📱 {private_name}\n\n"
                    f"❌ Ошибка создания ссылки. Обратитесь в поддержку."
                )
            main_bot.send_message(user_id, notification_text, parse_mode='HTML')
        except Exception as e:
            print(f"Ошибка отправки уведомления в основного бота: {e}")
        
        # Уведомление админу
        admin_text = (
            f"⭐ <b>Оплата через Telegram Stars</b>\n\n"
            f"💰 Тип: Приватка\n"
            f"👤 Пользователь: @{username}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📦 Товар: {private_name}\n"
            f"⭐ Способ оплаты: Telegram Stars"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                main_bot.send_message(admin_id, admin_text, parse_mode='HTML')
            except:
                pass
    
    # Обработка покупки премиума
    elif payment_type == 'premium':
        premium_type = parts[1]
        original_user_id = int(parts[2])
        
        from datetime import datetime, timedelta
        premium_until = datetime.now() + timedelta(hours=24)
        premium_name = "Премиум (обычные)" if premium_type == 'regular' else "VIP Премиум"
        
        if premium_type == 'regular':
            cursor.execute('UPDATE users SET premium_regular_until = ? WHERE user_id = ?', 
                         (premium_until.isoformat(), user_id))
        else:
            cursor.execute('UPDATE users SET premium_vip_until = ? WHERE user_id = ?', 
                         (premium_until.isoformat(), user_id))
        
        conn.commit()
        
        # Отправляем подтверждение в платежном боте
        text = (
            f"✅ <b>Премиум успешно активирован!</b>\n\n"
            f"⭐ Тип: {premium_name}\n"
            f"⏰ Действует до: {premium_until.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Вернитесь в основного бота для использования премиума!"
        )
        
        payment_bot.send_message(user_id, text, parse_mode='HTML')
        
        # Отправляем уведомление в основного бота
        try:
            notification_text = (
                f"🎉 <b>Премиум успешно активирован!</b>\n\n"
                f"⭐ Тип: {premium_name}\n"
                f"⏰ Действует до: {premium_until.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"Контент теперь бесплатный для вас!\n"
                f"Приятного использования!"
            )
            main_bot.send_message(user_id, notification_text, parse_mode='HTML')
        except Exception as e:
            print(f"Ошибка отправки уведомления в основного бота: {e}")
        
        # Уведомление админу
        admin_text = (
            f"⭐ <b>Оплата через Telegram Stars</b>\n\n"
            f"💰 Тип: Премиум подписка\n"
            f"👤 Пользователь: @{username}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📦 Товар: {premium_name}\n"
            f"⏰ До: {premium_until.strftime('%d.%m.%Y %H:%M')}\n"
            f"⭐ Способ оплаты: Telegram Stars"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                main_bot.send_message(admin_id, admin_text, parse_mode='HTML')
            except:
                pass
    
    conn.close()

if __name__ == '__main__':
    print("💳 Платежный бот запущен!")
    payment_bot.infinity_polling()
