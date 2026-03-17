#!/usr/bin/env python3
"""Validate XML samples against chatbot_dataset.xsd using xmlschema."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


try:
    import xmlschema
    from xmlschema.validators.exceptions import XMLSchemaValidationError
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "xmlschema не установлен. Установите зависимости: pip install -r requirements.txt"
    ) from exc


def _sorted_xml_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.xml") if path.is_file())


def _validate_group(schema: xmlschema.XMLSchema, files: list[Path], should_be_valid: bool) -> bool:
    ok = True
    expected = "VALID" if should_be_valid else "INVALID"

    for file_path in files:
        try:
            schema.validate(file_path)
            actual_valid = True
            error_text = ""
        except XMLSchemaValidationError as err:
            actual_valid = False
            error_text = str(err).splitlines()[0]

        if actual_valid == should_be_valid:
            print(f"[OK] {file_path} -> {expected}")
        else:
            ok = False
            actual = "VALID" if actual_valid else "INVALID"
            print(f"[FAIL] {file_path} -> expected {expected}, got {actual}")
            if error_text:
                print(f"       reason: {error_text}")

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate XML files by XSD schema.")
    parser.add_argument("--schema", default="schema/chatbot_dataset.xsd", help="Path to XSD schema")
    parser.add_argument("--valid-dir", default="samples/valid", help="Directory with valid XML samples")
    parser.add_argument("--invalid-dir", default="samples/invalid", help="Directory with invalid XML samples")
    args = parser.parse_args()

    schema_path = Path(args.schema)
    valid_dir = Path(args.valid_dir)
    invalid_dir = Path(args.invalid_dir)

    schema = xmlschema.XMLSchema(schema_path)
    valid_files = _sorted_xml_files(valid_dir)
    invalid_files = _sorted_xml_files(invalid_dir)

    if not valid_files:
        print(f"[WARN] Нет файлов в {valid_dir}")
    if not invalid_files:
        print(f"[WARN] Нет файлов в {invalid_dir}")

    valid_ok = _validate_group(schema, valid_files, should_be_valid=True)
    invalid_ok = _validate_group(schema, invalid_files, should_be_valid=False)

    if valid_ok and invalid_ok:
        print("\nИтог: все проверки соответствуют ожидаемому результату.")
        return 0

    print("\nИтог: найдены несоответствия между ожидаемым и фактическим результатом.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
