# Журнал фактических проверок

Файлы содержат реальные команды, stdout/stderr и exit codes. Неудачные первые прогоны сохранены для прозрачности.

- `00-environment.log` — среда, source SHA, 435 локальных media, 0 предыдущих ZIP.
- `01-existing-metadata.log` — штатный metadata verifier, PASS.
- `02-existing-indexed-leads.log` — штатный verifier 55 кандидатов, PASS.
- `03-existing-binary.log` — штатная бинарная проверка 435 JPEG, PASS.
- `04-existing-coverage.log` — первая попытка coverage в изолированной обвязке, FAIL из-за ROOT/symlink.
- `04-existing-coverage-retry.log` — исправленная обвязка, PASS_SOURCE_STRUCTURE; каталог всё равно INCOMPLETE.
- `existing-source-field-coverage.json` — машинный результат штатного coverage: 59 составов, 36 описаний, 54 размера.
- `github-source-tree-check.json` — рекурсивное GitHub tree source SHA: 435 media blob OIDs совпали, байты фото не скачивались.
- `05a-independent-initial-failure.log` — независимый скрипт: исправлена чрезмерно строгая проверка README.
- `05b-independent-evidence-semantics-failure.log` — исправлено понимание BATCH5 и исторических null-размеров.
- `05c-independent-provenance-coverage-failure.log` — добавлена маркировка значений, унаследованных из main.
- `05-independent-offline-audit.log` — финальный независимый офлайн-аудит, PASS_WITH_FINDINGS.
- `06-delivery-verification.log` — проверка изолированной дельты, privacy/secret patterns и SHA256SUMS.
- `07-hygiene-selftest.log` — самопроверка 11 шаблонов секретов/PII и компиляция двух Python-скриптов; синтетические значения не логировались.

Логи не содержат токенов, cookie, заголовков авторизации или данных покупателей.
