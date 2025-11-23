from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📂 Проекты", callback_data="repos:1")
    builder.button(text="⚙️ Настройки", callback_data="settings")
    # Удаляем "Перепривязать токен" отсюда, перенесем в настройки для чистоты
    builder.adjust(1)
    return builder.as_markup()

def settings_menu(ignore_own: bool):
    status = "✅ ВКЛ (Игнорю)" if ignore_own else "❌ ВЫКЛ (Вижу всё)"
    builder = InlineKeyboardBuilder()
    builder.button(text="🖥 Подключить сервер (SSH)", callback_data="setup_server") # NEW
    builder.button(text="🔑 Сменить GitHub Токен", callback_data="set_token")
    builder.button(text=f"Свои пуши: {status}", callback_data="toggle_ignore")
    builder.button(text="🔙 Назад", callback_data="start")
    builder.adjust(1)
    return builder.as_markup()

# Остальные функции (repo_list_pagination, repo_actions, push_notification_kb) оставь как были!
# Я не буду их дублировать, чтобы сэкономить место, код там не поменялся.
# Вставь их сюда из прошлого ответа.
# ...