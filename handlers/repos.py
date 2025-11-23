import html
from aiogram import Router, F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import database
import keyboards
from github_client import GitHubClient

router = Router()

class RepoManageStates(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_desc = State()

async def delete_msg(bot, chat_id, msg_id):
    try: await bot.delete_message(chat_id, msg_id)
    except: pass

async def show_repos_page(callback: types.CallbackQuery, page: int):
    user = await database.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Авторизуйся!", show_alert=True)
        return

    filter_mode = user.get('repo_filter', 'all')
    client = GitHubClient(user['github_token'])
    
    # per_page=10 (было 5), чтобы показать 2 столбца
    repos, has_next = await client.get_repos(page=page, per_page=10, filter_mode=filter_mode)
    
    if repos is None:
        await callback.message.edit_text("⚠️ Ошибка GitHub API.")
        return
        
    if not repos and page == 1:
        text = "🤷‍♂️ Репозитории не найдены."
        if filter_mode == 'owner':
            text += "\n(Фильтр: Только Мои)"
        
        await callback.message.edit_text(
            text, 
            reply_markup=keyboards.repo_list_pagination([], 1, False, filter_mode)
        )
        return

    await callback.message.edit_text(
        f"📦 <b>Ваши репозитории (Стр. {page})</b>:",
        parse_mode="HTML",
        reply_markup=keyboards.repo_list_pagination(repos, page, has_next, filter_mode)
    )

@router.callback_query(F.data.startswith("repos:"))
async def list_repos_paginated(callback: types.CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_repos_page(callback, page)
    await callback.answer()

@router.callback_query(F.data == "toggle_repo_filter")
async def toggle_repo_filter_handler(callback: types.CallbackQuery):
    await database.toggle_repo_filter(callback.from_user.id)
    await show_repos_page(callback, 1)
    await callback.answer("Фильтр изменен")

@router.callback_query(F.data == "noop")
async def noop_handler(callback: types.CallbackQuery):
    await callback.answer("Это текущая страница")

@router.callback_query(F.data.startswith("view:"))
async def view_repo(callback: types.CallbackQuery):
    _, owner, repo_name = callback.data.split(":")
    
    user = await database.get_user(callback.from_user.id)
    client = GitHubClient(user['github_token'])
    repo = await client.get_repo_details(owner, repo_name)
    
    if not repo:
        await callback.answer("Ошибка загрузки инфо", show_alert=True)
        return

    visibility = "🔒 Private" if repo['private'] else "🌍 Public"
    desc = html.escape(repo.get('description') or 'Нет описания')
    
    msg = (
        f"📂 <b>{html.escape(repo['full_name'])}</b>\n"
        f"{visibility} | ⭐ {repo['stargazers_count']} | 🍴 {repo['forks_count']}\n\n"
        f"<i>{desc}</i>"
    )
    
    await callback.message.edit_text(
        msg, 
        parse_mode="HTML",
        reply_markup=keyboards.repo_actions(repo['name'], repo['html_url'], repo['owner']['login'])
    )

# --- УПРАВЛЕНИЕ (MANAGE) ---

@router.callback_query(F.data.startswith("manage:"))
async def manage_repo_menu(callback: types.CallbackQuery):
    _, owner, repo_name = callback.data.split(":")
    await callback.message.edit_text(
        f"🛠 <b>Управление:</b> {html.escape(repo_name)}",
        parse_mode="HTML",
        reply_markup=keyboards.repo_management_kb(owner, repo_name)
    )

# --- RENAME ---
@router.callback_query(F.data.startswith("ren_repo:"))
async def rename_repo_start(callback: types.CallbackQuery, state: FSMContext):
    _, owner, repo_name = callback.data.split(":")
    await state.update_data(owner=owner, repo_name=repo_name)
    await state.set_state(RepoManageStates.waiting_for_new_name)
    
    msg = await callback.message.edit_text(
        f"✏️ <b>Переименование {repo_name}</b>\n"
        "Введи новое имя (латиница, без пробелов):",
        parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=msg.message_id)

@router.message(RepoManageStates.waiting_for_new_name)
async def rename_repo_finish(message: types.Message, state: FSMContext, bot):
    new_name = message.text.strip()
    await delete_msg(bot, message.chat.id, message.message_id)
    
    data = await state.get_data()
    if 'last_bot_msg_id' in data:
        await delete_msg(bot, message.chat.id, data['last_bot_msg_id'])
    
    user = await database.get_user(message.from_user.id)
    client = GitHubClient(user['github_token'])
    
    wait_msg = await message.answer("🔄 <b>Сохраняю...</b>", parse_mode="HTML")
    
    success, res = await client.update_repo(data['owner'], data['repo_name'], new_name=new_name)
    
    if success:
        await wait_msg.edit_text(
            f"✅ Репозиторий переименован в <b>{html.escape(new_name)}</b>!",
            parse_mode="HTML",
            reply_markup=keyboards.repo_list_pagination([], 1, False, 'all') 
        )
    else:
        await wait_msg.edit_text(
            f"❌ Ошибка: {html.escape(str(res))}",
            reply_markup=keyboards.main_menu()
        )
    await state.clear()

# --- DESCRIPTION ---
@router.callback_query(F.data.startswith("desc_repo:"))
async def desc_repo_start(callback: types.CallbackQuery, state: FSMContext):
    _, owner, repo_name = callback.data.split(":")
    
    user = await database.get_user(callback.from_user.id)
    client = GitHubClient(user['github_token'])
    repo = await client.get_repo_details(owner, repo_name)
    current_desc = repo.get('description') or "Нет описания"
    
    await state.update_data(owner=owner, repo_name=repo_name)
    await state.set_state(RepoManageStates.waiting_for_new_desc)
    
    msg = await callback.message.edit_text(
        f"📝 <b>Изменение описания {repo_name}</b>\n\n"
        f"Текущее: <i>{html.escape(current_desc)}</i>\n\n"
        "Введи новое описание:",
        parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=msg.message_id)

@router.message(RepoManageStates.waiting_for_new_desc)
async def desc_repo_finish(message: types.Message, state: FSMContext, bot):
    new_desc = message.text.strip()
    await delete_msg(bot, message.chat.id, message.message_id)
    
    data = await state.get_data()
    if 'last_bot_msg_id' in data:
        await delete_msg(bot, message.chat.id, data['last_bot_msg_id'])
    
    user = await database.get_user(message.from_user.id)
    client = GitHubClient(user['github_token'])
    
    wait_msg = await message.answer("🔄 <b>Обновляю...</b>", parse_mode="HTML")
    
    success, res = await client.update_repo(data['owner'], data['repo_name'], description=new_desc)
    
    if success:
        await wait_msg.delete()
        await message.answer(
            f"✅ Описание обновлено для <b>{html.escape(data['repo_name'])}</b>!",
            parse_mode="HTML",
            reply_markup=keyboards.repo_actions(data['repo_name'], res['html_url'], data['owner'])
        )
    else:
        await wait_msg.edit_text(f"❌ Ошибка: {html.escape(str(res))}")
    
    await state.clear()

# --- DELETE ---
@router.callback_query(F.data.startswith("del_confirm:"))
async def delete_confirm(callback: types.CallbackQuery):
    _, owner, repo_name = callback.data.split(":")
    await callback.message.edit_text(
        f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        f"Ты собираешься удалить репозиторий <b>{owner}/{repo_name}</b>.\n"
        "Это действие <b>НЕОБРАТИМО</b>.\n\n"
        "Ты уверен?",
        parse_mode="HTML",
        reply_markup=keyboards.repo_delete_confirm_kb(owner, repo_name)
    )

@router.callback_query(F.data.startswith("del_do:"))
async def delete_execute(callback: types.CallbackQuery):
    _, owner, repo_name = callback.data.split(":")
    
    user = await database.get_user(callback.from_user.id)
    client = GitHubClient(user['github_token'])
    
    await callback.message.edit_text("🗑 <b>Удаляю...</b>", parse_mode="HTML")
    
    success, msg = await client.delete_repo(owner, repo_name)
    
    if success:
        await callback.message.edit_text(
            f"✅ Репозиторий <b>{repo_name}</b> был удален.",
            parse_mode="HTML",
            reply_markup=keyboards.main_menu()
        )
    else:
        await callback.message.edit_text(
            f"❌ Не удалось удалить: {msg}",
            reply_markup=keyboards.repo_management_kb(owner, repo_name)
        )