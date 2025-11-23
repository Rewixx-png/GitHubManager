import os
import aiohttp
from aiohttp import web
import database
from github_client import GitHubClient

# HTML Template with GitHub-like Dark Theme & AGGRESSIVE ZOOM BLOCK
EDITOR_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Editing {{FILENAME}}</title>
    <style>
        :root {
            --bg-canvas: #0d1117;
            --bg-header: #161b22;
            --border-color: #30363d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --btn-green: #238636;
            --btn-green-hover: #2ea043;
            --accent-blue: #58a6ff;
        }

        body {
            margin: 0;
            padding: 0;
            background-color: var(--bg-canvas);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden; 
            touch-action: pan-x pan-y; /* Отключаем жесты зума в CSS */
        }

        /* HEADER */
        header {
            background-color: var(--bg-header);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }

        .breadcrumbs {
            font-size: 14px;
            color: var(--text-primary);
            display: flex;
            gap: 8px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .breadcrumbs a {
            color: var(--accent-blue);
            text-decoration: none;
        }
        
        .breadcrumbs a:hover {
            text-decoration: underline;
        }

        .breadcrumbs span.path {
            color: var(--text-secondary);
        }
        
        .breadcrumbs span.file {
            font-weight: 600;
        }

        /* MAIN CONTAINER */
        main {
            flex: 1;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
            box-sizing: border-box;
            overflow: hidden;
        }

        .editor-wrapper {
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background-color: #0d1117;
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            min-height: 0;
        }

        .editor-header {
            background-color: var(--bg-header);
            border-bottom: 1px solid var(--border-color);
            padding: 8px 16px;
            font-size: 13px;
            color: var(--text-secondary);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }

        #monaco-container {
            flex: 1;
            width: 100%;
            height: 100%;
        }

        /* FOOTER ACTIONS */
        .actions {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-top: 10px;
            flex-shrink: 0;
        }

        button {
            padding: 5px 16px;
            font-size: 14px;
            font-weight: 500;
            border-radius: 6px;
            cursor: pointer;
            border: 1px solid rgba(240, 246, 252, 0.1);
            line-height: 20px;
            transition: 0.2s;
        }

        .btn-primary {
            background-color: var(--btn-green);
            color: white;
            border-color: rgba(240, 246, 252, 0.1);
        }

        .btn-primary:hover {
            background-color: var(--btn-green-hover);
        }

        .btn-secondary {
            background-color: #21262d;
            color: var(--text-primary);
        }

        .btn-secondary:hover {
            background-color: #30363d;
        }

        /* LOADER */
        #status-msg {
            margin-right: 15px;
            font-size: 14px;
            opacity: 0;
            transition: opacity 0.3s;
        }
        
    </style>
</head>
<body>

    <header>
        <div class="breadcrumbs">
            <span>{{OWNER}}</span>
            <span>/</span>
            <strong>{{REPO}}</strong>
            <span>/</span>
            <span class="path">{{DIR_PATH}}</span>
            <span class="file">{{FILENAME_ONLY}}</span>
        </div>
        <div>
            <span style="font-size: 12px; color: #8b949e; margin-right: 10px;">Bot Editor</span>
        </div>
    </header>

    <main>
        <div class="editor-wrapper">
            <div class="editor-header">
                <span>Editing <strong>{{FILENAME}}</strong></span>
            </div>
            <div id="monaco-container"></div>
        </div>

        <div class="actions">
            <span id="status-msg">Saving...</span>
            <button class="btn-primary" onclick="saveContent()">Commit Changes via Bot</button>
        </div>
    </main>

    <!-- Monaco Editor CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs/loader.min.js"></script>
    <script>
        // --- ANTI-ZOOM HACKS ---
        
        // 1. Блокируем жест 'pinch' (два пальца) на уровне документа
        document.addEventListener('touchmove', function(event) {
            if (event.scale !== 1) { 
                event.preventDefault(); 
            }
        }, { passive: false });

        // 2. Блокируем жесты Safari (gesturestart/change/end)
        document.addEventListener('gesturestart', function(e) {
            e.preventDefault();
        });

        // 3. Блокируем двойной тап (часто вызывает зум)
        let lastTouchEnd = 0;
        document.addEventListener('touchend', function (event) {
            const now = (new Date()).getTime();
            if (now - lastTouchEnd <= 300) {
                event.preventDefault();
            }
            lastTouchEnd = now;
        }, false);
        
        // --- END HACKS ---

        require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});
        
        let editor;
        const uuid = "{{UUID}}";

        require(['vs/editor/editor.main'], function() {
            monaco.editor.defineTheme('github-dark', {
                base: 'vs-dark',
                inherit: true,
                rules: [
                    { token: '', background: '0d1117' } // Match container BG
                ],
                colors: {
                    'editor.background': '#0d1117',
                    'editor.lineHighlightBackground': '#161b22',
                    'editorLineNumber.foreground': '#8b949e',
                    'editor.foreground': '#c9d1d9'
                }
            });

            editor = monaco.editor.create(document.getElementById('monaco-container'), {
                value: `{{CONTENT}}`,
                language: '{{LANG}}',
                theme: 'github-dark',
                automaticLayout: true,
                fontSize: 14,
                fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace',
                minimap: { enabled: true },
                padding: { top: 16, bottom: 16 },
                scrollBeyondLastLine: false,
                renderWhitespace: "selection"
            });
        });

        async function saveContent() {
            const btn = document.querySelector('.btn-primary');
            const status = document.getElementById('status-msg');
            
            btn.disabled = true;
            btn.innerText = "Processing...";
            status.style.opacity = 1;
            status.innerText = "Sending to Bot...";
            status.style.color = "#8b949e";

            const content = editor.getValue();
            try {
                const resp = await fetch(`/editor/${uuid}/save`, {
                    method: 'POST',
                    body: content
                });
                
                if (resp.ok) {
                    status.innerText = "✅ Sent to Telegram!";
                    status.style.color = "#2ea043";
                    btn.innerText = "Check your Bot";
                } else {
                    status.innerText = "❌ Error saving";
                    status.style.color = "#f85149";
                    btn.disabled = false;
                    btn.innerText = "Commit Changes via Bot";
                }
            } catch (e) {
                status.innerText = "❌ Network Error";
                status.style.color = "#f85149";
                btn.disabled = false;
                btn.innerText = "Try Again";
            }
        }
        
        // Ctrl+S to save
        document.addEventListener('keydown', e => {
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                saveContent();
            }
        });
    </script>
</body>
</html>
"""

async def editor_handler(request):
    uuid = request.match_info['uuid']
    session = await database.get_editor_session(uuid)
    
    if not session:
        return web.Response(text="Link expired or invalid.", status=404)
    
    user = await database.get_user(session['user_id'])
    client = GitHubClient(user['github_token'])
    
    # Получаем контент
    file_data = await client.get_contents(session['owner'], session['repo'], session['path'])
    if not file_data or 'content' not in file_data:
        return web.Response(text="Failed to fetch file from GitHub", status=500)
    
    import base64
    content = base64.b64decode(file_data['content']).decode('utf-8')
    
    # Lang detection
    ext = session['path'].split('.')[-1]
    lang_map = {
        'py': 'python', 'js': 'javascript', 'ts': 'typescript', 
        'html': 'html', 'css': 'css', 'json': 'json', 'md': 'markdown',
        'yml': 'yaml', 'yaml': 'yaml', 'sh': 'shell', 'go': 'go'
    }
    lang = lang_map.get(ext, 'plaintext')
    
    # Path processing for breadcrumbs
    full_path = session['path']
    filename_only = full_path.split('/')[-1]
    dir_path = "/".join(full_path.split('/')[:-1]) + "/" if "/" in full_path else ""

    # Escaping logic
    safe_content = content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    
    html = EDITOR_TEMPLATE.replace("{{UUID}}", uuid)\
                          .replace("{{OWNER}}", session['owner'])\
                          .replace("{{REPO}}", session['repo'])\
                          .replace("{{FILENAME}}", full_path)\
                          .replace("{{FILENAME_ONLY}}", filename_only)\
                          .replace("{{DIR_PATH}}", dir_path)\
                          .replace("{{CONTENT}}", safe_content)\
                          .replace("{{LANG}}", lang)
    
    return web.Response(text=html, content_type='text/html')

async def editor_save_handler(request):
    uuid = request.match_info['uuid']
    content = await request.text()
    
    await database.update_editor_content(uuid, content)
    
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