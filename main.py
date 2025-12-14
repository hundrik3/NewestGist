import telebot
from telebot import types
import os
import psycopg2
from datetime import datetime, timedelta

# --- КОНФИГУРАЦИЯ ---
# Токен бота берется из переменных окружения
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
# Ссылка на базу данных (Internal Database URL из Render)
DATABASE_URL = os.environ.get('DATABASE_URL')

if not TOKEN:
    # Для локального теста можешь раскомментировать и вставить токен вручную, 
    # но перед загрузкой на Render верни как было.
    # TOKEN = "ТВОЙ_ТОКЕН"
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

bot = telebot.TeleBot(TOKEN)

# ID админов
users = [1035549880]

TRIAL_DURATION_DAYS = 1

# --- РАБОТА С БАЗОЙ ДАННЫХ (PostgreSQL) ---

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Создаем таблицу для хранения пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trial_users (
            user_id BIGINT PRIMARY KEY,
            trial_start TIMESTAMP NOT NULL,
            trial_expiry TIMESTAMP NOT NULL,
            trial_used BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def get_trial_info(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT trial_start, trial_expiry, trial_used FROM trial_users WHERE user_id = %s",
        (user_id,)
    )
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def get_trial_remaining(user_id):
    trial_info = get_trial_info(user_id)
    if trial_info is None:
        return None
    trial_start, trial_expiry, trial_used = trial_info
    
    now = datetime.now()
    if now >= trial_expiry:
        return 0
    remaining = trial_expiry - now
    return remaining

def has_used_trial(user_id):
    trial_info = get_trial_info(user_id)
    if trial_info is None:
        return False
    return trial_info[2]

def start_trial(user_id):
    if has_used_trial(user_id):
        return False
    
    now = datetime.now()
    expiry_time = now + timedelta(days=TRIAL_DURATION_DAYS)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Пытаемся добавить пользователя. 
    # ON CONFLICT DO NOTHING защищает, если запись уже есть (хотя мы проверили has_used_trial)
    cur.execute(
        """
        INSERT INTO trial_users (user_id, trial_start, trial_expiry, trial_used)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id, now, expiry_time)
    )
    
    # Если запись была вставлена, rowcount будет 1
    rows_affected = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    return rows_affected > 0

def has_trial_access(user_id):
    remaining = get_trial_remaining(user_id)
    if remaining is None or remaining == 0:
        return False
    return True

def has_access(user_id, topic_id=None):
    if user_id in users:
        return 'full'
    if has_trial_access(user_id) and topic_id == 'topic_1':
        return 'trial'
    return None

def get_status_text(user_id):
    if user_id in users:
        return '⚡ Статус подписки - <b>Активная</b>'
    remaining = get_trial_remaining(user_id)
    if remaining and remaining != 0:
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60) 
        return f'🎁 Пробный период\n📚 Доступен раздел: Эмбриология\n⏱ Осталось: {hours} ч. {minutes} мин.\n\nДля полного доступа обратитесь к @Allina_allin'
    if has_used_trial(user_id):
        return '❌ Пробный период истёк\n\nДля полного доступа обратитесь к @Allina_allin'
    return '🔓 Нажмите кнопку ниже, чтобы активировать пробный период на 1 день!\n📚 Будет доступен раздел: Эмбриология\n\nДля полного доступа обратитесь к @Allina_allin'

# --- ЛОГИКА БОТА ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    is_subscribed = user_id in users

    status_text = get_status_text(user_id)

    markup = types.InlineKeyboardMarkup()
  
    if not is_subscribed and not has_trial_access(user_id) and not has_used_trial(user_id):
        trial_btn = types.InlineKeyboardButton('🆓 Активировать пробный период (1 день)', callback_data='activate_trial')
        markup.row(trial_btn)
  
    # КНОПКИ ГЛАВНОГО МЕНЮ
    item1 = types.InlineKeyboardButton('👶 Эмбриология', callback_data='topic_1')
    item2 = types.InlineKeyboardButton('💈 Эпителиальные ткани', callback_data='topic_2')
    item3 = types.InlineKeyboardButton('🩸 Кровь и ткани внутренней среды', callback_data='topic_3')
    item4 = types.InlineKeyboardButton('🦴 Волокнистая, скелетная и жировая ткани', callback_data='topic_4')
    item5 = types.InlineKeyboardButton('👅 Мышечные и нервные ткани', callback_data='topic_5')
    item6 = types.InlineKeyboardButton('💉 ССС, органы кроветворения', callback_data='topic_6')
    item7 = types.InlineKeyboardButton('👄 Эндокринная система', callback_data='topic_7')
    item8 = types.InlineKeyboardButton('👃 Пищеварительная и дыхательная', callback_data='topic_8')
    item9 = types.InlineKeyboardButton('🔞 Мочевыделительная и половая', callback_data='topic_9')
    item10 = types.InlineKeyboardButton('ℹ️ Информация', callback_data='topic_10')

    markup.row(item1, item2)
    markup.row(item3)
    markup.row(item4)
    markup.row(item5)
    markup.row(item6)
    markup.row(item7)
    markup.row(item8)
    markup.row(item9)
    markup.row(item10)

    bot.send_message(
        message.chat.id,
        f'Привет, {message.from_user.first_name}!\n\n{status_text}',
        parse_mode='html', reply_markup=markup
    )


# ДАННЫЕ (Заполни здесь свои кнопки и ссылки)
topics = {
    'topic_1': '👶 Эмбриология',
    'topic_2': '💈 Эпителиальные ткани',
    'topic_3': '🩸 Кровь и ткани внутренней среды',
    'topic_4': '🦴 Волокнистая, скелетная и жировая ткани',
    'topic_5': '👅 Мышечные и нервные ткани',
    'topic_6': '💉 ССС, органы кроветворения',
    'topic_7': '👄 Эндокринная система',
    'topic_8': '👃 Пищеварительная и дыхательная',
    'topic_9': '🔞 Мочевыделительная и половая',
}

# Сюда пиши названия кнопок внутри тем
topic_buttons = {
    'topic_1': [
        'Cтроение сперматозоида',
        'Строение женской половой клетки',
        'Оплодотворение',
        'Дробление',
        # ... остальные кнопки темы 1 ...
    ],
    'topic_2': [
        'Основы цитологии', 
        # ... и так далее для всех 9 тем ...
    ],
    # Оставь пустыми те, которые еще не заполнил, чтобы не было ошибок
    'topic_3': [], 'topic_4': [], 'topic_5': [],
    'topic_6': [], 'topic_7': [], 'topic_8': [], 'topic_9': [],
}

# Сюда пиши контент (текст или ссылки)
topic_content = {
    'topic_1': {
        1: 'https://docs.google.com/document/d/EXAMPLE_LINK_1',
        2: 'https://docs.google.com/document/d/EXAMPLE_LINK_2',
        # ... ссылки должны соответствовать порядку кнопок ...
    },
    'topic_2': {}, 'topic_3': {}, 'topic_4': {}, 'topic_5': {},
    'topic_6': {}, 'topic_7': {}, 'topic_8': {}, 'topic_9': {},
}


@bot.callback_query_handler(func=lambda call: call.data == 'activate_trial')
def activate_trial_callback(call):
    user_id = call.message.chat.id
    
    if user_id in users:
        bot.answer_callback_query(call.id, '⚡ У вас уже есть полный доступ!')
        return
    
    if has_used_trial(user_id):
        bot.answer_callback_query(call.id, '❌ Вы уже использовали пробный период!')
        return
    
    if start_trial(user_id):
        bot.answer_callback_query(call.id, '🎁 Пробный период активирован!')
        start(call.message) # Обновляем меню
    else:
        bot.answer_callback_query(call.id, '❌ Не удалось активировать (ошибка или уже активирован)')
@bot.callback_query_handler(func=lambda call: call.data.startswith('topic_'))
def topic_callback(call):
    topic_id = call.data
    user_id = call.message.chat.id
    
    if topic_id == 'topic_10':
        info_text = '''ℹ️ <b>Информация о боте</b>\n\n🔬 Материалы по гистологии.\n💰 По вопросам доступа: @Allina_allin'''
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton('⬅️ Назад', callback_data='back_to_menu')
        markup.row(back_btn)
        bot.edit_message_text(info_text, call.message.chat.id, call.message.message_id, parse_mode='html', reply_markup=markup)
        return
    
    access = has_access(user_id, topic_id)
    
    if access is None:
        if has_used_trial(user_id):
            bot.answer_callback_query(call.id, '❌ Пробный период истёк.')
        else:
            bot.answer_callback_query(call.id, '🔒 Активируйте пробный период.')
        return
    
    if access == 'trial' and topic_id != 'topic_1':
        bot.answer_callback_query(call.id, '🔒 В пробной версии доступна только Эмбриология')
        return
    
    if topic_id not in topic_buttons or not topic_buttons[topic_id]:
        bot.answer_callback_query(call.id, '❌ Раздел пуст или в разработке')
        return
    
    topic_name = topics.get(topic_id, 'Раздел')
    buttons = topic_buttons[topic_id]
    
    markup = types.InlineKeyboardMarkup()
    for i, btn_text in enumerate(buttons):
        # content_topic_1_1 (индекс + 1)
        btn = types.InlineKeyboardButton(btn_text, callback_data=f'content_{topic_id}_{i+1}')
        markup.row(btn)
    
    back_btn = types.InlineKeyboardButton('⬅️ Назад', callback_data='back_to_menu')
    markup.row(back_btn)
    
    bot.edit_message_text(
        f'📖 <b>{topic_name}</b>\n\nВыберите тему:',
        call.message.chat.id,
        call.message.message_id,
        parse_mode='html',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('content_'))
def content_callback(call):
    parts = call.data.split('_')
    # Ожидаем: content_topic_1_1 -> parts[1]='topic', parts[2]='1', parts[3]='1'
    # topic_id будет 'topic_1'
    if len(parts) >= 4:
        topic_id = f'{parts[1]}_{parts[2]}'
        content_idx = int(parts[3])
    else:
        # На случай странного формата, просто игнорируем
        bot.answer_callback_query(call.id, '❌ Ошибка данных')
        return

    user_id = call.message.chat.id
    access = has_access(user_id, topic_id)
    
    if access is None:
        bot.answer_callback_query(call.id, '🔒 Нет доступа')
        return
    
    if topic_id not in topic_content or content_idx not in topic_content[topic_id]:
        bot.answer_callback_query(call.id, '❌ Контент не найден')
        return
    
    content = topic_content[topic_id][content_idx]
    
    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton('⬅️ Назад к разделу', callback_data=topic_id)
    menu_btn = types.InlineKeyboardButton('🏠 Главное меню', callback_data='back_to_menu')
    markup.row(back_btn)
    markup.row(menu_btn)
    
    bot.edit_message_text(
        content,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='html',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_menu')
def back_to_menu_callback(call):
    start(call.message)


if name == 'main':
    # Инициализация БД при старте
    try:
        init_db()
        print("Database initialized.")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        
    print('Bot started...')
    bot.polling(none_stop=True)
