import csv
from pathlib import Path

from src.models import Publication, Review, User


EMAIL_SEPARATOR = "|"


def save_users_to_dsv(
    users: list[User],
    users_path: Path,
    publications_path: Path,
    reviews_path: Path,
) -> None:
    users_path.parent.mkdir(parents=True, exist_ok=True)

    with users_path.open("w", newline="", encoding="utf-8") as users_handle, \
        publications_path.open("w", newline="", encoding="utf-8") as publications_handle, \
        reviews_path.open("w", newline="", encoding="utf-8") as reviews_handle:

        users_writer = csv.DictWriter(
            users_handle,
            delimiter="\t",
            fieldnames=[
                "user_id",
                "username",
                "emails",
                "registration_date",
                "last_authorization_date",
                "is_confirmed",
                "birth_date",
                "gender",
            ],
        )
        publications_writer = csv.DictWriter(
            publications_handle,
            delimiter="\t",
            fieldnames=[
                "publication_id",
                "user_id",
                "title",
                "description",
                "pages",
                "category",
                "publication_date",
            ],
        )
        reviews_writer = csv.DictWriter(
            reviews_handle,
            delimiter="\t",
            fieldnames=["review_id", "publication_id", "user_id", "text"],
        )

        users_writer.writeheader()
        publications_writer.writeheader()
        reviews_writer.writeheader()

        publication_id = 1
        review_id = 1

        for user in users:
            users_writer.writerow(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "emails": EMAIL_SEPARATOR.join(user.emails),
                    "registration_date": user.registration_date,
                    "last_authorization_date": user.last_authorization_date,
                    "is_confirmed": str(user.is_confirmed),
                    "birth_date": user.birth_date,
                    "gender": user.gender,
                }
            )

            for publication in user.publications:
                current_publication_id = publication_id
                publications_writer.writerow(
                    {
                        "publication_id": current_publication_id,
                        "user_id": user.user_id,
                        "title": publication.title,
                        "description": publication.description,
                        "pages": publication.pages,
                        "category": publication.category,
                        "publication_date": publication.publication_date,
                    }
                )

                for review in publication.reviews:
                    reviews_writer.writerow(
                        {
                            "review_id": review_id,
                            "publication_id": current_publication_id,
                            "user_id": review.user_id,
                            "text": review.text,
                        }
                    )
                    review_id += 1

                publication_id += 1


def read_users_from_dsv(
    users_path: Path,
    publications_path: Path,
    reviews_path: Path,
) -> list[User]:
    users: list[User] = []

    reviews_by_publication: dict[int, list[Review]] = {}
    with reviews_path.open("r", newline="", encoding="utf-8") as reviews_handle:
        reviews_reader = csv.DictReader(reviews_handle, delimiter="\t")
        for row in reviews_reader:
            publication_id = int(row["publication_id"])
            review = Review(user_id=int(row["user_id"]), text=row["text"])
            reviews_by_publication.setdefault(publication_id, []).append(review)

    publications_by_user: dict[int, list[Publication]] = {}
    with publications_path.open("r", newline="", encoding="utf-8") as publications_handle:
        publications_reader = csv.DictReader(publications_handle, delimiter="\t")
        for row in publications_reader:
            publication_id = int(row["publication_id"])
            user_id = int(row["user_id"])
            publication = Publication(
                title=row["title"],
                description=row["description"],
                pages=int(row["pages"]),
                category=row["category"],
                publication_date=row["publication_date"],
                reviews=reviews_by_publication.get(publication_id, []),
            )
            publications_by_user.setdefault(user_id, []).append(publication)

    with users_path.open("r", newline="", encoding="utf-8") as users_handle:
        users_reader = csv.DictReader(users_handle, delimiter="\t")
        for row in users_reader:
            user_id = int(row["user_id"])
            emails = row["emails"].split(EMAIL_SEPARATOR) if row["emails"] else []
            users.append(
                User(
                    user_id=user_id,
                    username=row["username"],
                    emails=emails,
                    registration_date=row["registration_date"],
                    last_authorization_date=row["last_authorization_date"],
                    is_confirmed=row["is_confirmed"].strip().lower() == "true",
                    publications=publications_by_user.get(user_id, []),
                    birth_date=row["birth_date"],
                    gender=row["gender"],
                )
            )

    return users
