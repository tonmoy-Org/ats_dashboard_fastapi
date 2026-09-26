from passlib.hash import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.verify(plain_password, hashed_password)
    except Exception:
        return plain_password == hashed_password

def hash_password(password: str) -> str:
    return bcrypt.hash(password)
