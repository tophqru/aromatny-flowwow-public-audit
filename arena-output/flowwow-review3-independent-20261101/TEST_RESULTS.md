# TEST_RESULTS — Review3 independent audit

## Реальные результаты

| Проверка | Результат | Доказательство |
|---|---|---|
| Первоначальная системная Python без зависимостей | НЕ baseline PASS: import errors | `logs/baseline-tests.log` |
| Pristine Review3 `6313dcd…`, dependencies установлены в отдельной venv | **104/104 OK** | `logs/baseline-tests-deps.log` |
| Первый независимый набор до исправлений (30 tests) | 18 failures, 11 errors, 1 pass | `logs/independent-before.log` |
| Финальные 69 независимых тестов на pristine Review3, без production changes | **35 failures, 29 errors, 5 pass** | `logs/final-independent-before.log` |
| Те же 69 тестов на исправленном коде | **69/69 OK** | `logs/final-independent-after.log` |
| Полная исправленная suite | **173/173 OK**, без skipped | `logs/final-all-tests.log` |
| compileall / diff whitespace check | exit 0 | `logs/final-command-results.json` |
| Doctor без site-packages | exit 0, dependencies=MISSING, JSON | `logs/doctor-no-deps.json` |
| POSIX kill/restart, committed WAL и OS lock | PASS, настоящий subprocess.kill(), не power loss | test `test_process_kill_releases_lock_and_keeps_committed_wal` |
| Windows failed-lock owner control-flow | PASS на mock msvcrt, **не Windows execution** | test `test_windows_failed_lock_does_not_unlock_active_owner_mock` |
| 30 x 18MiB bounded streams, Linux memory cap | PASS, peak RSS 61,956 KiB; 64KiB max read | `logs/offline-memory-probe.json` |
| Protected catalog | 66 products, 435 gallery refs, 435 JPG; changed paths=[] | `logs/protected-catalog-check.json` |
| Source blob provenance | 14/15 initial files identical to original Review2; capture integrated | `source-provenance.json` |
| Upstream CI | job metadata success; console log **NOT_RETRIEVED** | `logs/upstream-ci-job.json`, `logs/upstream-ci-log-access.txt` |
| Private pilot source blob identity | **NOT_VERIFIED**, HTTP 403 integration resource access | `logs/upstream-ci-log-access.txt` |
| Real Flowwow/browser/CDN scan | **NOT_PERFORMED** | нет GUI, браузерного binary или DISPLAY |
| ASUS 8GB Win10, Edge, PS5.1, remote/locked session | **NOT_PERFORMED** | `logs/environment.json` |

29 errors в before — в том числе отсутствующие **новые** acceptance/transport/path-helper интерфейсы. Это ожидаемые red tests при разработке, **не 29 самостоятельно подтверждённых уязвимостей**. Подтверждённые исходные дефекты перечислены в FINDINGS со сценариями, не выведены из одного счётчика FAIL. Characterization tests (например, уже безопасный 403 stop и malformed UTF8) не считаются новыми багами. Итерационные логи оставлены для прозрачности; итоговый результат берётся из `final-*`, а не из промежуточных counts.

## Среда

Python 3.11.2, Linux x86_64 / glibc 2.36, SQLite 3.40.1. Pillow 12.3.0, BeautifulSoup 4.15.0, Playwright library 1.64.1; точные transitive versions в `requirements-tested.txt`. Наличие Playwright library не означает установленный browser binary. DISPLAY/WAYLAND отсутствуют; Chromium/Edge/Chrome/PowerShell executables не найдены; Playwright Chromium executable path отсутствует.

Изоляция зависимостей: `/home/user/audit-venv`, вне Git repository. Существующие данные не модифицировались. Ни одного настоящего browser context не запускалось. Environment probe открывал только Playwright driver для получения configured executable path, без browser launch. Все browser interactions в tests — mocks/fakes. В промежуточной первой итерации старые media mocks перестали перехватывать новый transport, из-за чего были попытки DNS lookup CDN; они не являются live browser/CDN проверкой и не дали доказательств реальных фото. Финальные media tests перехватывают новый transport seam, прямой DNS/TLS также моделируется mocks.

## Воспроизведение после исправлений

Из корня repository (POSIX):

```bash
python3 -m venv /home/user/audit-venv
/home/user/audit-venv/bin/python -m pip install -r arena-output/flowwow-review3-independent-20261101/requirements-tested.txt
/home/user/audit-venv/bin/python -m compileall -q tools/flowwow-parser-review3-integrated/flowwow_review3
/home/user/audit-venv/bin/python -m unittest discover -s tools/flowwow-parser-review3-integrated/flowwow_review3/tests -v
/home/user/audit-venv/bin/python -m unittest discover -s tools/flowwow-parser-review3-integrated/flowwow_review3/tests -p test_round3_independent.py -v
/home/user/audit-venv/bin/python -S tools/flowwow-parser-review3-integrated/flowwow_review3/capture.py doctor
/home/user/audit-venv/bin/python arena-output/flowwow-review3-independent-20261101/offline_memory_probe.py
git diff --check
```

`offline_memory_probe.py` использует POSIX `resource`; на Windows не запускать как Windows benchmark. Воспроизведение сырых symlink fixtures на Windows потребует разрешений Developer Mode/admin; здесь они выполнялись на Linux.

Полное воспроизведение baseline/before/after без переключения ветки: `python arena-output/flowwow-review3-independent-20261101/reproduce_offline.py` (из venv с установленными зависимостями).

## Как получен fail-before без переключения рабочей ветки

1. `git archive 6313dcd1efa068c3ee011d8ccead8796dffbf60f tools/flowwow-parser-review3-integrated catalog/public-snapshot.json` распакован в отдельный временный `/home/user/review3-pristine-*`.
2. В него скопирован **только финальный** `tests/test_round3_independent.py`.
3. Запущен `python -m unittest discover -s <temp>/tools/flowwow-parser-review3-integrated/flowwow_review3/tests -p test_round3_independent.py -v` с той же venv.
4. Exit code 1 и полный вывод сохранены. Temp directory удалена после исполнения. Production files из pristine snapshot не исправлялись. Working branch не переключалась.

Отдельный полный 104-test baseline снят **до** изменения production/test sources. Ни один исходный test method не удалён: media mocks перенесены на `capture.fetch_image`, pilot queue expectation заменён с ложного 0 на 5, source-recheck test теперь считает DOM candidates недостаточным свидетельством. Независимый integration test проверяет настоящий pinned 66-SKU baseline без подмены pin constant.

CI workflow теперь требует >=173 tests, а не устаревшие >=101. Он запускается по PR в audit branch, без доступа к Flowwow, browser install или production secrets. Сам workflow/log status после публикации PR следует смотреть в GitHub; его наличие не заменяет локальный executed log.

## Что PASS не означает

Ни unit tests, ни memory probe не доказывают доступность живого Flowwow, реальный frame count, видимость каждого поля, подлинность seller-widget selector, работоспособность Windows 10/Edge/PS5.1, отсутствие системного OOM на ASUS или восстановление после внезапного отключения питания. Эти пункты остаются gate, а не «успешно смоделированной реальностью».
