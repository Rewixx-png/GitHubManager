import asyncio
import paramiko
import html
from aiogram import Router, F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import database
import keyboards
from crypto_utils import encrypt

router = Router()

class ServerSetupStates(StatesGroup):
    waiting_for_host = State()
    waiting_for_port = State()
    waiting_for_user = State()
    waiting_for_password = State() # or Key

@router.callback_query(F.data == "setup_server")
async def setup_server_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🖥 <b>Настройка сервера (SSH)</b>\n\n"
        "1. Введи IP адрес или домен сервера:",
        parse_mode="HTML"
    )
    await state.set_state(ServerSetupStates.waiting_for_host)
    await callback.answer()

@router.message(ServerSetupStates.waiting_for_host)
async def process_host(message: types.Message, state: FSMContext):
    await state.update_data(host=message.text.strip())
    await message.answer("2. Введи порт (обычно 22):")
    await state.set_state(ServerSetupStates.waiting_for_port)

@router.message(ServerSetupStates.waiting_for_port)
async def process_port(message: types.Message, state: FSMContext):
    try:
        port = int(message.text.strip())
        await state.update_data(port=port)
        await message.answer("3. Введи имя пользователя (например, <code>root</code>):", parse_mode="HTML")
        await state.set_state(ServerSetupStates.waiting_for_user)
    except ValueError:
        await message.answer("❌ Введи число.")

@router.message(ServerSetupStates.waiting_for_user)
async def process_user(message: types.Message, state: FSMContext):
    await state.update_data(username=message.text.strip())
    await message.answer(
        "4. Введи <b>Пароль</b> пользователя.\n"
        "(Поддержку SSH ключей добавим позже для простоты, пока только пароль)",
        parse_mode="HTML"
    )
    await state.set_state(ServerSetupStates.waiting_for_password)

@router.message(ServerSetupStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    
    msg = await message.answer("📡 <b>Проверяю соединение...</b>", parse_mode="HTML")
    
    # Пытаемся подключиться
    try:
        def test_ssh():
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=data['host'],
                port=data['port'],
                username=data['username'],
                password=password,
                timeout=5
            )
            client.close()
            
        await asyncio.to_thread(test_ssh)
        
        # Шифруем и сохраняем
        encrypted_pass = encrypt(password)
        await database.set_server(
            message.from_user.id,
            data['host'],
            data['port'],
            data['username'],
            'password',
            encrypted_pass
        )
        
        await msg.edit_text(
            "✅ <b>Успех!</b> Сервер подключен.\nТеперь ты можешь пушить код прямо с него.",
            parse_mode="HTML",
            reply_markup=keyboards.settings_menu(False) # Вернуться в настройки
        )
        await state.clear()
        
    except Exception as e:
        await msg.edit_text(f"❌ <b>Ошибка подключения:</b>\n<code>{html.escape(str(e))}</code>\nПопробуй заново.", parse_mode="HTML")
        await state.clear()
    
    # Удаляем сообщение с паролем
    try: await message.delete()
    except: pass