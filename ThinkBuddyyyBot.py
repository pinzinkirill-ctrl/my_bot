import telebot
import pandas as pd
import sqlite3
import os
import html

# Считываем токен из переменных окружения хостинга
TOKEN = ("8067866743:AAEwaJXCwByaaHp0RK-0XLMBsDMOz06mHoY")
bot = telebot.TeleBot(TOKEN)

# Твой ID в Telegram для доступа к админ-панели /stats
ADMIN_ID = 105385  

# Функция для нормализации текста (приравниваем Е и Ё)
def normalize_text(text):
    if pd.isna(text):
        return ""
    return str(text).lower().strip().replace('ё', 'е')

# Создаёт таблицу статистики в СУБД SQLite, если её ещё нет
def init_stats():
    try:
        with sqlite3.connect("statistics.db") as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    user_name TEXT,
                    query TEXT NOT NULL
                )
                """
            )
    except Exception as e:
        print(f"Ошибка базы логов: {e}")

# Безопасная запись логов напрямую в файл statistics.db
def save_stat(user_id, user_name, query):
    try:
        with sqlite3.connect("statistics.db", timeout=10) as connection:
            connection.execute(
                "INSERT INTO statistics (user_id, user_name, query) VALUES (?, ?, ?)",
                (user_id, user_name, query)
            )
    except Exception as e:
        print(f"Не удалось сохранить статистику: {e}")

# Главное меню бота
def get_main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🎲 Случайный термин"))
    markup.add(telebot.types.KeyboardButton("📚 Весь список слов"))
    return markup

# Функция разбиения длинных сообщений (до 4096 символов - фикс Kimi)
def send_long_message(chat_id, text, reply_markup=None):
    if len(text) <= 4096:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        for i in range(0, len(text), 4096):
            part = text[i:i+4096]
            current_markup = reply_markup if (i + 4096 >= len(text)) else None
            bot.send_message(chat_id, part, parse_mode='HTML', reply_markup=current_markup)

@bot.message_handler(commands=['start'])
def start_command(message):
    init_stats()  # Инициализируем БД логов при первом запуске
    bot.send_message(
        message.chat.id, 
        "Привет! Я твой бот-стратег по книгам В. Квинта. Введи термин или выбери действие ниже:", 
        reply_markup=get_main_menu()
    )

# АДМИН-ПАНЕЛЬ /stats
@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID and message.from_user.username != "kirya52142":
        bot.send_message(message.chat.id, "У вас нет прав для просмотра аналитики.")
        return
        
    try:
        with sqlite3.connect("statistics.db") as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*), COUNT(DISTINCT user_id) FROM statistics")
            total_req, total_users = cursor.fetchone()
            
            cursor.execute("SELECT query, COUNT(*) FROM statistics WHERE query NOT LIKE '%кнопка:%' GROUP BY query ORDER BY COUNT(*) DESC LIMIT 5")
            top_queries = cursor.fetchall()
            
            cursor.execute("SELECT query, COUNT(*) FROM statistics WHERE query LIKE '%не найдено:%' GROUP BY query ORDER BY COUNT(*) DESC LIMIT 5")
            failed_queries = cursor.fetchall()

        report = f"📊 <b>Аналитика продукта (СУБД SQLite):</b>\n\n"
        report += f"• Всего уникальных пользователей: <code>{total_users}</code>\n"
        report += f"• Всего обработано запросов: <code>{total_req}</code>\n\n"
        
        report += "🔝 <b>Популярные термины Квинта:</b>\n"
        for q, count in top_queries:
            report += f"— {html.escape(q)} ({count} раз)\n"
            
        if failed_queries:
            report += "\n❌ <b>Чего не хватает в Excel (ошибки поиска):</b>\n"
            for q, count in failed_queries:
                clean_q = q.replace("Не найдено:", "").replace("не найдено:", "")
                report += f"— {html.escape(clean_q)} ({count} раз)\n"
                
        bot.send_message(message.chat.id, report, parse_mode='HTML')
    except Exception as e:
        bot.send_message(message.chat.id, "Ошибка сбора статистики.", reply_markup=get_main_menu())

@bot.message_handler(content_types=['text'])
def handle_messages(message):
    user_query = message.text.strip()
    user_name = message.from_user.username or message.from_user.first_name
    
    try:
        df = pd.read_excel('database.xlsx', sheet_name=0)
        normalized_query = normalize_text(user_query)
        
        # 1. ФИЧА: ВЕСЬ СПИСОК СЛОВ В АЛФАВИТНОМ ПОРЯДКЕ
        if user_query == "📚 Весь список слов":
            save_stat(message.from_user.id, user_name, "Кнопка: Весь список")
            all_terms = df['Термин'].dropna().astype(str).tolist()
            
            clean_list = [html.escape(str(t).split(',')[0].strip()) for t in all_terms]
            sorted_list = sorted(list(set(clean_list)))
            
            text_list = "\n• ".join(sorted_list)
            response_text = f"<b>Доступные термины (в алфавитном порядке):</b>\n\n• {text_list}"
            send_long_message(message.chat.id, response_text, reply_markup=get_main_menu())
            return

        # 2. ФИЧА: СЛУЧАЙНЫЙ ТЕРМИН
        elif user_query == "🎲 Случайный термин":
            save_stat(message.from_user.id, user_name, "Кнопка: Случайный термин")
            valid_df = df.dropna(subset=['Термин', 'Определение'])
            if not valid_df.empty:
                random_row = valid_df.sample(n=1).iloc[0]
                show_result(message.chat.id, random_row, df)
            else:
                bot.send_message(message.chat.id, "База данных пуста!", reply_markup=get_main_menu())
            return
        
        # ОБЫЧНЫЙ ПОИСК ТЕРМИНА
        else:
            matched_indices = []
            for index, row in df.iterrows():
                if pd.isna(row['Термин']) or pd.isna(row['Определение']):
                    continue
                keywords = [normalize_text(k) for k in str(row['Термин']).split(',')]
                if normalized_query in keywords or any(normalized_query in kw for kw in keywords if len(normalized_query) >= 4):
                    matched_indices.append(index)

            if len(matched_indices) == 0:
                save_stat(message.from_user.id, user_name, f"Не найдено:{user_query}")
                bot.send_message(message.chat.id, "К сожалению, такой термин в трудах В. Квинта не найден. Проверь написание!", reply_markup=get_main_menu())
                
            elif len(matched_indices) == 1:
                save_stat(message.from_user.id, user_name, user_query)
                show_result(message.chat.id, df.iloc[matched_indices[0]], df)
                
            else:
                save_stat(message.from_user.id, user_name, user_query)
                markup = telebot.types.InlineKeyboardMarkup()
                for idx in matched_indices[:30]:
                    term_name = str(df.iloc[idx]['Термин']).split(',')[0].strip()
                    markup.add(telebot.types.InlineKeyboardButton(text=term_name, callback_data=f"row_{idx}"))
                    
                bot.send_message(message.chat.id, f"По запросу '{message.text}' найдено несколько похожих терминов. Выбери нужный:", reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, "Произошла внутренняя ошибка базы данных.", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith('row_'))
def callback_inline(call):
    try:
        idx = int(call.data.split('_')[1])
        df = pd.read_excel('database.xlsx', sheet_name=0)
        bot.answer_callback_query(call.id)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        show_result(call.message.chat.id, df.iloc[idx], df)
    except Exception:
        bot.send_message(call.message.chat.id, "Не удалось загрузить выбранный термин.", reply_markup=get_main_menu())

def show_result(chat_id, row, df):
    main_term = html.escape(str(row['Термин']).split(',')[0].strip())
    raw_definition = html.escape(str(row['Определение']).strip())
    definition = f"<b>{main_term}</b> — {raw_definition}"
    
    has_photo = False
    if 'Картинка' in df.columns and not pd.isna(row['Картинка']):
        photo_url = str(row['Картинка']).strip()
        if photo_url.startswith('http'):
            has_photo = True
            
    if has_photo:
        if len(definition) <= 1024:
            bot.send_photo(chat_id, photo_url, caption=definition, parse_mode='HTML', reply_markup=get_main_menu())
        else:
            bot.send_photo(chat_id, photo_url)
            send_long_message(chat_id, definition, reply_markup=get_main_menu())
    else:
        send_long_message(chat_id, definition, reply_markup=get_main_menu())

if __name__ == "__main__":
    init_stats()
    bot.polling(none_stop=True)
