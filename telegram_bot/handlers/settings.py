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

logger = logging.getLogger(__name__)

# Стани для ConversationHandler
CHILD_NAME, CHILD_AGE, CHILD_BASE_PRICE = range(3)
EDIT_CHILD_NAME, EDIT_CHILD_AGE, EDIT_CHILD_BASE_PRICE = range(3, 6)


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
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /settings - налаштування"""
    keyboard = [
        [InlineKeyboardButton("➕ Додати дитину", callback_data="add_child")],
        [InlineKeyboardButton("👶 Список дітей", callback_data="list_children")],
        [InlineKeyboardButton("📂 Архів дітей", callback_data="view_archive")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚙️ Налаштування:\n\nОберіть дію:",
        reply_markup=reply_markup
    )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка callback кнопок в налаштуваннях"""
    query = update.callback_query
    await query.answer()

    logger.info(f"Settings callback received: {query.data}")

    if query.data == "add_child":
        return await start_add_child(update, context)
    elif query.data == "list_children":
        return await list_children(update, context)
    elif query.data == "view_archive":
        return await view_archive(update, context)
    elif query.data == "select_unarchive":
        return await select_child_to_unarchive(update, context)
    elif query.data == "select_delete_archived":
        return await select_child_to_delete_from_archive(update, context)
    elif query.data == "select_edit":
        return await select_child_to_edit(update, context)
    elif query.data == "select_archive":
        return await select_child_to_archive(update, context)
    elif query.data == "select_delete":
        return await select_child_to_delete(update, context)
    elif query.data.startswith("edit_child_"):
        child_id = query.data.replace("edit_child_", "")
        return await show_edit_child_menu(update, context, child_id)
    elif query.data.startswith("archive_child_"):
        child_id = query.data.replace("archive_child_", "")
        return await archive_child_handler(update, context, child_id)
    elif query.data.startswith("unarchive_child_"):
        child_id = query.data.replace("unarchive_child_", "")
        return await unarchive_child_handler(update, context, child_id)
    elif query.data.startswith("delete_archived_"):
        child_id = query.data.replace("delete_archived_", "")
        return await confirm_delete_archived(update, context, child_id)
    elif query.data.startswith("confirm_delete_archived_"):
        child_id = query.data.replace("confirm_delete_archived_", "")
        return await delete_archived_child(update, context, child_id)
    elif query.data == "cancel_delete_archived":
        return await view_archive(update, context)
    elif query.data.startswith("delete_child_"):
        child_id = query.data.replace("delete_child_", "")
        return await confirm_delete_child(update, context, child_id)
    elif query.data.startswith("confirm_delete_"):
        child_id = query.data.replace("confirm_delete_", "")
        return await delete_child(update, context, child_id)
    elif query.data == "cancel_delete":
        return await cancel_delete_child(update, context)
    elif query.data == "back_to_settings":
        keyboard = [
            [InlineKeyboardButton("➕ Додати дитину", callback_data="add_child")],
            [InlineKeyboardButton("👶 Список дітей", callback_data="list_children")],
            [InlineKeyboardButton("📂 Архів дітей", callback_data="view_archive")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚙️ Налаштування:\n\nОберіть дію:",
            reply_markup=reply_markup
        )
    elif query.data == "back_to_list":
        return await list_children(update, context)
    elif query.data == "back_to_archive":
        return await view_archive(update, context)


async def start_add_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок процесу додавання дитини"""
    query = update.callback_query
    await query.edit_message_text(
        "➕ Додавання дитини\n\n"
        "Введіть ім'я дитини (наприклад: Антон Антоненко 🇺🇦):"
    )
    return CHILD_NAME


async def get_child_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання імені дитини"""
    name = update.message.text.strip()

    if not name:
        await update.message.reply_text("❌ Ім'я не може бути порожнім. Спробуйте ще раз:")
        return CHILD_NAME

    # Зберігаємо ім'я в context
    context.user_data['child_name'] = name

    await update.message.reply_text(
        f"Добре, ім'я: {name}\n\n"
        "Тепер введіть вік дитини (наприклад: 5):"
    )
    return CHILD_AGE


async def get_child_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання віку дитини"""
    age_text = update.message.text.strip()

    try:
        age = int(age_text)
        if age < 0 or age > 18:
            await update.message.reply_text(
                "❌ Вік має бути від 0 до 18. Спробуйте ще раз:"
            )
            return CHILD_AGE
    except ValueError:
        await update.message.reply_text(
            "❌ Введіть коректний вік (число). Спробуйте ще раз:"
        )
        return CHILD_AGE

    # Зберігаємо вік в context
    context.user_data['child_age'] = age

    await update.message.reply_text(
        f"Добре, вік: {age}\n\n"
        "Тепер введіть базову ціну за заняття (наприклад: 300):"
    )
    return CHILD_BASE_PRICE


async def get_child_base_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання базової ціни та збереження дитини в БД"""
    price_text = update.message.text.strip()

    try:
        base_price = float(price_text)
        if base_price < 0:
            await update.message.reply_text(
                "❌ Ціна не може бути від'ємною. Спробуйте ще раз:"
            )
            return CHILD_BASE_PRICE
    except ValueError:
        await update.message.reply_text(
            "❌ Введіть коректну ціну (число). Спробуйте ще раз:"
        )
        return CHILD_BASE_PRICE

    # Отримуємо збережені дані
    name = context.user_data.get('child_name')
    age = context.user_data.get('child_age')
    user_id = update.effective_user.id

    # Зберігаємо дитину в БД
    child_id = await db.add_child(user_id=user_id, name=name, age=age, base_price=base_price)

    logger.info(f"User {user_id} added child: {name}, age: {age}, base_price: {base_price}")

    keyboard = [[InlineKeyboardButton("⬅️ Назад до налаштувань", callback_data="back_to_settings")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ Дитину успішно додано!\n\n"
        f"Ім'я: {name}\n"
        f"Вік: {age}\n"
        f"Базова ціна: {base_price} грн",
        reply_markup=reply_markup
    )

    # Очищаємо дані користувача
    context.user_data.clear()

    return ConversationHandler.END


async def cancel_add_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скасування додавання дитини"""
    context.user_data.clear()

    keyboard = [[InlineKeyboardButton("⬅️ Назад до налаштувань", callback_data="back_to_settings")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "❌ Додавання дитини скасовано.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


async def list_children(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відображення списку дітей"""
    query = update.callback_query
    user_id = update.effective_user.id

    children = await db.get_children()

    if not children:
        keyboard = [[InlineKeyboardButton("⬅️ Назад до налаштувань", callback_data="back_to_settings")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "👶 У вас поки немає доданих дітей.",
            reply_markup=reply_markup
        )
        return

    text = "👶 Список дітей:\n\n"

    for i, child in enumerate(children, 1):
        name = child.get('name', 'Без імені')
        age = child.get('age', 'Невідомий')
        text += f"{i}. {name} ({age} років)\n"

    keyboard = [
        [InlineKeyboardButton("✏️ Редагувати", callback_data="select_edit")],
        [InlineKeyboardButton("📦 Архівувати", callback_data="select_archive")],
        [InlineKeyboardButton("⬅️ Назад до налаштувань", callback_data="back_to_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def select_child_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вибір дитини для редагування"""
    query = update.callback_query
    user_id = update.effective_user.id

    children = await db.get_children()

    if not children:
        await query.answer("❌ Немає дітей для редагування")
        return

    text = "✏️ Оберіть дитину для редагування:\n\n"
    keyboard = []

    for i, child in enumerate(children, 1):
        name = child.get('name', 'Без імені')
        age = child.get('age', 'Невідомий')
        child_id = str(child['_id'])

        text += f"{i}. {name} ({age} років)\n"
        keyboard.append([
            InlineKeyboardButton(f"{i}. {name}", callback_data=f"edit_child_{child_id}")
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def select_child_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вибір дитини для видалення"""
    query = update.callback_query
    user_id = update.effective_user.id

    children = await db.get_children()

    if not children:
        await query.answer("❌ Немає дітей для видалення")
        return

    text = "🗑️ Оберіть дитину для видалення:\n\n"
    keyboard = []

    for i, child in enumerate(children, 1):
        name = child.get('name', 'Без імені')
        age = child.get('age', 'Невідомий')
        child_id = str(child['_id'])

        text += f"{i}. {name} ({age} років)\n"
        keyboard.append([
            InlineKeyboardButton(f"{i}. {name}", callback_data=f"delete_child_{child_id}")
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def confirm_delete_child(update: Update, context: ContextTypes.DEFAULT_TYPE, child_id: str):
    """Підтвердження видалення дитини"""
    query = update.callback_query
    user_id = update.effective_user.id

    logger.info(f"confirm_delete_child called for child_id: {child_id}")

    # Перевіряємо чи дитина належить дозволеному користувачу
    child = await db.get_child(child_id)
    logger.info(f"Child data: {child}")

    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        logger.warning(f"Child not found or not allowed. child={child}, user_id={child.get('user_id') if child else None}")
        await query.answer("❌ Помилка: дитину не знайдено", show_alert=True)
        await list_children(update, context)
        return

    # Перевіряємо чи дитина використовується в розрахунках
    is_in_use = await db.is_child_in_use(child_id)
    logger.info(f"Is child in use: {is_in_use}")

    if is_in_use:
        logger.info("Child is in use, showing alert and returning to list")
        await query.answer(
            "⛔ Неможливо видалити: дитина має заняття/оплати.\n\n"
            "💡 Використайте 'Архівувати' щоб приховати дитину зі списку, "
            "зберігши всю статистику.",
            show_alert=True
        )
        await list_children(update, context)
        return

    logger.info(f"Showing delete confirmation for child: {child.get('name')}")
    name = child.get('name', 'Без імені')

    keyboard = [
        [
            InlineKeyboardButton("✅ Так, видалити", callback_data=f"confirm_delete_{child_id}"),
            InlineKeyboardButton("❌ Ні, скасувати", callback_data="cancel_delete")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"❓ Ви точно хочете видалити дитину?\n\n"
        f"Ім'я: {name}\n"
        f"Вік: {child.get('age', 'Невідомий')}\n\n"
        f"⚠️ Цю дію не можна буде скасувати!",
        reply_markup=reply_markup
    )


async def delete_child(update: Update, context: ContextTypes.DEFAULT_TYPE, child_id: str):
    """Видалення дитини після підтвердження"""
    query = update.callback_query
    user_id = update.effective_user.id

    logger.info(f"delete_child called for child_id: {child_id}")

    # Перевіряємо чи дитина належить дозволеному користувачу
    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.answer("❌ Помилка: дитину не знайдено", show_alert=True)
        await list_children(update, context)
        return

    # Видаляємо дитину
    deleted = await db.delete_child(child_id)

    if deleted:
        logger.info(f"User {user_id} deleted child: {child.get('name')}")
        await query.answer("✅ Дитину видалено")
        # Оновлюємо список
        await list_children(update, context)
    else:
        await query.answer("❌ Помилка видалення", show_alert=True)
        await list_children(update, context)


async def cancel_delete_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скасування видалення дитини"""
    query = update.callback_query
    await query.answer("❌ Видалення скасовано")
    # Повертаємось до списку
    await list_children(update, context)


# === Архівування дітей ===

async def select_child_to_archive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вибір дитини для архівування"""
    query = update.callback_query
    user_id = update.effective_user.id

    children = await db.get_children()

    if not children:
        await query.answer("❌ Немає дітей для архівування")
        return

    text = "📦 Оберіть дитину для архівування:\n\n"
    keyboard = []

    for i, child in enumerate(children, 1):
        name = child.get('name', 'Без імені')
        age = child.get('age', 'Невідомий')
        child_id = str(child['_id'])

        text += f"{i}. {name} ({age} років)\n"
        keyboard.append([
            InlineKeyboardButton(f"{i}. {name}", callback_data=f"archive_child_{child_id}")
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def archive_child_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, child_id: str):
    """Архівування дитини"""
    query = update.callback_query
    user_id = update.effective_user.id

    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.answer("❌ Помилка: дитину не знайдено", show_alert=True)
        await list_children(update, context)
        return

    # Архівуємо дитину
    archived = await db.archive_child(child_id)

    if archived:
        logger.info(f"User {user_id} archived child: {child.get('name')}")
        await query.answer("📦 Дитину заархівовано")
        await list_children(update, context)
    else:
        await query.answer("❌ Помилка архівування", show_alert=True)
        await list_children(update, context)


async def view_archive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перегляд архіву дітей"""
    query = update.callback_query

    archived_children = await db.get_archived_children()

    if not archived_children:
        keyboard = [[InlineKeyboardButton("⬅️ Назад до налаштувань", callback_data="back_to_settings")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📂 Архів порожній.\n\nВи можете архівувати дітей, які вже закінчили займатись.",
            reply_markup=reply_markup
        )
        return

    text = "📂 Архів дітей:\n\n"

    for i, child in enumerate(archived_children, 1):
        name = child.get('name', 'Без імені')
        age = child.get('age', 'Невідомий')
        text += f"{i}. {name} ({age} років)\n"

    text += "\nОберіть дію:"

    keyboard = [
        [InlineKeyboardButton("🔓 Розархівувати", callback_data="select_unarchive")],
        [InlineKeyboardButton("🗑️ Видалити", callback_data="select_delete_archived")],
        [InlineKeyboardButton("⬅️ Назад до налаштувань", callback_data="back_to_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def select_child_to_unarchive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вибір дитини для розархівування"""
    query = update.callback_query

    archived_children = await db.get_archived_children()

    if not archived_children:
        await query.answer("❌ Немає дітей для розархівування")
        await view_archive(update, context)
        return

    text = "🔓 Оберіть дитину для розархівування:\n\n"
    keyboard = []

    for i, child in enumerate(archived_children, 1):
        name = child.get('name', 'Без імені')
        age = child.get('age', 'Невідомий')
        child_id = str(child['_id'])

        text += f"{i}. {name} ({age} років)\n"
        keyboard.append([
            InlineKeyboardButton(f"{i}. {name}", callback_data=f"unarchive_child_{child_id}")
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Назад до архіву", callback_data="back_to_archive")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def select_child_to_delete_from_archive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вибір дитини для видалення з архіву"""
    query = update.callback_query

    archived_children = await db.get_archived_children()

    if not archived_children:
        await query.answer("❌ Немає дітей для видалення")
        await view_archive(update, context)
        return

    text = "🗑️ Оберіть дитину для видалення:\n\n"
    keyboard = []

    for i, child in enumerate(archived_children, 1):
        name = child.get('name', 'Без імені')
        age = child.get('age', 'Невідомий')
        child_id = str(child['_id'])

        text += f"{i}. {name} ({age} років)\n"
        keyboard.append([
            InlineKeyboardButton(f"{i}. {name}", callback_data=f"delete_archived_{child_id}")
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Назад до архіву", callback_data="back_to_archive")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def unarchive_child_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, child_id: str):
    """Розархівування дитини"""
    query = update.callback_query
    user_id = update.effective_user.id

    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.answer("❌ Помилка: дитину не знайдено", show_alert=True)
        await view_archive(update, context)
        return

    # Розархівуємо дитину
    unarchived = await db.unarchive_child(child_id)

    if unarchived:
        logger.info(f"User {user_id} unarchived child: {child.get('name')}")
        await query.answer("🔓 Дитину розархівовано")
        await view_archive(update, context)
    else:
        await query.answer("❌ Помилка розархівування", show_alert=True)
        await view_archive(update, context)


async def confirm_delete_archived(update: Update, context: ContextTypes.DEFAULT_TYPE, child_id: str):
    """Підтвердження видалення архівованої дитини"""
    query = update.callback_query
    user_id = update.effective_user.id

    logger.info(f"confirm_delete_archived called for child_id: {child_id}")

    # Перевіряємо чи дитина належить дозволеному користувачу
    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.answer("❌ Помилка: дитину не знайдено", show_alert=True)
        await view_archive(update, context)
        return

    # Перевіряємо кількість уроків та оплат
    from bson.objectid import ObjectId
    lessons_count = await db.db.lessons.count_documents({"child_id": ObjectId(child_id)})
    payments_count = await db.db.payments.count_documents({"child_id": ObjectId(child_id)})

    logger.info(f"Archived child has {lessons_count} lessons and {payments_count} payments")

    if lessons_count > 0 or payments_count > 0:
        logger.info("Archived child has lessons/payments, cannot delete")
        await query.answer(
            f"⛔ Неможливо видалити дитину!\n\n"
            f"У дитини є розрахункові документи:\n"
            f"📚 Уроків: {lessons_count}\n"
            f"💰 Оплат: {payments_count}\n\n"
            f"Видалити можна тільки коли їх очистити (0 уроків, 0 оплат).",
            show_alert=True
        )
        await view_archive(update, context)
        return

    logger.info(f"Showing delete confirmation for archived child: {child.get('name')}")
    name = child.get('name', 'Без імені')

    keyboard = [
        [
            InlineKeyboardButton("✅ Так, видалити назавжди", callback_data=f"confirm_delete_archived_{child_id}"),
            InlineKeyboardButton("❌ Ні, скасувати", callback_data="cancel_delete_archived")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"❓ Ви точно хочете видалити дитину НАЗАВЖДИ?\n\n"
        f"Ім'я: {name}\n"
        f"Вік: {child.get('age', 'Невідомий')}\n\n"
        f"✅ Дитина не має розрахункових документів:\n"
        f"📚 Уроків: {lessons_count}\n"
        f"💰 Оплат: {payments_count}\n\n"
        f"⚠️ Цю дію не можна буде скасувати!\n"
        f"Дитина буде видалена з бази даних.",
        reply_markup=reply_markup
    )


async def delete_archived_child(update: Update, context: ContextTypes.DEFAULT_TYPE, child_id: str):
    """Видалення архівованої дитини після підтвердження"""
    query = update.callback_query
    user_id = update.effective_user.id

    logger.info(f"delete_archived_child called for child_id: {child_id}")

    # Перевіряємо чи дитина належить дозволеному користувачу
    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.answer("❌ Помилка: дитину не знайдено", show_alert=True)
        await view_archive(update, context)
        return

    # Додаткова перевірка перед видаленням
    from bson.objectid import ObjectId
    lessons_count = await db.db.lessons.count_documents({"child_id": ObjectId(child_id)})
    payments_count = await db.db.payments.count_documents({"child_id": ObjectId(child_id)})

    if lessons_count > 0 or payments_count > 0:
        logger.warning(f"Attempted to delete child with {lessons_count} lessons and {payments_count} payments")
        await query.answer(
            f"⛔ Неможливо видалити!\n\n"
            f"📚 Уроків: {lessons_count}\n"
            f"💰 Оплат: {payments_count}\n\n"
            f"Спочатку очистіть всі дані.",
            show_alert=True
        )
        await view_archive(update, context)
        return

    # Видаляємо дитину
    deleted = await db.delete_child(child_id)

    if deleted:
        logger.info(f"User {user_id} permanently deleted archived child: {child.get('name')}")
        await query.answer("🗑️ Дитину видалено назавжди")
        await view_archive(update, context)
    else:
        await query.answer("❌ Помилка видалення", show_alert=True)
        await view_archive(update, context)


# === Редагування дитини ===

async def show_edit_child_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, child_id: str):
    """Меню редагування дитини"""
    query = update.callback_query
    user_id = update.effective_user.id

    # Перевіряємо чи дитина належить дозволеному користувачу
    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.answer("❌ Помилка: дитину не знайдено")
        return

    name = child.get('name', 'Без імені')
    age = child.get('age', 'Невідомий')
    base_price = child.get('base_price', 0)

    keyboard = [
        [InlineKeyboardButton("✏️ Редагувати ім'я", callback_data=f"edit_name_{child_id}")],
        [InlineKeyboardButton("✏️ Редагувати вік", callback_data=f"edit_age_{child_id}")],
        [InlineKeyboardButton("✏️ Редагувати базову ціну", callback_data=f"edit_price_{child_id}")],
        [InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✏️ Редагування дитини\n\n"
        f"Ім'я: {name}\n"
        f"Вік: {age}\n"
        f"Базова ціна: {base_price} грн\n\n"
        f"Оберіть що хочете змінити:",
        reply_markup=reply_markup
    )


async def start_edit_child_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок редагування імені дитини"""
    query = update.callback_query
    user_id = update.effective_user.id

    # Витягуємо child_id з callback_data
    child_id = query.data.replace("edit_name_", "")

    # Перевіряємо чи дитина належить дозволеному користувачу
    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.answer("❌ Помилка: дитину не знайдено")
        return ConversationHandler.END

    # Зберігаємо child_id в context
    context.user_data['editing_child_id'] = child_id

    await query.edit_message_text(
        f"✏️ Редагування імені\n\n"
        f"Поточне ім'я: {child.get('name', 'Без імені')}\n\n"
        f"Введіть нове ім'я:"
    )
    return EDIT_CHILD_NAME


async def get_edit_child_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання нового імені дитини"""
    name = update.message.text.strip()

    if not name:
        await update.message.reply_text("❌ Ім'я не може бути порожнім. Спробуйте ще раз:")
        return EDIT_CHILD_NAME

    child_id = context.user_data.get('editing_child_id')
    user_id = update.effective_user.id

    # Оновлюємо ім'я
    updated = await db.update_child(child_id, name=name)

    if updated:
        logger.info(f"User {user_id} updated child name: {name}")
        keyboard = [[InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ Ім'я успішно оновлено!\n\n"
            f"Нове ім'я: {name}",
            reply_markup=reply_markup
        )
    else:
        keyboard = [[InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ Помилка оновлення імені",
            reply_markup=reply_markup
        )

    # Очищаємо дані користувача
    context.user_data.clear()
    return ConversationHandler.END


async def start_edit_child_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок редагування віку дитини"""
    query = update.callback_query
    user_id = update.effective_user.id

    # Витягуємо child_id з callback_data
    child_id = query.data.replace("edit_age_", "")

    # Перевіряємо чи дитина належить дозволеному користувачу
    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.answer("❌ Помилка: дитину не знайдено")
        return ConversationHandler.END

    # Зберігаємо child_id в context
    context.user_data['editing_child_id'] = child_id

    await query.edit_message_text(
        f"✏️ Редагування віку\n\n"
        f"Поточний вік: {child.get('age', 'Невідомий')}\n\n"
        f"Введіть новий вік:"
    )
    return EDIT_CHILD_AGE


async def get_edit_child_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання нового віку дитини"""
    age_text = update.message.text.strip()

    try:
        age = int(age_text)
        if age < 0 or age > 18:
            await update.message.reply_text(
                "❌ Вік має бути від 0 до 18. Спробуйте ще раз:"
            )
            return EDIT_CHILD_AGE
    except ValueError:
        await update.message.reply_text(
            "❌ Введіть коректний вік (число). Спробуйте ще раз:"
        )
        return EDIT_CHILD_AGE

    child_id = context.user_data.get('editing_child_id')
    user_id = update.effective_user.id

    # Оновлюємо вік
    updated = await db.update_child(child_id, age=age)

    if updated:
        logger.info(f"User {user_id} updated child age: {age}")
        keyboard = [[InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ Вік успішно оновлено!\n\n"
            f"Новий вік: {age}",
            reply_markup=reply_markup
        )
    else:
        keyboard = [[InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ Помилка оновлення віку",
            reply_markup=reply_markup
        )

    # Очищаємо дані користувача
    context.user_data.clear()
    return ConversationHandler.END


async def start_edit_child_base_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок редагування базової ціни дитини"""
    query = update.callback_query
    user_id = update.effective_user.id

    # Витягуємо child_id з callback_data
    child_id = query.data.replace("edit_price_", "")

    # Перевіряємо чи дитина належить дозволеному користувачу
    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.answer("❌ Помилка: дитину не знайдено")
        return ConversationHandler.END

    # Зберігаємо child_id в context
    context.user_data['editing_child_id'] = child_id

    await query.edit_message_text(
        f"✏️ Редагування базової ціни\n\n"
        f"Поточна ціна: {child.get('base_price', 0)} грн\n\n"
        f"Введіть нову базову ціну:"
    )
    return EDIT_CHILD_BASE_PRICE


async def get_edit_child_base_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання нової базової ціни дитини"""
    price_text = update.message.text.strip()

    try:
        base_price = float(price_text)
        if base_price < 0:
            await update.message.reply_text(
                "❌ Ціна не може бути від'ємною. Спробуйте ще раз:"
            )
            return EDIT_CHILD_BASE_PRICE
    except ValueError:
        await update.message.reply_text(
            "❌ Введіть коректну ціну (число). Спробуйте ще раз:"
        )
        return EDIT_CHILD_BASE_PRICE

    child_id = context.user_data.get('editing_child_id')
    user_id = update.effective_user.id

    # Оновлюємо базову ціну
    updated = await db.update_child(child_id, base_price=base_price)

    if updated:
        logger.info(f"User {user_id} updated child base_price: {base_price}")
        keyboard = [[InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ Базову ціну успішно оновлено!\n\n"
            f"Нова ціна: {base_price} грн",
            reply_markup=reply_markup
        )
    else:
        keyboard = [[InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ Помилка оновлення ціни",
            reply_markup=reply_markup
        )

    # Очищаємо дані користувача
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_edit_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скасування редагування дитини"""
    context.user_data.clear()

    keyboard = [[InlineKeyboardButton("⬅️ Назад до списку", callback_data="back_to_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "❌ Редагування скасовано.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


# === ConversationHandlers ===
def get_add_child_conversation_handler():
    """Повертає ConversationHandler для додавання дитини"""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_child, pattern="^add_child$")],
        states={
            CHILD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_child_name)],
            CHILD_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_child_age)],
            CHILD_BASE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_child_base_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add_child)],
    )


def get_edit_child_conversation_handler():
    """Повертає ConversationHandler для редагування дитини"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_edit_child_name, pattern="^edit_name_"),
            CallbackQueryHandler(start_edit_child_age, pattern="^edit_age_"),
            CallbackQueryHandler(start_edit_child_base_price, pattern="^edit_price_"),
        ],
        states={
            EDIT_CHILD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_edit_child_name)],
            EDIT_CHILD_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_edit_child_age)],
            EDIT_CHILD_BASE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_edit_child_base_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit_child)],
    )
