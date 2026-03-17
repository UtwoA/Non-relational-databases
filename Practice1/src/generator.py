import random
from datetime import date, timedelta

from src.models import Publication, Review, User

FIRST_NAMES = [
    "Ivan",
    "Anna",
    "Olga",
    "Pavel",
    "Maria",
    "Nikita",
    "Daria",
    "Sergey",
    "Alexey",
    "Elena",
]
LAST_NAMES = [
    "Ivanov",
    "Petrova",
    "Sidorov",
    "Smirnova",
    "Kuznetsov",
    "Volkova",
    "Morozov",
    "Sokolova",
]
CATEGORIES = ["Science", "Technology", "Art", "History", "Education", "Business"]
GENDERS = ["male", "female", "other"]


def random_date(start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=random.randint(0, span))


def multiline_text(lines: int, prefix: str) -> str:
    return "\n".join(f"{prefix} line {i + 1}" for i in range(lines))


def generate_user(user_id: int, max_user_id: int) -> User:
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    username = f"{first_name.lower()}_{last_name.lower()}_{user_id}"

    email_count = random.randint(1, 3)
    emails = [f"{username}+{i}@example.com" for i in range(1, email_count + 1)]

    registration_date = random_date(date(2018, 1, 1), date(2025, 12, 31))
    last_authorization_date = random_date(registration_date, date(2026, 2, 1))

    publications: list[Publication] = []
    publication_count = random.randint(1, 4)
    for publication_index in range(publication_count):
        publication_date = random_date(registration_date, date(2026, 1, 31))

        reviews: list[Review] = []
        review_count = random.randint(0, 4)
        for review_index in range(review_count):
            reviews.append(
                Review(
                    user_id=random.randint(1, max_user_id),
                    text=multiline_text(
                        random.randint(2, 4),
                        f"Review {review_index + 1} for post {publication_index + 1}",
                    ),
                )
            )

        publications.append(
            Publication(
                title=f"Publication {publication_index + 1} of {username}",
                description=multiline_text(
                    random.randint(2, 5), f"Description {publication_index + 1}"
                ),
                pages=random.randint(10, 900),
                category=random.choice(CATEGORIES),
                publication_date=publication_date.isoformat(),
                reviews=reviews,
            )
        )

    birth_date = random_date(date(1970, 1, 1), date(2007, 12, 31))

    return User(
        user_id=user_id,
        username=username,
        emails=emails,
        registration_date=registration_date.isoformat(),
        last_authorization_date=last_authorization_date.isoformat(),
        is_confirmed=random.random() > 0.3,
        publications=publications,
        birth_date=birth_date.isoformat(),
        gender=random.choice(GENDERS),
    )


def generate_users(total: int) -> list[User]:
    return [generate_user(i, total) for i in range(1, total + 1)]
