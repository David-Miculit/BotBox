import hashlib

def hash_password(password):
    hashed_password = hashlib.sha256(password.encode())
    hashed_password = hashed_password.hexdigest()
    return hashed_password