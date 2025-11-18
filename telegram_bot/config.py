import os
from dotenv import load_dotenv

# Завантаження змінних з .env файлу
load_dotenv()


class Config:
    """Конфігурація бота"""

    # Telegram Bot Token
    BOT_TOKEN = os.getenv('BOT_TOKEN')

    # MongoDB
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'telegram_bot_db')

    # Admin IDs
    ADMIN_IDS = [
        int(admin_id.strip())
        for admin_id in os.getenv('ADMIN_IDS', '').split(',')
        if admin_id.strip()
    ]

    # Allowed User IDs
    ALLOWED_USER_IDS = [
        int(user_id.strip())
        for user_id in os.getenv('ALLOWED_USER_IDS', '').split(',')
        if user_id.strip()
    ]

    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Перевірка чи є користувач адміном"""
        return user_id in cls.ADMIN_IDS

    @classmethod
    def is_allowed_user(cls, user_id: int) -> bool:
        """Перевірка чи дозволено користувачу користуватись ботом"""
        return user_id in cls.ALLOWED_USER_IDS or user_id in cls.ADMIN_IDS


# Валідація конфігурації
if not Config.BOT_TOKEN:
    raise ValueError("BOT_TOKEN не знайдено в .env файлі!")
