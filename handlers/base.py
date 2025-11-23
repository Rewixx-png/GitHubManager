import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import ContentType
import keyboards

router = Router()

@router.message(Command("start"))
@router.callback_query(F.data == "start")
async def cmd_start(event: types.Message | types.CallbackQuery):
    # Удаляем сообщение пользователя с командой /start
    if isinstance(event, types.Message):
        try:
            await event.delete()
        except:
            pass

    msg_text = (
        "🛸 <b>GitHub Control Center</b>\n\n"
        "Система готова. Используй меню для управления проектами."
    )

    if isinstance(event, types.Message):
        await event.answer(msg_text, parse_mode="HTML", reply_markup=keyboards.main_menu())
    else:
        # Если это callback (кнопка Назад)
        message = event.message
        
        # Если предыдущее сообщение было с ФОТО (например, профиль)
        if message.content_type == ContentType.PHOTO:
            await message.delete()
            # 1. Отправляем текст (как ты просил, без кнопок сначала)
            new_msg = await message.answer(msg_text, parse_mode="HTML")
            # 2. Ждем полсекунды
            await asyncio.sleep(0.5)
            # 3. Добавляем меню
            await new_msg.edit_reply_markup(reply_markup=keyboards.main_menu())
        else:
            # Если это обычный текст, просто редактируем
            await message.edit_text(msg_text, parse_mode="HTML", reply_markup=keyboards.main_menu())