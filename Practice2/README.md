# Практическая работа: Разговорный чат-бот + XML Schema

## 1. Спроектированное содержание набора данных
Предметная область: **разговорный чат-бот**.

Используются 3 категории документов:
- `user` (пользователь);
- `conversation` (диалог);
- `message` (сообщение).

В данных присутствуют:
- строки (`username`, `content`, `topic`);
- числа (`age`, `dailyMessageLimit`, `priority`, `sizeKB`, `sentimentScore`);
- даты/дата-время (`registeredAt`, `createdAt`, `sentAt`, `readAt`);
- булевы значения (`isPremium`, `edited`, `containsProfanity`);
- массивы (повторяющиеся элементы: `language`, `tag`, `participant`, `messageRef`, `attachment`, `reaction`, `reader`, `intent`);
- вложенные документы (`settings`, `metadata`, `flags`, `attachments` и т.д.).

## 2. Реализованная схема XML Schema
Схема находится в файле:
- `schema/chatbot_dataset.xsd`

Основные особенности схемы:
- типовые ограничения (диапазоны, перечисления, шаблоны);
- обязательные поля и атрибуты;
- контроль ссылочной целостности через `xs:key`/`xs:keyref` (между пользователями, диалогами и сообщениями).

## 3. Корректные примеры данных
Файлы:
- `samples/valid/valid_01.xml`
- `samples/valid/valid_02.xml`
- `samples/valid/valid_03.xml`

В них специально показаны:
- массивы разной длины;
- пустые массивы (например, `<tags/>`, `<attachments/>`, `<intentTags/>`).

## 4. Некорректные примеры данных
Файлы:
- `samples/invalid/invalid_01_missing_required.xml`
- `samples/invalid/invalid_02_broken_refs.xml`
- `samples/invalid/invalid_03_wrong_types.xml`

Типы ошибок:
- отсутствует обязательный элемент и неверный формат даты;
- нарушены ссылки (`keyref`) на несуществующего пользователя;
- нарушены ограничения типов/диапазонов/перечислений.

## 5. Выбранная библиотека валидации
Используется библиотека Python:
- `xmlschema`

## 6. Проверка соответствия
Скрипт проверки:
- `scripts/validate_xml.py`

### Запуск
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/validate_xml.py
```

Ожидаемый результат:
- файлы из `samples/valid` проходят валидацию;
- файлы из `samples/invalid` не проходят валидацию.
