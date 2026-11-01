# Flowwow Parser Review3 — объединение исправлений Arena и строгого трёхтоварного пилота

Этот каталог — **изолированный кодовый аудит**, а не изменения рабочего магазина.

## Происхождение
- Исправленные исходники Arena Review2: public `tophqru/aromatny-flowwow-public-audit`, commit `2c6c79251be07355d5d6b864a1e48b73ec6a8cb6`, `arena-output/flowwow-parser-review2-independent-20261101/source/flowwow_review2/`. Все неизменённые файлы в этом Review3 использовали те же Git blob SHA, без пересборки/подмены.
- `pilot_targets.py` и `tests/test_pilot_targets.py` из private `tophqru/flower-shop` PR #9, SHA `74dcb841dd5bb8555a8aa4817870a8c1cf8db65a`. В новой версии перенесено 16 ранее проверенных сценариев.
- `capture.py` вручную интегрирован с Arena 85-test кодом: strict `--pilot-manifest`, три точных SKU, локальная SQLite-блокировка, SHA Git blob зафиксированного исходного JSON, отсутствие случайных загрузок индексных кандидатов при явном `--baseline`.
- Исходный public snapshot `catalog/public-snapshot.json`, pinned commit `864f6e222ea58cfed063f6594f896edb67ed8e7f`, blob SHA `b1ba9fbe10b7961d35a723d40af01686a0e10b78`; private import `ac74ac06983eff5b4cdd72e8cd11433baf1d7240`. Эти ссылки **не означают** доказательство актуальности живых страниц.

## Проверки
Заявленная цель: 53 baseline +32 Arena +16 strict pilot = **101 offline unittest**. В отличие от прошлых версий, объединённый код нельзя считать проверенным, пока GitHub Actions или локальный Python не выдаст фактическое `Ran 101 tests ... OK`. Workflow: `.github/workflows/flowwow-review3-tests.yml`. Все тесты offline; браузерная, Windows PowerShell и живая проверка Flowwow — **NOT_PERFORMED**.

## ASUS — единственный исполнитель живого пилота
На ASUS Windows 10 (8 GB RAM, i3) установлен Codex Desktop. Рабочий Compaq подключается к ASUS через Tailscale, но **парсер и GUI Playwright должны выполняться локально на ASUS в активном пользовательском сеансе**, а не в браузере Compaq. Tailscale предоставляет сетевой маршрут, не подменяет среду запуска. Не запускайте Codex/parsing параллельно на двух компьютерах и не используйте профили обычного Chrome. Один headed браузер/одна вкладка, ограниченное ожидание, не обновлять магазин при 403/CAPTCHA. Установку зависимостей, реальные Win10 команды и запуск должен выполнить Codex (после успешного CI).

## Что ещё НЕ реализовано и требует независимого аудита
- `record_product()` ещё не кликает «Показать ещё» внутри описания, состав/размеры или каждую миниатюру/полноэкранное фото. Лишь DOM-кандидаты; галерею запрещено помечать complete.
- Вложенные scroll containers, SPA-подгрузка и видимые кнопки по реальному Flowwow ещё не проверены.
- Скачать image через `context.request.get().body()` всё ещё означает полную буферизацию до проверки длины; нужен ограниченный потоковый механизм до разрешения массового обхода.
- Код `crawl` 0 означает окончание batch, а не успешные три seller-verified товара. Требуется явный пилотный acceptance result до GitHub-delivery.
- Нет автоматической записи в GitHub в самом парсере: Codex создаёт только очищенную дельту в отдельной ветке/PR #9, не трогая `main`, 435 JPG, sale flags, stock/prices.

[Новое задание Arena Round3](ARENA_ROUND3_TASK.md) проверяет это и ищет самостоятельные ошибки. Нельзя auto-merge и запускать полный каталог.
