from aiogram import Router, F, types
from aiogram.filters import Command
import keyboards

router = Router()

@router.message(Command("start"))
@router.callback_query(F.data == "start")
async def cmd_start(event: types.Message | types.CallbackQuery):
    msg_text = (
        "🛸 <b>GitHub Control Center</b>\n\n"
        "Система готова. Используй меню для управления проектами."
    )
    if isinstance(event, types.Message):
        await event.answer(msg_text, parse_mode="HTML", reply_markup=keyboards.main_menu())
    else:
        await event.message.edit_text(msg_text, parse_mode="HTML", reply_markup=keyboards.main_menu())