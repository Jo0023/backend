import re


def validate_telegram_username(username: str | None) -> str | None:
    """Валидация Telegram username"""
    if username is None or username.strip() == "":
        return None

    username = username.strip()

    if not username.startswith('@'):
        raise ValueError("Telegram username должен начинаться с @")

    if len(username) < 6 or len(username) > 33:  # @ + 5-32 символов
        raise ValueError("Telegram username должен содержать от 5 до 32 символов после @")

    # Проверка символов
    username_part = username[1:]  # Без @
    if not re.match(r'^\w{5,32}$', username_part):
        raise ValueError("Telegram username может содержать только буквы, цифры и подчеркивания")

    return username