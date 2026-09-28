"""
Ishchilar boti (aiogram 3.x).
Ishga tushirish:  python manage.py runworkerbot
"""
import asyncio
import logging

from django.core.management.base import BaseCommand
from django.conf import settings
from asgiref.sync import sync_to_async

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage

from apps.workers.bot import keyboards as kb
from apps.workers.bot.handlers_worker import router as worker_router
from apps.workers.bot.handlers_boss import router as boss_router


start_router = Router()


@sync_to_async
def get_worker_role(tg_id):
    from apps.workers.models import Worker
    w = Worker.objects.filter(telegram_id=tg_id).first()
    return (w.role, w.name) if w else (None, None)


@start_router.message(CommandStart())
async def cmd_start(message: Message):
    role, name = await get_worker_role(message.from_user.id)

    if role == 'worker':
        await message.answer(
            f"Assalomu alaykum, {name}! 👷\n\nVazifalaringizni ko'rish uchun quyidagi tugmadan foydalaning.",
            reply_markup=kb.worker_main_kb()
        )
    elif role in ('boss', 'admin'):
        await message.answer(
            f"Assalomu alaykum, {name}! 👔\n\n"
            f"Siz {'boshliq' if role == 'boss' else 'admin'} sifatida ro'yxatdasiz.\n\n"
            f"➕ <b>Vazifa qo'shish</b> — ishchiga to'g'ridan-to'g'ri topshiriq berish\n"
            f"📜 <b>Tarix</b> — kim vaqtida bajardi/bajarmadi\n\n"
            f"Vazifa bajarilganda sizga hisobot ham keladi.",
            parse_mode="HTML", reply_markup=kb.boss_main_kb()
        )
    else:
        await message.answer(
            "Assalomu alaykum! 👋\n\n"
            "Siz hali tizimda ro'yxatdan o'tmagansiz.\n"
            "Administrator sizni tizimga qo'shishi kerak.\n\n"
            f"Sizning Telegram ID: <code>{message.from_user.id}</code>\n"
            "Shu ID ni administratorga yuboring.",
            parse_mode="HTML"
        )


class Command(BaseCommand):
    help = "Ishchilar botini ishga tushiradi (aiogram)"

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO)
        token = settings.WORKER_BOT_TOKEN
        if not token:
            self.stderr.write(self.style.ERROR("WORKER_BOT_TOKEN .env faylida yo'q!"))
            return

        async def main():
            bot = Bot(token=token)
            dp = Dispatcher(storage=MemoryStorage())
            dp.include_router(start_router)
            dp.include_router(boss_router)
            dp.include_router(worker_router)
            await bot.delete_webhook(drop_pending_updates=True)
            self.stdout.write(self.style.SUCCESS("Ishchilar boti ishga tushdi..."))
            await dp.start_polling(bot)

        asyncio.run(main())