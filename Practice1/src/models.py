from dataclasses import dataclass


@dataclass
class Review:
    user_id: int
    text: str


@dataclass
class Publication:
    title: str
    description: str
    pages: int
    category: str
    publication_date: str
    reviews: list[Review]


@dataclass
class User:
    user_id: int
    username: str
    emails: list[str]
    registration_date: str
    last_authorization_date: str
    is_confirmed: bool
    publications: list[Publication]
    birth_date: str
    gender: str
