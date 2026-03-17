from src.models import User


def filter_confirmed_users(users: list[User]) -> list[User]:
    return [user for user in users if user.is_confirmed]
