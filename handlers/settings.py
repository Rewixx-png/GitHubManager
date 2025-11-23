from aiogram import Router, F, types
import database
import keyboards

router = Router()

@router.callback_query(F.data == "settings")
async def open_settings(callback: types.CallbackQuery):
    user = await database.get_user(callback.from_user.id)
    if not user: return await callback.answer("Нет авторизации")
    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>", 
        parse_mode="HTML", 
        reply_markup=keyboards.settings_menu(user['ignore_own_pushes'])
    )

@router.callback_query(F.data == "toggle_ignore")
async def toggle_ignore(callback: types.CallbackQuery):
    new_val = await database.toggle_ignore_own(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=keyboards.settings_menu(new_val))
    await callback.answer("Сохранено")