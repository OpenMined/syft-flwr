import re
import zlib

EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"


def is_valid_datasite(datasite: str) -> bool:
    return re.match(EMAIL_REGEX, datasite)


def str_to_int(input_string: str) -> int:
    """Convert a string to an int32"""
    return zlib.crc32(input_string.encode())
