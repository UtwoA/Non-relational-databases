from src.config import PUBLICATIONS_DSV_PATH, REVIEWS_DSV_PATH, USERS_DSV_PATH, XML_PATH
from src.dsv_io import read_users_from_dsv
from src.transform import filter_confirmed_users
from src.xml_io import save_users_to_xml


def main() -> None:
    users = read_users_from_dsv(USERS_DSV_PATH, PUBLICATIONS_DSV_PATH, REVIEWS_DSV_PATH)
    confirmed_users = filter_confirmed_users(users)
    save_users_to_xml(confirmed_users, XML_PATH)

    print("STEP 2: READ DSV + TRANSFORM + SAVE XML")
    print(f"Loaded from DSV (users): {len(users)}")
    print(f"Confirmed users: {len(confirmed_users)}")
    print(f"XML file: {XML_PATH}")


if __name__ == "__main__":
    main()
