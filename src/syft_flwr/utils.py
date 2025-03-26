import hashlib


def string_to_hash_int(input_string: str) -> int:
    """Convert a string to a hash integer."""
    hash_object = hashlib.sha256(input_string.encode("utf-8"))
    hash_hex = hash_object.hexdigest()
    hash_int = int(hash_hex, 16) % (2**32)
    return hash_int
