import telebot
import pandas as pd

bot = telebot.TeleBot("8067866743:AAHoU1EgQrMEKrwQoUbfGlZFkFeNvVhmbo0")

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "Привет! Я твой бот-стратег по книгам В. Квинта. Введи термин, и я найду его в Excel!")

@bot.message_handler(content_types=['text'])
def search_term(message):
    user_query = message.text.lower().strip()
    
    try:
        df = pd.read_excel('database.xlsx')
        matched_rows = []
        
        # Листаем таблицу и проверяем ключевые слова через запятую
        for index, row in df.iterrows():
            if pd.isna(row['Термин']) or pd.isna(row['Определение']):
                continue
                
            term_cell = str(row['Термин']).lower()
            # Разделяем ячейку А по запятым, убирая пробелы вокруг слов
            keywords = [k.strip() for k in term_cell.split(',')]
            
            # Проверяем точное или частичное совпадение (неполный поиск)
            if user_query in keywords or any(user_query in kw for kw in keywords if len(user_query) >= 4):
                matched_rows.append(row)
        
        # ЕСЛИ НИЧЕГО НЕ НАШЛИ
        if len(matched_rows) == 0:
            bot.send_message(message.chat.id, "К сожалению, такой термин в трудах В. Квинта не найден. Проверь написание!")
            
        # ЕСЛИ НАШЛИ СТРОГО ОДИН ТЕРМИН (Идеально)
        elif len(matched_rows) == 1:
            selected_row = matched_rows[0]  # Исправлено: берем первую найденную строку из списка по индексу 0
            
            # Извлекаем данные, убирая пробелы
            raw_term = str(selected_row['Термин'])
            # Берем первое ключевое слово до запятой и делаем заглавную букву для красивого вывода
            main_term = raw_term.split(',')[0].strip().capitalize()
            raw_definition = str(selected_row['Определение']).strip()
            
            # Автосклейка: "Термин — Определение"
            definition = f"{main_term} — {raw_definition}"
            
            # Проверяем картинку в столбце "Картинка"
            has_photo = False
            if 'Картинка' in df.columns and not pd.isna(selected_row['Картинка']):
                photo_url = str(selected_row['Картинка']).strip()
                if photo_url.startswith('http'):
                    has_photo = True
            
            if has_photo:
                # Ограничение Telegram на подпись к фото — 1024 символа
                if len(definition) <= 1024:
                    bot.send_photo(message.chat.id, photo_url, caption=definition)
                else:
                    bot.send_photo(message.chat.id, photo_url)
                    bot.send_message(message.chat.id, definition)
            else:
                bot.send_message(message.chat.id, definition)
            
        # ЕСЛИ НАШЛИ НЕСКОЛЬКО ПОХОЖИХ СЛОВ (Выводим кнопки)
        else:
            markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            added_buttons = set()
            
            for row in matched_rows:
                raw_term = str(row['Termин'] if 'Termин' in row else row['Термин'])
                first_keyword = raw_term.split(',')[0].strip().capitalize()
                if first_keyword not in added_buttons:
                    markup.add(telebot.types.KeyboardButton(first_keyword))
                    added_buttons.add(first_keyword)
                
            bot.send_message(
                message.chat.id, 
                f"По запросу '{message.text}' найдено несколько похожих терминов. Введи нужный на клавиатуре:", 
                reply_markup=markup
            )
            
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при поиске: {e}")

bot.polling(none_stop=True)

