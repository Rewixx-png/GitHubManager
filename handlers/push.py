import os
import shutil
import tempfile
import logging
import html
import asyncio
import paramiko
from git import Repo, Actor
from aiogram import Router, F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import database
import keyboards
from crypto_utils import decrypt

router = Router()

class PushStates(StatesGroup):
    waiting_for_zip = State()
    waiting_for_message = State()
    waiting_for_remote_path = State()
    waiting_for_remote_message = State()

async def delete_msg(bot, chat_id, msg_id):
    """Безопасное удаление сообщения"""
    try:
        await bot.delete_message(chat_id, msg_id)
    except:
        pass

@router.callback_query(F.data.startswith("push:"))
async def start_push_flow(callback: types.CallbackQuery, state: FSMContext):
    _, owner, repo_name = callback.data.split(":")
    await state.update_data(owner=owner, repo_name=repo_name)
    
    server = await database.get_server(callback.from_user.id)
    
    buttons = []
    buttons.append([types.InlineKeyboardButton(text="📄 Через ZIP (Локально)", callback_data="push_method:zip")])
    if server:
        buttons.append([types.InlineKeyboardButton(text=f"🖥 С сервера ({server['host']})", callback_data="push_method:ssh")])
    buttons.append([types.InlineKeyboardButton(text="❌ Отмена", callback_data="noop")])
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Сохраняем ID меню, если захотим редактировать его, но пока просто отправляем новое или редактируем текущее
    await callback.message.answer(
        f"🚀 <b>Deploy: {owner}/{repo_name}</b>\nВыбери метод:",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()

# --- МЕТОД ZIP ---
@router.callback_query(F.data == "push_method:zip")
async def push_via_zip(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PushStates.waiting_for_zip)
    msg = await callback.message.edit_text(
        "1. Пришли мне <b>.zip</b> архив.\n⚠️ Все файлы в репо будут перезаписаны!",
        parse_mode="HTML"
    )
    # Сохраняем ID сообщения бота
    await state.update_data(last_bot_msg_id=msg.message_id)

@router.message(PushStates.waiting_for_zip, F.document)
async def handle_zip_upload(message: types.Message, state: FSMContext, bot):
    if not message.document.file_name.endswith('.zip'):
        await message.answer("❌ Это не ZIP.")
        return
    
    # Удаляем сообщение с файлом юзера
    await delete_msg(bot, message.chat.id, message.message_id)
    
    # Удаляем предыдущий промпт бота
    data = await state.get_data()
    if 'last_bot_msg_id' in data:
        await delete_msg(bot, message.chat.id, data['last_bot_msg_id'])

    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path
    
    temp_zip = tempfile.mktemp(suffix=".zip")
    await bot.download_file(file_path, temp_zip)
    
    await state.update_data(zip_path=temp_zip)
    msg = await message.answer("📝 <b>Сообщение коммита:</b>", parse_mode="HTML")
    await state.set_state(PushStates.waiting_for_message)
    await state.update_data(last_bot_msg_id=msg.message_id)

@router.message(PushStates.waiting_for_message)
async def execute_push_zip(message: types.Message, state: FSMContext, bot):
    commit_message = message.text.strip()
    
    # Чистка чата
    await delete_msg(bot, message.chat.id, message.message_id)
    data = await state.get_data()
    if 'last_bot_msg_id' in data:
        await delete_msg(bot, message.chat.id, data['last_bot_msg_id'])
        
    zip_path = data['zip_path']
    owner = data['owner']
    repo_name = data['repo_name']
    
    user_id = message.from_user.id
    user = await database.get_user(user_id)
    token = user['github_token']
    
    msg = await message.answer(f"⚙️ <b>Processing {repo_name}...</b>", parse_mode="HTML")
    
    work_dir = tempfile.mkdtemp()
    repo_dir = os.path.join(work_dir, "repo")
    
    try:
        repo_url = f"https://oauth2:{token}@github.com/{owner}/{repo_name}.git"
        
        def git_operations():
            Repo.clone_from(repo_url, repo_dir)
            repo = Repo(repo_dir)
            
            for item in os.listdir(repo_dir):
                if item == '.git': continue
                item_path = os.path.join(repo_dir, item)
                if os.path.isfile(item_path): os.remove(item_path)
                elif os.path.isdir(item_path): shutil.rmtree(item_path)
            
            shutil.unpack_archive(zip_path, repo_dir)
            repo.git.add('--all')
            
            if not repo.index.diff("HEAD"):
                return False, "Нет изменений для коммита."
            
            author = Actor(user['github_username'], f"{user['github_username']}@bot.com")
            repo.index.commit(commit_message, author=author, committer=author)
            origin = repo.remote(name='origin')
            origin.push()
            return True, "OK"

        success, status = await asyncio.to_thread(git_operations)
        
        if success:
            await msg.edit_text(f"✅ <b>Успешно!</b>\nКоммит запушен в <code>{repo_name}</code>.", parse_mode="HTML")
        else:
            await msg.edit_text(f"⚠️ <b>Внимание:</b> {status}", parse_mode="HTML")

    except Exception as e:
        await msg.edit_text(f"❌ <b>Ошибка:</b>\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")
    finally:
        if os.path.exists(work_dir): shutil.rmtree(work_dir)
        if os.path.exists(zip_path): os.remove(zip_path)
        await state.clear()

# --- МЕТОД SSH (Remote) ---
@router.callback_query(F.data == "push_method:ssh")
async def push_via_ssh(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PushStates.waiting_for_remote_path)
    
    # Это сообщение мы потом удалим, когда юзер введет путь
    msg = await callback.message.edit_text(
        "📂 <b>Remote Deploy</b>\n\n"
        "Введи полный путь к папке проекта на сервере:\n"
        "Пример: <code>/var/www/my_bot</code>",
        parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=msg.message_id)

@router.message(PushStates.waiting_for_remote_path)
async def ssh_get_path(message: types.Message, state: FSMContext, bot):
    path = message.text.strip()
    if path.endswith('/'): path = path[:-1]
    
    # 1. Удаляем сообщение юзера с путем
    await delete_msg(bot, message.chat.id, message.message_id)
    
    # 2. Удаляем сообщение бота "Введи путь"
    data = await state.get_data()
    if 'last_bot_msg_id' in data:
        await delete_msg(bot, message.chat.id, data['last_bot_msg_id'])
    
    await state.update_data(remote_path=path)
    
    # 3. Отправляем новое и запоминаем ID
    msg = await message.answer("📝 <b>Напиши сообщение для коммита:</b>", parse_mode="HTML")
    await state.set_state(PushStates.waiting_for_remote_message)
    await state.update_data(last_bot_msg_id=msg.message_id)

@router.message(PushStates.waiting_for_remote_message)
async def execute_ssh_push(message: types.Message, state: FSMContext, bot):
    commit_msg = message.text.strip()
    
    # 1. Удаляем сообщение юзера (коммит)
    await delete_msg(bot, message.chat.id, message.message_id)
    
    # 2. Удаляем сообщение бота "Напиши коммит"
    data = await state.get_data()
    if 'last_bot_msg_id' in data:
        await delete_msg(bot, message.chat.id, data['last_bot_msg_id'])
        
    path = data['remote_path']
    owner = data['owner']
    repo_name = data['repo_name']
    
    server = await database.get_server(message.from_user.id)
    if not server:
        await message.answer("❌ Сервер отвалился.")
        return

    msg = await message.answer(f"📡 <b>Подключение к {server['host']}...</b>", parse_mode="HTML")

    try:
        password = decrypt(server['auth_data'])
        
        def run_ssh_commands():
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(server['host'], server['port'], server['username'], password, timeout=10)
            
            # 1. Проверяем папку
            stdin, stdout, stderr = client.exec_command(f"cd {path} && git status")
            if stdout.channel.recv_exit_status() != 0:
                err = stderr.read().decode()
                # Определяем, кривой ли путь
                is_path_error = "No such file or directory" in err or "Нет такого файла" in err
                return False, f"Ошибка Git или пути:\n{err}", is_path_error
            
            # 2. Add, Commit, Push
            cmds = [
                f"cd {path}",
                "git add .",
                f"git commit -m '{commit_msg}'",
                "git push"
            ]
            full_cmd = " && ".join(cmds)
            
            stdin, stdout, stderr = client.exec_command(full_cmd)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode()
            err = stderr.read().decode()
            
            client.close()
            
            if exit_code != 0:
                if "nothing to commit" in out or "нечего коммитить" in out:
                    return True, "Нет изменений.", False
                return False, f"STDERR: {err}\nSTDOUT: {out}", False
            
            return True, out, False

        # success, result_text, is_path_error
        success, result, is_path_error = await asyncio.to_thread(run_ssh_commands)
        
        if success:
            await msg.edit_text(
                f"✅ <b>Remote Push Success!</b>\n\n"
                f"Repo: <code>{owner}/{repo_name}</code>\n"
                f"Path: <code>{path}</code>\n"
                f"Result: <code>{result[:100]}...</code>",
                parse_mode="HTML",
                reply_markup=keyboards.ssh_error_kb(False) # Просто кнопка Назад
            )
        else:
            # ОШИБКА
            await msg.edit_text(
                f"❌ <b>Remote Error:</b>\n<code>{html.escape(result)}</code>", 
                parse_mode="HTML",
                reply_markup=keyboards.ssh_error_kb(allow_change_path=is_path_error)
            )

    except Exception as e:
        await msg.edit_text(
            f"❌ <b>SSH Error:</b>\n<code>{html.escape(str(e))}</code>", 
            parse_mode="HTML",
            reply_markup=keyboards.ssh_error_kb(False)
        )
    
    await state.clear()