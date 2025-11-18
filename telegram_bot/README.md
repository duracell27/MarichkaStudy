# Telegram Bot з MongoDB

Telegram бот на Python з підтримкою MongoDB та контролем доступу.

## Структура проекту

```
telegram_bot/
├── main.py              # Головний файл бота
├── config.py            # Конфігурація та завантаження .env
├── database.py          # Робота з MongoDB
├── requirements.txt     # Залежності Python
├── .env                 # Змінні середовища (заповніть своїми даними!)
├── .gitignore          # Файли для ігнорування Git
└── handlers/           # Папка для додаткових handlers
```

## Встановлення

1. Встановіть залежності:
```bash
cd telegram_bot
pip install -r requirements.txt
```

2. Встановіть MongoDB (якщо ще не встановлено):
- macOS: `brew install mongodb-community`
- Ubuntu: `sudo apt install mongodb`
- Windows: завантажте з офіційного сайту MongoDB

3. Запустіть MongoDB:
```bash
# macOS/Linux
mongod

# або якщо встановлено через brew на macOS
brew services start mongodb-community
```

## Налаштування

1. Відредагуйте файл `.env` та заповніть необхідні дані:

```env
# Отримайте токен від @BotFather в Telegram
BOT_TOKEN=your_bot_token_here

# MongoDB підключення
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=telegram_bot_db

# ID адміністраторів (отримайте свій ID від @userinfobot)
ADMIN_IDS=123456789,987654321

# ID користувачів, яким дозволено користуватись ботом
ALLOWED_USER_IDS=111111111,222222222,333333333
```

2. Як отримати свій Telegram ID:
   - Напишіть боту @userinfobot
   - Він надішле вам ваш ID

3. Як створити бота та отримати токен:
   - Напишіть @BotFather в Telegram
   - Використайте команду /newbot
   - Слідуйте інструкціям
   - Скопіюйте отриманий токен в .env файл

## Запуск

```bash
cd telegram_bot
python main.py
```

## Функціонал

### Для всіх дозволених користувачів:
- `/start` - Початок роботи з ботом
- `/help` - Довідка
- Бот відповідає на текстові повідомлення

### Для адміністраторів:
- `/stats` - Статистика користувачів
- `/users` - Список всіх користувачів бота

## Безпека

- Файл `.env` додано до `.gitignore` та не буде закомічено в Git
- Бот відповідає тільки користувачам з `ALLOWED_USER_IDS` та `ADMIN_IDS`
- Адміністраторські команди доступні тільки користувачам з `ADMIN_IDS`

## База даних

Бот використовує MongoDB з наступними колекціями:
- `users` - інформація про користувачів
- `messages` - логи повідомлень

## Розширення функціоналу

Додавайте нові handlers в папку `handlers/` та імпортуйте їх в `main.py`
