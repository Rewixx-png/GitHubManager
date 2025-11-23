from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ... (ВСЕ СТАРЫЕ ФУНКЦИИ main_menu, settings_menu и т.д. ОСТАВЛЯЕМ!) ...
# ...
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="📂 Проекты", callback_data="repos:1")
    builder.button(text="⚙️ Настройки", callback_data="settings")
    builder.adjust(1)
    return builder.as_markup()

def profile_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="start")
    return builder.as_markup()

def repo_actions(repo_name, repo_url, owner):
    builder = InlineKeyboardBuilder()
    # file_nav:owner:repo_name:path
    builder.button(text="📁 Файлы (Beta)", callback_data=f"files:{owner}:{repo_name}:") # NEW
    builder.button(text="🛠 Управление", callback_data=f"manage:{owner}:{repo_name}")
    builder.button(text="🔔 Подписаться (Webhook)", callback_data=f"sub:{owner}:{repo_name}")
    builder.button(text="🚀 Деплой / Push", callback_data=f"push:{owner}:{repo_name}")
    builder.button(text="💾 Скачать ZIP", callback_data=f"dl:{owner}:{repo_name}")
    builder.button(text="🔗 Открыть на GitHub", url=repo_url)
    builder.button(text="🔙 Назад", callback_data="repos:1")
    builder.adjust(1)
    return builder.as_markup()

# --- FILE MANAGER KEYBOARDS ---

def file_browser_kb(owner, repo, current_path, items):
    """Клавиатура для навигации по файлам"""
    builder = InlineKeyboardBuilder()
    
    # Сортируем: Папки сверху, файлы снизу
    folders = [i for i in items if i['type'] == 'dir']
    files = [i for i in items if i['type'] == 'file']
    
    # Лимит кнопок тг - 100, но лучше держать около 20-30
    # TODO: Пагинация файлов, если их много
    
    for folder in folders[:15]:
        path = folder['path']
        # f_nav:{owner}:{repo}:{path}
        # Сокращаем ключи для экономии места в callback
        # Примечание: тут потенциальная проблема с длиной path.
        builder.button(text=f"📂 {folder['name']}", callback_data=f"f_nav:{owner}:{repo}:{path}")

    for file in files[:15]:
        path = file['path']
        builder.button(text=f"📄 {file['name']}", callback_data=f"f_view:{owner}:{repo}:{path}")
    
    builder.adjust(2)
    
    # Кнопка "Наверх"
    if current_path:
        parent = "/".join(current_path.split("/")[:-1])
        builder.row(InlineKeyboardButton(text="⬅️ Наверх", callback_data=f"f_nav:{owner}:{repo}:{parent}"))
    else:
        builder.row(InlineKeyboardButton(text="🔙 К проекту", callback_data=f"view:{owner}:{repo}"))
        
    return builder.as_markup()

def file_view_kb(owner, repo, path, web_url):
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить", callback_data=f"f_edit:{owner}:{repo}:{path}")
    builder.button(text="🔗 Web Editor (GitHub-like)", url=web_url) # Наша ссылка
    # Back button to folder
    parent = "/".join(path.split("/")[:-1])
    builder.button(text="🔙 Назад", callback_data=f"f_nav:{owner}:{repo}:{parent}")
    builder.adjust(1)
    return builder.as_markup()

def file_edit_action_kb(owner, repo, path):
    builder = InlineKeyboardBuilder()
    builder.button(text="💾 Сохранить", callback_data=f"f_save:{owner}:{repo}:{path}")
    builder.button(text="🔙 Отменить изменения", callback_data=f"f_view:{owner}:{repo}:{path}")
    builder.adjust(1)
    return builder.as_markup()

def web_edit_confirm_kb(uuid):
    builder = InlineKeyboardBuilder()
    builder.button(text="💾 Применить (Commit)", callback_data=f"w_save:{uuid}")
    builder.button(text="❌ Сбросить", callback_data=f"w_discard:{uuid}")
    builder.adjust(1)
    return builder.as_markup()

# ...(Остальные функции repo_list_pagination и т.д. нужны!)...
# Вставь repo_list_pagination, settings_menu и прочие
def settings_menu(ignore_own: bool):
    status = "✅ ВКЛ (Игнорю)" if ignore_own else "❌ ВЫКЛ (Вижу всё)"
    builder = InlineKeyboardBuilder()
    builder.button(text="🖥 Подключить сервер (SSH)", callback_data="setup_server")
    builder.button(text="🔑 Сменить GitHub Токен", callback_data="set_token")
    builder.button(text=f"Свои пуши: {status}", callback_data="toggle_ignore")
    builder.button(text="🔙 Назад", callback_data="start")
    builder.adjust(1)
    return builder.as_markup()

def repo_list_pagination(repos, page, has_next, filter_mode):
    builder = InlineKeyboardBuilder()
    for repo in repos:
        name = repo['name']
        owner = repo['owner']['login']
        display_name = (name[:12] + '..') if len(name) > 12 else name
        builder.button(text=f"📦 {display_name}", callback_data=f"view:{owner}:{name}")
    builder.adjust(2)
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"repos:{page-1}"))
    filter_text = "🕵️ Только мои" if filter_mode == 'all' else "🌐 Все доступные"
    nav_buttons.append(InlineKeyboardButton(text=filter_text, callback_data="toggle_repo_filter"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"repos:{page+1}"))
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="✨ Создать новый проект", callback_data="create_repo_start"))
    builder.row(InlineKeyboardButton(text="🔙 В меню", callback_data="start"))
    return builder.as_markup()

def repo_management_kb(owner, repo_name):
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить имя", callback_data=f"ren_repo:{owner}:{repo_name}")
    builder.button(text="📝 Изменить описание", callback_data=f"desc_repo:{owner}:{repo_name}")
    builder.button(text="🗑 Удалить проект", callback_data=f"del_confirm:{owner}:{repo_name}")
    builder.button(text="🔙 Назад", callback_data=f"view:{owner}:{repo_name}")
    builder.adjust(1)
    return builder.as_markup()

def repo_delete_confirm_kb(owner, repo_name):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ДА, УДАЛИТЬ", callback_data=f"del_do:{owner}:{repo_name}")
    builder.button(text="❌ Нет, отмена", callback_data=f"manage:{owner}:{repo_name}")
    builder.adjust(1)
    return builder.as_markup()

def create_visibility_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔒 Private", callback_data="cr_vis:private")
    builder.button(text="🌍 Public", callback_data="cr_vis:public")
    builder.button(text="❌ Отмена", callback_data="start")
    builder.adjust(2)
    return builder.as_markup()

def create_gitignore_kb():
    builder = InlineKeyboardBuilder()
    langs = [("Python", "Python"), ("Node", "Node"), ("Go", "Go"), ("C++", "C++")]
    for label, val in langs:
        builder.button(text=label, callback_data=f"cr_git:{val}")
    builder.button(text="🚫 Не создавать", callback_data="cr_git:None")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="start"))
    return builder.as_markup()

def create_upload_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Пропустить (Пустой)", callback_data="cr_skip_zip")
    builder.button(text="❌ Отмена", callback_data="start")
    builder.adjust(1)
    return builder.as_markup()

def push_notification_kb(compare_url):
    builder = InlineKeyboardBuilder()
    builder.button(text="👀 Посмотреть изменения", url=compare_url)
    return builder.as_markup()

def ssh_error_kb(allow_change_path: bool):
    builder = InlineKeyboardBuilder()
    if allow_change_path:
        builder.button(text="📝 Изменить путь", callback_data="push_method:ssh")