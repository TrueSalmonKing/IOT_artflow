import json
import hashlib
from flask_login import UserMixin


def load_credentials():
    with open('credentials.json') as f:
        return json.load(f)

credentials = load_credentials()
users = credentials.get("users", {})

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

class User(UserMixin):
    def __init__(self, username):
        self.id = username

def get_user(username):
    if username in users:
        return User(username)
    return None

def check_password(username, password):
    hashed_pass = hash_password(password)
    user = users.get(username)
    if user and user['password'] == hashed_pass:
        return True
    return False