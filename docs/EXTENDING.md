# Расширение AstroBridge

## Структура

```text
src/astrobridge/
  config.py       настройки, proxy modes, проверка URL
  catalog.py      сервисы, схемы операций, capability discovery
  network.py      общий HTTP-клиент, прокси, TLS, лимиты, raw-ответы
  providers.py    протокольные адаптеры TAP/MAST/Horizons/литературы/VO
  tables.py       VOTable, типы/маски/единицы, нормализация API-таблиц
  core.py         выполнение, история, SHA-256, кэш, экспорт
  cli.py          argparse, JSON stdout, JSONL, коды завершения
  gui.py          Qt-формы по схемам, QThread, таблица и настройки
```

Зависимости направлены от GUI/CLI к Bridge, затем к адаптеру и Transport. Адаптеры не должны импортировать GUI. Поэтому ядро и CLI работают без Qt.

## Добавить TAP без кода

В `services` конфигурации добавьте новый ключ:

```json
{
  "my_catalog": {
    "label": "My catalog",
    "kind": "tap",
    "url": "https://REPLACE_WITH_REAL_HOST/tap",
    "table": "schema.catalog",
    "ra_column": "ra",
    "dec_column": "dec",
    "columns": "source_id,ra,dec",
    "release": "Explicit release label"
  }
}
```

Минимум — `kind` и `url`. Остальное задаёт defaults для cone search и provenance. При переопределении встроенного ключа поля объединяются с его исходным описанием. Изменение endpoint/настроек провайдера меняет cache key.

Для SIA 1/SSA достаточно `kind=sia`/`kind=ssa` и реального endpoint. Формы и список поддерживаемых операций появятся автоматически. Параметры новых сервисов сохраняются только при явном сохранении конфигурации.

## Новый протокол или операция

Python API предоставляет два регистратора:

```python
from astrobridge.catalog import register_operation, spec, TEXT
from astrobridge.providers import register_handler
from astrobridge.tables import from_rows

def search_adapter(service, operation, params, limit, transport):
    # ВАЖНО: только предоставленный transport, никаких requests.get в обход него.
    response = transport.request(
        "GET", service["url"],
        params={"query": params["query"], "limit": limit},
    )
    data = response.json()
    result = from_rows(data["items"], limit=limit)
    result.metadata["total"] = data.get("total")
    if data.get("total", len(data["items"])) > len(result.table):
        result.truncated = True
        result.warnings.append("There are more remote rows; implement pagination.")
    return result

def install_extension():
    register_operation(
        "myarchive.search",
        spec(["query"], {"query": TEXT("Archive query")}, {"query": "star"}),
        kinds={"myarchive"},
    )
    register_handler("myarchive", search_adapter)
```

Это пример интерфейса расширения, **не реализация существующего внешнего архива**: замените формат HTTP-запроса/ответа на документированный формат своего сервиса.

Выполните `install_extension()` **до создания Bridge и до CLI main**. Для собственного CLI wrapper:

```python
from my_extension import install_extension
from astrobridge.cli import main

install_extension()
raise SystemExit(main())
```

В конфигурации добавьте сервис с `kind=myarchive`. После регистрации `schema`/`providers` и GUI используют добавленную операцию. Новая операция должна иметь совместимую со схемами GUI структуру params: string, number, integer, boolean, enum, array/object. Для сложных вложенных схем используйте JSON-режим; стандартный генератор форм оптимизирован под встроенные операции.

Автоматическое обнаружение сторонних пакетов через entry points пока не реализовано: расширение подключается явным импортом. Произвольные имена Python-модулей из JSON-конфигурации не исполняются.

## Контракт адаптера

```text
handler(service: dict, operation: str, params: dict,
        limit: int, transport: Transport) -> Result
```

`Result`:

- `table`: Astropy Table или None для нетабличной операции;
- `metadata`: JSON-совместимые сведения о запросе/результате;
- `warnings`: список осмысленных предупреждений;
- `truncated`: явный признак усечения/следующей страницы.

Возвращаемая таблица должна сохранять маски, unit, description и по возможности UCD. Не заменяйте отсутствующие величины нулями. Вложенные API-объекты можно сохранить JSON-строками с явным описанием формата. Не преобразуйте большие идентификаторы через float.

`transport.request(method, url, ...)` использует общий прокси, timeouts, TLS, ограничение размера и сохраняет raw. Для повторяемого поискового POST можно передать `retry_read=True`; для создания серверного задания это делать нельзя. `transport.download` потоково сохраняет файл с ограничением размера. `transport.check()`/`wait()` обеспечивают отмену между этапами.

При дополнительных собственных сетевых циклах явно ограничивайте число итераций/время. Уважайте `Retry-After` и условия нагрузки сервиса. В адаптере используйте `BridgeError(code, message, retryable=...)`, не вставляйте exception текст библиотек с возможными credentials в пользовательские сообщения.

Если используете astroquery в будущем, подключайте транспорт ко **всем** используемым клиентам/сессиям, включая вложенные служебные запросы. Не меняйте глобальные singleton-сессии в GUI-потоках и не считайте, что установка одного HTTP_PROXY доказывает отсутствие сетевых обходов. Добавьте проверку с недоступным прямым endpoint и доступным тестовым proxy.

## Что проверить для нового адаптера

1. Схема отклоняет некорректный запрос до обращения к сервису.
2. Пустой результат отличается от ошибки HTTP/API.
3. Серверные лимиты, страницы и локальное усечение явно отражены.
4. Авторизация не записывается в argv, manifest, request или сообщения ошибок.
5. HTTP/HTTPS/SOCKS-прокси применяются ко всем запросам.
6. Идентификаторы, маски, единицы и исходные ответы не теряются.
7. Timeout/отмена не оставляют успешную таблицу из неполных данных.
8. Новые научные преобразования, если они нужны, отделены от получения исходных данных.

Используйте локальный тестовый сервер по примеру `tests/conftest.py`; для проверки внешнего endpoint — отдельный ограниченный smoke test. Отмечайте, что именно было проверено: наличие endpoint, метаданные, реальные строки, download, auth или все этапы.

