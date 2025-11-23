import html
import uuid
import base64
import os
from aiogram import Router, F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

import database
import keyboards
from github_client import GitHubClient

router = Router()

class FileEditStates(StatesGroup):
    waiting_for_new_content = State()

# --- BROWSER ---

@router.callback_query(F.data.startswith("files:"))
async def file_browser_start(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    owner = parts[1]
    repo_name = parts[2]
    path = ":".join(parts[3:]) if len(parts) > 3 else ""

    await show_file_browser(callback, owner, repo_name, path)

@router.callback_query(F.data.startswith("f_nav:"))
async def file_navigate(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    owner = parts[1]
    repo_name = parts[2]
    path = ":".join(parts[3:])
    
    await show_file_browser(callback, owner, repo_name, path)

async def show_file_browser(callback: types.CallbackQuery, owner, repo_name, path):
    user = await database.get_user(callback.from_user.id)
    client = GitHubClient(user['github_token'])
    
    items = await client.get_contents(owner, repo_name, path)
    
    if items is None:
        await callback.answer("Ошибка доступа или пусто", show_alert=True)
        return
    
    if isinstance(items, dict): 
        await show_file_view(callback, owner, repo_name, path)
        return

    current_display = f"/{path}" if path else "/"
    await callback.message.edit_text(
        f"📂 <b>{repo_name}</b>: <code>{current_display}</code>",
        parse_mode="HTML",
        reply_markup=keyboards.file_browser_kb(owner, repo_name, path, items)
    )

# --- VIEWER ---

@router.callback_query(F.data.startswith("f_view:"))
async def file_view_entry(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    owner = parts[1]
    repo_name = parts[2]
    path = ":".join(parts[3:])
    await show_file_view(callback, owner, repo_name, path)

async def show_file_view(callback: types.CallbackQuery, owner, repo, path):
    user = await database.get_user(callback.from_user.id)
    client = GitHubClient(user['github_token'])
    
    data = await client.get_contents(owner, repo, path)
    if not data or 'content' not in data:
        await callback.answer("Не удалось прочитать файл", show_alert=True)
        return

    try:
        content = base64.b64decode(data['content']).decode('utf-8')
    except:
        await callback.answer("Бинарный файл. Просмотр недоступен.", show_alert=True)
        return
    
    # Генерируем ссылку на Web Editor
    session_uuid = str(uuid.uuid4())
    await database.create_editor_session(
        session_uuid, 
        callback.from_user.id, 
        owner, 
        repo, 
        path, 
        data['sha']
    )
    
    # --- FIX: ИСПОЛЬЗУЕМ BASE_URL ---
    base_url = os.getenv("BASE_URL")
    if base_url:
        # Убираем слеш в конце если есть
        base_url = base_url.rstrip('/')
        web_url = f"{base_url}/editor/{session_uuid}"
    else:
        # Fallback на IP (если BASE_URL не задан)
        host = os.getenv("WEBHOOK_HOST", "127.0.0.1")
        port = os.getenv("WEBHOOK_PORT", "8080")
        web_url = f"http://{host}:{port}/editor/{session_uuid}"

    preview = html.escape(content[:500])
    if len(content) > 500: preview += "..."
    
    ext = path.split('.')[-1]
    
    msg_text = (
        f"📄 <b>{html.escape(path)}</b>\n"
        f"Size: {data['size']} bytes\n\n"
        f"<pre language='{ext}'>{preview}</pre>"
    )
    
    await callback.message.edit_text(
        msg_text,
        parse_mode="HTML",
        reply_markup=keyboards.file_view_kb(owner, repo, path, web_url)
    )

# --- EDIT (SMALL FILES) ---

@router.callback_query(F.data.startswith("f_edit:"))
async def edit_file_start(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    owner = parts[1]
    repo_name = parts[2]
    path = ":".join(parts[3:])
    
    user = await database.get_user(callback.from_user.id)
    client = GitHubClient(user['github_token'])
    data = await client.get_contents(owner, repo_name, path)
    
    content = base64.b64decode(data['content']).decode('utf-8')
    
    if len(content) > 3000:
        await callback.answer("Файл слишком большой для чата! Используй Web Editor.", show_alert=True)
        return

    await state.update_data(owner=owner, repo=repo_name, path=path, sha=data['sha'])
    
    await callback.message.answer(
        f"✏️ <b>Редактирование:</b> {path}\n"
        "Пришли мне новое содержимое файла текстом.\n"
        "Старое содержимое:",
        parse_mode="HTML"
    )
    await callback.message.answer(f"<code>{html.escape(content)}</code>", parse_mode="HTML")
    await state.set_state(FileEditStates.waiting_for_new_content)
    await callback.answer()

@router.message(FileEditStates.waiting_for_new_content)
async def edit_file_preview(message: types.Message, state: FSMContext):
    new_content = message.text
    data = await state.get_data()
    
    await state.update_data(pending_content=new_content)
    
    await message.answer(
        f"📝 <b>Предпросмотр ({data['path']}):</b>\n\n"
        f"<code>{html.escape(new_content)}</code>",
        parse_mode="HTML",
        reply_markup=keyboards.file_edit_action_kb(data['owner'], data['repo'], data['path'])
    )

@router.callback_query(F.data.startswith("f_save:"))
async def edit_file_commit(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    user = await database.get_user(callback.from_user.id)
    client = GitHubClient(user['github_token'])
    
    success, res = await client.update_file(
        data['owner'], data['repo'], data['path'],
        message=f"Update {data['path']} via Bot",
        content=data['pending_content'],
        sha=data['sha']
    )
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Файл сохранен!</b>\nCommit: <code>{res['commit']['sha'][:7]}</code>",
            parse_mode="HTML",
            reply_markup=keyboards.repo_actions(data['repo'], res['content']['html_url'], data['owner'])
        )
    else:
        await callback.message.edit_text(f"❌ Ошибка коммита: {res}")
    
    await state.clear()

# --- WEB EDITOR CONFIRM ---

@router.callback_query(F.data.startswith("w_save:"))
async def web_save_confirm(callback: types.CallbackQuery):
    uuid = callback.data.split(":")[1]
    session = await database.get_editor_session(uuid)
    
    if not session or not session['pending_content']:
        await callback.answer("Сессия истекла или нет данных", show_alert=True)
        return
    
    user = await database.get_user(callback.from_user.id)
    client = GitHubClient(user['github_token'])
    
    await callback.message.edit_text("💾 <b>Коммичу...</b>", parse_mode="HTML")
    
    success, res = await client.update_file(
        session['owner'], session['repo'], session['path'],
        message=f"Web Edit: {session['path']}",
        content=session['pending_content'],
        sha=session['original_sha']
    )
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Изменения приняты!</b>\nФайл: <code>{session['path']}</code> обновлен.",
            parse_mode="HTML"
        )
        await database.delete_editor_session(uuid)
    else:
        await callback.message.edit_text(f"❌ Ошибка GitHub: {res}")

@router.callback_query(F.data.startswith("w_discard:"))
async def web_discard(callback: types.CallbackQuery):
    uuid = callback.data.split(":")[1]
    await database.delete_editor_session(uuid)
    await callback.message.edit_text("🗑 Изменения отменены.")