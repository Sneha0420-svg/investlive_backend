from passlib.hash import argon2

# Hash password
def hash_password(password: str) -> str:
    return argon2.hash(password)

# Verify password
def verify_password(password: str, hashed: str) -> bool:
    return argon2.verify(password, hashed)