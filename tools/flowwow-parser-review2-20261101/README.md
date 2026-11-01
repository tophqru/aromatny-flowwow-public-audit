# Flowwow local browser parser — Review2, независимый аудит

**Публичный исходный код для Arena AI**, но **НЕ** production и **НЕ** каталог для продажи. Только read-only сбор с разрешённого браузера.

- Ветка источника: `audit/chatgpt-description-recovery-20261031` (base SHA `864f6e222ea58cfed063f6594f896edb67ed8e7f`). Создан отдельный Draft PR; **main не менялся**.
- Полный пакет: [flowwow_review2_source_code_only.tar.xz](flowwow_review2_source_code_only.tar.xz), 24 576 байт, SHA256 `8a1df3c26ec7fdeb732ffdf3d2b1dd1360c6ec7859abc558fabe67c057d365a5`.
- Содержимое: `capture.py`, `scroll_logic.py`, `category_logic.py`, `parsing.py`, `storage.py`, 3 PowerShell сценария, requirements и 4 набора тестов, SHA256SUMS.txt.
- **Локальные проверки:** Python compileall PASS и **53/53 offline unittest PASS**, включая 12 mock-тестов прокрутки, раскрытия и категорий. **Windows PowerShell, live Flowwow, реальные галереи, GUI WebQA — NOT_PERFORMED.**
- Дефекты, исправления, ограничения: [REVIEW2_DEEP_AUDIT.md](REVIEW2_DEEP_AUDIT.md).
- Полное новое ТЗ Arena: [ARENA_REVIEW2_ASSIGNMENT.md](ARENA_REVIEW2_ASSIGNMENT.md).

## Как открыть и проверить

```bash
# Download archive from this GitHub folder and unpack using 7-Zip or tar -xf
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q .
```

Для запуска браузера на Windows сначала прочтите `setup_windows.ps1`, `run_trial.ps1`; не запускать полный обход до подтверждения 2-SKU GUI. Просьба Arena: не ограничиваться замечаниями к отчёту, а самостоятельно проверить код, добавить регрессионные mock-тесты и сделать отдельный Draft PR/ZIP с поправками.

**Архив не содержит cookie, user-data-dir, SQLite, профили Chrome, реальные скачанные JPG или секреты.** Исторические 66 SKU/435 JPEG остаются в каталоге GitHub отдельно, их не требуется копировать. Товары автоматически не одобряются к продаже.