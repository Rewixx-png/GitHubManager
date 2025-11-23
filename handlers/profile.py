import html
from aiogram import Router, F, types
import database
import keyboards
from github_client import GitHubClient

router = Router()

@router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    user_db = await database.get_user(callback.from_user.id)
    
    # 1. Проверка авторизации
    if not user_db or not user_db.get('github_token'):
        await callback.answer("Сначала авторизуйся!", show_alert=True)
        return

    # 2. Загрузка данных
    # Пытаемся редактировать сообщение, чтобы показать лоадер
    try:
        await callback.message.edit_text("🔄 <b>Загрузка профиля...</b>", parse_mode="HTML")
    except:
        pass # Если сообщение с фото, edit_text может упасть, не страшно

    client = GitHubClient(user_db['github_token'])
    info = await client.get_user_info()
    
    if not info:
        await callback.message.edit_text(
            "❌ <b>Ошибка API GitHub.</b>\nВозможно, токен протух.",
            reply_markup=keyboards.main_menu()
        )
        return

    # 3. Парсинг данных
    login = html.escape(info.get('login', 'Unknown'))
    name = html.escape(info.get('name') or login)
    bio = html.escape(info.get('bio') or 'Нет описания')
    location = html.escape(info.get('location') or 'Не указано')
    company = html.escape(info.get('company') or 'Нет')
    avatar_url = info.get('avatar_url')
    
    public_repos = info.get('public_repos', 0)
    followers = info.get('followers', 0)
    following = info.get('following', 0)
    
    # Формируем красивый текст
    caption = (
        f"👤 <b>{name}</b> (<code>{login}</code>)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 <i>{bio}</i>\n\n"
        f"📍 <b>Локация:</b> {location}\n"
        f"🏢 <b>Компания:</b> {company}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"├ 📦 Репозитории: <b>{public_repos}</b>\n"
        f"├ 👥 Подписчики: <b>{followers}</b>\n"
        f"└ 👀 Подписки: <b>{following}</b>\n\n"
        f"🔗 <a href='{info.get('html_url')}'>Открыть на GitHub</a>"
    )

    # 4. Отправка (Удаляем старое, шлем фото)
    await callback.message.delete()
    
    await callback.message.answer_photo(
        photo=avatar_url,
        caption=caption,
        parse_mode="HTML",
        reply_markup=keyboards.profile_kb()
    )