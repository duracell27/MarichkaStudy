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
SELECT_CHILD, LESSON_DATE, LESSON_START_TIME, LESSON_END_TIME, ASK_REPEAT_MONTHLY = range(5)


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
async def add_lesson_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /addLesson - додавання заняття"""
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
    text = "📚 Додавання заняття\n\nОберіть дитину:"
    keyboard = []

    for child in children:
        name = child.get('name', 'Без імені')
        child_id = str(child['_id'])
        keyboard.append([
            InlineKeyboardButton(f"{name}", callback_data=f"lesson_child_{child_id}")
        ])

    keyboard.append([InlineKeyboardButton("❌ Скасувати", callback_data="cancel_lesson")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup)
    return SELECT_CHILD


async def select_child_for_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вибір дитини для заняття"""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_lesson":
        await query.edit_message_text("❌ Додавання заняття скасовано.")
        context.user_data.clear()
        return ConversationHandler.END

    child_id = query.data.replace("lesson_child_", "")
    user_id = update.effective_user.id

    # Перевіряємо чи дитина належить дозволеному користувачу
    child = await db.get_child(child_id)
    if not child or child.get('user_id') not in Config.ALLOWED_USER_IDS:
        await query.edit_message_text("❌ Помилка: дитину не знайдено")
        return ConversationHandler.END

    # Зберігаємо child_id в context
    context.user_data['lesson_child_id'] = child_id
    context.user_data['lesson_child_name'] = child.get('name', 'Без імені')

    # Створюємо швидкі кнопки для дат
    from datetime import timedelta
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    keyboard = [
        [InlineKeyboardButton(f"Сьогодні ({today.strftime('%d.%m')})", callback_data=f"date_{today.strftime('%d.%m.%Y')}")],
        [InlineKeyboardButton(f"Завтра ({tomorrow.strftime('%d.%m')})", callback_data=f"date_{tomorrow.strftime('%d.%m.%Y')}")],
        [InlineKeyboardButton(f"Післязавтра ({day_after.strftime('%d.%m')})", callback_data=f"date_{day_after.strftime('%d.%m.%Y')}")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel_lesson")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Дитина: {child.get('name', 'Без імені')}\n\n"
        f"Оберіть дату заняття або введіть вручну:\n\n"
        f"Формати:\n"
        f"• ДД.ММ (наприклад: 22.11)\n"
        f"• ДД.ММ.РРРР (наприклад: 14.11.2024)",
        reply_markup=reply_markup
    )
    return LESSON_DATE


async def handle_date_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка кнопки швидкого вибору дати"""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_lesson":
        await query.edit_message_text("❌ Додавання заняття скасовано.")
        context.user_data.clear()
        return ConversationHandler.END

    # Витягуємо дату з callback_data
    date_text = query.data.replace("date_", "")

    try:
        # Парсимо дату
        date_obj = datetime.strptime(date_text, "%d.%m.%Y")
        date_str = date_obj.strftime("%Y-%m-%d")
        context.user_data['lesson_date'] = date_str
        context.user_data['lesson_date_display'] = date_obj.strftime("%d.%m.%Y")

        await query.edit_message_text(
            f"Дата: {date_obj.strftime('%d.%m.%Y')}\n\n"
            f"Введіть час початку заняття:\n\n"
            f"Формати:\n"
            f"• ГГ:ХХ (наприклад: 10:00)\n"
            f"• ГГХХ (наприклад: 1000)"
        )
        return LESSON_START_TIME

    except ValueError:
        await query.edit_message_text("❌ Помилка обробки дати")
        return ConversationHandler.END


async def get_lesson_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання дати заняття"""
    date_text = update.message.text.strip()

    try:
        # Спробуємо спочатку формат ДД.ММ.РРРР
        try:
            date_obj = datetime.strptime(date_text, "%d.%m.%Y")
        except ValueError:
            # Якщо не вийшло, пробуємо формат ДД.ММ (використовуємо поточний рік)
            date_obj = datetime.strptime(date_text, "%d.%m")
            date_obj = date_obj.replace(year=datetime.now().year)

        # Зберігаємо у форматі YYYY-MM-DD для БД
        date_str = date_obj.strftime("%Y-%m-%d")
        context.user_data['lesson_date'] = date_str
        context.user_data['lesson_date_display'] = date_obj.strftime("%d.%m.%Y")

        await update.message.reply_text(
            f"Дата: {date_obj.strftime('%d.%m.%Y')}\n\n"
            f"Введіть час початку заняття:\n\n"
            f"Формати:\n"
            f"• ГГ:ХХ (наприклад: 10:00)\n"
            f"• ГГХХ (наприклад: 1000)"
        )
        return LESSON_START_TIME

    except ValueError:
        await update.message.reply_text(
            "❌ Неправильний формат дати. Спробуйте ще раз.\n"
            "Формати:\n"
            "• ДД.ММ (наприклад: 22.11)\n"
            "• ДД.ММ.РРРР (наприклад: 14.11.2024)"
        )
        return LESSON_DATE


async def get_lesson_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання часу початку заняття"""
    time_text = update.message.text.strip()

    try:
        # Спробуємо спочатку формат ГГ:ХХ
        try:
            time_obj = datetime.strptime(time_text, "%H:%M")
            time_formatted = time_text
        except ValueError:
            # Якщо не вийшло, пробуємо формат ГГХХ (наприклад: 1000)
            if len(time_text) == 4 and time_text.isdigit():
                hours = time_text[:2]
                minutes = time_text[2:]
                time_formatted = f"{hours}:{minutes}"
                time_obj = datetime.strptime(time_formatted, "%H:%M")
            else:
                raise ValueError("Invalid time format")

        context.user_data['lesson_start_time'] = time_formatted
        context.user_data['lesson_start_time_obj'] = time_obj  # Зберігаємо для розрахунку +30хв/+55хв

        # Розраховуємо час +30хв та +55хв
        from datetime import timedelta
        time_plus_30 = time_obj + timedelta(minutes=30)
        time_plus_55 = time_obj + timedelta(minutes=55)

        # Створюємо швидкі кнопки
        keyboard = [
            [InlineKeyboardButton(f"+30хв ({time_plus_30.strftime('%H:%M')})", callback_data=f"endtime_{time_plus_30.strftime('%H:%M')}")],
            [InlineKeyboardButton(f"+55хв ({time_plus_55.strftime('%H:%M')})", callback_data=f"endtime_{time_plus_55.strftime('%H:%M')}")],
            [InlineKeyboardButton("❌ Скасувати", callback_data="cancel_lesson")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Час початку: {time_formatted}\n\n"
            f"Оберіть час закінчення заняття або введіть вручну:\n\n"
            f"Формати:\n"
            f"• ГГ:ХХ (наприклад: 11:00)\n"
            f"• ГГХХ (наприклад: 1100)",
            reply_markup=reply_markup
        )
        return LESSON_END_TIME

    except ValueError:
        await update.message.reply_text(
            "❌ Неправильний формат часу. Спробуйте ще раз.\n"
            "Формати:\n"
            "• ГГ:ХХ (наприклад: 10:00)\n"
            "• ГГХХ (наприклад: 1000)"
        )
        return LESSON_START_TIME


async def handle_end_time_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка кнопки швидкого вибору часу закінчення"""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_lesson":
        await query.edit_message_text("❌ Додавання заняття скасовано.")
        context.user_data.clear()
        return ConversationHandler.END

    # Витягуємо час з callback_data
    time_text = query.data.replace("endtime_", "")

    # Перевіряємо що час закінчення пізніше початку
    start_time = context.user_data.get('lesson_start_time')
    if time_text <= start_time:
        await query.edit_message_text(
            "❌ Час закінчення має бути пізніше часу початку. Спробуйте ще раз:"
        )
        return LESSON_END_TIME

    # Зберігаємо заняття в БД
    user_id = update.effective_user.id
    child_id = context.user_data.get('lesson_child_id')
    date = context.user_data.get('lesson_date')
    end_time = time_text

    lesson_id = await db.add_lesson(
        user_id=user_id,
        child_id=child_id,
        date=date,
        start_time=start_time,
        end_time=end_time
    )

    child_name = context.user_data.get('lesson_child_name')
    date_display = context.user_data.get('lesson_date_display')

    logger.info(f"User {user_id} added lesson for child {child_id} on {date} from {start_time} to {end_time}")

    # Зберігаємо дані для можливого повторення
    context.user_data['lesson_added'] = True
    context.user_data['last_lesson_id'] = str(lesson_id)
    context.user_data['lesson_end_time'] = end_time

    # Запитуємо про автоматичне планування
    keyboard = [
        [InlineKeyboardButton("✅ Так, запланувати", callback_data="repeat_monthly_yes")],
        [InlineKeyboardButton("❌ Ні, не треба", callback_data="repeat_monthly_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ Заняття успішно додано!\n\n"
        f"Дитина: {child_name}\n"
        f"Дата: {date_display}\n"
        f"Час: {start_time} - {end_time}\n\n"
        f"💡 Запланувати цей урок на наступний місяць?\n"
        f"(Заплануються 4 заняття на той самий день тижня і час)",
        reply_markup=reply_markup
    )

    return ASK_REPEAT_MONTHLY


async def get_lesson_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання часу закінчення заняття та збереження в БД"""
    time_text = update.message.text.strip()

    try:
        # Спробуємо спочатку формат ГГ:ХХ
        try:
            time_obj = datetime.strptime(time_text, "%H:%M")
            time_formatted = time_text
        except ValueError:
            # Якщо не вийшло, пробуємо формат ГГХХ (наприклад: 1100)
            if len(time_text) == 4 and time_text.isdigit():
                hours = time_text[:2]
                minutes = time_text[2:]
                time_formatted = f"{hours}:{minutes}"
                time_obj = datetime.strptime(time_formatted, "%H:%M")
            else:
                raise ValueError("Invalid time format")

        # Перевіряємо що час закінчення пізніше початку
        start_time = context.user_data.get('lesson_start_time')
        if time_formatted <= start_time:
            await update.message.reply_text(
                "❌ Час закінчення має бути пізніше часу початку. Спробуйте ще раз:"
            )
            return LESSON_END_TIME

        # Зберігаємо заняття в БД
        user_id = update.effective_user.id
        child_id = context.user_data.get('lesson_child_id')
        date = context.user_data.get('lesson_date')
        end_time = time_formatted

        lesson_id = await db.add_lesson(
            user_id=user_id,
            child_id=child_id,
            date=date,
            start_time=start_time,
            end_time=end_time
        )

        child_name = context.user_data.get('lesson_child_name')
        date_display = context.user_data.get('lesson_date_display')

        logger.info(f"User {user_id} added lesson for child {child_id} on {date} from {start_time} to {end_time}")

        # Зберігаємо дані для можливого повторення
        context.user_data['lesson_added'] = True
        context.user_data['last_lesson_id'] = str(lesson_id)
        context.user_data['lesson_end_time'] = end_time

        # Запитуємо про автоматичне планування
        keyboard = [
            [InlineKeyboardButton("✅ Так, запланувати", callback_data="repeat_monthly_yes")],
            [InlineKeyboardButton("❌ Ні, не треба", callback_data="repeat_monthly_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ Заняття успішно додано!\n\n"
            f"Дитина: {child_name}\n"
            f"Дата: {date_display}\n"
            f"Час: {start_time} - {end_time}\n\n"
            f"💡 Запланувати цей урок на наступний місяць?\n"
            f"(Заплануються 4 заняття на той самий день тижня і час)",
            reply_markup=reply_markup
        )

        return ASK_REPEAT_MONTHLY

    except ValueError:
        await update.message.reply_text(
            "❌ Неправильний формат часу. Спробуйте ще раз.\n"
            "Формати:\n"
            "• ГГ:ХХ (наприклад: 11:00)\n"
            "• ГГХХ (наприклад: 1100)"
        )
        return LESSON_END_TIME


async def cancel_add_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скасування додавання заняття"""
    context.user_data.clear()
    await update.message.reply_text("❌ Додавання заняття скасовано.")
    return ConversationHandler.END


# === Автоматичне планування на місяць ===

async def handle_repeat_monthly_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка відповіді про автоматичне планування"""
    query = update.callback_query
    await query.answer()

    if query.data == "repeat_monthly_no":
        await query.edit_message_text(
            f"{query.message.text.split('💡')[0]}"  # Залишаємо тільки успішне повідомлення
        )
        context.user_data.clear()
        return ConversationHandler.END

    elif query.data == "repeat_monthly_yes":
        # Розраховуємо дати для наступних 4 тижнів
        from datetime import datetime, timedelta

        date_str = context.user_data.get('lesson_date')  # формат YYYY-MM-DD
        start_time = context.user_data.get('lesson_start_time')
        end_time = context.user_data.get('lesson_end_time')
        child_name = context.user_data.get('lesson_child_name')

        # Парсимо початкову дату
        base_date = datetime.strptime(date_str, "%Y-%m-%d")

        # Генеруємо дати для наступних 4 тижнів
        future_lessons = []
        for i in range(1, 5):  # 4 тижні
            future_date = base_date + timedelta(weeks=i)
            future_lessons.append({
                'date': future_date.strftime("%Y-%m-%d"),
                'date_display': future_date.strftime("%d.%m.%Y"),
                'weekday': future_date.strftime("%A")  # день тижня
            })

        # Збережемо для підтвердження
        context.user_data['future_lessons'] = future_lessons

        # Показуємо попередній перегляд
        weekdays_uk = {
            'Monday': 'Понеділок',
            'Tuesday': 'Вівторок',
            'Wednesday': 'Середа',
            'Thursday': 'Четвер',
            'Friday': 'П\'ятниця',
            'Saturday': 'Субота',
            'Sunday': 'Неділя'
        }

        preview_text = f"📅 Заплануються 4 заняття:\n\n"
        preview_text += f"Дитина: {child_name}\n"
        preview_text += f"Час: {start_time} - {end_time}\n\n"

        for i, lesson in enumerate(future_lessons, 1):
            weekday_uk = weekdays_uk.get(lesson['weekday'], lesson['weekday'])
            preview_text += f"{i}. {lesson['date_display']} ({weekday_uk})\n"

        keyboard = [
            [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm_monthly_yes")],
            [InlineKeyboardButton("❌ Скасувати", callback_data="confirm_monthly_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(preview_text, reply_markup=reply_markup)
        return ASK_REPEAT_MONTHLY


async def confirm_monthly_lessons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Підтвердження та додавання місячних уроків"""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_monthly_no":
        await query.edit_message_text("❌ Автоматичне планування скасовано.")
        context.user_data.clear()
        return ConversationHandler.END

    elif query.data == "confirm_monthly_yes":
        user_id = update.effective_user.id
        child_id = context.user_data.get('lesson_child_id')
        start_time = context.user_data.get('lesson_start_time')
        end_time = context.user_data.get('lesson_end_time')
        future_lessons = context.user_data.get('future_lessons', [])

        # Додаємо всі заняття в БД
        added_count = 0
        for lesson in future_lessons:
            try:
                await db.add_lesson(
                    user_id=user_id,
                    child_id=child_id,
                    date=lesson['date'],
                    start_time=start_time,
                    end_time=end_time
                )
                added_count += 1
            except Exception as e:
                logger.error(f"Error adding lesson: {e}")

        logger.info(f"User {user_id} auto-scheduled {added_count} lessons")

        await query.edit_message_text(
            f"✅ Успішно заплановано {added_count} занять на наступний місяць!\n\n"
            f"Ви можете переглянути їх у /timetable"
        )

        context.user_data.clear()
        return ConversationHandler.END


# ============= РОЗКЛАД ЗАНЯТЬ =============

@access_control
async def timetable_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /timeTable - перегляд розкладу на день"""
    from datetime import timedelta
    today = datetime.now()
    user_id = update.effective_user.id

    # Показуємо розклад на сьогодні
    date_str = today.strftime("%Y-%m-%d")
    date_display = today.strftime("%d.%m.%Y")

    # Отримуємо всі заняття користувача на сьогодні
    all_lessons = await db.get_lessons(user_id)
    day_lessons = [lesson for lesson in all_lessons if lesson.get('date') == date_str]

    if not day_lessons:
        message = f"📅 Розклад на сьогодні ({date_display})\n\n❌ Занять на сьогодні не знайдено."
        keyboard = [
            [InlineKeyboardButton(f"📅 Завтра ({(today + timedelta(days=1)).strftime('%d.%m')})", callback_data=f"timetable_tomorrow")],
            [InlineKeyboardButton("📆 На тиждень", callback_data="timetable_week")]
        ]
    else:
        # Сортуємо заняття по часу початку
        day_lessons.sort(key=lambda x: x.get('start_time', ''))
        message = f"📅 Розклад на сьогодні ({date_display})\n\n"

        for i, lesson in enumerate(day_lessons, 1):
            # Отримуємо інформацію про дитину
            child = await db.get_child(str(lesson['child_id']))
            child_name = child.get('name', 'Без імені') if child else 'Невідома дитина'

            start_time = lesson.get('start_time', 'N/A')
            end_time = lesson.get('end_time', 'N/A')
            completed = lesson.get('completed', False)
            cancelled = lesson.get('cancelled', False)

            # Визначаємо статус
            if cancelled:
                status = "🚫 "
            elif completed:
                status = "✅ "
            else:
                status = "⏳ "

            message += f"{i}. {status}{child_name}\n"
            message += f"   ⏰ {start_time} - {end_time}\n\n"

        # Додаємо кнопки для позначення занять
        keyboard = []
        # Кожне заняття - окремий ряд з 2 кнопками
        for i, lesson in enumerate(day_lessons, 1):
            lesson_id = str(lesson['_id'])
            # Отримуємо ім'я дитини для кнопки
            child = await db.get_child(str(lesson['child_id']))
            child_name = child.get('name', 'Без імені') if child else 'Невідома'
            completed = lesson.get('completed', False)
            cancelled = lesson.get('cancelled', False)

            row = []
            # Кнопка відмітки проведення
            if completed:
                row.append(InlineKeyboardButton(f"❌ {i}. {child_name}", callback_data=f"unmark_{lesson_id}"))
            else:
                row.append(InlineKeyboardButton(f"✅ {i}. {child_name}", callback_data=f"mark_{lesson_id}"))

            # Кнопка скасування
            if cancelled:
                row.append(InlineKeyboardButton(f"🔄 Відновити", callback_data=f"uncancel_{lesson_id}"))
            else:
                row.append(InlineKeyboardButton(f"🚫 Скасувати", callback_data=f"cancel_{lesson_id}"))

            keyboard.append(row)

        # Додаємо кнопки "Завтра" та "На тиждень"
        tomorrow = today + timedelta(days=1)
        keyboard.append([InlineKeyboardButton(f"📅 Завтра ({tomorrow.strftime('%d.%m')})", callback_data=f"timetable_tomorrow")])
        keyboard.append([InlineKeyboardButton("📆 На тиждень", callback_data="timetable_week")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)


async def handle_timetable_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка кнопок розкладу"""
    query = update.callback_query
    await query.answer()

    from datetime import timedelta
    today = datetime.now()
    user_id = query.from_user.id

    # Обробка позначення/скасування позначки заняття
    if query.data.startswith("mark_") or query.data.startswith("unmark_"):
        # Важливо: спочатку перевіряємо unmark_, потім mark_
        if query.data.startswith("unmark_"):
            lesson_id = query.data.replace("unmark_", "")
            is_mark = False
        else:
            lesson_id = query.data.replace("mark_", "")
            is_mark = True

        # Оновлюємо статус заняття
        await db.mark_lesson_completed(lesson_id, is_mark)

        # Оновлюємо повідомлення
        date_str = today.strftime("%Y-%m-%d")
        date_display = today.strftime("%d.%m.%Y")

        all_lessons = await db.get_lessons(user_id)
        day_lessons = [lesson for lesson in all_lessons if lesson.get('date') == date_str]

        if day_lessons:
            day_lessons.sort(key=lambda x: x.get('start_time', ''))
            message = f"📅 Розклад на сьогодні ({date_display})\n\n"

            for i, lesson in enumerate(day_lessons, 1):
                child = await db.get_child(str(lesson['child_id']))
                child_name = child.get('name', 'Без імені') if child else 'Невідома дитина'
                start_time = lesson.get('start_time', 'N/A')
                end_time = lesson.get('end_time', 'N/A')
                completed = lesson.get('completed', False)
                cancelled = lesson.get('cancelled', False)
                paid = lesson.get('paid', False)

                # Визначаємо статус
                if cancelled:
                    status = "🚫 "
                elif completed:
                    status = "✅ "
                else:
                    status = "⏳ "

                message += f"{i}. {status}{child_name}\n"
                message += f"   ⏰ {start_time} - {end_time}\n\n"

            # Оновлюємо кнопки
            keyboard = []
            for i, lesson in enumerate(day_lessons, 1):
                lid = str(lesson['_id'])
                # Отримуємо ім'я дитини для кнопки
                child = await db.get_child(str(lesson['child_id']))
                child_name = child.get('name', 'Без імені') if child else 'Невідома'
                completed = lesson.get('completed', False)
                cancelled = lesson.get('cancelled', False)

                row = []
                # Кнопка відмітки проведення
                if completed:
                    row.append(InlineKeyboardButton(f"❌ {i}. {child_name}", callback_data=f"unmark_{lid}"))
                else:
                    row.append(InlineKeyboardButton(f"✅ {i}. {child_name}", callback_data=f"mark_{lid}"))

                # Кнопка скасування
                if cancelled:
                    row.append(InlineKeyboardButton(f"🔄 Відновити", callback_data=f"uncancel_{lid}"))
                else:
                    row.append(InlineKeyboardButton(f"🚫 Скасувати", callback_data=f"cancel_{lid}"))

                keyboard.append(row)

            tomorrow = today + timedelta(days=1)
            keyboard.append([InlineKeyboardButton(f"📅 Завтра ({tomorrow.strftime('%d.%m')})", callback_data=f"timetable_tomorrow")])
            keyboard.append([InlineKeyboardButton("📆 На тиждень", callback_data="timetable_week")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup)

    # Обробка скасування/відновлення заняття
    elif query.data.startswith("cancel_") or query.data.startswith("uncancel_"):
        if query.data.startswith("uncancel_"):
            lesson_id = query.data.replace("uncancel_", "")
            is_cancel = False
        else:
            lesson_id = query.data.replace("cancel_", "")
            is_cancel = True

        # Оновлюємо статус скасування
        await db.mark_lesson_cancelled(lesson_id, is_cancel)

        # Оновлюємо повідомлення
        date_str = today.strftime("%Y-%m-%d")
        date_display = today.strftime("%d.%m.%Y")

        all_lessons = await db.get_lessons(user_id)
        day_lessons = [lesson for lesson in all_lessons if lesson.get('date') == date_str]

        if day_lessons:
            day_lessons.sort(key=lambda x: x.get('start_time', ''))
            message = f"📅 Розклад на сьогодні ({date_display})\n\n"

            for i, lesson in enumerate(day_lessons, 1):
                child = await db.get_child(str(lesson['child_id']))
                child_name = child.get('name', 'Без імені') if child else 'Невідома дитина'
                start_time = lesson.get('start_time', 'N/A')
                end_time = lesson.get('end_time', 'N/A')
                completed = lesson.get('completed', False)
                cancelled = lesson.get('cancelled', False)
                paid = lesson.get('paid', False)

                # Визначаємо статус
                if cancelled:
                    status = "🚫 "
                elif completed:
                    status = "✅ "
                else:
                    status = "⏳ "

                message += f"{i}. {status}{child_name}\n"
                message += f"   ⏰ {start_time} - {end_time}\n\n"

            # Оновлюємо кнопки
            keyboard = []
            for i, lesson in enumerate(day_lessons, 1):
                lid = str(lesson['_id'])
                # Отримуємо ім'я дитини для кнопки
                child = await db.get_child(str(lesson['child_id']))
                child_name = child.get('name', 'Без імені') if child else 'Невідома'
                completed = lesson.get('completed', False)
                cancelled = lesson.get('cancelled', False)

                row = []
                # Кнопка відмітки проведення
                if completed:
                    row.append(InlineKeyboardButton(f"❌ {i}. {child_name}", callback_data=f"unmark_{lid}"))
                else:
                    row.append(InlineKeyboardButton(f"✅ {i}. {child_name}", callback_data=f"mark_{lid}"))

                # Кнопка скасування
                if cancelled:
                    row.append(InlineKeyboardButton(f"🔄 Відновити", callback_data=f"uncancel_{lid}"))
                else:
                    row.append(InlineKeyboardButton(f"🚫 Скасувати", callback_data=f"cancel_{lid}"))

                keyboard.append(row)

            tomorrow = today + timedelta(days=1)
            keyboard.append([InlineKeyboardButton(f"📅 Завтра ({tomorrow.strftime('%d.%m')})", callback_data=f"timetable_tomorrow")])
            keyboard.append([InlineKeyboardButton("📆 На тиждень", callback_data="timetable_week")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup)

    elif query.data == "timetable_tomorrow":
        # Показуємо розклад на завтра
        tomorrow = today + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")
        date_display = tomorrow.strftime("%d.%m.%Y")

        all_lessons = await db.get_lessons(user_id)
        day_lessons = [lesson for lesson in all_lessons if lesson.get('date') == date_str]

        if not day_lessons:
            message = f"📅 Розклад на завтра ({date_display})\n\n❌ Занять на завтра не знайдено."
        else:
            day_lessons.sort(key=lambda x: x.get('start_time', ''))
            message = f"📅 Розклад на завтра ({date_display})\n\n"

            for i, lesson in enumerate(day_lessons, 1):
                child = await db.get_child(str(lesson['child_id']))
                child_name = child.get('name', 'Без імені') if child else 'Невідома дитина'
                start_time = lesson.get('start_time', 'N/A')
                end_time = lesson.get('end_time', 'N/A')
                completed = lesson.get('completed', False)

                status = "✅ " if completed else ""
                message += f"{i}. {status}{child_name}\n"
                message += f"   ⏰ {start_time} - {end_time}\n\n"

        await query.edit_message_text(message)

    elif query.data == "timetable_week":
        # Показуємо розклад на тиждень
        await show_week_timetable(query, user_id)


async def show_week_timetable(query, user_id: int):
    """Відображення розкладу на тиждень"""
    from datetime import timedelta
    today = datetime.now()

    # Отримуємо всі заняття користувача
    all_lessons = await db.get_lessons(user_id)

    message = "📆 Розклад на тиждень\n\n"

    # Проходимо по кожному дню тижня
    for day_offset in range(7):
        day = today + timedelta(days=day_offset)
        date_str = day.strftime("%Y-%m-%d")
        date_display = day.strftime("%d.%m.%Y")

        # Фільтруємо заняття по даті
        day_lessons = [lesson for lesson in all_lessons if lesson.get('date') == date_str]

        if day_lessons:
            # Сортуємо заняття по часу початку
            day_lessons.sort(key=lambda x: x.get('start_time', ''))

            # Визначаємо день тижня
            weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
            weekday = weekday_names[day.weekday()]

            message += f"▪️ {weekday}, {date_display}\n"

            for lesson in day_lessons:
                child = await db.get_child(str(lesson['child_id']))
                child_name = child.get('name', 'Без імені') if child else 'Невідома дитина'
                start_time = lesson.get('start_time', 'N/A')
                end_time = lesson.get('end_time', 'N/A')
                completed = lesson.get('completed', False)

                status = "✅ " if completed else ""
                message += f"  {start_time}-{end_time} | {status}{child_name}\n"

            message += "\n"

    if message == "📆 Розклад на тиждень\n\n":
        message += "❌ Занять на тиждень не знайдено."

    await query.edit_message_text(message)


# ============= PAYMENT ENTRY =============

# Стани для внесення оплати
SELECT_CHILD_PAYMENT, ENTER_PAYMENT_AMOUNT, CONFIRM_PAYMENT = range(100, 103)

@access_control
async def payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /payment - внесення оплати"""
    user_id = update.effective_user.id

    # Отримуємо всіх дітей
    all_children = await db.get_children()

    if not all_children:
        await update.message.reply_text(
            "❌ У вас ще немає доданих дітей.\n"
            "Спочатку додайте дитину через /settings"
        )
        return ConversationHandler.END

    # Показуємо список дітей з базовою ціною
    message = "💰 Внесення оплати\n\nОберіть дитину:\n\n"
    keyboard = []

    for child in all_children:
        child_id = str(child['_id'])
        child_name = child.get('name', 'Без імені')
        base_price = child.get('base_price', 0)

        message += f"👤 {child_name} - {base_price} грн/заняття\n"

        keyboard.append([
            InlineKeyboardButton(
                f"{child_name}",
                callback_data=f"pay_select_{child_id}"
            )
        ])

    keyboard.append([InlineKeyboardButton("❌ Скасувати", callback_data="pay_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message, reply_markup=reply_markup)
    return SELECT_CHILD_PAYMENT


async def select_child_for_payment_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вибір дитини для внесення оплати"""
    query = update.callback_query
    await query.answer()

    if query.data == "pay_cancel":
        await query.edit_message_text("❌ Внесення оплати скасовано.")
        context.user_data.clear()
        return ConversationHandler.END

    child_id = query.data.replace("pay_select_", "")

    child = await db.get_child(child_id)
    if not child:
        await query.edit_message_text("❌ Помилка: дитину не знайдено")
        return ConversationHandler.END

    child_name = child.get('name', 'Без імені')
    base_price = child.get('base_price', 0)

    if base_price <= 0:
        await query.edit_message_text(
            f"❌ У дитини {child_name} не встановлена базова ціна.\n"
            f"Встановіть ціну через /settings"
        )
        return ConversationHandler.END

    # Зберігаємо дані в контексті
    context.user_data['payment_entry_child_id'] = child_id
    context.user_data['payment_entry_child_name'] = child_name
    context.user_data['payment_entry_base_price'] = base_price

    await query.edit_message_text(
        f"💰 Внесення оплати\n\n"
        f"Дитина: {child_name}\n"
        f"Ціна за заняття: {base_price} грн\n\n"
        f"Введіть суму оплати в гривнях:"
    )
    return ENTER_PAYMENT_AMOUNT


async def enter_payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Введення суми оплати"""
    amount_text = update.message.text.strip()

    try:
        amount = float(amount_text)
        if amount <= 0:
            await update.message.reply_text(
                "❌ Сума має бути більше 0. Спробуйте ще раз:"
            )
            return ENTER_PAYMENT_AMOUNT
    except ValueError:
        await update.message.reply_text(
            "❌ Введіть коректну суму (число). Спробуйте ще раз:"
        )
        return ENTER_PAYMENT_AMOUNT

    child_name = context.user_data.get('payment_entry_child_name')
    base_price = context.user_data.get('payment_entry_base_price')

    # Рахуємо кількість занять
    lessons_count = amount / base_price

    # Перевіряємо чи ділиться рівно
    if lessons_count != int(lessons_count):
        # Не ділиться рівно
        await update.message.reply_text(
            f"⚠️ Увага!\n\n"
            f"Сума {amount} грн не відповідає рівній кількості занять.\n\n"
            f"При ціні {base_price} грн за заняття, ця сума дорівнює {lessons_count:.2f} занять.\n\n"
            f"Внесіть іншу суму, яка ділиться рівно на {base_price}.\n"
            f"Наприклад:\n"
            f"  • {base_price} грн = 1 заняття\n"
            f"  • {base_price * 5} грн = 5 занять\n"
            f"  • {base_price * 10} грн = 10 занять"
        )
        return ENTER_PAYMENT_AMOUNT

    lessons_count = int(lessons_count)

    # Зберігаємо дані
    context.user_data['payment_entry_amount'] = amount
    context.user_data['payment_entry_lessons_count'] = lessons_count

    # Запитуємо підтвердження
    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="pay_confirm_yes")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="pay_confirm_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"💰 Підтвердження оплати\n\n"
        f"Дитина: {child_name}\n"
        f"Сума: {amount} грн\n"
        f"За {lessons_count} занять(я)\n\n"
        f"Підтверджуєте внесення оплати?",
        reply_markup=reply_markup
    )
    return CONFIRM_PAYMENT


async def confirm_payment_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Підтвердження та збереження оплати"""
    query = update.callback_query
    await query.answer()

    if query.data == "pay_confirm_no":
        await query.edit_message_text("❌ Внесення оплати скасовано.")
        context.user_data.clear()
        return ConversationHandler.END

    # Зберігаємо оплату
    user_id = update.effective_user.id
    child_id = context.user_data.get('payment_entry_child_id')
    child_name = context.user_data.get('payment_entry_child_name')
    amount = context.user_data.get('payment_entry_amount')
    lessons_count = context.user_data.get('payment_entry_lessons_count')

    from datetime import datetime
    payment_date = datetime.now().strftime("%Y-%m-%d")

    payment_id = await db.add_payment(
        user_id=user_id,
        child_id=child_id,
        amount=amount,
        lessons_count=lessons_count,
        payment_date=payment_date
    )

    logger.info(f"User {user_id} added payment: {amount} грн for {lessons_count} lessons for child {child_id}")

    await query.edit_message_text(
        f"✅ Оплату успішно внесено!\n\n"
        f"Дитина: {child_name}\n"
        f"Сума: {amount} грн\n"
        f"За {lessons_count} занять(я)\n"
        f"Дата: {datetime.now().strftime('%d.%m.%Y')}"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_payment_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скасування внесення оплати"""
    context.user_data.clear()
    await update.message.reply_text("❌ Внесення оплати скасовано.")
    return ConversationHandler.END


# ConversationHandler для внесення оплати
def get_payment_entry_conversation_handler():
    """Повертає ConversationHandler для внесення оплати"""
    return ConversationHandler(
        entry_points=[CommandHandler("payment", payment_command)],
        states={
            SELECT_CHILD_PAYMENT: [CallbackQueryHandler(select_child_for_payment_entry)],
            ENTER_PAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_payment_amount)],
            CONFIRM_PAYMENT: [CallbackQueryHandler(confirm_payment_entry)],
        },
        fallbacks=[CommandHandler("cancel", cancel_payment_entry)],
    )


# ============= BALANCE VIEWING =============

@access_control
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /balance - перегляд балансу оплат"""
    user_id = update.effective_user.id

    # Отримуємо всіх дітей
    all_children = await db.get_children()

    # Отримуємо всі заняття та оплати
    all_lessons = await db.get_lessons(user_id)
    all_payments = await db.get_payments(user_id)

    # Рахуємо баланс для кожної дитини
    children_with_balance = []

    for child in all_children:
        child_id = str(child['_id'])

        # Рахуємо проведені заняття
        completed_lessons = [
            lesson for lesson in all_lessons
            if str(lesson['child_id']) == child_id
            and lesson.get('completed', False)
            and not lesson.get('cancelled', False)
        ]
        completed_count = len(completed_lessons)

        # Рахуємо оплачені заняття
        child_payments = [
            payment for payment in all_payments
            if str(payment['child_id']) == child_id
        ]
        paid_lessons = sum(p.get('lessons_count', 0) for p in child_payments)

        # Баланс = оплачені - проведені
        balance = paid_lessons - completed_count

        # Додаємо тільки якщо є дисбаланс
        if balance != 0:
            children_with_balance.append({
                'child_id': child_id,
                'child_name': child.get('name', 'Без імені'),
                'balance': balance,
                'completed_count': completed_count,
                'paid_lessons': paid_lessons
            })

    if not children_with_balance:
        await update.message.reply_text(
            "✅ Баланс по всіх дітях рівний нулю!\nВсі заняття оплачені."
        )
        return

    # Формуємо повідомлення
    message = "💰 Баланс оплат\n\n"
    keyboard = []

    for item in children_with_balance:
        child_name = item['child_name']
        balance = item['balance']

        if balance > 0:
            status = f"💵 Переплата: +{balance} занять"
        else:
            status = f"⚠️ Недоплата: {balance} занять"

        message += f"👤 {child_name}\n"
        message += f"   {status}\n\n"

        # Кнопка для перегляду деталей
        keyboard.append([
            InlineKeyboardButton(
                f"📋 {child_name} - Звіт",
                callback_data=f"balance_child_{item['child_id']}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)


async def handle_balance_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка кнопок балансу"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data.startswith("balance_child_"):
        child_id = query.data.replace("balance_child_", "")

        child = await db.get_child(child_id)
        child_name = child.get('name', 'Без імені') if child else 'Невідома'

        # Отримуємо заняття
        all_lessons = await db.get_lessons(user_id)
        child_lessons = [
            lesson for lesson in all_lessons
            if str(lesson['child_id']) == child_id
            and lesson.get('completed', False)
            and not lesson.get('cancelled', False)
        ]
        child_lessons.sort(key=lambda x: (x.get('date', ''), x.get('start_time', '')))

        # Отримуємо оплати
        all_payments = await db.get_payments(user_id)
        child_payments = [
            payment for payment in all_payments
            if str(payment['child_id']) == child_id
        ]
        child_payments.sort(key=lambda x: x.get('payment_date', ''))

        # Рахуємо баланс
        completed_count = len(child_lessons)
        paid_lessons = sum(p.get('lessons_count', 0) for p in child_payments)
        balance = paid_lessons - completed_count

        # Формуємо повідомлення
        message = f"💰 Деталі оплат: {child_name}\n\n"

        # Баланс
        if balance > 0:
            message += f"💵 Переплата: +{balance} занять\n\n"
        elif balance < 0:
            message += f"⚠️ Недоплата: {balance} занять\n\n"
        else:
            message += f"✅ Баланс: 0 (все оплачено)\n\n"

        # Список оплат
        message += "📝 Оплати:\n"
        if child_payments:
            total_amount = 0
            for payment in child_payments:
                date_str = payment.get('payment_date', '')
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_display = date_obj.strftime("%d.%m.%Y")
                except:
                    date_display = date_str

                amount = payment.get('amount', 0)
                lessons_count = payment.get('lessons_count', 0)
                total_amount += amount

                message += f"  • {date_display}: {amount} грн за {lessons_count} занять\n"

            message += f"  Всього: {total_amount} грн\n\n"
        else:
            message += "  Немає оплат\n\n"

        # Список проведених занять
        message += f"📚 Проведено занять: {completed_count}\n"
        if child_lessons:
            # Показуємо тільки останні 5
            recent_lessons = child_lessons[-5:]
            if len(child_lessons) > 5:
                message += f"(показано останні 5 з {len(child_lessons)})\n"

            for lesson in recent_lessons:
                date_str = lesson.get('date', '')
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_display = date_obj.strftime("%d.%m.%Y")
                except:
                    date_display = date_str

                start_time = lesson.get('start_time', 'N/A')
                message += f"  • {date_display} {start_time}\n"

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="balance_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    elif query.data == "balance_back":
        # Повертаємось до головного меню оплат
        # Отримуємо всіх дітей
        all_children = await db.get_children()

        # Отримуємо всі заняття та оплати
        all_lessons = await db.get_lessons(user_id)
        all_payments = await db.get_payments(user_id)

        # Рахуємо баланс для кожної дитини
        children_with_balance = []

        for child in all_children:
            child_id = str(child['_id'])

            # Рахуємо проведені заняття
            completed_lessons = [
                lesson for lesson in all_lessons
                if str(lesson['child_id']) == child_id
                and lesson.get('completed', False)
                and not lesson.get('cancelled', False)
            ]
            completed_count = len(completed_lessons)

            # Рахуємо оплачені заняття
            child_payments = [
                payment for payment in all_payments
                if str(payment['child_id']) == child_id
            ]
            paid_lessons = sum(p.get('lessons_count', 0) for p in child_payments)

            # Баланс = оплачені - проведені
            balance = paid_lessons - completed_count

            # Додаємо тільки якщо є дисбаланс
            if balance != 0:
                children_with_balance.append({
                    'child_id': child_id,
                    'child_name': child.get('name', 'Без імені'),
                    'balance': balance,
                    'completed_count': completed_count,
                    'paid_lessons': paid_lessons
                })

        if not children_with_balance:
            await query.edit_message_text(
                "✅ Баланс по всіх дітях рівний нулю!\nВсі заняття оплачені."
            )
            return

        # Формуємо повідомлення
        message = "💰 Баланс оплат\n\n"
        keyboard = []

        for item in children_with_balance:
            child_name = item['child_name']
            balance = item['balance']

            if balance > 0:
                status = f"💵 Переплата: +{balance} занять"
            else:
                status = f"⚠️ Недоплата: {balance} занять"

            message += f"👤 {child_name}\n"
            message += f"   {status}\n\n"

            # Кнопка для перегляду деталей
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 {child_name} - Звіт",
                    callback_data=f"balance_child_{item['child_id']}"
                )
            ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)


# ============= DASHBOARD =============

@access_control
async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /dashboard - звіт за місяць"""
    user_id = update.effective_user.id

    from datetime import datetime
    today = datetime.now()

    # Назва місяця українською
    months_uk = {
        1: 'Січень', 2: 'Лютий', 3: 'Березень', 4: 'Квітень',
        5: 'Травень', 6: 'Червень', 7: 'Липень', 8: 'Серпень',
        9: 'Вересень', 10: 'Жовтень', 11: 'Листопад', 12: 'Грудень'
    }
    month_name = months_uk[today.month]
    year = today.year

    # Перший та останній день місяця
    first_day = today.replace(day=1).strftime("%Y-%m-%d")
    if today.month == 12:
        last_day = today.replace(year=today.year + 1, month=1, day=1)
    else:
        last_day = today.replace(month=today.month + 1, day=1)
    last_day = (last_day - timedelta(days=1)).strftime("%Y-%m-%d")

    # Отримуємо всі заняття за місяць
    all_lessons = await db.get_lessons(user_id)
    month_lessons = [
        lesson for lesson in all_lessons
        if first_day <= lesson.get('date', '') <= last_day
    ]

    # Рахуємо проведені та скасовані
    completed_count = sum(1 for l in month_lessons if l.get('completed', False) and not l.get('cancelled', False))
    cancelled_count = sum(1 for l in month_lessons if l.get('cancelled', False))

    # Отримуємо всі оплати за місяць
    all_payments = await db.get_payments(user_id)
    month_payments = [
        payment for payment in all_payments
        if first_day <= payment.get('payment_date', '') <= last_day
    ]

    # Рахуємо суму оплат
    total_payments_amount = sum(p.get('amount', 0) for p in month_payments)

    # Рахуємо переплати та недоплати в грн
    all_children = await db.get_children()
    total_overpay = 0  # переплата
    total_underpay = 0  # недоплата

    for child in all_children:
        child_id = str(child['_id'])
        base_price = child.get('base_price', 0)

        # Рахуємо проведені заняття (всі, не тільки за місяць)
        child_completed = [
            lesson for lesson in all_lessons
            if str(lesson['child_id']) == child_id
            and lesson.get('completed', False)
            and not lesson.get('cancelled', False)
        ]
        completed_lessons_count = len(child_completed)

        # Рахуємо оплачені заняття (всі оплати)
        all_child_payments = [
            payment for payment in all_payments
            if str(payment['child_id']) == child_id
        ]
        paid_lessons_count = sum(p.get('lessons_count', 0) for p in all_child_payments)

        # Баланс в заняттях
        balance = paid_lessons_count - completed_lessons_count

        # Переводимо в гривні
        balance_amount = balance * base_price

        if balance_amount > 0:
            total_overpay += balance_amount
        elif balance_amount < 0:
            total_underpay += abs(balance_amount)

    # Формуємо повідомлення
    message = f"📊 Звіт за {month_name} {year}\n\n"
    message += f"📚 Всього проведено занять: {completed_count}\n"
    message += f"🚫 Всього скасовано занять: {cancelled_count}\n\n"
    message += f"💰 Всього отримано оплат на суму: {total_payments_amount:.0f} грн\n"
    message += f"💵 Всього переплат на суму: {total_overpay:.0f} грн\n"
    message += f"⚠️ Всього недоплат на суму: {total_underpay:.0f} грн\n"

    # Кнопки
    keyboard = [
        [InlineKeyboardButton("📅 Доходи по днях", callback_data="dashboard_by_days")],
        [InlineKeyboardButton("👤 Доходи по дітях", callback_data="dashboard_by_children")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message, reply_markup=reply_markup)


async def handle_dashboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка кнопок dashboard"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    from datetime import datetime, timedelta
    today = datetime.now()

    # Перший та останній день місяця
    first_day = today.replace(day=1).strftime("%Y-%m-%d")
    if today.month == 12:
        last_day = today.replace(year=today.year + 1, month=1, day=1)
    else:
        last_day = today.replace(month=today.month + 1, day=1)
    last_day = (last_day - timedelta(days=1)).strftime("%Y-%m-%d")

    if query.data == "dashboard_by_days":
        # Доходи по днях (на основі проведених занять)
        all_lessons = await db.get_lessons(user_id)
        month_lessons = [
            lesson for lesson in all_lessons
            if first_day <= lesson.get('date', '') <= last_day
            and lesson.get('completed', False)
            and not lesson.get('cancelled', False)
        ]

        # Отримуємо всіх дітей для отримання цін
        all_children = await db.get_children()
        children_dict = {str(child['_id']): child for child in all_children}

        # Групуємо по днях
        from collections import defaultdict
        income_by_day = defaultdict(float)

        for lesson in month_lessons:
            date_str = lesson.get('date', '')
            child_id = str(lesson['child_id'])
            child = children_dict.get(child_id)
            if child:
                base_price = child.get('base_price', 0)
                income_by_day[date_str] += base_price

        # Сортуємо по даті
        sorted_days = sorted(income_by_day.items())

        months_uk = {
            1: 'Січень', 2: 'Лютий', 3: 'Березень', 4: 'Квітень',
            5: 'Травень', 6: 'Червень', 7: 'Липень', 8: 'Серпень',
            9: 'Вересень', 10: 'Жовтень', 11: 'Листопад', 12: 'Грудень'
        }
        month_name = months_uk[today.month]

        message = f"📅 Доходи по днях за {month_name}\n\n"

        if sorted_days:
            total = 0
            for date_str, amount in sorted_days:
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_display = date_obj.strftime("%d.%m.%Y")
                except:
                    date_display = date_str

                message += f"{date_display}: {amount:.0f} грн\n"
                total += amount

            message += f"\n💰 Всього: {total:.0f} грн"
        else:
            message += "Немає проведених занять за цей місяць"

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="dashboard_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup)

    elif query.data == "dashboard_by_children":
        # Доходи по дітях (на основі проведених занять)
        all_lessons = await db.get_lessons(user_id)
        month_lessons = [
            lesson for lesson in all_lessons
            if first_day <= lesson.get('date', '') <= last_day
            and lesson.get('completed', False)
            and not lesson.get('cancelled', False)
        ]

        # Отримуємо всіх дітей для отримання цін
        all_children = await db.get_children()
        children_dict = {str(child['_id']): child for child in all_children}

        # Групуємо по дітях
        from collections import defaultdict
        income_by_child = defaultdict(float)

        for lesson in month_lessons:
            child_id = str(lesson['child_id'])
            child = children_dict.get(child_id)
            if child:
                base_price = child.get('base_price', 0)
                income_by_child[child_id] += base_price

        months_uk = {
            1: 'Січень', 2: 'Лютий', 3: 'Березень', 4: 'Квітень',
            5: 'Травень', 6: 'Червень', 7: 'Липень', 8: 'Серпень',
            9: 'Вересень', 10: 'Жовтень', 11: 'Листопад', 12: 'Грудень'
        }
        month_name = months_uk[today.month]

        message = f"👤 Доходи по дітях за {month_name}\n\n"

        if income_by_child:
            total = 0
            for child_id, amount in income_by_child.items():
                child = children_dict.get(child_id)
                child_name = child.get('name', 'Без імені') if child else 'Невідома'

                message += f"{child_name}: {amount:.0f} грн\n"
                total += amount

            message += f"\n💰 Всього: {total:.0f} грн"
        else:
            message += "Немає проведених занять за цей місяць"

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="dashboard_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup)

    elif query.data == "dashboard_back":
        # Повернутись до головного dashboard
        # Назва місяця українською
        months_uk = {
            1: 'Січень', 2: 'Лютий', 3: 'Березень', 4: 'Квітень',
            5: 'Травень', 6: 'Червень', 7: 'Липень', 8: 'Серпень',
            9: 'Вересень', 10: 'Жовтень', 11: 'Листопад', 12: 'Грудень'
        }
        month_name = months_uk[today.month]
        year = today.year

        # Отримуємо всі заняття за місяць
        all_lessons = await db.get_lessons(user_id)
        month_lessons = [
            lesson for lesson in all_lessons
            if first_day <= lesson.get('date', '') <= last_day
        ]

        # Рахуємо проведені та скасовані
        completed_count = sum(1 for l in month_lessons if l.get('completed', False) and not l.get('cancelled', False))
        cancelled_count = sum(1 for l in month_lessons if l.get('cancelled', False))

        # Отримуємо всі оплати за місяць
        all_payments = await db.get_payments(user_id)
        month_payments = [
            payment for payment in all_payments
            if first_day <= payment.get('payment_date', '') <= last_day
        ]

        # Рахуємо суму оплат
        total_payments_amount = sum(p.get('amount', 0) for p in month_payments)

        # Рахуємо переплати та недоплати в грн
        all_children = await db.get_children()
        total_overpay = 0
        total_underpay = 0

        for child in all_children:
            child_id = str(child['_id'])
            base_price = child.get('base_price', 0)

            # Рахуємо проведені заняття (всі)
            child_completed = [
                lesson for lesson in all_lessons
                if str(lesson['child_id']) == child_id
                and lesson.get('completed', False)
                and not lesson.get('cancelled', False)
            ]
            completed_lessons_count = len(child_completed)

            # Рахуємо оплачені заняття (всі оплати)
            all_child_payments = [
                payment for payment in all_payments
                if str(payment['child_id']) == child_id
            ]
            paid_lessons_count = sum(p.get('lessons_count', 0) for p in all_child_payments)

            # Баланс в заняттях
            balance = paid_lessons_count - completed_lessons_count

            # Переводимо в гривні
            balance_amount = balance * base_price

            if balance_amount > 0:
                total_overpay += balance_amount
            elif balance_amount < 0:
                total_underpay += abs(balance_amount)

        # Формуємо повідомлення
        message = f"📊 Звіт за {month_name} {year}\n\n"
        message += f"📚 Всього проведено занять: {completed_count}\n"
        message += f"🚫 Всього скасовано занять: {cancelled_count}\n\n"
        message += f"💰 Всього отримано оплат на суму: {total_payments_amount:.0f} грн\n"
        message += f"💵 Всього переплат на суму: {total_overpay:.0f} грн\n"
        message += f"⚠️ Всього недоплат на суму: {total_underpay:.0f} грн\n"

        # Кнопки
        keyboard = [
            [InlineKeyboardButton("📅 Доходи по днях", callback_data="dashboard_by_days")],
            [InlineKeyboardButton("👤 Доходи по дітях", callback_data="dashboard_by_children")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup)


# ============= CONVERSATION HANDLERS =============

# Створення ConversationHandler
def get_add_lesson_conversation_handler():
    """Повертає ConversationHandler для додавання заняття"""
    return ConversationHandler(
        entry_points=[CommandHandler("addlesson", add_lesson_command)],
        states={
            SELECT_CHILD: [CallbackQueryHandler(select_child_for_lesson)],
            LESSON_DATE: [
                CallbackQueryHandler(handle_date_button),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_lesson_date)
            ],
            LESSON_START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_lesson_start_time)],
            LESSON_END_TIME: [
                CallbackQueryHandler(handle_end_time_button),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_lesson_end_time)
            ],
            ASK_REPEAT_MONTHLY: [
                CallbackQueryHandler(handle_repeat_monthly_response, pattern="^repeat_monthly_"),
                CallbackQueryHandler(confirm_monthly_lessons, pattern="^confirm_monthly_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_add_lesson)],
    )
