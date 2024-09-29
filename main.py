from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
import json
import re
from collections import defaultdict
import time

# ID владельцевd
OWNER_IDS = [7488476093, 5535857928]

# Путь к файлу для хранения антиспам-списка
ANTI_SPAM_FILE = "anti_spam_list.json"

# Глобальный список антиспама
anti_spam_list = {}
# Словарь для отслеживания стикеров и гифок
media_count = defaultdict(int)
# Словарь для временных меток отправленных стикеров и гифок
last_media_time = defaultdict(int)

# Токен бота
TOKEN = "7513028997:AAHE_E0SkCt43GrMUQeOin96wR61m92oyHk"

def load_anti_spam_list():
    global anti_spam_list
    try:
        with open(ANTI_SPAM_FILE, "r") as file:
            anti_spam_list = json.load(file)
    except FileNotFoundError:
        anti_spam_list = {}

def save_anti_spam_list():
    with open(ANTI_SPAM_FILE, "w") as file:
        json.dump(anti_spam_list, file)

def is_owner(user_id):
    return user_id in OWNER_IDS

def is_admin(user_id, chat_id, context):
    """Проверка, является ли пользователь администратором в чате"""
    try:
        chat = context.bot.get_chat(chat_id)
        if chat.type in ["group", "supergroup"]:
            admins = chat.get_administrators()
            return any(admin.user.id == user_id for admin in admins)
    except Exception:
        return False
    return False

def handle_message(update: Update, context: CallbackContext):
    if update.message and update.message.text:
        message_text = update.message.text.strip()
        
        # Проверка на наличие ссылки в сообщении
        if re.search(r'http[s]?://|t.me/', message_text):
            user_id = update.effective_user.id
            if str(user_id) not in anti_spam_list:
                anti_spam_list[str(user_id)] = "Автоматическая блокировка спамера"
                save_anti_spam_list()
                context.bot.ban_chat_member(update.effective_chat.id, user_id)
                context.bot.send_message(update.effective_chat.id, f"{update.effective_user.first_name}, вы были заблокированы за отправку ссылки.")
            return  # Завершаем функцию, чтобы не продолжать обработку

        if is_owner(update.effective_user.id):
            # Обработка команд владельца
            process_owner_commands(update, context, message_text)

    # Проверка на антиспам для новых участников
    if update.message and update.message.new_chat_members:
        for member in update.message.new_chat_members:
            user_id = member.id
            if str(user_id) in anti_spam_list:
                reason = anti_spam_list[str(user_id)]
                context.bot.ban_chat_member(update.effective_chat.id, user_id)
                context.bot.send_message(update.effective_chat.id, f"Обнаружен спамер: {member.first_name} (@{member.username})!\nУдаляю.\nПричина: {reason}")

    # Удаление сообщений пользователей в антиспаме
    if update.message:
        user_id = str(update.effective_user.id)
        if user_id in anti_spam_list:
            if not is_admin(user_id, update.effective_chat.id, context):
                context.bot.ban_chat_member(update.effective_chat.id, user_id)
                context.bot.send_message(update.effective_chat.id, "Вы были заблокированы за нарушение.")
            else:
                context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)

def handle_media(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    current_time = time.time()

    if update.message.sticker or update.message.animation:  # Проверка на стикеры или анимации
        if user_id not in last_media_time or current_time - last_media_time[user_id] > 1:
            media_count[user_id] = 1  # Сбросить счетчик, если прошло больше 1 секунды
        else:
            media_count[user_id] += 1  # Увеличиваем счетчик стикеров или гифок
        
        last_media_time[user_id] = current_time  # Обновляем время последнего стикера или гифки

        if media_count[user_id] >= 5:
            reason = "Какая-то активность похоже на рейд"
            anti_spam_list[user_id] = reason
            save_anti_spam_list()
            context.bot.ban_chat_member(update.effective_chat.id, user_id)
            context.bot.send_message(update.effective_chat.id, f"{update.effective_user.first_name} был заблокирован за отправку слишком большого количества стикеров или гифок подряд.")
            media_count[user_id] = 0  # Сбросить счетчик после бана

def handle_private_message(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_id in anti_spam_list:
        reason = anti_spam_list[user_id]
        update.message.reply_text(f"Вы в антиспаме. Причина: {reason}")
    else:
        update.message.reply_text("Вы не в антиспаме.")

def process_owner_commands(update, context, message_text):
    if message_text.startswith("+ас"):
        args = message_text.split()
        if len(args) > 1:
            user_id = args[1].replace('@', '')  # Убираем @
            reason = " ".join(args[2:]) if len(args) > 2 else "Причина не указана"

            if user_id not in anti_spam_list:
                anti_spam_list[user_id] = reason  # Добавляем пользователя с причиной
                save_anti_spam_list()  # Сохраняем изменения в файл
                update.message.reply_text(f'{user_id} добавлен в антиспам с причиной: {reason}')
            else:
                update.message.reply_text(f'{user_id} уже находится в антиспаме.')
        else:
            update.message.reply_text('Пожалуйста, укажите пользователя для добавления.')

    elif message_text.startswith("-ас"):
        args = message_text.split()
        if len(args) > 1:
            user_id = args[1].replace('@', '')  # Убираем @
            if user_id in anti_spam_list:
                del anti_spam_list[user_id]
                save_anti_spam_list()  # Сохраняем изменения в файл
                update.message.reply_text(f'{user_id} удален из антиспама.')
            else:
                update.message.reply_text(f'{user_id} не найден в антиспаме.')
        else:
            update.message.reply_text('Пожалуйста, укажите пользователя для удаления.')

    elif message_text == "список":
        if anti_spam_list:
            response = 'Список антиспама:\n'
            for user_id, reason in anti_spam_list.items():
                response += f'{user_id} - {reason}\n'
            update.message.reply_text(response)
        else:
            update.message.reply_text('Антиспам пуст.')

    elif message_text == "кик спамеров":
        for user_id in anti_spam_list.keys():
            try:
                context.bot.ban_chat_member(update.effective_chat.id, user_id)
                update.message.reply_text(f'{user_id} исключен из чата.')
            except Exception as e:
                update.message.reply_text(f'Не удалось исключить {user_id}. Ошибка: {e}')
        update.message.reply_text('Все спамеры исключены из чата.')

    elif message_text == "удалить всех":
        anti_spam_list.clear()  # Очищаем список
        save_anti_spam_list()
        update.message.reply_text('Все пользователи удалены из антиспама.')

    elif message_text.startswith("баны"):
        args = message_text.split()
        if len(args) > 1:
            user_id = args[1].replace('@', '')  # Убираем @
            if user_id in anti_spam_list:
                reason = anti_spam_list[user_id]
                update.message.reply_text(f'{user_id} находится в антиспаме. Причина: {reason}')
            else:
                update.message.reply_text(f'{user_id} не найден в антиспаме.')
        else:
            update.message.reply_text('Пожалуйста, укажите пользователя для проверки.')

def main():
    load_anti_spam_list()  # Загружаем список при запуске
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Обработка текстовых сообщений
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dispatcher.add_handler(MessageHandler(Filters.status_update.new_chat_members, handle_message))  # Обработка новых участников
    dispatcher.add_handler(MessageHandler(Filters.sticker | Filters.animation, handle_media))  # Обработка стикеров и анимаций
    dispatcher.add_handler(MessageHandler(Filters.private & Filters.text & Filters.regex(r'^мои баны$'), handle_private_message))  # Обработка команды "мои баны"

    updater.start_polling()
    updater.idle()  # Ожидание завершения работы

if __name__ == "__main__":
    main()
