import os
import aiohttp
from aiohttp import web
import database
from github_client import GitHubClient

# HTML Template with Monaco Editor
EDITOR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Bot Web Editor</title>
    <style>
        body { margin: 0; padding: 0; background-color: #1e1e1e; color: #d4d4d4; font-family: sans-serif; }
        #header { height: 50px; display: flex; align-items: center; padding: 0 20px; background: #252526; border-bottom: 1px solid #333; }
        #filename { font-weight: bold; margin-right: auto; }
        #container { width: 100%; height: calc(100vh - 50px); }
        button { padding: 8px 16px; background: #0e639c; color: white; border: none; cursor: pointer; border-radius: 2px; }
        button:hover { background: #1177bb; }
    </style>
</head>
<body>
    <div id="header">
        <span id="filename">{{FILENAME}}</span>
        <button onclick="saveContent()">💾 Save & Close</button>
    </div>
    <div id="container"></div>

    <!-- Monaco Editor CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs/loader.min.js"></script>
    <script>
        require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});
        
        let editor;
        const uuid = "{{UUID}}";

        require(['vs/editor/editor.main'], function() {
            editor = monaco.editor.create(document.getElementById('container'), {
                value: `{{CONTENT}}`,
                language: '{{LANG}}',
                theme: 'vs-dark',
                automaticLayout: true
            });
        });

        async function saveContent() {
            const content = editor.getValue();
            try {
                const resp = await fetch(`/editor/${uuid}/save`, {
                    method: 'POST',
                    body: content
                });
                if (resp.ok) {
                    document.body.innerHTML = "<h2 style='text-align:center; margin-top:50px; color: #4ec9b0'>Saved! Return to Telegram Bot.</h2>";
                    // Optional: Close window
                    // window.close(); 
                } else {
                    alert("Error saving!");
                }
            } catch (e) {
                alert("Network error: " + e);
            }
        }
    </script>
</body>
</html>
"""

async def editor_handler(request):
    uuid = request.match_info['uuid']
    session = await database.get_editor_session(uuid)
    
    if not session:
        return web.Response(text="Link expired or invalid.", status=404)
    
    # Загружаем контент из GitHub, если еще нет pending_content
    # Или берем свежий? Лучше брать текущий с GitHub для старта
    user = await database.get_user(session['user_id'])
    client = GitHubClient(user['github_token'])
    
    # Получаем контент
    file_data = await client.get_contents(session['owner'], session['repo'], session['path'])
    if not file_data or 'content' not in file_data:
        return web.Response(text="Failed to fetch file from GitHub", status=500)
    
    import base64
    content = base64.b64decode(file_data['content']).decode('utf-8')
    
    # Определяем язык для подсветки
    ext = session['path'].split('.')[-1]
    lang_map = {'py': 'python', 'js': 'javascript', 'html': 'html', 'css': 'css', 'json': 'json', 'md': 'markdown'}
    lang = lang_map.get(ext, 'plaintext')
    
    # Рендерим шаблон
    # Экранируем контент для JS строки (просто, но нужно быть аккуратным с backticks)
    safe_content = content.replace("`", "\\`").replace("${", "\\${")
    
    html = EDITOR_TEMPLATE.replace("{{UUID}}", uuid)\
                          .replace("{{FILENAME}}", session['path'])\
                          .replace("{{CONTENT}}", safe_content)\
                          .replace("{{LANG}}", lang)
    
    return web.Response(text=html, content_type='text/html')

async def editor_save_handler(request):
    uuid = request.match_info['uuid']
    content = await request.text()
    
    # Сохраняем во временное хранилище
    await database.update_editor_content(uuid, content)
    
    # Тут можно было бы триггернуть бота отправить сообщение юзеру, 
    # но aiohttp работает отдельно.
    # Юзер сам нажмет кнопку в боте (или мы отправим сообщение, если бот инстанс глобален)
    
    # Вариант: Просто сохраняем в БД. Бот должен быть уведомлен?
    # В рамках этой архитектуры проще всего, если бот сам увидит изменение,
    # но мы обещали "бот в лс юзеру скажет".
    # Для этого нам нужен доступ к объекту `bot` из main.py. 
    # Пока вернем 200 OK, а в handlers/files.py сделаем механизм проверки.
    # ЛИБО: Импортируем bot из main (циклический импорт!).
    # Решение: В main.py передадим bot в app.
    
    bot = request.app['bot']
    session = await database.get_editor_session(uuid)
    if session:
        import keyboards
        await bot.send_message(
            chat_id=session['user_id'],
            text=f"✍️ <b>Web Editor:</b> Получены изменения для <code>{session['path']}</code>.\nСохранить в репозиторий?",
            parse_mode="HTML",
            reply_markup=keyboards.web_edit_confirm_kb(uuid)
        )

    return web.Response(text="OK")