import os
import logging
import html
from aiogram import Router, F, types
from aiogram.types import FSInputFile

import database
from github_client import GitHubClient

router = Router()
BASE_URL = os.getenv("BASE_URL")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

@router.callback_query(F.data.startswith("sub:"))
async def subscribe_handler(callback: types.CallbackQuery):
    _, owner, repo_name = callback.data.split(":")
    user = await database.get_user(callback.from_user.id)
    
    if not BASE_URL:
        await callback.answer("BASE_URL not set", show_alert=True)
        return

    webhook_url = f"{BASE_URL}/github-webhook"
    
    msg = await callback.message.answer("🛰 <b>Connecting...</b>", parse_mode="HTML")
    client = GitHubClient(user['github_token'])
    success, res = await client.create_webhook(owner, repo_name, webhook_url, WEBHOOK_SECRET)
    
    if success:
        await database.add_subscription(callback.from_user.id, f"{owner}/{repo_name}")
        await msg.edit_text(f"✅ <b>Подписка оформлена!</b>\nОтвет: {html.escape(str(res))}", parse_mode="HTML")
    else:
        await msg.edit_text(f"❌ Ошибка: {html.escape(str(res))}", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("dl:"))
async def download_handler(callback: types.CallbackQuery):
    _, owner, repo_name = callback.data.split(":")
    user = await database.get_user(callback.from_user.id)
    
    msg = await callback.message.answer(f"⏳ <b>Качаю {html.escape(repo_name)}...</b>", parse_mode="HTML")
    client = GitHubClient(user['github_token'])
    path = await client.download_repo(owner, repo_name)
    
    if path:
        try:
            file_size = os.path.getsize(path)
            
            if file_size == 0:
                await msg.edit_text("❌ <b>Ошибка:</b> Файл пустой (0 байт).")
                return

            if file_size > 49 * 1024 * 1024:
                size_mb = round(file_size / (1024 * 1024), 2)
                await msg.edit_text(f"❌ <b>Слишком большой файл!</b>\nРазмер: {size_mb} MB.")
                return

            file = FSInputFile(path, filename=f"{repo_name}.zip")
            await callback.message.answer_document(file, caption=f"📦 {html.escape(repo_name)}.zip")
            await msg.delete()
        except Exception as e:
            logging.error(f"Send error: {e}")
            await msg.edit_text(f"❌ <b>Ошибка отправки:</b>\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")
        finally:
            if os.path.exists(path): os.remove(path)
    else:
        await msg.edit_text("❌ Ошибка при скачивании с GitHub.")
    await callback.answer()