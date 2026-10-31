# QA — фактические проверки и ограничения

Дата: 31.10.2026 UTC. Исходный SHA: `f1e717fda918ce4ca8ccba9d4e8dc5ab7ab8f048`.

## Среда

- Python 3.11.2
- Pillow 11.3.0 в локальном виртуальном окружении
- git 2.39.5
- gh 2.23.0
- Исходные 435 JPEG уже присутствовали в рабочем дереве и Git objects; повторного скачивания с Flowwow не было.
- Предыдущих ZIP в `/home/user` до аудита найдено: 0.

## Исполненные команды

| Лог | Команда/действие | Результат |
|---|---|---|
| `logs/00-environment.log` | Версии, SHA, число локальных media, поиск ZIP | 66 source context, 435 media files, 0 ZIP |
| `logs/01-existing-metadata.log` | `python scripts/verify_catalog.py --metadata-only` | exit 0, PASS, 66 SKU / 435 photos / 49 614 983 bytes |
| `logs/02-existing-indexed-leads.log` | `python scripts/verify_indexed_leads.py` | exit 0, PASS_INDEXED_CANDIDATES, 55 leads, 0 retail additions |
| `logs/03-existing-binary.log` | `python scripts/verify_catalog.py --check-media` | exit 0, PASS, SHA256/bytes/JPEG decode |
| `logs/04-existing-coverage.log` | Первая изолированная попытка `report_source_field_gaps.py` | exit 1: ошибка тестовой обвязки, resolving symlink изменил ROOT |
| `logs/04-existing-coverage-retry.log` | Повтор с настоящим каталогом `scripts/` во временной копии | exit 0, PASS_SOURCE_STRUCTURE, 59/36/54, catalog_completion INCOMPLETE |
| `logs/github-source-tree-check.json` | `gh api repos/tophqru/aromatny-flowwow-public-audit/git/trees/f1e717f...?recursive=1` | 435 remote media blobs, paths/OIDs equal local source tree, truncated=false, image bytes downloaded=0 |
| `logs/05a-independent-initial-failure.log` | Первый прогон независимого скрипта | exit 1: слишком строгая проверка README, требовавшая shop URL во всех карточках |
| `logs/05b-independent-evidence-semantics-failure.log` | Второй прогон | exit 1: неверно поняты BATCH5 Merci и шесть исторических null-размеров, позже заполненных |
| `logs/05c-independent-provenance-coverage-failure.log` | Третий прогон | exit 1: восемь размеров и десять составов унаследованы из main и не повторены в поздних evidence |
| `logs/05-independent-offline-audit.log` | Финальный `python arena-output/flowwow-independent-20261031/scripts/audit_offline.py` | exit 0, PASS_OFFLINE_AUDIT_WITH_FINDINGS, 16 находок |
| `logs/06-delivery-verification.log` | `python arena-output/flowwow-independent-20261031/scripts/verify_delivery.py` | exit 0, PASS_DELTA_DELIVERY_CHECKS; SHA256SUMS на первом проходе ещё не генерировался |
| `logs/07-hygiene-selftest.log` | Самопроверка 11 secret/PII regex в памяти и compile двух скриптов | exit 0, 11/11 patterns matched synthetic samples, значения не логировались |

Неудачные прогоны сохранены намеренно. Они относятся к логике независимого аудиторского скрипта/тестовой обвязки, а не к изменению исходного каталога. Исходные карточки, фотографии и цены не исправлялись этими прогонами.

## Что проверил независимый скрипт

- Строгий JSON parse 83 файлов каталога, отсутствие дублей ключей.
- 66 уникальных SKU, canonical product URLs, сохранённый exact seller URL.
-Equality всех 66 card JSON с snapshot.
- 75 Markdown-файлов каталога, локальные ссылки и порядок изображений в README карточек.
- 435 JPEG: bytes, SHA256, Git blob OID, Pillow decode/verify, размер 1000×1000, RGB.
- Отсутствие EXIF и JPEG comments; наличие ICC profile у 105 файлов зафиксировано без извлечения персональных данных.
- Дедупликация source URL и SHA256; 8 групп точных повторов внутри галерей.
- Сравнение сохранённых сырьевых составов, описаний, размеров и отдельных evidence batches.
- 55 кандидатов, 4 pending, 2 quarantine, отсутствие исключённого SKU в товарных списках.
- Все sale flags `false`; никаких новых SKU/фото/полей не объявлено восстановленными.
- Защищённые пути `catalog/`, `data/`, `scripts/`, `.github/`, `arena/` не изменены относительно source SHA.

## Финальная проверка дельты

`verify_delivery.py`: **PASS_DELTA_DELIVERY_CHECKS** — фактически исполнен, exit 0, лог `logs/06-delivery-verification.log`. На первом проходе `SHA256SUMS` ещё отсутствовал; после финальной доставки файл хешей генерируется и проверка повторяется.

Проверка включает: обязательные файлы, строгий JSON, 66/55/4/2 counts, пустые recoveries/gallery/new-skus, отсутствие изображений в дельте, отсутствие включённых sale flags, отсутствие защищённых source changes, high-confidence scan секретов/cookie/email/телефонов, `SHA256SUMS` после его генерации. Regex-шаблоны дополнительно проверены на 11 синтетических примерах в памяти; синтетические секреты не записывались в публичные файлы.

## GitHub delivery / Actions

Официальный Arena GitHub Connector: `unsupported`. Уже настроенные `git`/`gh` в среде имели public repo push permission; токены в чат не запрашивались и не записывались.

Существующий `catalog-qa.yml` автоматически запускается на push только для `main`, `review/chatgpt-reference`, `audit/arena-independent`, а на pull_request — только в `main`. Поэтому данный Draft PR в рабочую audit-ветку и изменения только в `arena-output/**` не обязаны автоматически запускать этот workflow. Фактический ручной запуск/результат, если выполнен, фиксируется в `delivery.json` и комментарии к PR; отсутствие автозапуска не объявляется успешным тестом.

## Неисполненные тесты — явно NOT_PERFORMED

- Живое открытие магазина и товарных страниц Flowwow.
- Прокрутка категорий и нажатие «Показать ещё» до конца списка.
- Переход «Перейти в магазин» и новое подтверждение canonical seller.
- Сверка текущих цен, наличия, вариантов доставки и города.
- Полнота и порядок живых галерей, визуальное соответствие каждого фото текущему SKU.
- Подтверждение 55 кандидатов как товаров именно этого продавца.
- Догрузка оригиналов четырёх pending-галерей.
- Seller UI, заказы, платежи, остатки, права продажи — не выполнялись и не изменялись.

Причина: в доступном наборе инструментов нет настоящего интерактивного браузера. HTTP 403, упомянутые в старых evidence, являются прежними наблюдениями репозитория, а не запросами этого запуска.

## Статус

`PASS_OFFLINE_AUDIT_WITH_FINDINGS` для исполненных офлайн-проверок. Общая задача: `PARTIAL`, каталог: `INCOMPLETE`. Успешный exit code не означает complete Flowwow inventory или живую достоверность всех полей.
