import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv

load_dotenv()

# Используем BOT_TOKEN как базу для ключа шифрования
# В идеале это должна быть отдельная секретная переменная в .env
SECRET_KEY = os.getenv("BOT_TOKEN", "default-secret-key").encode()

def _get_fernet():
    salt = b'static_salt_for_bot' # В проде соль должна быть случайной, но для простоты так
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY))
    return Fernet(key)

def encrypt(data: str) -> str:
    if not data: return None
    f = _get_fernet()
    return f.encrypt(data.encode()).decode()

def decrypt(token: str) -> str:
    if not token: return None
    f = _get_fernet()
    return f.decrypt(token.encode()).decode()