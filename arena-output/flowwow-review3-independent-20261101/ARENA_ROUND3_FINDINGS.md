# Независимый аудит Flowwow Review3 — 2026-11-01

## Вердикт

**Офлайн-регрессии исправленного кода: PASS, 173/173. Приёмка живого пилота: BLOCKED / NOT_PERFORMED.**

Это исправления работающего исходного кода, а не только рекомендации. Но это **не сертификат готовности к импорту**: описание/состав не раскрываются проверенными живыми DOM-действиями, каждый кадр галереи не обходится. Для них явно записывается `NOT_PROVEN`; текущий extractor не производит доказательств, достаточных для `PASS`. Пилот, сохранивший только DOM-кандидатов, заканчивается ненулевым кодом 5. Реальный браузерный прогон, ASUS Windows 10 / PowerShell 5.1 / Edge, заблокированный экран и Tailscale: **NOT_PERFORMED**.

- Проверенный исходный SHA PR #5: `6313dcd1efa068c3ee011d8ccead8796dffbf60f`.
- База нового Draft PR: `audit/flowwow-review3-asus-pilot-20261101`, не `main`.
- Работа выполнена на закреплённой ветке `arena/4a8a7fca-aromatny-flowwow-public-audit`; переключения веток и merge не выполнялись.
- Исходные **104 теста воспроизведены независимо**. Число 101 из задания/README не использовалось как результат.
- Добавлено **69 отдельных новых тестов**. На нетронутом исходном SHA: 35 assertion failures, 29 errors, 5 pass. На исправленном коде: 69/69 OK. Ошибки отсутствующих новых интерфейсов не выдаются за 29 дополнительных уязвимостей.
- Сохранены 66 SKU / 435 JPEG / 435 baseline gallery references. Изменений `catalog/`, `data/`, магазина, цен, stock, заказов и sale flags нет. Проверка: `logs/protected-catalog-check.json`.

## Происхождение и пределы проверки

Прочитаны `ARENA_ROUND3_TASK.md`, исходный README, все модули/тесты Review3, прежние `ARENA_NEW_FINDINGS.md` N01–N15 и `input/REVIEW2_DEEP_AUDIT.md` R7–R17. R1–R6 как отдельный первичный отчёт в checkout не обнаружены; соответствующие доступные Review1 regression tests сохранены. Известные R11/R12/R13/R16 и N03/N04/N07/N12/N14 не переименованы в «новые находки».

Public Review2 SHA `2c6c79251be07355d5d6b864a1e48b73ec6a8cb6` получен через git. Из 15 сопоставимых файлов 14 имеют **идентичные исходные Git blob SHA**; отличен интегрированный `capture.py`. Полная таблица — `source-provenance.json`, сравнение относится к начальному Review3, не к нашим исправлениям.

Pinned public baseline независимо связан с commit `864f6e222ea58cfed063f6594f896edb67ed8e7f`: blob `b1ba9fbe10b7961d35a723d40af01686a0e10b78` совпадает с локальным файлом. Git SHA-1 здесь — идентификатор конкретного blob, **не подпись владельца**, не доказательство актуальности Flowwow и не криптографическая защита от изменения программы доверенным локальным пользователем.

Private `tophqru/flower-shop` @ `74dcb841dd5bb8555a8aa4817870a8c1cf8db65a`: GitHub API ответил **403 Resource not accessible by integration**. Побайтовая идентичность `pilot_targets.py` и private-тестов **NOT_VERIFIED**. В публичном исходном Review3 фактически 19 pilot tests, не заявленные ранее 16; подтверждать «точную копию private pilot» нельзя. Private reference `ac74ac…` в manifest сохранён как требуемая ссылка, а не как наша аттестация private-содержимого.

CI job #124763765942 для исходного SHA сообщает success всех шагов. **Полный upstream console log не получен**: download redirect ведёт на недоступный sandbox-хост `results-receiver.actions.githubusercontent.com`, запрос завершился EOF. Сохранены реальные job metadata и ошибка доступа. Основное доказательство 104/104 — собственный локальный запуск, а не CI metadata.

## Новые подтверждённые дефекты

Пути далее относительно `tools/flowwow-parser-review3-integrated/flowwow_review3/`. `до` — строки исходного SHA; `после` — строки исправленного дерева. Все перечисленные тесты находятся в `tests/test_round3_independent.py`, реально исполнены и проходят в финальном логе.

### F01 — HIGH: «точные три» фактически выбирались произвольным manifest
- До: `pilot_targets.py:46–105`: проверялись количество, порядок ролей и membership, но не три заданных slug. Можно заменить pending на любой неизвестный товар или baseline target на другой baseline SKU.
- После: `pilot_targets.py:13,100–104`: неизменяемый tuple `EXACT_SLUGS`, точный URL/slug/роль/порядок. Пример manifest включён в исходники.
- Доказательства: `test_replacement_pending_sku_rejected`, `test_replacement_baseline_sku_rejected`: FAIL → PASS.

### F02 — HIGH: manifest сам удостоверял произвольный baseline; возможен split parsed/hash
- До: `capture.py:481–491`, `pilot_targets.py:46`: доверие blob SHA, указанному тем же manifest. Проверка commit-строки не доказывала связь bytes с этим commit. Парсинг и повторное чтение bytes были раздельными.
- После: `capture.py:104,545,557`: independently pinned blob сравнивается до открытия SQLite/браузера; один read при загрузке, проверка origin SHA256 и повторная проверка inputs перед запуском и каждым target. `pilot_targets.py:48` сравнивает parsed object с декодированными хешированными bytes, duplicate keys отвергаются.
- Тесты: `test_valid_self_signed_but_untrusted_baseline_rejected`, `test_mid_session_manifest_change_stops_next_product`, `test_mid_session_baseline_change_stops_next_product`, `test_invalid_manifest_never_opens_wrong_database`, `test_actual_pinned_baseline_and_manifest_offline_preflight`.
- Это граница доверия доверенной программы/локального оператора, не защита от администратора, меняющего код одновременно с исполнением. Файловые гонки между последней проверкой и чтением браузера не превращают in-memory очередь в другие SKU.

### F03 — HIGH: разрешённый row URL скрывал чужой payload/slug и unsafe sale flags
- До: `pilot_targets.py:108`: проверялась только колонка URL; JSON мог содержать другой товар, `may_order=true` или вообще не иметь запретов продажи.
- После: `pilot_targets.py:117`: identity row/payload согласованы; CAPTURED требует явные false flags и identity; проверяются pin allowed_urls, asset sizes/status/path ownership, metadata-only запрет, budgets. `Store.record_page/record_asset` дополнительно защищают границу записи.
- Тесты: `test_db_payload_foreign_url_rejected`, `test_db_row_foreign_slug_rejected`, `test_db_sale_flag_true_rejected`, `test_db_captured_missing_flags_rejected`, `test_pin_allowed_urls_must_match`, `test_media_path_cannot_belong_to_other_target`.

### F04 — HIGH: strict listing создавал собственную «заражённую» БД
- До: `capture.py:501–508`, `storage.py:84`: preflight проверял пустую БД, затем shop scan сохранял **все** ссылки, хотя очередь была из трёх SKU. Следующий restart мог отвергнуть собственный результат; экспорт мог содержать чужой discovery.
- После: `storage.py:Store.discover`, `capture.py:crawl`: allowlist устанавливается до listing; чужая ссылка не записывается, а не удаляется постфактум. Финальная scope-проверка выполняется повторно.
- Тесты: `test_discovery_allowlist_at_write_boundary`, `test_shop_foreign_discovery_never_persisted`.
- Это новая strict-integration ошибка, не повтор R14 о качестве обнаружения карточек в широком каталоге. Сами live selectors карточек по-прежнему не доказаны.

### F05 — HIGH: export обходил весь pilot guard
- До: `capture.py:551`: экспорт любых pages/discovery/assets независимо от allowlist pin. Подмешивание после preflight не обнаруживалось.
- После: `capture.py:682–745`, `pilot_targets.py:verify_pilot_export`: повторная проверка pin/scope и таблиц; отдельный `pilot-scope.json` не даёт незаметно превратить pilot в non-pilot удалением events. Некорректный экспорт не создаёт новый успешный acceptance.
- Тесты: `test_export_rejects_post_preflight_foreign_discovery`, `test_export_scope_marker_cannot_be_downgraded`, `test_corrupted_db_export_invalidates_old_acceptance`, `test_export_after_rejected_foreign_db_never_falls_back_to_nonpilot`. Маркеры начатого пилота также запрещают non-pilot fallback после неуспешного preflight.

### F06 — HIGH: экспорт не брал run lock
- До: `capture.py:551`: несколько SELECT разных таблиц и хеширование файлов могли идти одновременно с crawl; SQLite защищает отдельную транзакцию, но не этот многошаговый отчёт.
- После: `capture.py:682`: тот же OS lock на весь export и проверки файлов. Второй процесс не получает смешанный отчёт; экспорт из работающего crawl отклоняется.
- Тест: `test_export_takes_exclusive_lock`: FAIL → PASS. Отдельный реальный POSIX subprocess kill проверяет освобождение lock и сохранение committed WAL.

### F07 — HIGH: metadata-only target мог скачивать фото; baseline proof переиспользовался между SKU
- До: `capture.py:371–374,464`: глобальные by_url/by_hash индексы по всем товарам и отсутствие media-policy третьего target.
- После: `capture.py:406,471`: download guard для S3, запрет S3 assets в БД; URL/hash baseline dedup только внутри текущего SKU. Путь новой фотографии должен принадлежать slug строки.
- Тесты: `test_metadata_only_download_is_rejected_before_network`, `test_db_pending_metadata_only_cannot_have_media`, `test_other_sku_baseline_photo_never_counts_as_owned`, `test_media_path_cannot_belong_to_other_target`.

### F08 — HIGH: предсказуемый atomic temp и linkable SQLite обходили изоляцию
- До: `storage.py:15–21,36`, `capture.py:469`: `.tmp-PID` открывался через `wb`, следуя заранее созданной symlink; DB path/WAL могли быть ссылками на чужие файлы. `--output` мог указывать в существующий каталог репозитория. Медиа-only path check не защищал остальные writes.
- После: `storage.py:17–54,84`: mkstemp, проверка ancestors/symlinks/reparse points/hardlinks DB+sidecars, bounded Windows paths. `capture.py:533` запрещает output внутри защищённого репозитория, кроме специально отведённого parser/output; short external local path предпочтителен. Browser profile также не должен попадать в репозиторий.
- Тесты: `test_atomic_predictable_temp_symlink_not_followed`, `test_atomic_parent_symlink_rejected`, `test_store_symlink_rejected_before_wal`, `test_store_hardlink_rejected`, `test_symlink_wal_rejected`, `test_output_catalog_rejected`, `test_path_length_fail_before_write`.
- Не заявляется защита portable check-then-open от враждебного same-user процесса, одновременно заменяющего ancestors. Нужна private local directory; не использовать общий/network output. Реальные Windows reparse points не испытывались.

### F09 — HIGH: Store изменял чужую SQLite до распознавания
- До: `storage.py:36–69`: `journal_mode=WAL` и CREATE TABLE выполнялись в любой переданной SQLite.
- После: `storage.py:60–83`: существующая БД сначала read-only, quick_check, точный набор таблиц/колонок, отсутствие triggers/views; пустые/слишком большие файлы отвергаются. Никакого reset, repair или удаления базы.
- Тесты: `test_unrelated_sqlite_schema_unchanged`, `test_corrupted_sqlite_no_repair_or_reset`, `test_invalid_manifest_never_opens_wrong_database`. Сравнение bytes и отсутствия WAL сделано реально.

### F10 — HIGH: неуспешный Windows lock всё равно выполнял unlock
- До: `storage.py:113–136`: unconditional finally-unlock даже при отказе LK_NBLCK; может освободить активную блокировку того же процесса на Windows.
- После: `storage.py:173–199`: unlock только после успешно полученной блокировки.
- Тест `test_windows_failed_lock_does_not_unlock_active_owner_mock`: FAIL → PASS с моделью msvcrt lock ownership. **Это mock доказательство control-flow; реальный Windows runtime NOT_PERFORMED.**

### F11 — MEDIUM: дробные/противоречивые размеры превращались в целые подтверждённые
- До: `parsing.py:169–182`: `Ширина 35,5` могла стать 35; один `35x45` скрывал другие labelled размеры.
- После: `parsing.py:169–190`: decimal/mm/negative форматы и противоречия fail closed как `UNVERIFIED_PARSE`.
- Тесты: `test_dimension_decimal_not_silently_integer`, `test_dimension_contradictory_sizes_rejected`: FAIL → PASS. Не заявляется поддержка всех единиц/локалей.

### F12 — MEDIUM: «Using cached snapshot» не загружало snapshot
- До: `capture.py:84–96`: online exception при наличии cache печатал warning, но snapshot оставался unbound.
- После: `capture.py:104–131`: bytes реально читаются из cache в exception branch, bounded чтение. Strict CLI всё равно требует pinned local baseline и не использует этот moving/cache путь.
- Тест `test_failing_online_read_actually_uses_existing_cache`: UnboundLocalError → PASS.

### F13 — HIGH: browser profile мог оказаться в Git repository; output locks не сериализовали общий профиль
- До: `capture.py:224–230,469`: запрещался только parser ROOT, но `LOCALAPPDATA=repo_root` сохранял сессию рядом с каталогом; два разных output имели разные locks, но один профиль.
- После: `capture.py:257–264,578`: проверяется весь repository root и link ancestors; отдельный profile lock удерживается до закрытия context; лишние начальные вкладки закрываются. `service_workers=block` предотвращает обход route guard через service worker в этом профиле.
- Тест `test_browser_profile_never_stored_under_repository`: FAIL → PASS. OS lock механизм проверен subprocess kill. **Гарантия RAM/поведения настоящего Chromium на двух Windows-сеансах не заявлена.**

### F14 — HIGH: wrong/unverified seller всё равно выдавал структурированные поля как CAPTURED
- До: `capture.py:433–465`: metadata/gallery извлекались независимо от результата seller click (только скачивание имело seller gate).
- После: `capture.py:471–495`: `SELLER_UNVERIFIED`, только identity/seller/reason + false flags, без composition/dimensions/gallery; acceptance BLOCKED. Чужие поля не становятся кандидатом импорта под разрешённым slug.
- Тест `test_unverified_seller_fields_and_photos_are_quarantined`: FAIL → PASS.
- Точный клик в магазин остаётся только наблюдением по известной эвристике ссылки: привязка этой ссылки к реальному seller widget требует live gate.

### F15 — MEDIUM: --recheck-unverified считал incomplete gallery уже достаточной
- До: `capture.py:134–140`: полностью заполненные text fields + `GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS` → False, то есть явный recheck не запускался для непроверенной галереи.
- После: `capture.py:164–172`: для прекращения recheck нужны all-frame evidence и section-expansion evidence; без opt-in автоматического пересканирования нет.
- Тест `test_recheck_cannot_treat_candidate_gallery_as_complete`: FAIL → PASS; прежний helper test обновлён под честную семантику.

## Исправление известных открытых рисков — НЕ новые находки

### R12 / N07: ограниченный media transport
`media_transport.py:17–89`: отдельный unauthenticated HTTPS клиент без browser cookies, proxy environment и redirects. DNS resolve один раз; **весь** набор ответов должен быть global IP, затем TCP к зафиксированному IP с TLS SNI и certificate validation для исходного CDN hostname. HTTP encoding кроме identity отклоняется до body; Content-Length проверяется заранее, single-underlying-read `read1` <=64 KiB (не сборка полного chunk при slow trickle), hard body cap 18 MiB + один sentinel byte. Сокеты закрываются при любом исходе. Ограничение wall-time проверяется между reads; системный DNS resolver не имеет переносимого жёсткого deadline — это остаточное ограничение, а не обещание ровно 45 секунд.

Pillow size <=6000x6000/36M pixels, формат JPEG/PNG/WEBP, минимум 480x480 и single frame; animated и pixel bomb fixtures отвергаются до verify. Хеширование локальных файлов потоковое, локальный baseline bounded 10 MiB. Это не обещание hard total RSS 18 MiB: существуют bytearray/bytes/Pillow overhead.

Реальный **offline** memory probe: 30 последовательных 18 MiB ответов под Linux RLIMIT_AS 256 MiB; peak RSS 61,956 KiB в сохранённом запуске. Огромный chunked body остановлен после 18,874,369 bytes. Нет HTTP сети/браузера. Это не ASUS 8 GB browser benchmark.

### R16: отдельная acceptance и аварийная инвалидация
`acceptance.py:5`, `capture.py:563–676,688–746`: machine-readable `review/pilot-acceptance.json`, ровно три URL, per-target missing evidence, `PASS/PARTIAL/BLOCKED`, 0 automatic approvals. До preflight ставятся `pilot-run.json=IN_PROGRESS` и BLOCKED report; crash/browser launch failure не оставляет прежний PASS. Export не повышает незавершённый run и инвалидирует старый report до открытия повреждённой БД. Файлы отчёта пишутся атомарно по одному; это не единая FS/SQLite транзакция. Потребитель обязан проверять acceptance и состояние run, не только наличие HTML/products.json.

Exit codes: 0 — acceptance PASS (в текущем extractor практически недостижим); 2 — setup/preflight/runtime exception; 3 — access blocked; 4 — local-media integrity failure внутри crawl; 5 — incomplete/failed acceptance; 130 — interrupt. `SESSION_FINISHED`/«batch ended» не является отдельным разрешением импорта.

Broad CLI crawl без manifest запрещён. Старые `run_full.ps1`/`run_trial.ps1` теперь требуют manifest/baseline/output и делегируют strict pilot, а не обходят весь каталог. Новый `run_pilot.ps1` сохраняет ненулевые crawl/export коды. PowerShell проверен статически, не исполнением Windows.

### N03/N04/R17: дополнительные regression hardening
Закрываются все новые seller popups, включая множественные; show-more popup закрывается, а его stop_reason поднимается в `BrowserBlocked`, не только записывается в category log. Проверка unauthorized document route выполняется **до** сетевого обращения к чужому document URL. Browser subresources/CDN dependencies остаются browser-managed: это не глобальный browser DNS firewall и не доказательство отсутствия фоновых сетевых запросов Chromium.

N01–N15 regressions (XSS escaping, URL scheme validation, redirects, BOM/Unicode fixtures, fsync, source seller return, missing/corrupt local media, diagnostics) повторно исполнялись. Media tests переведены с mock `context.request` на новый transport seam; queue test больше не требует ложного exit 0; ни один исходный test method не удалён.

## UI coverage и незакрытые блокеры

| Область | Что реально есть | Статус |
|---|---|---|
| Intermediate/virtualized shop scroll | bounded window scroll, сохранение ранее виденных allowlisted links, mock regression | DOM capability NOT_PROVEN |
| Nested scroll container | обнаружение possible_nested_scroll, но нет обхода каждого nested container | NOT_PROVEN, полнота запрещена |
| Несколько «Показать ещё» | ambiguity stop; main role button/link; popup/off-shop stops | mock PASS, live NOT_PROVEN |
| Description/composition read-more | нет проверенного action contract, не выдумывались selectors | NOT_PROVEN, sections_expanded=false |
| SPA delayed content | фиксированные bounded waits, не semantic readiness witness | NOT_PROVEN |
| Галерея thumbnails/fullscreen | DOM img candidates, srcset/lazy attrs, truncation flag | all frames NOT_PROVEN |
| Unknown gallery count / >60 | отсутствие count или truncation запрещает acceptance PASS | fail-closed mock PASS |
| Seller click/return | clicked target URL и повторная exact SKU проверка; wrong seller quarantine | mock PASS; реальная widget ownership NOT_PROVEN |
| Image HTTP / DNS / encoding | ограниченный transport, synthetic responses/DNS/TLS mocks | offline PASS, live CDN NOT_PERFORMED |
| Win10 / Edge / PS5.1 / screen lock / Tailscale | wrappers + Win-lock mock, ручной gate | NOT_PERFORMED |

До реального прохода `REAL_BROWSER_GATE.md` **не разрешено** писать «all 3 verified», «галерея полная», импортировать delta или публиковать товары. Не менять flags, не обходить 403/CAPTCHA, не включать массовые workers. Raw browser profile, cookies, SQLite, screenshots и живые фото в публичный PR не включены.

## Артефакты

- `TEST_RESULTS.md` — точные команды, counts, окружение и смысл before errors.
- `REAL_BROWSER_GATE.md` — owner-safe Codex/ASUS gate, включая byte-safe экспорт baseline в PowerShell 5.1.
- `source-provenance.json`, `requirements-tested.txt`, реальные `logs/`.
- `changes.patch` — воспроизводимый diff только исправляемого isolated parser/workflow, без self-referential отчётов.
- `SHA256SUMS` — SHA256 patch, исходников, тестов, отчётов и логов. Это контроль целостности доставки, не подпись владельца.
