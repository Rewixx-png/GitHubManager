import asyncio
import logging
import os
import sys
import html
import ssl
from aiohttp import web
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

import database
import keyboards
from handlers import router 
from github_client import verify_signature
from web_editor import editor_handler, editor_save_handler

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8080))
# WEBHOOK_HOST теперь используется как fallback, если нет BASE_URL
WEBHOOK_HOST = "0.0.0.0" 

# SSL Config
SSL_CERT = os.getenv("SSL_CERT")
SSL_KEY = os.getenv("SSL_KEY")

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def github_webhook_handle(request):
    try:
        signature = request.headers.get('X-Hub-Signature-256')
        body = await request.read()
        
        if WEBHOOK_SECRET and not verify_signature(body, WEBHOOK_SECRET, signature):
             return web.Response(status=403, text="Invalid Signature")

        data = await request.json()
        event_type = request.headers.get('X-GitHub-Event')
        
        if event_type == 'push':
            repo_full_name = data['repository']['full_name']
            pusher_name = data['pusher']['name']
            commits = data['commits']
            compare_url = data.get('compare', data['repository']['html_url'])
            
            subscriber_ids = await database.get_subscribers(repo_full_name)
            
            if subscriber_ids:
                msg_text = (
                    f"🚀 <b>{html.escape(repo_full_name)}</b>\n"
                    f"👤 <code>{html.escape(pusher_name)}</code>\n\n"
                )
                
                for c in commits[:5]:
                    commit_msg = html.escape(c['message'].splitlines()[0])
                    msg_text += f"▪️ {commit_msg}\n"
                
                if len(commits) > 5: 
                    msg_text += f"<i>+ {len(commits)-5} more...</i>"

                kb = keyboards.push_notification_kb(compare_url)

                for user_id in subscriber_ids:
                    user = await database.get_user(user_id)
                    if not user: continue
                    if user['ignore_own_pushes'] and user['github_username'] == pusher_name:
                        continue
                    try:
                        await bot.send_message(
                            chat_id=user_id, 
                            text=msg_text, 
                            parse_mode="HTML",
                            reply_markup=kb,
                            disable_web_page_preview=True
                        )
                    except Exception as e:
                        logging.error(f"Failed to send to {user_id}: {e}")

        return web.Response(text="OK")
    except Exception as e:
        logging.error(f"Webhook fatal: {e}")
        return web.Response(status=500)

async def start_webhook_server():
    app = web.Application()
    app['bot'] = bot
    
    app.router.add_post('/github-webhook', github_webhook_handle)
    app.router.add_get('/editor/{uuid}', editor_handler)
    app.router.add_post('/editor/{uuid}/save', editor_save_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # --- SSL CONFIGURATION ---
    ssl_context = None
    if SSL_CERT and SSL_KEY:
        if os.path.exists(SSL_CERT) and os.path.exists(SSL_KEY):
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(SSL_CERT, SSL_KEY)
            logging.info("🔒 SSL enabled")
        else:
            logging.error("❌ SSL paths provided but files not found!")
    
    site = web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT, ssl_context=ssl_context)
    await site.start()
    logging.info(f"🕸 Web Server running on port {WEBHOOK_PORT}")

async def main():
    await database.init_db()
    dp.include_router(router)
    await start_webhook_server()
    
    logging.info("🤖 Bot Polling Started")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass