from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

from src.models import User


def save_users_to_xml(users: list[User], path: Path) -> None:
    root = ET.Element("users")

    for user in users:
        user_element = ET.SubElement(
            root,
            "user",
            id=str(user.user_id),
            confirmed=str(user.is_confirmed).lower(),
        )
        ET.SubElement(user_element, "username").text = user.username

        emails_element = ET.SubElement(user_element, "emails")
        for email in user.emails:
            ET.SubElement(emails_element, "email").text = email

        ET.SubElement(user_element, "registration_date").text = user.registration_date
        ET.SubElement(user_element, "last_authorization_date").text = user.last_authorization_date
        ET.SubElement(user_element, "birth_date").text = user.birth_date
        ET.SubElement(user_element, "gender").text = user.gender

        publications_element = ET.SubElement(user_element, "publications")
        for publication in user.publications:
            publication_element = ET.SubElement(publications_element, "publication")
            ET.SubElement(publication_element, "title").text = publication.title
            ET.SubElement(publication_element, "description").text = publication.description
            ET.SubElement(publication_element, "pages").text = str(publication.pages)
            ET.SubElement(publication_element, "category").text = publication.category
            ET.SubElement(publication_element, "publication_date").text = publication.publication_date

            reviews_element = ET.SubElement(publication_element, "reviews")
            for review in publication.reviews:
                review_element = ET.SubElement(reviews_element, "review")
                ET.SubElement(review_element, "user_id").text = str(review.user_id)
                ET.SubElement(review_element, "text").text = review.text

    xml_bytes = ET.tostring(root, encoding="utf-8")
    pretty_xml = minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding="utf-8")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(pretty_xml)
