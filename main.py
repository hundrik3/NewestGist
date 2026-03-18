import telebot
from telebot import types
import psycopg2
import os
from datetime import datetime, timedelta
import flask

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')

top1 = os.environ.get('TOP1')
top2 = os.environ.get('TOP2')
top3 = os.environ.get('TOP3')
top4 = os.environ.get('TOP4')
top5 = os.environ.get('TOP5')
top6 = os.environ.get('TOP6')
top7 = os.environ.get('TOP7')
top8 = os.environ.get('TOP8')
top9 = os.environ.get('TOP9')

manager = os.environ.get('MANAGER')
channel_id = os.environ.get('CHANNEL_ID')
channel_url = os.environ.get('CHANNEL_URL')

users = [2028669813, 1035549880]

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

bot = telebot.TeleBot(TOKEN)

TRIAL_DURATION_DAYS = 1

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
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
    return trial_expiry - now

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
    cur.execute(
        """
        INSERT INTO trial_users (user_id, trial_start, trial_expiry, trial_used)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id, now, expiry_time)
    )
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
        return '⚡ <b>Статус подписки</b> - <code>Активная</code>'
    remaining = get_trial_remaining(user_id)
    if remaining and remaining != 0:
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60) 
        return f'<b>🎁 Статус подписки</b> - <code>Пробная</code>\n\n📚 Доступный раздел: <code>👶 Эмбриология</code>\n🕧 Осталось: <code>{hours} ч. {minutes} мин.</code>'
    if has_used_trial(user_id):
        return f'❌ <b>Статус подписки</b> - <code>Неактивная</code>\n\n⭐ Для полного доступа обратитесь к {manager}'
    return f'🔓 Нажмите кнопку ниже, чтобы активировать пробный период на 24 часа!\n📚 Будет доступен раздел: 👶 Эмбриология'

def get_main_menu_markup(user_id):
    is_subscribed = user_id in users
    markup = types.InlineKeyboardMarkup()
    if not is_subscribed and not has_trial_access(user_id) and not has_used_trial(user_id):
        markup.row(types.InlineKeyboardButton('🎫 Активировать пробный период', callback_data='activate_trial'))
    buttons = [
        ('👶 Эмбриология', 'topic_1'), ('💈 Эпителиальные ткани', 'topic_2'),
        ('🩸 Кровь и ткани внутренней среды', 'topic_3'),
        ('🦴 Волокнистая, скелетная и жировая ткани', 'topic_4'),
        ('👅 Мышечные и нервные ткани', 'topic_5'),
        ('💉 ССС, органы кроветворения', 'topic_6'),
        ('👄 Эндокринная система', 'topic_7'),
        ('👃 Пищеварительная и дыхательная', 'topic_8'),
        ('🔞 Мочевыделительная и половая', 'topic_9'),
        ('ℹ️ Информация', 'topic_10'),
    ]
    markup.row(types.InlineKeyboardButton(buttons[0][0], callback_data=buttons[0][1]),
               types.InlineKeyboardButton(buttons[1][0], callback_data=buttons[1][1]))
    for text, data in buttons[2:]:
        markup.row(types.InlineKeyboardButton(text, callback_data=data))
    return markup

def is_subscribed(user_id):
    if not channel_id:
        return True 
    if user_id in users:
        return True
    
    try:
        status = bot.get_chat_member(channel_id, user_id).status
        return status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False

def get_sub_markup():
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton('📢 Подписаться на канал', url=channel_url))
    markup.row(types.InlineKeyboardButton('🔄 Я подписался', callback_data='check_sub'))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if not is_subscribed(user_id):
        bot.send_message(
            user_id,
            '❌ <b>Доступ закрыт!</b>\n\n⚠️ Для использования бота необходимо подписаться на наш канал.',
            parse_mode='html',
            reply_markup=get_sub_markup()
        )
        return
    bot.send_message(
        message.chat.id,
        f'👋 Привет, <b>{message.from_user.first_name}</b>!\n\n{get_status_text(user_id)}',
        parse_mode='html', reply_markup=get_main_menu_markup(user_id)
    )

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

topic_buttons = {
    'topic_1': ['Cтроение сперматозоида', 'Строение женской половой клетки', 'Оплодотворение', 'Дробление', 'Имплантация', 'Гаструляция', 'Провизорные органы', 'Нотогенез', 'Плацента: функции, развитие и строение', 'Развитие ЖКТ', 'Развитие дыхательной системы', 'Развитие жаберного аппарата', 'Развитие мочевыделительной системы', 'Развитие половой системы'],
    'topic_2': ['Основы цитологии', 'Приготовление гистологических препаратов', 'Виды окрасок препаратов', 'Эпителиальная ткань: общая характеристика, классификация и развитие', 'Эпителиальная ткань: однослойные эпителии', 'Многослойные эпителии: неороговевающий и переходный', 'Многослойный плоский ороговевающий эпителий', 'Железистые эпителии: общая характеристика и классификация', 'Железистые эпителии: примеры сложных желез, развитие'],
    'topic_3': ['Ткани внутренней среды. Свойства, классификация', 'Кровь. Основы гемограммы', 'Эритроциты: строение, функции', 'Эритроциты: строение плазмолеммы', 'Тромбоциты', 'Лейцоциты: нейтрофилы', 'Эозинофилы', 'Базофилы', 'Лимфоциты', 'Моноциты'],
    'topic_4': ['Собственно соединительная ткань: общая характеристика', 'РВСТ: клеточный состав', 'РВСТ: волокна и аморфное вещество', 'Плотная волокнистая соединительная ткань', 'Ткани со специальными свойствами: жировая ткань', 'Ткани со специальными свойствами: ретикулярная, слизистая и пигментная ткани', 'Хрящевая ткань', 'Скелетные соединительные ткани, обзор', 'Костная ткань. Остеобласты, остеоциты, остеокласты', 'Надкостница и виды костных тканей', 'Пластинчатая костная ткань. Остеоны. Плоские кости', 'Прямой остеогенез. Челюсть зародыша', 'Непрямой остеогенез'],
    'topic_5': ['Мышечные ткани. Классификация. Основные различия', 'Срез языка. Препарат', 'Строение саркомера', 'Организация миофиламентов', 'Мембранные системы мышечных волокон', 'Сокращение и типы мышечных волокон', 'Мышца как орган. Мион. НМЕ. Переход мышцы в сухожиление. Репарация мышечного волокна', 'Сердечная поперечно-полосатая мышечная ткань', 'Гладкая мышечная ткань', 'Нервная ткань. Функции нейронов и глиоцитов', 'Развитие нервной системы. Три типа нейронов', 'Проводящие пути. Отростки нейронов', 'Цитоплазма нейронов', 'Ультраструктура нейтрона', 'Нейроглия', 'Типы нервных волокон', 'Перехваты Ранвье', 'Нервные окончания', 'Синапсы', 'ЦНС. ПНС. Рефклекторные дуги и прочая магия', 'Нервные стволы, узлы', 'Спинной мозг', 'Мозжечек', 'Кора полушарий', 'Препарат задняя стенка глаза', 'Кортиев орган', 'Вкусовая почка'],
    'topic_6': ['ССС | Артерии и вены. Общий план', 'ССС | Артерии: классификация, особенности строения', 'ССС | Принципы строения вен и их классификация', 'ССС | Сердце: развитие, строение, функции', 'ССС | Строение микроциркуляторного русла', 'ССС | Лимфатическая система', 'Кроветворение | Этапы кроветворения', 'Кроветворение | Органы кроветворения. Красный костный мозг - строение', 'Кроветворение | Гемопоэтические клетки', 'Кроветворение | Эритроципотоэз и тромбоцитопоэз', 'Кроветворение | Гранулоцитопоэз', 'Кроветворение | Лимфоцитопоэз | АнтигенНЕзависимая дифференцировка', 'Кроветворение | Антигенозависимая дифференцировка', 'Кроветворение | Активированные Т-лимфоциты', 'Кроветворение | Активация В-лимфоцитов, иммуноглобины', 'Кроветворение | Тимус', 'Кроветворение | Лимфатический узел', 'Кроветворение | Селезенка'],
    'topic_7': ['Общий план строения эндокринной системы', 'Гипотоламо-гипофизарная система', 'Эпифиз', 'Щитовидная железа', 'Околощитовидные железы', 'Надпочечники', 'APUD - серия', 'Общий план строения ЖКТ', 'Ротовая полость: губы, щеки, десны, мягкое и твердое небо', 'Язык', 'Лимфоэпителиальное глоточное кольцо', 'Слюнные железы', 'Общий план строения зуба. Эмаль', 'Строение зуба. Дентин', 'Строение зуба. Цемент и пульпа', 'Одонтогенез. Первый и второй этапы', 'Одонтогенез. Третий этап - гистогенез тканей зуба'],
    'topic_8': ['Пищевод', 'Желудок', 'Тонкая кишка', 'Толстая кишка', 'Печень', 'Поджелудочная железа', 'Общая характеристика, развитие и функции дыхательной системы', 'Носовая полость, гортань', 'Трахея, бронхиальное дерево', 'Респираторный отдел легкого', 'Кожа', 'Потовые, сальные железы, волосы и ногти', 'Молочные железы'],
    'topic_9': ['Почка: развитие и общая характеристика строения', 'Почка: нефроны и собирательные трубочки', 'Почка: юкстагломерулярный комплекс', 'Мочевыводящие пути: строение и функции', 'Яичко: развитие, строение и функции', 'Семявыносящие пути: развитие, строение и функции', 'Предстательная железа: развитие, строение и функции', 'Яичник: развитие, строение, функции, циклическая деятельность', 'Маточная труба: развитие, строение и функции', 'Матка: развитие, строение, регенерация, циклические изменения', 'Шейка матки: строение в разных отделах, функции, изменения в разные фазы меструального цикла', 'Влагалище,  развитие, строение, функции и регенерация'],
}

topic_urls = {
    'topic_1': (f'{top1}', 14),
    'topic_2': (f'{top2}', 9),
    'topic_3': (f'{top3}', 10),
    'topic_4': (f'{top4}', 13),
    'topic_5': (f'{top5}', 27),
    'topic_6': (f'{top6}', 18),
    'topic_7': (f'{top7}', 17),
    'topic_8': (f'{top8}', 13),
    'topic_9': (f'{top9}', 12),
}

def get_topic_content(topic_id, content_idx):
    if topic_id not in topic_urls:
        return None
    url, count = topic_urls[topic_id]
    if content_idx < 1 or content_idx > count:
        return None
    return f'{url}'

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
        bot.edit_message_text(
            f'🎁 Пробный период активирован!\n\n{get_status_text(user_id)}',
            call.message.chat.id, call.message.message_id,
            parse_mode='html', reply_markup=get_main_menu_markup(user_id)
        )
    else:
        bot.answer_callback_query(call.id, '❌ Не удалось активировать')

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_menu')
def back_to_menu_callback(call):
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        get_status_text(user_id),
        call.message.chat.id, call.message.message_id,
        parse_mode='html', reply_markup=get_main_menu_markup(user_id)
    )

@bot.callback_query_handler(func=lambda call: call.data == 'check_sub')
def check_sub_callback(call):
    user_id = call.message.chat.id
    if is_subscribed(user_id):
        bot.answer_callback_query(call.id, '✅ Подписка подтверждена!')
        bot.edit_message_text(
            f'👋 Привет, <b>{call.from_user.first_name}</b>!\n\n{get_status_text(user_id)}',
            user_id, call.message.message_id,
            parse_mode='html', reply_markup=get_main_menu_markup(user_id)
        )
    else:
        bot.answer_callback_query(call.id, '❌ Вы еще не подписались!', show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('topic_'))
def topic_callback(call):
    topic_id = call.data
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if not is_subscribed(user_id):
        bot.answer_callback_query(call.id, '❌ Вы отписались от канала!', show_alert=True)
        bot.edit_message_text(
            '⚠️ <b>Доступ закрыт!</b>\n\nДля использования бота необходимо быть подписанным на наш канал.',
            user_id, call.message.message_id,
            parse_mode='html',
            reply_markup=get_sub_markup()
        )
        return
    
    bot.answer_callback_query(call.id)
    
    if topic_id == 'topic_10':
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('⬅️ Назад', callback_data='back_to_menu'))
        bot.edit_message_text( f'ℹ️ <b>Информация</b>\n\n🔬 9 разделов для изучения\n\n⭐ Поддержка: {manager}',
            call.message.chat.id, call.message.message_id, parse_mode='html', reply_markup=markup
        )
        return
    
    access = has_access(user_id, topic_id)
    if access is None or (access == 'trial' and topic_id != 'topic_1'):
        topic_name = topics.get(topic_id, 'Раздел')
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('⬅️ Назад', callback_data='back_to_menu'))
        if has_used_trial(user_id):
            text = f'<b>{topic_name}</b>\n\n🔒 Этот раздел недоступен.\n\n⌛ Ваша пробная подписка истекла.\n\n⭐ Для полного доступа обратитесь к {manager}'
        elif access == 'trial':
            text = f'<b>{topic_name}</b>\n\n🔒 Этот раздел недоступен.\n\n📚 В пробной версии доступна только 👶 Эмбриология.\n\n⭐ Для полного доступа обратитесь к {manager}'
        else:
            text = f'<b>{topic_name}</b>\n\n🔒 Этот раздел недоступен.\n\n🎫 Активируйте пробный период для доступа к разделу 👶 Эмбриология.\n\n⭐ Для полного доступа обратитесь к {manager}'
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='html', reply_markup=markup)
        return
    if topic_id not in topic_buttons or not topic_buttons[topic_id]:
        bot.answer_callback_query(call.id, '❌ Раздел пуст или в разработке')
        return
    
    markup = types.InlineKeyboardMarkup()
    for i, btn_text in enumerate(topic_buttons[topic_id]):
        markup.row(types.InlineKeyboardButton(btn_text, callback_data=f'content_{topic_id}_{i+1}'))
    markup.row(types.InlineKeyboardButton('⬅️ Назад', callback_data='back_to_menu'))
    
    bot.edit_message_text(
        f'<b>{topics.get(topic_id, "Раздел")}</b>',
        call.message.chat.id, call.message.message_id,
        parse_mode='html', reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('content_'))
def content_callback(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    if len(parts) < 4:
        return
    
    topic_id = f'{parts[1]}_{parts[2]}'
    content_idx = int(parts[3])
    user_id = call.message.chat.id
    
    if has_access(user_id, topic_id) is None:
        return
    
    content = get_topic_content(topic_id, content_idx)
    if content is None:
        bot.answer_callback_query(call.id, '❌ Не найдено')
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton('⬅️ Назад к разделу', callback_data=topic_id))
    markup.row(types.InlineKeyboardButton('🏠 Главное меню', callback_data='back_to_menu'))
    
    bot.edit_message_text(content, call.message.chat.id, call.message.message_id, parse_mode='html', reply_markup=markup)

WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST')
WEBHOOK_PORT = int(os.environ.get('PORT', '10000'))

if WEBHOOK_HOST:
    app = flask.Flask(__name__)
    WEBHOOK_URL_BASE = f"https://{WEBHOOK_HOST}"
    WEBHOOK_URL_PATH = f"/{TOKEN}"
    
    @app.route(WEBHOOK_URL_PATH, methods=['POST'])
    def webhook():
        if flask.request.headers.get('content-type') == 'application/json':
            update = telebot.types.Update.de_json(flask.request.get_data().decode('utf-8'))
            bot.process_new_updates([update])
            return ''
        flask.abort(403)

if __name__ == '__main__':
    try:
        init_db()
        print("✅ Database initialized.")
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        
    if WEBHOOK_HOST:
        bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
        print(f"Webhook: {WEBHOOK_URL_BASE}{WEBHOOK_URL_PATH}")
        app.run(host='0.0.0.0', port=WEBHOOK_PORT)
    else:
        print('♻️ Starting in Polling mode...')
        bot.polling(none_stop=True)
