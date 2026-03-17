import random

from src.config import (
    PUBLICATIONS_DSV_PATH,
    RANDOM_SEED,
    RECORD_COUNT,
    REVIEWS_DSV_PATH,
    USERS_DSV_PATH,
)
from src.dsv_io import save_users_to_dsv
from src.generator import generate_users


def main() -> None:
    random.seed(RANDOM_SEED)
    users = generate_users(RECORD_COUNT)
    save_users_to_dsv(users, USERS_DSV_PATH, PUBLICATIONS_DSV_PATH, REVIEWS_DSV_PATH)

    print("STEP 1: DATA GENERATION + DSV SAVE")
    print(f"Generated users: {len(users)}")
    print(f"Users DSV: {USERS_DSV_PATH}")
    print(f"Publications DSV: {PUBLICATIONS_DSV_PATH}")
    print(f"Reviews DSV: {REVIEWS_DSV_PATH}")


if __name__ == "__main__":
    main()
