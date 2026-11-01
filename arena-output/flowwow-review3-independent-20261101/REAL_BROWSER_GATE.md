# Отдельный live gate для Codex на ASUS — сейчас NOT_PERFORMED

## Предусловия (не заменять mock-тестами)

1. Локальный ASUS Windows 10, i3, 8GB RAM; активный **видимый** пользовательский desktop. Парсер и Codex работают на ASUS. Compaq/Tailscale — только удалённое управление, не второй исполнитель и не remote browser endpoint. При locked screen/недоступном headed launch остановиться, не подменять headless-«успехом».
2. Согласованный человеком запуск только для трёх URL из `pilot-manifest.example.json`. Draft PR сначала рассмотрен; нет merge/main/prod/import. Никаких parallel workers, обхода CAPTCHA, изменения proxy/fingerprint или автоматических повторов при 401/403/429.
3. Доступ к private source восстановлен владельцем, исходный private pilot и reference SHA проверены отдельно. Здесь этот пункт NOT_VERIFIED (403), нельзя утверждать exact private-source equality.
4. Worktree/venv желательно короткий путь; output — новый **локальный приватный** каталог вне repo, например `C:\FW\r3a`. Не использовать UNC/network share или общую writable папку. Output path budget 140 символов, каждый файл <=240. Unicode/пробелы допустимы, длинный путь отвергается заранее.
5. До браузера: `compileall`, offline suite, `doctor`. Доктор не подтверждает GUI/browser работоспособность. Записать Python/Pillow/Playwright/Edge versions и Windows build, available RAM, наличие активного desktop. Неподдерживаемая Win10/browser комбинация — BLOCKED; setup partial — не success.

## Byte-safe baseline в Windows PowerShell 5.1

Нельзя использовать `git show ... > baseline.json`: PowerShell 5.1 может перекодировать вывод в UTF-16/BOM и сломать pin. Из repo, после fetch pinned commit:

```powershell
git fetch origin 864f6e222ea58cfed063f6594f896edb67ed8e7f
# Выбрать установленный Python 3.10+; команда читает git stdout как bytes.
python -c "import pathlib,subprocess; pathlib.Path(r'C:\FW\baseline.json').write_bytes(subprocess.check_output(['git','show','864f6e222ea58cfed063f6594f896edb67ed8e7f:catalog/public-snapshot.json']))"
```

Проверить Git blob SHA `b1ba9fbe10b7961d35a723d40af01686a0e10b78`; сопоставить manifest SHA256 и запланированные URL. Manifest не разрешает sale/publication; false flags не менять.

Из parser directory, после setup (реальное исполнение этих команд здесь NOT_PERFORMED):

```powershell
.\run_pilot.ps1 -Browser msedge -Manifest .\pilot-manifest.example.json -Baseline C:\FW\baseline.json -Output C:\FW\r3a
```

Этот запуск **не является готовым gallery crawler** и ожидаемо даст PARTIAL/5 при отсутствии доказанных DOM возможностей. `run_full.ps1` больше не запускает весь каталог. Никаких автоматических retry; после разрешённого восстановления доступа `-RetryFailed` — отдельное явное решение оператора. `-RecheckUnverified` пересматривает CAPTURED, но для `SELLER_UNVERIFIED` нужен явный retry failed.

## Реальная UI проверка и адаптация, прежде чем разрешать PASS

Нельзя вставлять придуманные CSS selectors в отчёт как проверенные. Codex должен на **действительно открытой** странице каждого из трёх товаров:

- Снять локальные before/after evidence (вне публичного Git). Подтвердить visible unique product heading, exact requested/final SKU URL, отсутствие challenge/error. Один persistent headed context, одна рабочая вкладка; временный seller popup закрывается сразу. При popup/off-shop redirect от show-more — STOP.
- Отдельно установить product-list root, а не весь `main`, рекомендации или reviews. Пройти видимые промежуточные карточки и каждый реальный nested scrolling root, сохраняя virtualized links по ходу. В SQLite/export допускаются только три allowlisted URL. Несколько одинаковых кнопок — однозначность не угадывать; стоп и redacted fixture для адаптации.
- Найти настоящий seller widget, зафиксировать его связь с карточкой, кликнуть, дождаться canonical exact seller URL. Если новый tab — проверить его; если несколько tabs — unverified/stop. После возврата заново проверить exact SKU и актуальный DOM, не использовать DOM до seller navigation.
- Для **каждой** секции description/composition/dimensions установить actual scope и все read-more/«Показать ещё». Кликнуть только unique visible/enabled control в этой секции; ждать конкретного изменения content/aria-expanded, а не только sleep. Проверить отсутствие оставшегося collapsed content/ellipsis; записать, что контроль отсутствовал и секция уже полностью раскрыта, если это действительно видно. Ambiguity/delay budget/error -> NOT_PROVEN.
- Для gallery установить observed total из реального UI; если count неизвестен — **не утверждать полноту**. Посетить каждую thumbnail/стрелку/fullscreen frame, дождаться реально отображённого original/currentSrc, проверить distinct frame identity, не зацикливаться на clone slides. Сопоставить total, visited frames, URLs и сохранённые файлы; CSS background/lazy frames/SPA transitions учитывать только по наблюдению. >60 или budget stop -> PARTIAL, не truncation=complete.
- Для первых двух SKU проверить новые файлы с bounded downloader; старые 435 JPG не переписывать, совпадения подтверждать внутри того же SKU. Для третьего **PENDING_SELLER_VERIFIED_METADATA_ONLY** оригинальные медиа не скачивать и не включать в media delta; gallery evidence может быть наблюдением UI, не импортом фото.
- Добавить минимальные очищенные DOM fixtures и **действительно исполняемый** bounded action adapter с mock tests для observed selectors. Текущий код оставляет `sections_expanded=false` и gallery click capability NOT_PROVEN намеренно. Не редактировать JSON/SQLite вручную, чтобы нарисовать ALL_GALLERY_FRAMES_OBSERVED или PASS.
- Повторить offline suite и разрешённый visible exactly-three run **после** адаптации. Проверить одновременно per-target evidence, photos, seller и run FINISHED. Сохранить реальные exit codes и timestamps, не заменять их фразой `Crawl ended`.

## Отказоустойчивость и Win10/8GB приёмка

В разрешённой локальной тестовой папке (не production):

- Второй процесс с тем же output и второй output с тем же browser profile должны остановиться до дополнительного browser launch.
- Остановить процесс после committed target / после file atomic rename до DB record; открыть БД после restart, выполнить quick_check, сверить files/SHA256 и missing evidence. Убийство процесса — не испытание power loss. Не стирать БД для «починки».
- Проверить отказ headed launch/закрытый browser tab, отвал remote desktop, переход к locked session. Любой отказ оставляет BLOCKED/IN_PROGRESS и ненулевой exit, export не повышает его до PASS.
- Статусы 401/403/429/CAPTCHA требуют STOP и действий оператора, не retry loop. DNS/proxy/redirect guards не обходить ради «успешного скачивания».
- Снять реальный Task Manager peak RAM браузера + Python + Codex, pagefile и отсутствие OOM на 8GB. Linux downloader-only probe не переносить в этот пункт.
- Исполнить именно PowerShell 5.1 wrappers с Unicode/space paths и путями у length boundary; проверить `$LASTEXITCODE`, setup partial и отсутствие success banner при PARTIAL/5.

## Gate выпуска / доставки

PASS допустим лишь после реализации и доказательства UI capabilities, всех трёх seller/mandatory-field/gallery checks и локальной целостности фото. До этого status PARTIAL/BLOCKED — правильный результат.

Даже PASS не меняет owner_approved/may_order/may_show_publicly и не разрешает publication. Доставка: отдельный Draft PR с очищенной metadata delta и manifest/checksums; никаких cookies/browser profile/raw SQLite/личных данных/скриншотов в public repository. Исходные 66 SKU/435 JPEG не заменять. Владелец отдельно решает импорт и отдельно даёт разрешение продажи. Merge не выполнять.
