import html
from aiogram import Router, F, types
import database
import keyboards
from github_client import GitHubClient

router = Router()

async def show_repos_page(callback: types.CallbackQuery, page: int):
    """Внутренняя логика отрисовки страницы."""
    user = await database.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Авторизуйся!", show_alert=True)
        return

    filter_mode = user.get('repo_filter', 'all')
    client = GitHubClient(user['github_token'])
    
    repos, has_next = await client.get_repos(page=page, per_page=5, filter_mode=filter_mode)
    
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