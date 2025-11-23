import aiohttp
import os
import tempfile
import hmac
import hashlib
import logging

GITHUB_API = "https://api.github.com"

class GitHubClient:
    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }

    async def get_user_info(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GITHUB_API}/user", headers=self.headers) as resp:
                if resp.status != 200: return None
                return await resp.json()

    async def get_repos(self, page: int = 1, per_page: int = 5, filter_mode: str = 'all'):
        """
        Получаем список репозиториев с пагинацией и фильтрацией.
        filter_mode: 'owner' (только мои) или 'all' (все доступные)
        """
        affiliation = "owner" if filter_mode == 'owner' else "owner,collaborator,organization_member"
        
        url = f"{GITHUB_API}/user/repos?sort=updated&per_page={per_page}&page={page}&affiliation={affiliation}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200: return None, False
                
                data = await resp.json()
                has_next = len(data) == per_page
                return data, has_next

    async def get_repo_details(self, owner: str, repo: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=self.headers) as resp:
                if resp.status != 200: return None
                return await resp.json()

    async def download_repo(self, owner: str, repo: str):
        url = f"{GITHUB_API}/repos/{owner}/{repo}/zipball"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200: return None
                fd, path = tempfile.mkstemp(suffix=".zip", prefix=f"{repo}_")
                os.close(fd)
                with open(path, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024):
                        f.write(chunk)
                return path

    async def create_webhook(self, owner: str, repo: str, webhook_url: str, secret: str):
        api_url = f"{GITHUB_API}/repos/{owner}/{repo}/hooks"
        payload = {
            "name": "web",
            "active": True,
            "events": ["push"],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=self.headers) as resp:
                if resp.status == 201: return True, "Created"
                resp_data = await resp.json()
                if resp.status == 422:
                    for err in resp_data.get('errors', []):
                        if "Hook already exists" in err.get('message', ''):
                            return True, "Already Exists"
                return False, resp_data.get('message', 'Unknown Error')

def verify_signature(payload_body, secret_token, signature_header):
    if not signature_header: return False
    sha_name, signature = signature_header.split('=')
    if sha_name != 'sha256': return False
    mac = hmac.new(secret_token.encode(), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)