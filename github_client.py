import aiohttp
import os
import tempfile
import hmac
import hashlib
import logging
import time
import base64

GITHUB_API = "https://api.github.com"

# In-Memory Cache storage
_cache = {}
CACHE_TTL = 300  # 5 минут

class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }

    # ... (старые методы кеширования _get_cache_key, _get_from_cache, _save_to_cache оставляем) ...
    def _get_cache_key(self, endpoint: str, params: str = ""):
        raw = f"{self.token}:{endpoint}:{params}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_from_cache(self, key: str):
        if key in _cache:
            entry = _cache[key]
            if time.time() < entry['expires_at']:
                return entry['data']
            else:
                del _cache[key]
        return None

    def _save_to_cache(self, key: str, data: any):
        _cache[key] = {
            'data': data,
            'expires_at': time.time() + CACHE_TTL
        }
    
    def _invalidate_cache(self):
        global _cache
        _cache = {} 

    # ... (Остальные методы get_user_info, get_repos, get_repo_details, create_repo и т.д. ОСТАВЛЯЕМ) ...
    # Вставь их сюда, если копипастишь. Я добавлю только НОВЫЕ методы для файлов.

    async def get_user_info(self):
        cache_key = self._get_cache_key("user")
        cached = self._get_from_cache(cache_key)
        if cached: return cached

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GITHUB_API}/user", headers=self.headers) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                self._save_to_cache(cache_key, data)
                return data
    
    # Чтобы не дублировать тонну кода, я подразумеваю наличие create_repo, update_repo, delete_repo и т.д.
    # Реализуем только новые для файлов:

    async def get_contents(self, owner: str, repo: str, path: str = ""):
        """Получение списка файлов или содержимого конкретного файла"""
        url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()

    async def update_file(self, owner: str, repo: str, path: str, message: str, content: str, sha: str):
        """Коммит изменения файла"""
        url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        
        # GitHub API требует base64 encoded content
        encoded_content = base64.b64encode(content.encode()).decode()
        
        payload = {
            "message": message,
            "content": encoded_content,
            "sha": sha
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=payload, headers=self.headers) as resp:
                if resp.status in [200, 201]:
                    self._invalidate_cache()
                    return True, await resp.json()
                err = await resp.json()
                return False, err.get('message', 'Unknown Error')

    # ВАЖНО: Функции create_webhook и verify_signature тоже должны быть тут.
    # Если ты копируешь весь файл, возьми их из предыдущего ответа.

    async def get_repos(self, page: int = 1, per_page: int = 5, filter_mode: str = 'all'):
        # (Код из прошлого ответа)
        affiliation = "owner" if filter_mode == 'owner' else "owner,collaborator,organization_member"
        params_key = f"page={page}&per_page={per_page}&filter={filter_mode}"
        cache_key = self._get_cache_key("repos", params_key)
        
        cached = self._get_from_cache(cache_key)
        if cached: return cached[0], cached[1]
        
        url = f"{GITHUB_API}/user/repos?sort=updated&per_page={per_page}&page={page}&affiliation={affiliation}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200: return None, False
                data = await resp.json()
                has_next = len(data) == per_page
                self._save_to_cache(cache_key, (data, has_next))
                return data, has_next
    
    async def get_repo_details(self, owner: str, repo: str):
         # (Код из прошлого ответа)
        cache_key = self._get_cache_key(f"repos/{owner}/{repo}")
        cached = self._get_from_cache(cache_key)
        if cached: return cached

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=self.headers) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                self._save_to_cache(cache_key, data)
                return data

def verify_signature(payload_body, secret_token, signature_header):
    if not signature_header: return False
    sha_name, signature = signature_header.split('=')
    if sha_name != 'sha256': return False
    mac = hmac.new(secret_token.encode(), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)