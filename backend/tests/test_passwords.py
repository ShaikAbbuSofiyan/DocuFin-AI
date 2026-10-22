import pytest
from app.core.security import hash_password, verify_password


def test_argon2_password_hashing():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    # Argon2 hashes start with $argon2
    assert hashed.startswith("$argon2")
    assert hashed != password

    # Verification with correct password
    assert verify_password(password, hashed) is True

    # Verification with incorrect password
    assert verify_password("WrongPassword123!", hashed) is False

    # Verification with empty or tampered hash
    assert verify_password(password, "invalid_hash") is False
    assert verify_password(password, "") is False


def test_unique_salts():
    password = "SamePassword123!"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    # Each hash must produce a distinct salt and string
    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True
