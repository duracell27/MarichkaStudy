from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from config import Config
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    """Клас для роботи з MongoDB"""

    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        """Підключення до MongoDB"""
        try:
            self.client = AsyncIOMotorClient(Config.MONGODB_URI, tlsAllowInvalidCertificates=True)
            self.db = self.client[Config.MONGODB_DB_NAME]
            # Перевірка підключення
            await self.client.admin.command('ping')
            logger.info("✅ Успішно підключено до MongoDB")
        except ConnectionFailure as e:
            logger.error(f"❌ Помилка підключення до MongoDB: {e}")
            raise

    async def disconnect(self):
        """Відключення від MongoDB"""
        if self.client:
            self.client.close()
            logger.info("MongoDB відключено")

    # === Користувачі ===
    async def add_user(self, user_id: int, username: str = None, first_name: str = None):
        """Додавання або оновлення користувача"""
        user_data = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name
        }
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": user_data},
            upsert=True
        )

    async def get_user(self, user_id: int):
        """Отримання даних користувача"""
        return await self.db.users.find_one({"user_id": user_id})

    async def get_all_users(self):
        """Отримання всіх користувачів"""
        cursor = self.db.users.find()
        return await cursor.to_list(length=None)

    # === Повідомлення/Логи ===
    async def log_message(self, user_id: int, message_text: str, message_type: str = "text"):
        """Логування повідомлень"""
        log_data = {
            "user_id": user_id,
            "message_text": message_text,
            "message_type": message_type,
            "timestamp": None  # MongoDB додасть timestamp автоматично
        }
        await self.db.messages.insert_one(log_data)

    async def get_user_messages(self, user_id: int, limit: int = 100):
        """Отримання історії повідомлень користувача"""
        cursor = self.db.messages.find({"user_id": user_id}).sort("_id", -1).limit(limit)
        return await cursor.to_list(length=limit)

    # === Діти ===
    async def add_child(self, user_id: int, name: str, age: int, base_price: float = 0):
        """Додавання дитини"""
        child_data = {
            "user_id": user_id,
            "name": name,
            "age": age,
            "base_price": base_price,
            "archived": False,  # за замовчуванням активна
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = await self.db.children.insert_one(child_data)
        return result.inserted_id

    async def get_children(self, user_id: int = None, include_archived: bool = False):
        """Отримання дітей (для всіх дозволених користувачів)"""
        from config import Config
        # Фільтр по всіх дозволених користувачах
        query = {"user_id": {"$in": Config.ALLOWED_USER_IDS}}
        # За замовчуванням показуємо тільки активних (не архівованих)
        if not include_archived:
            query["archived"] = {"$ne": True}
        cursor = self.db.children.find(query).sort("created_at", 1)
        return await cursor.to_list(length=None)

    async def get_child(self, child_id):
        """Отримання дитини за ID"""
        from bson.objectid import ObjectId
        return await self.db.children.find_one({"_id": ObjectId(child_id)})

    async def update_child(self, child_id, name: str = None, age: int = None, base_price: float = None):
        """Оновлення даних дитини"""
        from bson.objectid import ObjectId
        update_data = {"updated_at": datetime.utcnow()}

        if name is not None:
            update_data["name"] = name
        if age is not None:
            update_data["age"] = age
        if base_price is not None:
            update_data["base_price"] = base_price

        result = await self.db.children.update_one(
            {"_id": ObjectId(child_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete_child(self, child_id):
        """Видалення дитини"""
        from bson.objectid import ObjectId
        result = await self.db.children.delete_one({"_id": ObjectId(child_id)})
        return result.deleted_count > 0

    async def is_child_in_use(self, child_id):
        """
        Перевірка чи дитина використовується в розрахунках
        """
        from bson.objectid import ObjectId
        # Перевіряємо чи є заняття для цієї дитини
        lessons_count = await self.db.lessons.count_documents({"child_id": ObjectId(child_id)})
        # Перевіряємо чи є оплати для цієї дитини
        payments_count = await self.db.payments.count_documents({"child_id": ObjectId(child_id)})

        return lessons_count > 0 or payments_count > 0

    async def archive_child(self, child_id):
        """Архівування дитини"""
        from bson.objectid import ObjectId
        result = await self.db.children.update_one(
            {"_id": ObjectId(child_id)},
            {"$set": {"archived": True, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def unarchive_child(self, child_id):
        """Розархівування дитини"""
        from bson.objectid import ObjectId
        result = await self.db.children.update_one(
            {"_id": ObjectId(child_id)},
            {"$set": {"archived": False, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def get_archived_children(self):
        """Отримання архівованих дітей"""
        from config import Config
        query = {
            "user_id": {"$in": Config.ALLOWED_USER_IDS},
            "archived": True
        }
        cursor = self.db.children.find(query).sort("created_at", 1)
        return await cursor.to_list(length=None)

    # === Заняття ===
    async def add_lesson(self, user_id: int, child_id: str, date: str, start_time: str, end_time: str):
        """Додавання заняття"""
        from bson.objectid import ObjectId
        lesson_data = {
            "user_id": user_id,
            "child_id": ObjectId(child_id),
            "date": date,  # формат: "2024-11-14"
            "start_time": start_time,  # формат: "10:00"
            "end_time": end_time,  # формат: "11:00"
            "completed": False,  # чи проведено заняття
            "cancelled": False,  # чи скасовано заняття
            "paid": False,  # чи оплачено заняття
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = await self.db.lessons.insert_one(lesson_data)
        return result.inserted_id

    async def get_lessons(self, user_id: int = None, child_id: str = None):
        """Отримання занять (для всіх дозволених користувачів або конкретної дитини)"""
        from bson.objectid import ObjectId
        from config import Config

        # Фільтруємо по всіх дозволених користувачах
        query = {"user_id": {"$in": Config.ALLOWED_USER_IDS}}
        if child_id:
            query["child_id"] = ObjectId(child_id)

        cursor = self.db.lessons.find(query).sort("date", -1)
        return await cursor.to_list(length=None)

    async def get_lesson(self, lesson_id):
        """Отримання заняття за ID"""
        from bson.objectid import ObjectId
        return await self.db.lessons.find_one({"_id": ObjectId(lesson_id)})

    async def update_lesson(self, lesson_id, date: str = None, start_time: str = None, end_time: str = None):
        """Оновлення заняття"""
        from bson.objectid import ObjectId
        update_data = {"updated_at": datetime.utcnow()}

        if date is not None:
            update_data["date"] = date
        if start_time is not None:
            update_data["start_time"] = start_time
        if end_time is not None:
            update_data["end_time"] = end_time

        result = await self.db.lessons.update_one(
            {"_id": ObjectId(lesson_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete_lesson(self, lesson_id):
        """Видалення заняття"""
        from bson.objectid import ObjectId
        result = await self.db.lessons.delete_one({"_id": ObjectId(lesson_id)})
        return result.deleted_count > 0

    async def mark_lesson_completed(self, lesson_id, completed: bool = True):
        """Позначення заняття як проведеного або скасування позначки"""
        from bson.objectid import ObjectId
        result = await self.db.lessons.update_one(
            {"_id": ObjectId(lesson_id)},
            {"$set": {"completed": completed, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def mark_lesson_cancelled(self, lesson_id, cancelled: bool = True):
        """Позначення заняття як скасованого або скасування позначки"""
        from bson.objectid import ObjectId
        result = await self.db.lessons.update_one(
            {"_id": ObjectId(lesson_id)},
            {"$set": {"cancelled": cancelled, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def mark_lesson_paid(self, lesson_id, paid: bool = True):
        """Позначення заняття як оплаченого або скасування позначки"""
        from bson.objectid import ObjectId
        result = await self.db.lessons.update_one(
            {"_id": ObjectId(lesson_id)},
            {"$set": {"paid": paid, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    # === Оплати ===
    async def add_payment(self, user_id: int, child_id: str, amount: float, lessons_count: int, payment_date: str, note: str = ""):
        """Додавання оплати"""
        from bson.objectid import ObjectId
        payment_data = {
            "user_id": user_id,
            "child_id": ObjectId(child_id),
            "amount": amount,
            "lessons_count": lessons_count,  # за скільки занять
            "payment_date": payment_date,  # дата оплати
            "note": note,  # необов'язкова примітка
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = await self.db.payments.insert_one(payment_data)
        return result.inserted_id

    async def get_payments(self, user_id: int = None, child_id: str = None):
        """Отримання оплат (для всіх дозволених користувачів або конкретної дитини)"""
        from bson.objectid import ObjectId
        from config import Config

        # Фільтруємо по всіх дозволених користувачах
        query = {"user_id": {"$in": Config.ALLOWED_USER_IDS}}
        if child_id:
            query["child_id"] = ObjectId(child_id)

        cursor = self.db.payments.find(query).sort("payment_date", -1)
        return await cursor.to_list(length=None)

    async def get_payment(self, payment_id):
        """Отримання оплати за ID"""
        from bson.objectid import ObjectId
        return await self.db.payments.find_one({"_id": ObjectId(payment_id)})

    async def delete_payment(self, payment_id):
        """Видалення оплати"""
        from bson.objectid import ObjectId
        result = await self.db.payments.delete_one({"_id": ObjectId(payment_id)})
        return result.deleted_count > 0


# Глобальний екземпляр бази даних
db = Database()
