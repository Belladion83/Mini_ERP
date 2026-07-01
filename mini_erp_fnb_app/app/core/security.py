import hashlib
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, password_hash: str) -> bool:
    # Production hashes should be bcrypt.
    # The seed admin user uses a sha256$ bootstrap hash so the demo can run consistently.
    if password_hash.startswith("sha256$"):
        expected = password_hash.split("$", 1)[1]
        return hashlib.sha256(plain_password.encode("utf-8")).hexdigest() == expected
    return pwd_context.verify(plain_password, password_hash)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
