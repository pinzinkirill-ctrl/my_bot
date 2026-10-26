import telebot
import pandas as pd
# Создание экземпляра бота
bot = telebot.TeleBot("8067866743:AAHOu1EgQrMEKrwQoUbfGlZfkFeNvVhmbo0")


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "Привет! Я твой бот-стратег. Чем могу помочь?")


# Обработчик команды /help
@bot.message_handler(commands=['help', 'помощь'])
def help_command(message):
    bot.reply_to(message, "Раздел помощи. Информация о боте")


@bot.message_handler(content_types=['text'])
# --- НОВЫЙ БЛОК: Поиск терминов в Excel ---

@bot.message_handler(content_types=['text'])
def search_term(message):
    user_query = message.text.lower().strip()

    try:
        df = pd.read_excel('database.xlsx')
        result = df[df['Термин'].astype(str).str.lower().str.strip() == user_query]

        if not result.empty:
            definition = result.iloc[0]['Определение']  # Добавил, чтобы бралась первая строка без ошибок
            bot.send_message(message.chat.id, definition)
        else:
            bot.send_message(message.chat.id,
                             "К сожалению, такой термин в трудах В. Квинта не найден. Проверь написание!")

    except FileNotFoundError:
        bot.send_message(message.chat.id, "Ошибка: Файл базы данных 'database.xlsx' не найден в папке с ботом!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при чтении таблицы: {e}")


# Запуск бота
bot.polling(none_stop=True)
