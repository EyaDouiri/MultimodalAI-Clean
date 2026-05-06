import jwt
import hashlib
from datetime import datetime, timedelta
from django.conf import settings

SECRET = getattr(settings, 'SECRET_KEY', 'dev')


def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def check_password(raw: str, hashed: str) -> bool:
    return hash_password(raw) == hashed


def make_token(user_id: int, role: str) -> str:
    payload = {
        'user_id': user_id,
        'role':    role,
        'exp':     datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET, algorithm='HS256')


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=['HS256'])


def get_user_from_request(request):
    """Retourne (user_id, role) depuis le header Authorization: Bearer <token>"""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, None
    try:
        payload = decode_token(auth.split(' ', 1)[1])
        return payload['user_id'], payload['role']
    except Exception:
        return None, None
