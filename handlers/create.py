import html
import os
import shutil
import tempfile
import asyncio
from git import Repo, Actor
from aiogram import Router, F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import database
import keyboards
from github_client import GitHubClient

router = Router()

class CreateRepoStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_desc = State()
    waiting_for_visibility = State()
    waiting_for_gitignore = State()
    waiting_for_zip = State()

async def delete_msg(bot, chat_id, msg_id):
    try: await bot.delete_message(chat_id, msg_id)
    except: pass

@router.callback_query(F.data == "create_repo_start")
async def create_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CreateRepoStates.waiting_for_name)
    msg = await callback.message.edit_text(
        "✨ <b>Новый проект (Шаг 1/5)</b>\n\n"
        "Введите <b>название</b> репозитория (латиница, без пробелов):",
        parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=msg.message_id)

@router.message(CreateRepoStates.waiting_for_name)
async def create_name(message: types.Message, state: FSMContext, bot):
    name = message.text.strip()
    await delete_msg(bot, message.chat.id, message.message_id)
    
    data = await state.get_data()
    if 'last_bot_msg_id' in data:
        await delete_msg(bot, message.chat.id, data['last_bot_msg_id'])
        
    await state.update_data(repo_name=name)
    await state.set_state(CreateRepoStates.waiting_for_desc)
    
    msg = await message.answer(
        f"📝 <b>Шаг 2/5: Описание</b>\n\n"
        f"Название: <code>{html.escape(name)}</code>\n"
        "Введите описание проекта (можно на русском):",
        parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=msg.message_id)

@router.message(CreateRepoStates.waiting_for_desc)
async def create_desc(message: types.Message, state: FSMContext, bot):
    desc = message.text.strip()
    await delete_msg(bot, message.chat.id, message.message_id)
    
    data = await state.get_data()
    if 'last_bot_msg_id' in data:
        await delete_msg(bot, message.chat.id, data['last_bot_msg_id'])
        
    await state.update_data(repo_desc=desc)
    
    msg = await message.answer(
        "🔒 <b>Шаг 3/5: Приватность</b>\n\n"
        "Кто сможет видеть этот проект?",
        parse_mode="HTML",
        reply_markup=keyboards.create_visibility_kb()
    )
    # Здесь мы не можем просто удалить сообщение с кнопками при ответе кнопкой,
    # это сделает сам callback handler, но обновим state на всякий
    await state.update_data(last_bot_msg_id=msg.message_id)
    await state.set_state(CreateRepoStates.waiting_for_visibility)

@router.callback_query(CreateRepoStates.waiting_for_visibility, F.data.startswith("cr_vis:"))
async def create_visibility(callback: types.CallbackQuery, state: FSMContext):
    vis = callback.data.split(":")[1] # private / public
    is_private = (vis == 'private')
    await state.update_data(is_private=is_private)
    
    await callback.message.edit_text(
        "📄 <b>Шаг 4/5: .gitignore</b>\n\n"
        "Выберите шаблон для игнорирования лишних файлов:",
        parse_mode="HTML",
        reply_markup=keyboards.create_gitignore_kb()
    )
    await state.set_state(CreateRepoStates.waiting_for_gitignore)

@router.callback_query(CreateRepoStates.waiting_for_gitignore, F.data.startswith("cr_git:"))
async def create_process(callback: types.CallbackQuery, state: FSMContext):
    git_template = callback.data.split(":")[1] # 'Python' or 'None'
    
    await callback.message.edit_text("⏳ <b>Создаю репозиторий на GitHub...</b>", parse_mode="HTML")
    
    data = await state.get_data()
    user = await database.get_user(callback.from_user.id)
    client = GitHubClient(user['github_token'])
    
    success, res = await client.create_repo(
        name=data['repo_name'],
        description=data['repo_desc'],
        private=data['is_private'],
        gitignore_template=git_template
    )
    
    if not success:
        await callback.message.edit_text(f"❌ <b>Ошибка создания:</b>\n{res}", parse_mode="HTML")
        await state.clear()
        return

    # Сохраняем инфо о созданном репо
    await state.update_data(
        final_owner=res['owner']['login'],
        final_repo=res['name'],
        final_url=res['html_url']
    )

    # Переход к загрузке кода
    msg = await callback.message.edit_text(
        f"✅ <b>Проект создан!</b>\n"
        f"🔗 <a href='{res['html_url']}'>{res['full_name']}</a>\n\n"
        "📦 <b>Шаг 5/5: Загрузка кода</b>\n"
        "Отправь мне <b>.zip</b> архив с исходным кодом, чтобы я залил его в репозиторий.\n"
        "Или нажми 'Пропустить', если хочешь оставить его пустым.",
        parse_mode="HTML",
        reply_markup=keyboards.create_upload_kb(),
        disable_web_page_preview=True
    )
    await state.update_data(last_bot_msg_id=msg.message_id)
    await state.set_state(CreateRepoStates.waiting_for_zip)

@router.callback_query(F.data == "cr_skip_zip")
async def skip_zip(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        f"🎉 <b>Готово!</b>\nПроект <code>{data['final_repo']}</code> создан.",
        parse_mode="HTML",
        reply_markup=keyboards.repo_actions(data['final_repo'], data['final_url'], data['final_owner'])
    )
    await state.clear()

@router.message(CreateRepoStates.waiting_for_zip, F.document)
async def upload_zip_initial(message: types.Message, state: FSMContext, bot):
    if not message.document.file_name.endswith('.zip'):
        await message.answer("❌ Это не ZIP.")
        return

    # Удаляем файл юзера
    await delete_msg(bot, message.chat.id, message.message_id)
    
    data = await state.get_data()
    if 'last_bot_msg_id' in data:
        await delete_msg(bot, message.chat.id, data['last_bot_msg_id'])

    file = await bot.get_file(message.document.file_id)
    temp_zip = tempfile.mktemp(suffix=".zip")
    await bot.download_file(file.file_path, temp_zip)

    msg = await message.answer("🔄 <b>Инициализация кода...</b>", parse_mode="HTML")
    
    user_id = message.from_user.id
    user = await database.get_user(user_id)
    token = user['github_token']
    
    owner = data['final_owner']
    repo_name = data['final_repo']
    
    work_dir = tempfile.mkdtemp()
    repo_dir = os.path.join(work_dir, "repo")

    try:
        def initial_push():
            repo_url = f"https://oauth2:{token}@github.com/{owner}/{repo_name}.git"
            
            # 1. Clone (там уже может быть .gitignore и README)
            Repo.clone_from(repo_url, repo_dir)
            repo = Repo(repo_dir)
            
            # 2. Unzip over it
            shutil.unpack_archive(temp_zip, repo_dir)
            
            # 3. Add all
            repo.git.add('--all')
            
            if not repo.index.diff("HEAD"):
                 return "Пустой архив или нет изменений"
            
            author = Actor(user['github_username'], f"{user['github_username']}@bot.com")
            repo.index.commit("Initial commit via Bot", author=author, committer=author)
            
            origin = repo.remote(name='origin')
            origin.push()
            return "OK"

        res = await asyncio.to_thread(initial_push)
        
        if res == "OK":
             await msg.edit_text(
                f"🎉 <b>Успех!</b>\nПроект создан и код загружен.\n🔗 {data['final_url']}",
                parse_mode="HTML",
                reply_markup=keyboards.repo_actions(repo_name, data['final_url'], owner),
                disable_web_page_preview=True
             )
        else:
             await msg.edit_text(f"⚠️ Проект создан, но код не залит: {res}")

    except Exception as e:
        await msg.edit_text(f"❌ Ошибка Git: {e}")
    finally:
        if os.path.exists(work_dir): shutil.rmtree(work_dir)
        if os.path.exists(temp_zip): os.remove(temp_zip)
        await state.clear()