## АКТУАЛЬНО 31.10.2026 — 66 SKU / 435 JPEG / 59 СОСТАВОВ / 36 ОРИГИНАЛЬНЫХ ОПИСАНИЙ / 49 РАЗМЕРОВ

В рабочем Draft PR #2 восстановлены исходное описание и размеры 21×23 см для [композиции в сумочке №678899](https://flowwow.com/flowers/kompoziciya-v-sumochke-s--9069/) по точному индексированному URL (provenance `evidence/SOURCE_DESCRIPTION_RECOVERY_2026-10-31_BATCH7.json`). ОСТАЛОСЬ **7 составов, 30 описаний, 17 пар размеров** на **32 уникальных SKU**. Фото, цены, запасы и разрешения на продажу не изменены. Приватная ветка `data/flowwow-catalog-import-20261031` синхронизирована: **36/49**, backlog 32; GitHub QA на последнем приватном queue HEAD `20f4c7118c6a13003a443b569083340e28210fd9` SUCCESS.

Индексация дополнительно выявила **52 уникальные возможные карточки** с отображаемым продавцом «Ароматный букет», вне 66 SKU, 4 отдельно проверенных Seller-кандидатов и двух карантинных страниц: [первая 21](discovery/FLOWWOW_INDEXED_21_NEW_POSSIBLE_PRODUCTS_2026-10-31.md), [следующие 6](discovery/FLOWWOW_INDEXED_6_MORE_POSSIBLE_PRODUCTS_2026-10-31.md), [последние 25](discovery/FLOWWOW_INDEXED_25_MORE_POSSIBLE_PRODUCTS_2026-10-31.md). **Это не доказанные товары именно нашего canonical Seller ID:** переход по «Перейти в магазин» не выполнен, точный shop link и полные фотогалереи не проверены, 0 новых JPG; не включать их в импорт/витрину. В текущем tool-просмотре Flowwow даёт Cache miss; кнопку «Показать ещё» фактически нажать не удалось. Не выдумывать факт обхода всех категорий.

---

## Обновление рабочей ветки 31.10.2026 — 35/66 оригинальных описаний

В [Draft PR #2](https://github.com/tophqru/aromatny-flowwow-public-audit/pull/2) восстановлен оригинальный текст набора Merci по точной индексированной странице и совпадающему уже сохранённому в GitHub тексту. **66 SKU / 435 оригинальных JPEG / 59 составов / 48 размеров / 35 исходных описаний.** Осталось **7 составов, 18 размеров, 31 описание**. `main` не изменён; никаких разрешений к продаже. [Новые наблюдения и расхождения](evidence/SOURCE_OBSERVATIONS_2026-10-31_BATCH6.json), включая 23 против 35 пионов и товар с исторически изменившимися ценой/наличием. Отсутствие текста на индексированной странице не доказывает незавершённую карточку. Прямой HTTP Flowwow ранее дал 403.

---

## АКТУАЛЬНАЯ РАБОЧАЯ ВЕТКА, 31.10.2026 — 66/435; 59 СОСТАВОВ; 48 РАЗМЕРОВ; 34 ОРИГИНАЛЬНЫХ ОПИСАНИЯ

**Это рабочая ветка `audit/chatgpt-description-recovery-20261031`, НЕ публичный `main`.** Здесь восстановлены **8 исходных описаний** сверх main 26/66 и **2 размера** по точным URL индексированных страниц Flowwow. Не закрыты 7 составов, 18 размеров, 32 описания. Оригинальные изображения 435 не изменены. Восстановление индексного текста не доказывает актуальные цену/остаток; весь закрытый ассортимент Seller не доказан.

[Семь невскрытых исходных страниц — не доказаны пустыми](review/POTENTIALLY_UNFINISHED_PRODUCTS_2026-10-31.md) · [Две возможные незавершённые карточки — карантин, без импорта](discovery/QUARANTINED_INCOMPLETE_PUBLIC_CANDIDATES_2026-10-31.md) · [Доказательства восстановленных текстов](evidence/SOURCE_DESCRIPTION_RECOVERY_2026-10-31_BATCH4.json) · [Draft PR #2](https://github.com/tophqru/aromatny-flowwow-public-audit/pull/2).

GitHub Actions coverage [#41223295266](https://github.com/tophqru/aromatny-flowwow-public-audit/actions/runs/41223295266) и binary QA [#41223299371](https://github.com/tophqru/aromatny-flowwow-public-audit/actions/runs/41223299371) на commit `4cd40039b5d46c8fa459a832b10db962ab64c5c6` завершились SUCCESS, **но `catalog_completion=INCOMPLETE`**. Старые контрольные точки ниже исторические.

---

## Обновление 31.10.2026 — публичный каталог перед независимым аудитом Arena

- **66 отдельных карточек**, **435 реально загруженных JPEG** (49 614 983 байта), **59/66 составов**, **46/66 размеров**, **26/66 подлинных исходных описаний**. **40 описаний**, 7 составов и 20 размеров остаются неподтверждёнными; не выдумывать их.
- Контрольный публичный HEAD `e37066b8901eec8ee88956ccb9046ca36425af5e`; проверка [GitHub Actions 41218378573 SUCCESS](https://github.com/tophqru/aromatny-flowwow-public-audit/actions/runs/41218378573) на этом HEAD. SHA-256 всех 435 JPEG проверены без повторной загрузки.
- Arena должна проверять **все 66 карточек**, догружать публичные разделы, искать недостающие SKU, сверять состав, описания, наличие, цены и **все** галереи. Результаты отдельно в `audit/arena-independent` либо ZIP только с дельтами; существующие 435 фото повторно скачивать не требуется.
- Контрольная `main` и `review/chatgpt-reference` остаются неизменяемым исходным материалом при работе Arena. Публикация всех 66 карточек в GitHub **не означает разрешение к продаже**; owner-excluded №4183 отсутствует, полный скрытый Seller inventory неизвестен.
- Сначала проверять актуальный main, Actions, ветки и `catalog/public-snapshot.json` после любого обрыва.

---

## Контрольная точка 31.10.2026: подтверждено 66 карточек / 435 оригинальных JPEG

- **435 JPEG physically stored**, 66 folders, 49 614 983 bytes; initial importer [41216722238 SUCCESS](https://github.com/tophqru/aromatny-flowwow-public-audit/actions/runs/41216722238).
- **59/66** составов с количеством цветов; **46/66** размеров; **21/66** исходных описаний текста, 45 остальных не утверждать как заполненные; 7 страниц не удалось прочитать доступным инструментом.
- **48 товаров** дополнительно открыты и сверены на публичных страницах Flowwow (остальные значения унаследованы от ранее проверенного импорта). Проверки и исходники: `catalog/evidence/`, каждый `product.json` содержит URL и поля наблюдения.
- Старые цены сохранены; новые **27** наблюдаемых цен из блока покупки записаны отдельно. Статус «закончился» или «временно отсутствует» не разрешает продажу на собственном сайте.
- Независимый QA после дополнения описаний: [41217602752 SUCCESS](https://github.com/tophqru/aromatny-flowwow-public-audit/actions/runs/41217602752).
- Branch `review/chatgpt-reference` — независимая проверка ChatGPT; `audit/arena-independent` — независимая работа Arena. Контрольная ветка `main` не должна меняться Arena.
- Важное: **публичность позволяет Arena чтение без токена, но НЕ запись/push без аутентификации.** Если нет write-доступа, достаточно прислать `arena-results/` delta ZIP (без повторной упаковки 435 JPEG).
- Исключённый владельцем №4183 в этом репозитории отсутствует. Полный скрытый/архивный Seller inventory не доказан, все товары непокупаемы.

---

# Каталог букетов «Ароматный букет»

**66 карточек и 435 фото в манифесте.** Изображения считаются перенесёнными только после GitHub Actions и бинарной проверки.

[Машинный JSON](public-snapshot.json) | [Задание Arena](../ARENA_PUBLIC_TASK.md)

Каталог неполон по описаниям, составу и размерам. Не предназначен для продаж.

## Авторские букеты

- [Букет воздушный пудинг роза кустовая, маттиола, диантус](cards/buket-vozdushniy-puding-roza-k/README.md) — 6 фото
- [Акция! Авторский букет с гортензией, матиолла кустовая, роза пионовидная кустовая 46788](cards/avtorskiy-buket-s-gortenz-3168/README.md) — 6 фото
- [Авторский букет роза, альстромерии, маттиола, роза пионовидная кустовая, эвкалипт 5778](cards/avtorskiy-buket-roza-alst-8286/README.md) — 8 фото
- [Букет с маттиолой розой кустовой диантусами эвкалиптом](cards/buket-s-mattioloy-rozoy-k-9188/README.md) — 6 фото
- [Букет гортензии, маттиола, диантус, роза пионовидная кустовая 0008](cards/buket-gortenzii-mattiola--1218/README.md) — 6 фото
- [Акция! Премиум букет кустовой пионовидной розы, альстромерии](cards/buket-iz-kustovoy-pionovi-3287/README.md) — 6 фото
- [Букет гортензии, роза пионовидная кустовая, диантус, маттиола, эвкалипт](cards/buket-gortenzii-roza-pionovidn/README.md) — 6 фото
- [Акция! Букет маттиола, роза пионовидная кустовая, диантус, гортензия 007](cards/buket-mattiola-roza-piono-5396/README.md) — 6 фото
- [Букет из роз, кустовой пионовидной розы, диантуса, маттиолы, эвкалипта](cards/buket-iz-roz-kustovoy-pio-6913/README.md) — 5 фото
- [Букет из диантуса, ароматной маттиолы кустовой в стильной упаковке](cards/buket-iz-diantusa-gvozdik-6944/README.md) — 6 фото
- [Акция! Авторский букет Люблю роза пионовидная кустовая маттиола диантус эустома](cards/avtorskiy-buket-lyublyu-roza-p/README.md) — 6 фото
- [Акция! Букет с пионовидной кустовой розой и альстромерией](cards/buket-s-pionovidnoy-kusto-4643/README.md) — 6 фото
- [Букет гортензии, кустовой пионовидной розы, диантуса, пионов, эвкалипта](cards/buket-iz-gortenzii-kustov-7019/README.md) — 6 фото
- [Авторский букетик роза, гортензия, роза кустовая, альстромерия](cards/avtorskiy-buketik-dlya-tebya-r/README.md) — 6 фото
- [Авторский букет роза пионовидная, роза пионовидная кустовая, маттиола, озотамнус, диантус, дофаминовый](cards/avtorskiy-buket-roza-pion-7064/README.md) — 8 фото
- [Букет хризантем, маттиола, ромашка, роза пионовидная кустовая](cards/buket-hrizantem-mattiola-romas/README.md) — 6 фото
- [Авторский букетик гортензии, маттиолы кустовые, роза кустовая, эвкалипт](cards/avtorskiy-buketik-23/README.md) — 5 фото
- [Авторский букетик гортензии, маттиола, роза, эустома, эвкалипт](cards/avtorskiy-buketik-gortenzii-ra/README.md) — 6 фото
- [Авторский букет26](cards/avtorskiy-buket-9444/README.md) — 6 фото
- [Акция!!! Авторский букетик «Для Вас»](cards/avtorskiy-buketik-dlya-vas-1541/README.md) — 6 фото
- [Яркий букет Сезон](cards/buket-sezon-6869/README.md) — 8 фото
- [Авторский букет Осенний 24579](cards/avtorskiy-buket-24579/README.md) — 8 фото
- [Авторский букет гортензия роза эустома маттиола](cards/avtorskiy-buket-3448/README.md) — 6 фото
- [Авторский букет Воздушное безе 23578](cards/avtorskiy-buket-vozdushnoe-bez/README.md) — 8 фото
- [Авторский букетик с розой, гортензией, диантусом, эустомой, маттиолой и ромашкой](cards/avtorskiy-buketik-roza-go-1029/README.md) — 6 фото
- [Авторский букет Сицилия, гортензия и розы](cards/buket-siciliya-6909/README.md) — 6 фото
- [Букетик с французской розой, гортензией, маттиолой, ромашкой и диантусом](cards/avtorskiy-buketik-francuz-9106/README.md) — 6 фото
- [Букет с орхидеей, эустомой и гортензией](cards/avtorskiy-buket-7186/README.md) — 6 фото
- [Дофаминовый букет с пионами и гортензией](cards/avtorskiy-buket-pion-gort-6904/README.md) — 7 фото
- [Букет с гортензией, розой, эустомой, маттиолой и орхидеей](cards/avtorskiy-buket-gortenzii-3341/README.md) — 8 фото
- [Дофаминовый букет с розой, маттиолой и орхидеей](cards/avtorskiy-buket-roza-mattiola-/README.md) — 6 фото
- [Авторский букет 67899](cards/avtorskiy-buket-67899/README.md) — 8 фото
- [Букет с маттиолой, розой, гортензией и эустомой](cards/avtorskiy-buket-mattiol-roza-g/README.md) — 8 фото
- [Букет «Лавандовые грезы»](cards/buket-lavandovye-grezy-roza-ma/README.md) — 6 фото
- [Букет «Перышко»](cards/buket-peryshko/README.md) — 6 фото
- [Букет «Звезда»](cards/buket-zvezda/README.md) — 6 фото

## Монобукеты

- [Букет гортензий 23](cards/buket-gortenziy-23/README.md) — 6 фото
- [Букет роз французских под ленту 21 штука](cards/francuzskie-rozy-pod-lentu-21-/README.md) — 6 фото
- [Акция! Букет гладиолус под ленту](cards/cve-7264/README.md) — 8 фото
- [Букет астр осенних](cards/buket-astr-osennih/README.md) — 8 фото
- [Букет ароматных маттиол кустовых](cards/buket-aromatnyh-mattiol-kustov/README.md) — 6 фото
- [Букетик из 13 веточек пионовидных кустовых роз в упаковке](cards/mono-9992/README.md) — 6 фото
- [Букет астр 67892](cards/buket-astr-67892/README.md) — 7 фото

## Цветы в коробке

- [Композиция в шляпной коробочке роза пионовидная кустовая, эустома, эвкалипт 00002324234](cards/buket-rozy-pionovidnoy-kustovo/README.md) — 8 фото
- [Композиция в коробочке эустома и роза пионовидная кустовая](cards/kompoziciya-v-korobochke-eusto/README.md) — 6 фото
- [Композиция в шляпной коробочке пионы с эвкалиптом](cards/kompoziciya-v-shlyapnoy-k-7428/README.md) — 8 фото
- [Композиция в шляпной коробочке 014](cards/kompoziciya-v-shlyapnoy-k-3035/README.md) — 6 фото
- [Букет в шляпной коробке](cards/buket-v-shlyapnoy-korobke-8250/README.md) — 6 фото
- [Композиция в шляпной коробочке астра, гортензия, маттиола, эустома, эвкалипт](cards/kompoziciya-v-shlyapnoy-k-6842/README.md) — 8 фото
- [Композиция в шляпной коробочке 24688](cards/kompoziciya-v-shlyapnoy-k-7637/README.md) — 8 фото
- [Композиция в сумочке с цветами 04567](cards/komp-2289/README.md) — 7 фото
- [Композиция в шляпной коробочке, эустома, орхидея, роза кустовая, гипсофила, эвкалипт](cards/kompoziciya-v-shlyapnoy-k-8804/README.md) — 6 фото
- [Композиция роза пионовидная кустовая, эрингиум, маттиола, озотамнус, эвкалипт](cards/kompoziciya-roza-pionovidnaya-/README.md) — 8 фото

## Букеты невесты

- [Букет невесты, дофаминовый](cards/buket-nevesty-3482/README.md) — 2 фото
- [Букет невесты](cards/buket-nevesty-1149/README.md) — 8 фото

## Цветы в корзине

- [Композиция премиум в корзине с цветами](cards/kompoziciya-premium-v-korzine-/README.md) — 6 фото
- [Акция! Композиция в корзине астра, подсолнух, хризантема, гринтрик, эустома, маттиола, диантус, ромашка кустовая](cards/kompoziciya-v-korzine-astra-po/README.md) — 7 фото
- [Премиум композиция в корзине ароматный пион, роза пионовидная кустовая, орхидея, роза, эвкалипт](cards/buketik-premium-v-korzine/README.md) — 6 фото
- [Композиция в корзине](cards/buketik-cvetov-v-korzine/README.md) — 6 фото
- [Композиция в корзине гортензия, роза, роза пионовидная кустовая, пион, эвкалипт](cards/buket-v-korzine-exclusive/README.md) — 6 фото
- [Акция! Композиция в корзине ромашка кустовая, маттиола, эустома, эвкалипт](cards/kompoziciya-v-korzine-rom-4151/README.md) — 8 фото
- [Премиум композиция в корзине Осень](cards/premium-kompoziciya-v-kor-2521/README.md) — 8 фото
- [Композиция ароматных огромных пионов в корзине с эвкалиптом](cards/kompoziciya-aromatnyh-ogromnyh/README.md) — 6 фото

## Наборы с цветами

- [Набор пионов с конфетами Raffaello](cards/buket-aromatniy-pion-evkalipt-/README.md) — 7 фото
- [Набор конфеты Merci c букетом пионов](cards/nabor-konfety-merci-c-buketom-/README.md) — 8 фото

## Цветы в ящиках

- [Композиция в сумочке с цветами 678899](cards/kompoziciya-v-sumochke-s--9069/README.md) — 8 фото

**Исключённый владельцем товар №4183 не включён.**

Полный архив, скрытые и сезонные позиции Flowwow Seller неизвестны.

