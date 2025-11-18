from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CommandHandler
)
from database import db
from config import Config
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Стани для ConversationHandler
SELECT_CHILD_PAYMENT, PAYMENT_LESSONS_COUNT, PAYMENT_AMOUNT, PAYMENT_DATE = range(4)


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
async def add_payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /addPayment - додавання оплати"""
    user_id = update.effective_user.id

    # Отримуємо список дітей
    children = await db.get_children()

    if not children:
        await update.message.reply_text(
            "❌ У вас ще немає доданих дітей.\n"
            "Спочатку додайте дитину через /settings"
        )
        return ConversationHandler.END

    # Показуємо список дітей для вибору
    text = "💰 Додавання оплати\n\nОберіть дитину:"
    keyboard = []

    for child in children:
        name = child.get('name', 'Без імені')
        child_id = str(child['_id'])
        keyboard.append([
            InlineKeyboardButton(f"{name}", callback_data=f"payment_child_{child_id}")
        ])

    keyboard.append([InlineKeyboardButton("❌ Скасувати", callback_data="cancel_payment")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup)
    return SELECT_CHILD_PAYMENT


async def select_child_for_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вибір дитини для оплати"""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_payment":
        await query.edit_message_text("❌ Додавання оплати скасовано.")
        context.user_data.clear()
        return ConversationHandler.END

    child_id = query.data.replace("payment_child_", "")
    user_id = update.effective_user.id

    # Перевіряємо чи дитина належить дозволеному користувачу
    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.edit_message_text("❌ Помилка: дитину не знайдено")
        return ConversationHandler.END

    # Зберігаємо child_id в context
    context.user_data['payment_child_id'] = child_id
    context.user_data['payment_child_name'] = child.get('name', 'Без імені')
    context.user_data['payment_base_price'] = child.get('base_price', 0)

    await query.edit_message_text(
        f"Дитина: {child.get('name', 'Без імені')}\n"
        f"Базова ціна за заняття: {child.get('base_price', 0)} грн\n\n"
        f"За скільки занять оплата? (по стандарту 1)\n"
        f"Введіть кількість занять:"
    )
    return PAYMENT_LESSONS_COUNT


async def get_payment_lessons_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання кількості занять"""
    count_text = update.message.text.strip()

    try:
        lessons_count = int(count_text)
        if lessons_count <= 0:
            await update.message.reply_text(
                "❌ Кількість занять має бути більше 0. Спробуйте ще раз:"
            )
            return PAYMENT_LESSONS_COUNT
    except ValueError:
        await update.message.reply_text(
            "❌ Введіть коректну кількість (ціле число). Спробуйте ще раз:"
        )
        return PAYMENT_LESSONS_COUNT

    context.user_data['payment_lessons_count'] = lessons_count

    # Рахуємо рекомендовану суму
    base_price = context.user_data.get('payment_base_price', 0)
    recommended_amount = base_price * lessons_count

    await update.message.reply_text(
        f"Кількість занять: {lessons_count}\n\n"
        f"Рекомендована сума: {recommended_amount} грн\n"
        f"({base_price} грн × {lessons_count})\n\n"
        f"Введіть суму оплати в гривнях:"
    )
    return PAYMENT_AMOUNT


async def get_payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання суми оплати"""
    amount_text = update.message.text.strip()

    try:
        amount = float(amount_text)
        if amount <= 0:
            await update.message.reply_text(
                "❌ Сума має бути більше 0. Спробуйте ще раз:"
            )
            return PAYMENT_AMOUNT
    except ValueError:
        await update.message.reply_text(
            "❌ Введіть коректну суму (число). Спробуйте ще раз:"
        )
        return PAYMENT_AMOUNT

    context.user_data['payment_amount'] = amount

    await update.message.reply_text(
        f"Сума: {amount} грн\n\n"
        f"Введіть дату оплати у форматі ДД.ММ.РРРР\n"
        f"Наприклад: 14.11.2024"
    )
    return PAYMENT_DATE


async def get_payment_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання дати оплати та збереження в БД"""
    date_text = update.message.text.strip()

    try:
        # Парсимо дату у форматі ДД.ММ.РРРР
        date_obj = datetime.strptime(date_text, "%d.%m.%Y")
        # Зберігаємо у форматі YYYY-MM-DD для БД
        date_str = date_obj.strftime("%Y-%m-%d")

        # Зберігаємо оплату в БД
        user_id = update.effective_user.id
        child_id = context.user_data.get('payment_child_id')
        amount = context.user_data.get('payment_amount')
        lessons_count = context.user_data.get('payment_lessons_count')

        payment_id = await db.add_payment(
            user_id=user_id,
            child_id=child_id,
            amount=amount,
            lessons_count=lessons_count,
            payment_date=date_str
        )

        child_name = context.user_data.get('payment_child_name')

        logger.info(f"User {user_id} added payment for child {child_id}: {amount} грн for {lessons_count} lessons")

        await update.message.reply_text(
            f"✅ Оплату успішно додано!\n\n"
            f"Дитина: {child_name}\n"
            f"Сума: {amount} грн\n"
            f"За {lessons_count} занять(я)\n"
            f"Дата оплати: {date_text}"
        )

        # Очищаємо дані
        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Неправильний формат дати. Спробуйте ще раз.\n"
            "Формат: ДД.ММ.РРРР (наприклад: 14.11.2024)"
        )
        return PAYMENT_DATE


async def cancel_add_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скасування додавання оплати"""
    context.user_data.clear()
    await update.message.reply_text("❌ Додавання оплати скасовано.")
    return ConversationHandler.END


# Створення ConversationHandler
def get_add_payment_conversation_handler():
    """Повертає ConversationHandler для додавання оплати"""
    return ConversationHandler(
        entry_points=[CommandHandler("addpayment", add_payment_command)],
        states={
            SELECT_CHILD_PAYMENT: [CallbackQueryHandler(select_child_for_payment)],
            PAYMENT_LESSONS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_payment_lessons_count)],
            PAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_payment_amount)],
            PAYMENT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_payment_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add_payment)],
    )
