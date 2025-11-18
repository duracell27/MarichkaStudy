import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from config import Config
from database import db
from handlers.settings import (
    settings_command,
    settings_callback,
    get_add_child_conversation_handler,
    get_edit_child_conversation_handler
)
from handlers.lessons import (
    get_add_lesson_conversation_handler,
    timetable_command,
    handle_timetable_button,
    get_payment_entry_conversation_handler,
    balance_command,
    handle_balance_button,
    dashboard_command,
    handle_dashboard_button
)
from handlers.payments import get_add_payment_conversation_handler

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def access_control(func):
    """Декоратор для перевірки доступу користувача"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if not Config.is_allowed_user(user_id):
            await update.message.reply_text(
                "⛔ Вибачте, у вас немає доступу до цього бота."
            )
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            return

        return await func(update, context)

    return wrapper


@access_control
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /start"""
    user = update.effective_user

    # Додавання користувача в базу даних
    await db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )

    welcome_message = f"Привіт, {user.first_name}!\n\n"
    welcome_message += "Доступні команди:\n"
    welcome_message += "/start - Початок роботи\n"
    welcome_message += "/settings - Налаштування\n"
    welcome_message += "/addlesson - Додати заняття\n"
    welcome_message += "/payment - Внести оплату\n"
    welcome_message += "/balance - Баланс оплат\n"
    welcome_message += "/timetable - Розклад на день\n"
    welcome_message += "/dashboard - Звіт за місяць\n"
    welcome_message += "/help - Допомога\n"

    await update.message.reply_text(welcome_message)


@access_control
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /help"""
    help_text = "Я бот-помічник!\n\n"
    help_text += "Використовуйте /start для початку роботи.\n"
    help_text += "Надішліть мені будь-яке повідомлення, і я відповім!"

    await update.message.reply_text(help_text)


@access_control
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка текстових повідомлень"""
    user = update.effective_user
    message_text = update.message.text

    # Логування повідомлення
    await db.log_message(user.id, message_text)

    # Відповідь
    response = f"Ви написали: {message_text}"
    await update.message.reply_text(response)


async def callback_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логування всіх callback запитів"""
    if update.callback_query:
        logger.info(f"[GLOBAL] Callback received: {update.callback_query.data}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка помилок"""
    logger.error(f"Update {update} caused error {context.error}")


async def post_init(application: Application):
    """Функція, що виконується після ініціалізації бота"""
    await db.connect()
    logger.info("🚀 Бот запущено!")


async def post_shutdown(application: Application):
    """Функція, що виконується перед зупинкою бота"""
    await db.disconnect()
    logger.info("🛑 Бот зупинено!")


def main():
    """Головна функція запуску бота"""
    # Створення application
    application = (
        Application.builder()
        .token(Config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Реєстрація handlers
    # Група -2: Глобальне логування (найвищий пріоритет)
    application.add_handler(CallbackQueryHandler(callback_logger), group=-2)

    # Група -1: Команди з найвищим пріоритетом (працюють завжди)
    application.add_handler(CommandHandler("start", start_command), group=-1)
    application.add_handler(CommandHandler("help", help_command), group=-1)
    application.add_handler(CommandHandler("settings", settings_command), group=-1)
    application.add_handler(CommandHandler("timetable", timetable_command), group=-1)
    application.add_handler(CommandHandler("balance", balance_command), group=-1)
    application.add_handler(CommandHandler("dashboard", dashboard_command), group=-1)

    # Група 0: ConversationHandlers (за замовчуванням)
    application.add_handler(get_add_child_conversation_handler())
    application.add_handler(get_edit_child_conversation_handler())
    application.add_handler(get_add_lesson_conversation_handler())
    application.add_handler(get_payment_entry_conversation_handler())

    # Група 0: CallbackQuery обробники
    application.add_handler(CallbackQueryHandler(handle_timetable_button, pattern="^(timetable_|mark_|unmark_|cancel_|uncancel_)"))
    application.add_handler(CallbackQueryHandler(handle_balance_button, pattern="^(balance_)"))
    application.add_handler(CallbackQueryHandler(handle_dashboard_button, pattern="^(dashboard_)"))
    application.add_handler(CallbackQueryHandler(settings_callback))

    # Обробка текстових повідомлень (має бути останнім)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Обробка помилок
    application.add_error_handler(error_handler)

    # Запуск бота
    logger.info("Запуск бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
