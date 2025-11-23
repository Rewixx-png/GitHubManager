import html
from aiogram import Router, F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import database
import keyboards
from github_client import GitHubClient

router = Router()

class AuthStates(StatesGroup):
    waiting_for_token = State()

@router.callback_query(F.data == "set_token")
async def ask_token(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔑 <b>Введи GitHub Token:</b>", parse_mode="HTML")
    await state.set_state(AuthStates.waiting_for_token)
    await callback.answer()

@router.message(AuthStates.waiting_for_token)
async def save_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    msg = await message.answer("🔄 <b>Check...</b>", parse_mode="HTML")
    
    client = GitHubClient(token)
    user_info = await client.get_user_info()
    if not user_info:
        await msg.edit_text("❌ Bad Token.")
        return
    
    gh_username = user_info['login']
    await database.set_user_data(message.from_user.id, token, gh_username)
    await msg.edit_text(
        f"✅ Logged in as: <code>{html.escape(gh_username)}</code>", 
        parse_mode="HTML",
        reply_markup=keyboards.main_menu()
    )
    await state.clear()
    try: await message.delete() 
    except: pass