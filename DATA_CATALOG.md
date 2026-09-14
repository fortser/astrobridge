# AstroBridge: полный каталог доступных данных и CLI-запросов

Версия программы: **0.1.0**. Дата составления и снимка каталогов: **14 сентября 2026 года**.

Этот документ описывает возможности **реализованной программы**, а не все возможности сайтов, библиотек astroquery/pyvo или архивов вообще. Синтаксис машинного протокола подробно описан в [README_LLM.md](README_LLM.md).

## 1. Что означает «полный список»

- В документе перечислены все 13 встроенных источников и все 13 операций JSON-запросов текущей версии; данные сгруппированы по научному содержанию, архиву и способу получения.
- Для шести TAP-архивов приложены **полные полученные ответы со списками таблиц**, а не только подборка популярных каталогов: суммарно **66 577 строк метаданных**. Они включают служебные таблицы и возможные повторения; это не число уникальных научных наборов.
- Таблицы и их поля меняются. Не существует постоянного конечного перечня «всех данных»: новые каталоги появляются в VizieR, архивы публикуют новые наблюдения, а пользователь может подключить дополнительный TAP-сервис.
- Полнота здесь имеет проверяемую границу: текущие адаптеры, сохранённый снимок метаданных и команды для получения актуального перечня таблиц и полей. Не каждая перечисленная таблица проверена отдельной научной выборкой.
- **Табличные параметры**, **метаданные наблюдений**, **ссылки на файлы** и **содержимое файлов** — разные результаты. Найденная запись не гарантирует доступность соответствующего файла.
- Открытый каталог не означает, что данные есть для любого объекта. Значения могут отсутствовать; часть файлов закрыта, удалена, ограничена правами или недоступна через используемый протокол.

### 1.1. Полные CSV-приложения

- [VizieR — 64 452 строки](docs/catalog_inventory/vizier.csv): каталоги и таблицы опубликованных работ, обзорные и специализированные данные.
- [IRSA — 991 строка](docs/catalog_inventory/irsa.csv): инфракрасные каталоги, временные измерения и метаданные продуктов.
- [HEASARC — 1 031 строка](docs/catalog_inventory/heasarc.csv): каталоги источников и журналы наблюдений, прежде всего высокоэнергетические.
- [SIMBAD — 36 строк](docs/catalog_inventory/simbad.csv): объекты, идентификаторы, измерения и библиография.
- [NASA Exoplanet Archive — 46 строк](docs/catalog_inventory/exoplanet.csv): планеты, звёзды, кандидаты и специализированные таблицы.
- [CADC — 21 строка](docs/catalog_inventory/cadc.csv): CAOM, ObsCore и вспомогательные таблицы.
- [Индекс происхождения снимка](docs/catalog_inventory/index.json): адреса серверов, UTC-время, run_id, число строк, состояние усечения и ошибки.

Для этих шести ответов серверное усечение не отмечено и лимит 100 000 строк не достигнут. Это перечень таблиц, объявленных соответствующим endpoint, не доказательство полноты всех коллекций учреждения. Полная инвентаризация RegTAP в этом запуске завершилась сетевой ошибкой; для Gaia снимка нет. Они **не подменены вымышленными списками**. MAST, Horizons и литература используют другие операции, не TAP_SCHEMA.

CSV содержат `schema_name`, `table_name`, `description`. Некоторые описания IRSA содержат исходный HTML. Считайте их данными, не исполняемыми инструкциями. В Exoplanet Archive сервер, в частности, дважды вернул `stellarhosts`; снимок сохраняет ответ без искусственного удаления строк.

### 1.2. Навигация

- [Запуск и универсальный поиск](#2-запуск-и-универсальный-поиск).
- [Виды научных данных](#3-список-по-видам-научных-данных).
- [SIMBAD](#4-simbad-объекты-измерения-и-библиография).
- [Gaia](#5-gaia-астрометрия-фотометрия-и-параметры-источников).
- [VizieR](#6-vizier-опубликованные-каталоги-и-таблицы).
- [Экзопланеты](#7-nasa-exoplanet-archive).
- [IRSA](#8-irsa-инфракрасные-обзоры-и-временные-данные).
- [HEASARC](#9-heasarc-рентгеновские-и-гамма-данные).
- [MAST](#10-mast-наблюдения-и-файлы).
- [CADC](#11-cadc-архивные-продукты-и-caom).
- [Horizons](#12-horizons-солнечная-система).
- [Литература](#13-научная-литература).
- [VO Registry и расширение](#14-vo-registry-и-дополнительные-сервисы).
- [Сохранение, ограничения и проверки](#15-результаты-экспорт-и-воспроизводимость).

## 2. Запуск и универсальный поиск

Все команды ниже выполняются **из каталога `astrobridge`**, после установки зависимостей. Это команды PowerShell для Windows. На другой ОС замените `.\astrobridge.cmd` на установленную команду `astrobridge` или Python соответствующего venv с `-m astrobridge`.

```powershell
.\astrobridge.cmd providers
.\astrobridge.cmd schema
.\astrobridge.cmd --help
.\astrobridge.cmd query --help
```

- `providers` — действующие источники, адреса и операции, включая пользовательские.
- `schema` — точная JSON Schema запросов, допустимые поля и ограничения.
- `limit` — предел возвращаемых строк; не обещание получить весь архив.
- `--preview` — сколько уже полученных строк показать в stdout; остальные остаются на диске.
- `--workspace`, `--config`, `--proxy`, `--timeout`, `--direct` ставятся **перед командой**.
- Все углы `cone` — десятичные градусы ICRS: `0.01° = 36″`. Нельзя передавать часы RA вместо градусов.
- Примеры `TOP 5` предназначены для разведки структуры. Без `ORDER BY` это не стабильная и не статистически репрезентативная выборка.

### 2.1. Узнать любые таблицы и все их поля

```powershell
.\astrobridge.cmd tables irsa --contains "WISE" --limit 1000
.\astrobridge.cmd tables heasarc --contains "Chandra" --limit 1000
.\astrobridge.cmd columns irsa allwise_p3as_psd --limit 1000
.\astrobridge.cmd query irsa --adql "SELECT TOP 5 * FROM allwise_p3as_psd" --limit 5
```

- `tables` возвращает имена схем, таблиц и их описания.
- `columns` возвращает имена полей, типы, единицы, UCD и описания, если сервер их публикует.
- `SELECT TOP 5 *` возвращает все поля пяти записей. Перед большой выгрузкой замените `*` на необходимые поля.
- Поиск `--contains` использует серверный `LIKE`: чувствительность к регистру зависит от сервера; отсутствие совпадений не доказывает отсутствие данных.
- Имена с `/`, пробелами и специальными символами требуют ADQL-кавычек. Для VizieR используйте готовый JSON-файл: это исключает потерю двойных кавычек при передаче через Windows shell.

### 2.2. Единый JSON-запрос

Готовый файл [exoplanet_planets.json](examples/catalog/exoplanet_planets.json):

```json
{
  "service": "exoplanet",
  "operation": "tap.query",
  "params": {
    "query": "SELECT TOP 5 pl_name,hostname,pl_orbper,pl_rade,pl_bmasse,pl_eqt,st_teff,st_rad,st_mass,sy_dist FROM pscomppars WHERE pl_rade IS NOT NULL"
  },
  "limit": 5
}
```

```powershell
.\astrobridge.cmd run examples/catalog/exoplanet_planets.json
.\astrobridge.cmd --timeout 120 run examples/catalog/exoplanet_planets.json --no-cache
```

Для LLM предпочтителен запуск процесса со списком аргументов, без shell; JSON можно передать в stdin команды `run -`. Большие запросы ADQL можно хранить в UTF-8-файле и передавать через `query SERVICE --file PATH`.

### 2.3. Прокси

```powershell
.\astrobridge.cmd --proxy socks5h://127.0.0.1:1080 resolve M31
.\astrobridge.cmd --proxy http://127.0.0.1:8080 run examples/catalog/mast_jwst.json
.\astrobridge.cmd --direct resolve M31
```

- Первые две команды требуют реально работающий локальный прокси на указанном порту; программа сама его не создаёт.
- Для логина и пароля используйте переменную окружения `ASTROBRIDGE_PROXY` и ручной режим конфигурации, описанный в [README_LLM.md](README_LLM.md), а не аргумент командной строки или JSON запроса.
- `socks5h` передаёт разрешение имени на прокси. `--direct` явно отключает прокси.
- Прокси применяется к запросам, опросу TAP-заданий и скачиванию. Автоматического перехода на прямое соединение при отказе ручного прокси нет.
- Прокси не предоставляет прав на закрытые данные и не гарантирует снятие ограничений архива.

## 3. Список по видам научных данных

В каждом пункте источник означает маршрут получения, а не гарантию заполнения всех перечисленных величин у каждого объекта. Точные поля, единицы, релиз и флаги определяются выбранной таблицей.

- **Идентификация и классификация объектов**:
  - Основное имя, альтернативные обозначения, идентификаторы каталогов: SIMBAD `basic`, `ident`, `ids`.
  - Тип объекта, дополнительные классификации, иерархические связи: SIMBAD `otypes`, `alltypes`, `h_link`.
  - Идентификаторы наблюдений, программ и архивных продуктов: MAST, CADC, HEASARC.
- **Положение и движение**:
  - RA/Dec, ошибки координат, параллаксы, собственные движения, корреляции и качество астрометрии: Gaia; соответствующие каталоги VizieR.
  - Измеренные расстояния, собственные движения и параллаксы из публикаций: SIMBAD `mesDistance`, `mesPM`, `mesPLX`.
  - Лучевые скорости и красные смещения: Gaia, SIMBAD `mesVelocities`, каталоги VizieR.
  - Положение и скорость тел Солнечной системы во времени: Horizons.
- **Фотометрия и спектральное распределение энергии**:
  - Звёздные величины, потоки, ошибки, верхние пределы, качество измерений: SIMBAD, Gaia, VizieR, IRSA.
  - Оптическая фотометрия: Gaia, Pan-STARRS, SDSS и другие опубликованные таблицы VizieR.
  - Ближний ИК: 2MASS; средний ИК: WISE/AllWISE/NEOWISE, Spitzer; дальний ИК: AKARI/Herschel и связанные таблицы IRSA.
  - Радио-, микроволновые, УФ-, рентгеновские и гамма-потоки: соответствующие каталоги VizieR/HEASARC/IRSA и продукты архивов.
  - Готовые измерения SED — когда опубликованы; автоматического объединения разнородной фотометрии в согласованную SED нет.
- **Физические параметры звёзд**:
  - Температура, поверхностная гравитация, металличность, отдельные химические abundances: специализированные таблицы Gaia/VizieR; SIMBAD `mesFe_h`.
  - Спектральный класс, вращение, угловой диаметр: SIMBAD `mesSpT`, `mesRot`, `mesDiameter`.
  - Масса, радиус, светимость, возраст, поглощение и расстояние: каталоги модельных оценок Gaia/VizieR/Exoplanet Archive, если включены в конкретный набор.
  - Двойные/кратные системы и орбитальные решения: специализированные таблицы Gaia и VizieR.
- **Переменность и временные ряды**:
  - Классы переменности, периоды, амплитуды и параметры моделей: Gaia, SIMBAD `mesVar`, VizieR.
  - Кривые блеска, временные FITS-продукты и пиксельные ряды: MAST, если продукт присутствует и открыт.
  - Отдельные эпохи ИК-фотометрии: NEOWISE в IRSA; PTF/ZTF — опубликованные таблицы и метаданные доступных продуктов.
  - Транзитные события, кандидаты и сводные параметры: Exoplanet Archive.
  - События вспышек, GRB, мониторинг и исторические временные каталоги: HEASARC/VizieR.
- **Спектры и спектроскопия**:
  - Табличные параметры спектров и линий, классификации, redshift, скорости: SIMBAD/VizieR/Gaia/HEASARC.
  - Передаточные и эмиссионные спектры атмосфер экзопланет: Exoplanet Archive.
  - Одномерные спектры, спектральные кубы, калибровочные продукты: открытые файлы MAST/CADC/IRSA и подключённых SSA-сервисов.
  - Спектральные массивы не возникают автоматически из записи «объект наблюдался спектрографом»: нужен конкретный доступный файл.
- **Изображения и пространственно разрешённые данные**:
  - Обработанные и необработанные изображения, мозаики, карты, error/weight/mask extensions: архивные файлы, если опубликованы.
  - WCS, заголовки, детекторные массивы: внутри загруженного FITS; их интерпретация отдельным кодом.
  - Спектральные и многомерные кубы: файлы соответствующих наблюдений.
  - Поля зрения и покрытия, координаты центров, временные/спектральные границы: MAST/CADC/ObsCore/SIA.
- **Экзопланеты**:
  - Подтверждённые планеты, кандидаты, методы и обстоятельства открытия.
  - Период, большая полуось, эксцентриситет, наклонение и транзитные параметры.
  - Масса/минимальная масса, радиус, плотность, равновесная температура, облучение.
  - Параметры звезды, системы, фотометрия, расстояние, ссылки на публикации.
  - Атмосферные измерения, микролинзовые системы, наблюдательные списки: специализированные таблицы Exoplanet Archive.
- **Галактики, AGN и космология**:
  - Положения, redshift, фотометрия, размеры, морфология, линии и производные параметры — по опубликованным каталогам VizieR/SIMBAD/HEASARC.
  - Квазары, активные ядра, скопления, гравитационные линзы, сверхновые, стандартные свечи — поиск специализированных таблиц VizieR.
  - Каталоги компактных источников и SZ-кандидатов Planck: IRSA; карты и космологические likelihood-файлы не являются автоматически встроенной функцией.
- **Высокоэнергетическая астрофизика**:
  - Рентгеновские/гамма-источники, положения, потоки, диапазоны энергии, спектральные характеристики и переменность — HEASARC.
  - Журналы наблюдений, экспозиции, приборы, режимы, доступные файлы событий — соответствующие миссии.
  - GRB, транзиенты, пульсары, двойные системы — специализированные каталоги.
- **Солнечная система**:
  - Эфемериды, декартовы векторы, оскулирующие элементы, наблюдательные величины — Horizons.
  - Каталожные измерения малых тел и параметры орбит — VizieR; специализированные Gaia-таблицы после проверки схемы.
- **Библиография и происхождение**:
  - Название, авторы, год, DOI, аннотация, число цитирований — поддерживаемые поля ADS.
  - DOI-метаданные и библиографические связи — Crossref.
  - Препринты и аннотации — arXiv.
  - Связь объекта с публикациями — SIMBAD; библиографические поля научных каталогов.
- **Метаданные инфраструктуры**:
  - Таблицы, столбцы, типы, единицы, UCD — TAP_SCHEMA.
  - VO-ресурсы, типы протоколов, адреса доступа — RegTAP.
  - Локальные запросы, ответы серверов, контрольные суммы, история и ошибки — AstroBridge.

## 4. SIMBAD: объекты, измерения и библиография

Источник: `simbad`. Полный перечень имён и серверных описаний: [simbad.csv](docs/catalog_inventory/simbad.csv).

- **Основные сведения**:
  - `basic` — основная запись объекта, координаты и сводные характеристики.
  - `ident`, `ids`, `cat` — идентификаторы, их сводные представления и каталоги.
  - `otypes`, `alltypes`, `otypedef`, `mesOtype` — классификации и определения типов.
  - `h_link` — связи объектов; не автоматически вычисленный физический состав системы.
- **Фотометрия**:
  - `flux`, `allfluxes`, `filter` — измерения, сводные величины и фильтры.
  - В `allfluxes` представлены, в частности, U/B/V/I/J/H/K и обозначенные в схеме оптические полосы; реальные названия полей проверяйте `columns`.
- **Опубликованные измерения**:
  - `mesDiameter` — диаметры.
  - `mesDistance` — расстояния.
  - `mesFe_h` — металличность, температура, гравитация в соответствующих измерениях.
  - `mesPLX`, `mesPM` — параллаксы и собственные движения.
  - `mesRot`, `mesSpT`, `mesVar` — вращение, спектральные типы, переменность.
  - `mesVelocities` — скорости и красные смещения.
  - `mesHerschel`, `mesISO`, `mesIUE`, `mesXmm` — связанные измерения/сведения по указанным миссиям; не универсальная выгрузка всех их файлов.
- **Библиография**:
  - `biblio`, `has_ref`, `ref`, `author`, `journals`, `keywords` — ссылки, связи, авторы, журналы и ключевые слова.
- **Служебные таблицы**:
  - `TAP_SCHEMA.schemas`, `tables`, `columns`, `keys`, `key_columns` — схема и связи.

```powershell
.\astrobridge.cmd resolve M31
.\astrobridge.cmd cone simbad --ra 10.6847 --dec 41.269 --radius 0.02 --limit 20
.\astrobridge.cmd columns simbad basic --limit 1000
.\astrobridge.cmd query simbad --adql "SELECT TOP 1 * FROM basic WHERE main_id='M  31'" --limit 1
.\astrobridge.cmd query simbad --adql "SELECT TOP 20 i.id FROM ident AS i JOIN basic AS b ON i.oidref=b.oid WHERE b.main_id='M  31'" --limit 20
.\astrobridge.cmd query simbad --adql "SELECT TOP 5 * FROM mesFe_h" --limit 5
.\astrobridge.cmd query simbad --adql "SELECT TOP 5 * FROM allfluxes" --limit 5
.\astrobridge.cmd query simbad --adql "SELECT TOP 5 * FROM mesVelocities" --limit 5
.\astrobridge.cmd columns simbad has_ref --limit 1000
```

`resolve` возвращает только `main_id`, `ra`, `dec`, `otype`; для остальных полей нужен ADQL. Точное имя `M  31` содержит два пробела и получено из SIMBAD, а не угадано по пользовательскому обозначению. Перед JOIN другой таблицы смотрите её колонки и ключи.

## 5. Gaia: астрометрия, фотометрия и параметры источников

Источник: `gaia`; встроенная основная таблица — `gaiadr3.gaia_source`. Для текущего соединения ESA ранее возвращал timeout, поэтому примеры этого раздела не объявляются успешно выполненными в сети.

- Основная астрометрия: `source_id`, RA/Dec, параллакс, собственные движения, ошибки, корреляции, параметры решения и качество.
- Средняя фотометрия G/BP/RP, потоки, ошибки, цвета, число измерений и диагностические признаки.
- Лучевая скорость и связанные поля для источников с соответствующими измерениями.
- Астрофизические оценки: параметры атмосферы, поглощение и другие модельные величины в `gaiadr3.astrophysical_parameters` и связанных таблицах.
- Переменные источники, классификации и параметры по типам переменности: семейство `vari_*`.
- Некратность/кратность и орбитальные решения: семейство `nss_*`.
- Источники Солнечной системы и их наблюдения: семейство `sso_*`.
- Кросс-сопоставления и специализированные выборки: таблицы соответствующего релиза.

Состав семейств и научные определения сверяются с [документацией Gaia DR3](https://gea.esac.esa.int/archive/documentation/GDR3/). Наличие в архиве спектров XP/RVS и эпохальной фотометрии **не означает**, что текущая программа умеет получать их через отдельный Gaia DataLink API: такого адаптера здесь нет. Доступны TAP-таблицы и обычные открытые файловые URL, когда они действительно предоставлены.

```powershell
.\astrobridge.cmd tables gaia --contains "gaiadr3" --limit 1000
.\astrobridge.cmd columns gaia gaiadr3.gaia_source --limit 1000
.\astrobridge.cmd cone gaia --ra 56.75 --dec 24.12 --radius 0.03 --limit 100
.\astrobridge.cmd query gaia --adql "SELECT TOP 20 source_id,ra,dec,parallax,parallax_error,pmra,pmdec,phot_g_mean_mag,ruwe FROM gaiadr3.gaia_source WHERE parallax>20 AND parallax_over_error>10 AND ruwe<1.4" --limit 20
.\astrobridge.cmd run examples/catalog/gaia_astrophysics.json
.\astrobridge.cmd tables gaia --contains "vari_" --limit 1000
.\astrobridge.cmd tables gaia --contains "nss_" --limit 1000
.\astrobridge.cmd tables gaia --contains "sso_" --limit 1000
```

Пороги `parallax_over_error>10`, `ruwe<1.4` — пример фильтра, не универсальный стандарт качества. Не превращайте отрицательный параллакс в «отрицательное физическое расстояние» и не применяйте `1/parallax` без оценки ошибок и систематики. В JSON большие `source_id` могут быть строками для предотвращения потери точности.

## 6. VizieR: опубликованные каталоги и таблицы

Источник: `vizier`. **Все 64 452 записи снимка** находятся в [vizier.csv](docs/catalog_inventory/vizier.csv); ниже только маршруты по содержанию.

- Астрометрические каталоги:
  - `I/355/gaiadr3` — Gaia DR3.
  - `I/259/tyc2` — Tycho-2.
  - `I/311/hip2` — новая редукция Hipparcos.
- Фотометрические и обзорные каталоги:
  - `II/246/out` — 2MASS Point Source Catalog.
  - `II/328/allwise` — AllWISE.
  - `II/349/ps1` — Pan-STARRS DR1.
  - `V/147/sdss12`, `V/154/sdss16` — соответствующие каталоги SDSS.
  - `IV/38/tic` — TESS Input Catalog v8; это каталог объектов, не TESS-кривая блеска.
- Спектроскопические исследования: параметры звёзд и объектов, скорости, abundances, классификации, линии; ищите LAMOST, APOGEE, GALAH, RAVE и название нужной работы.
- Радиокаталоги: положения, потоки, размеры, спектральные индексы — если опубликованы в выбранной таблице; ищите NVSS/FIRST и названия обзоров.
- Специализированные выборки: звёздные скопления, переменные, двойные, белые карлики, молодые звёзды, галактики, AGN, квазары, линзы, сверхновые, GRB и малые тела.
- Таблицы отдельных статей: результаты измерений, параметры моделей, выборки объектов, сопоставления и библиографические ссылки.
- Наличие спектральных параметров или фотометрии не гарантирует публикацию исходного спектра/изображения в TAP. При наличии файловых ссылок используйте отдельную загрузку.

```powershell
.\astrobridge.cmd run examples/catalog/vizier_2mass.json
.\astrobridge.cmd run examples/catalog/vizier_2mass_columns.json
.\astrobridge.cmd tables vizier --contains "LAMOST" --limit 1000
.\astrobridge.cmd tables vizier --contains "APOGEE" --limit 1000
.\astrobridge.cmd tables vizier --contains "GALAH" --limit 1000
.\astrobridge.cmd tables vizier --contains "NVSS" --limit 1000
.\astrobridge.cmd tables vizier --contains "quasar" --limit 1000
.\astrobridge.cmd tables vizier --contains "supernova" --limit 1000
```

Первый JSON содержит `SELECT TOP 5 * FROM "II/246/out"`. Во втором `params.table` равно строке `"II/246/out"` с внутренними кавычками: это точное значение `table_name`, возвращённое TAP_SCHEMA данного сервера.

Для пространственного поиска создайте копию JSON со следующим содержимым. Имена `RAJ2000`/`DEJ2000` относятся именно к этой таблице, а не ко всем каталогам VizieR:

```json
{
  "service": "vizier",
  "operation": "tap.cone",
  "params": {
    "table": "\"II/246/out\"",
    "ra": 56.75,
    "dec": 24.12,
    "radius": 0.05,
    "ra_column": "RAJ2000",
    "dec_column": "DEJ2000",
    "columns": "*"
  },
  "limit": 20
}
```

Включённая в этот документ копия такого запроса: [vizier_2mass_cone.json](examples/catalog/vizier_2mass_cone.json).

```powershell
.\astrobridge.cmd run examples/catalog/vizier_2mass_cone.json
```

## 7. NASA Exoplanet Archive

Источник: `exoplanet`. Полный снимок: [exoplanet.csv](docs/catalog_inventory/exoplanet.csv).

### 7.1. Какие величины можно получить

- Планета и система: имя, звезда-хозяин, число компонентов/планет, координаты, расстояние.
- Открытие: метод, год, инструменты/обсерватория, ссылки и флаги обнаружения.
- Орбита: период, большая полуось, эксцентриситет, наклонение, эпохи и связанные ошибки.
- Планета: масса или её оценка, радиус, плотность, равновесная температура, облучение; происхождение величины нужно проверять.
- Транзит/RV: глубина, длительность, отношение радиусов, полуамплитуда и другие доступные параметры.
- Звезда: температура, масса, радиус, металличность, гравитация, возраст, фотометрия — где опубликованы.
- Атмосфера: опубликованные трансмиссионные и эмиссионные измерения.

Названия и определения полей: [официальный словарь PS/PSCompPars](https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html). `ps` хранит решения из отдельных источников, `pscomppars` объединяет параметры и может смешивать публикации. Одна строка composite-таблицы не обязательно является единым согласованным решением.

```powershell
.\astrobridge.cmd run examples/catalog/exoplanet_planets.json
.\astrobridge.cmd columns exoplanet pscomppars --limit 1000
.\astrobridge.cmd query exoplanet --adql "SELECT TOP 5 * FROM ps WHERE pl_name='TRAPPIST-1 e'" --limit 5
.\astrobridge.cmd query exoplanet --adql "SELECT TOP 5 * FROM transitspec" --limit 5
.\astrobridge.cmd query exoplanet --adql "SELECT TOP 5 * FROM emissionspec" --limit 5
.\astrobridge.cmd cone exoplanet --ra 346.622 --dec -5.041 --radius 0.1 --limit 20
```

### 7.2. Все семейства таблиц снимка

- Подтверждённые планеты и звёзды:
  - `ps`, `pscomppars`, `stellarhosts`.
  - `ml` — микролинзовые планеты.
  - `object_aliases`, `keplernames`, `k2names` — обозначения и сопоставления.
- Кандидаты и транзитные выборки:
  - `toi`, `k2pandc`, `CUMULATIVE`.
  - `Q1_Q6_KOI`, `Q1_Q8_KOI`, `Q1_Q12_KOI`, `Q1_Q16_KOI`.
  - `Q1_Q17_DR24_KOI`, `Q1_Q17_DR25_KOI`, `Q1_Q17_DR25_SUP_KOI`.
  - `Q1_Q12_TCE`, `Q1_Q16_TCE`, `Q1_Q17_DR24_TCE`, `Q1_Q17_DR25_TCE`.
  - `TD` — Transit Detection Table.
- Звёздные/целевые выборки Kepler/K2:
  - `KEPLERSTELLAR`, `K2TARGETS`.
  - `Q1_Q12_KS`, `Q1_Q16_KS`, `Q1_Q17_DR24_KS`, `Q1_Q17_DR25_KS`, `Q1_Q17_DR25_SUP_KS`.
- Спектроскопия и наблюдения:
  - `transitspec`, `emissionspec`, `spectra`.
  - `nexolist`, `observations`, `pandora`, `DI_STARS_EXEP` — специальные списки/программы; состав уточняется по `columns` и серверному описанию.
- Временные данные:
  - `KEPLERTIMESERIES`, `kelttimeseries`, `superwasptimeseries`, `ukirttimeseries`.
  - Эти названия не означают, что любая строка содержит весь временной ряд: проверяйте, возвращены ли сами измерения или ссылки/описания.
- Служебные: пять таблиц `TAP_SCHEMA` — `schemas`, `tables`, `columns`, `keys`, `key_columns`.

```powershell
.\astrobridge.cmd query exoplanet --adql "SELECT TOP 5 * FROM toi" --limit 5
.\astrobridge.cmd query exoplanet --adql "SELECT TOP 5 * FROM ml" --limit 5
.\astrobridge.cmd columns exoplanet KEPLERTIMESERIES --limit 1000
.\astrobridge.cmd query exoplanet --adql "SELECT TOP 5 * FROM nexolist" --limit 5
```

Кандидат не равнозначен подтверждённой планете; разные релизы KOI/TCE нельзя бездумно объединять как независимые объекты.

## 8. IRSA: инфракрасные обзоры и временные данные

Источник: `irsa`; [все 991 запись таблиц](docs/catalog_inventory/irsa.csv). TAP возвращает каталоги и метаданные; доступ к изображениям и спектрам зависит от опубликованных URL. Базовые примеры 2MASS/AllWISE соответствуют [интерфейсу IRSA TAP](https://irsa.ipac.caltech.edu/docs/program_interface/TAP.html).

- **2MASS**:
  - `fp_psc` — точечные источники, координаты, J/H/Ks, ошибки, флаги.
  - `fp_xsc` — протяжённые источники, фотометрия и параметры, предусмотренные схемой.
- **WISE / AllWISE / NEOWISE / unWISE**:
  - `allwise_p3as_psd` — сводный каталог источников.
  - `neowiser_p1bs_psd` — отдельные экспозиционные измерения NEOWISE.
  - `neowiser_p1bs_frm`, `neowiser_p1bm_frm`, `neowiser_p1ba_mch`, `neowiser_p1bl_lod` — связанные таблицы кадров/служебной информации.
  - `unwise_2019`, `unwise.unwise_neo3_images` — каталог и метаданные изображений.
- **Spitzer**:
  - Фотометрические обзоры GLIMPSE/APOGLIMPSE/Deep GLIMPSE и другие программы.
  - Примеры: `glimpse_s07`, `glimpse2_v2cat`, `glimpse360c`, `apoglimpsec`, `deepglimpsec`.
  - Варианты archive/catalog отличаются полнотой и надёжностью, согласно описаниям сервера.
- **AKARI**:
  - `akari_fis`, `akari_irc` — каталоги источников.
  - `akari.akari_images` — метаданные изображений.
- **Herschel**:
  - Изображения и мозаики: например `herschel.hermes_images`, `herschel.hatlas_images`, `herschel.kingfish_images`.
  - Спектры: `herschel.hexos_spectra`, `herschel.hifistars_spectra`, `herschel.hop_spectra`.
  - Спектральные кубы/продукты: `herschel.digit_pacs_cube`, `herschel.hpdp_cubes`, `herschel.hpdp_spectra`.
  - Это таблицы продуктов: содержимое спектра/куба нужно скачивать отдельно по ссылке.
- **Planck**:
  - `com_pccs1_030`, `044`, `070`, `100`, `143`, `217`, `353`, `545`, `857` с общим префиксом `com_pccs1_` — каталоги компактных источников по каналам.
  - `com_pccs1_sz_mmf1` и связанные таблицы — SZ-каталоги; полный список ищите по `com_pccs`.
- **PTF/ZTF**:
  - `ptf_objects`, `ptf_sources`, `ptf_lightcurves` — объекты, измерения и сведения о кривых блеска.
  - `ptf.ptf_procimg`, `ptf.ptf_refims` — метаданные изображений.
  - Семейство `ztf.*` — доступные метаданные продуктов; ищите актуальные таблицы.
  - Не реализован приём потока ZTF alerts или специализированный broker API.
- **Прочие коллекции**: тематические поля, галактические и внегалактические обзоры, сопоставленные каталоги, специализированные результаты отдельных программ — в полном CSV.

```powershell
.\astrobridge.cmd run examples/catalog/irsa_2mass.json
.\astrobridge.cmd cone irsa --table allwise_p3as_psd --ra-column ra --dec-column dec --columns "*" --ra 56.75 --dec 24.12 --radius 0.05 --limit 20
.\astrobridge.cmd query irsa --adql "SELECT TOP 5 * FROM fp_xsc" --limit 5
.\astrobridge.cmd query irsa --adql "SELECT TOP 5 * FROM neowiser_p1bs_psd" --limit 5
.\astrobridge.cmd query irsa --adql "SELECT TOP 5 * FROM akari_fis" --limit 5
.\astrobridge.cmd query irsa --adql "SELECT TOP 5 * FROM com_pccs1_857" --limit 5
.\astrobridge.cmd columns irsa herschel.hpdp_spectra --limit 1000
.\astrobridge.cmd tables irsa --contains "ztf" --limit 1000
.\astrobridge.cmd columns irsa ptf_lightcurves --limit 1000
```

Для кривой блеска NEOWISE отберите область/идентификатор, проверьте время, флаги и единицы в `columns`, затем отсортируйте по фактическому столбцу времени. `TOP 5` без фильтра — только проверка формата, не временной ряд одного объекта.

## 9. HEASARC: рентгеновские и гамма-данные

Источник: `heasarc`; [все 1 031 запись](docs/catalog_inventory/heasarc.csv). Важное различие: **master observation catalog** описывает наблюдения, **source catalog** — обнаруженные источники. Официальный навигатор: [HEASARC Browse catalogs](https://heasarc.gsfc.nasa.gov/W3Browse/all/).

- **Chandra**: `chanmaster` — наблюдения; `csc`, `cscstack` — каталог источников и связанные данные. В снимке `csc` описан как v2.1.1.
- **XMM-Newton**: `xmmmaster` — наблюдения; `xmmssc` — каталог источников. Сервер в этом снимке описывает `xmmssc` как **5XMM-DR15**; нельзя автоматически подписывать результат старым названием 4XMM.
- **NuSTAR**: `numaster` — наблюдения; `nustarssc`, `nustarssc2` — каталоги источников. Реальное имя — `numaster`, не предполагаемое `nustarmaster`.
- **NICER**: `nicermastr` — журнал наблюдений.
- **Swift**: `swiftmastr` — наблюдения; `swift2sxps` — каталог рентгеновских источников.
- **eROSITA**: `erass1main`, `erass1hard`, `erassmastr`, `erosmaster` — опубликованные каталоги/сведения о наблюдениях соответствующего назначения.
- **ROSAT/Suzaku**: `rosmaster`, `suzamaster` и связанные таблицы.
- **Fermi LAT**:
  - `fermilpsc` — в снимке 14-летний 4FGL-DR4.
  - `fermi3fgl`, `fermi3fhl`, `fermifhl` — другие опубликованные каталоги.
  - `fermilac`, `fermil2psr`, `fermilgrb`, `fermilweek`, `fermiltrns` — специализированные выборки AGN/пульсаров/всплесков/переменности согласно описанию каждой таблицы.
- **Fermi GBM**: `fermigbrst`, `fermigtrig`, `fermigdays`, `fermigsol` — всплески, триггеры и связанные продукты.
- **BATSE**: `batse4b`, `batsegrb`, `batsegrbsp`, `batsetrigs`, `batsedaily`, `batsepulsr`, `batseeocat`.
- **Другие миссии и тематические каталоги**: все перечислены в CSV; выбирайте по прибору, объекту, энергетическому диапазону и публикации.

Типы возвращаемых величин зависят от таблицы:

- Координаты, позиционные ошибки, идентификаторы, ассоциации.
- Потоки, ошибки/пределы, спектральные параметры, диапазоны энергии, признаки переменности.
- Время начала/конца, экспозиция, режим, прибор, цель, номер наблюдения.
- Ссылки и идентификаторы продуктов, если опубликованы.
- Сами event lists, спектры, response-файлы и изображения — только отдельной загрузкой найденных открытых файлов; ADQL-таблица их не заменяет.

```powershell
.\astrobridge.cmd run examples/catalog/heasarc_nustar.json
.\astrobridge.cmd query heasarc --adql "SELECT TOP 5 * FROM chanmaster" --limit 5
.\astrobridge.cmd query heasarc --adql "SELECT TOP 5 * FROM csc" --limit 5
.\astrobridge.cmd query heasarc --adql "SELECT TOP 5 * FROM xmmssc" --limit 5
.\astrobridge.cmd query heasarc --adql "SELECT TOP 5 * FROM swift2sxps" --limit 5
.\astrobridge.cmd query heasarc --adql "SELECT TOP 5 * FROM erass1main" --limit 5
.\astrobridge.cmd query heasarc --adql "SELECT TOP 5 * FROM fermilpsc" --limit 5
.\astrobridge.cmd query heasarc --adql "SELECT TOP 5 * FROM fermigbrst" --limit 5
.\astrobridge.cmd columns heasarc numaster --limit 1000
```

## 10. MAST: наблюдения и файлы

Источник: `mast`. Операции: `mast.cone`, `mast.search`, `mast.products`, `download`.

### 10.1. Какие данные возвращает поиск

- Миссия/коллекция, прибор, фильтр, цель, программа/PI, идентификаторы наблюдения.
- Положение, область покрытия, начальное/конечное время, экспозиция, спектральные границы.
- Тип продукта, уровень калибровки и права доступа.
- Категории модели CAOM включают image, spectrum, timeseries, cube, eventlist, catalog, SED, visibility, engineering; наличие конкретной категории зависит от коллекции.
- В MAST `s_ra/s_dec` — градусы, `t_min/t_max` — MJD, `t_exptime` — секунды, `em_min/em_max` — **нанометры**. Не переносите сюда единицы ObsCore автоматически. Определения: [MAST CAOM fields](https://mast.stsci.edu/api/v0/_c_a_o_mfields.html).

### 10.2. Какие файлы можно искать

- HST/JWST: изображения, спектры, кубы и вспомогательные продукты конкретных наблюдений.
- TESS/Kepler/K2: кривые блеска, пиксельные продукты, изображения и другие опубликованные файлы.
- GALEX/IUE/FUSE и другие архивные коллекции — через реально представленные записи поиска.
- Авторские high-level science products, если опубликованы в соответствующей коллекции.
- Точный охват миссий определяется [каталогом MAST](https://archive.stsci.edu/missions-and-data) и ответом сервиса; специальный API каждой миссии в AstroBridge не реализован.

```powershell
.\astrobridge.cmd cone mast --ra 10.6847 --dec 41.269 --radius 0.02 --limit 20
.\astrobridge.cmd run examples/catalog/mast_jwst.json
.\astrobridge.cmd run examples/catalog/mast_tess.json
.\astrobridge.cmd run examples/catalog/mast_products.json
```

В [mast_jwst.json](examples/catalog/mast_jwst.json) используются реальные фильтры:

```json
{
  "service": "mast",
  "operation": "mast.search",
  "params": {
    "filters": [
      {"paramName": "obs_collection", "values": ["JWST"]},
      {"paramName": "dataRights", "values": ["PUBLIC"]}
    ]
  },
  "limit": 5
}
```

### 10.3. Путь от наблюдения к файлу

- Найдите наблюдение через cone или filters.
- Возьмите числовой **`obsid`**, а не строковый **`obs_id`**.
- Передайте его строкой в `mast.products`. Готовый пример использует `27307305`, полученный из реального поиска TESS при подготовке документа.
- В ответе проверьте `dataURI`, `productFilename`, `size`, тип/описание продукта и доступность.
- Выберите нужный файл и вызовите `download`; программа не скачивает все продукты автоматически.

Реальный TESS URI, успешно скачанный при проверке программы (17 775 360 байт):

```powershell
.\astrobridge.cmd download "mast:TESS/product/tess2019297232926-s0017-2-4-0161-s_ffir.fits" --filename tess_s0017_ffir.fits --max-mb 20
```

Это конкретный FITS-продукт TESS, не универсальный URL для любого объекта. Список `mast.products` выше служит отдельным примером и не обещает, что именно этот файл входит в данное наблюдение.

Пагинация: `params.page` начинается с 1; при наличии следующей страницы повторяйте тот же запрос с увеличенным номером. Смотрите `metadata.paging` и `warnings`. Размер страницы ограничивается адаптером до 10 000. Закрытые продукты MAST и токенная авторизация MAST в этой версии не поддержаны.

## 11. CADC: архивные продукты и CAOM

Источник: `cadc`; [полный снимок](docs/catalog_inventory/cadc.csv).

- `ivoa.ObsCore` — унифицированная информация о продуктах:
  - Тип данных, коллекция, идентификатор, положение.
  - Временные и спектральные границы.
  - Формат и URL доступа, когда опубликованы.
- Основная модель CAOM:
  - `caom2.Observation` — наблюдение.
  - `caom2.Plane` — научный продукт/плоскость обработки.
  - `caom2.Artifact` — физический файл/артефакт.
  - `caom2.Part`, `caom2.Chunk` — части и описания массивов.
  - `caom2.ObservationMember`, `caom2.ProvenanceInput` — членство и происхождение.
- Представления и справочники:
  - `caom2.SIAv1` — представление изображений.
  - `caom2.EnumField`, `caom2.ObsCoreEnumField`.
  - `caom2.distinct_proposal_id`, `caom2.distinct_proposal_pi`, `caom2.distinct_proposal_title`.
- Служебные:
  - `caom2.HarvestState`, `caom2.HarvestSkipURI`.
  - `tap_schema.schemas`, `tables`, `columns`, `keys`, `key_columns`.

```powershell
.\astrobridge.cmd run examples/catalog/cadc_obscore.json
.\astrobridge.cmd columns cadc ivoa.ObsCore --limit 1000
.\astrobridge.cmd query cadc --adql "SELECT TOP 20 DISTINCT obs_collection FROM ivoa.ObsCore" --limit 20
.\astrobridge.cmd query cadc --adql "SELECT TOP 5 * FROM caom2.Artifact" --limit 5
.\astrobridge.cmd columns cadc caom2.Plane --limit 1000
```

Снимок с `TOP 20 DISTINCT` — до 20 коллекций, не обязательно полный их список. Для научных соединений CAOM изучите ключи TAP_SCHEMA. `cadc:` и `ivo:` URI не преобразуются автоматически в загрузочный URL. Применяйте `download` к реально возвращённому HTTP(S)-адресу прямого файла; DataLink-ответ — ещё не научный FITS. Закрытый доступ с сертификатами CADC не реализован.

В стандартном ObsCore спектральные границы `em_min/em_max` задаются в метрах, время `t_min/t_max` — в MJD; проверяйте опубликованные единицы колонок. Это отличается от `em_min/em_max` MAST CAOM. Источник: [стандарт ObsCore 1.1](https://www.ivoa.net/documents/ObsCore/20170509/REC-ObsCore-v1.1-20170509.pdf).

## 12. Horizons: Солнечная система

Источник: `horizons`. Все запросы требуют явных `target`, `center`, `start`, `stop`, `step`, `time_scale`, `kind`.

- Объекты: планеты, спутники, астероиды, кометы, доступные аппараты, барицентры и другие поддерживаемые Horizons цели.
- `kind="vectors"`: декартовы координаты и скорости относительно выбранного центра; система ICRF, единицы AU-D; коррекции `NONE`, `LT`, `LT+S`.
- `kind="elements"`: оскулирующие элементы орбиты относительно центра, в заданной плоскости `FRAME` или `ECLIPTIC`.
- `kind="ephemerides"`: наблюдательные величины, выбираемые строкой `quantities`:
  - RA/Dec и движение по небу.
  - Видимая яркость и связанные величины.
  - Расстояния, скорости изменения расстояния, угловая геометрия.
  - Дополнительные доступные величины, включая топоцентрические, при подходящем центре.
- Не всякая величина определена для любой цели/центра. Значения кодов `quantities` и единицы сверяйте с [руководством Horizons](https://ssd.jpl.nasa.gov/horizons/manual.html) и заголовком ответа.

```powershell
.\astrobridge.cmd run examples/catalog/mars_vectors.json
.\astrobridge.cmd run examples/catalog/mars_observer.json
.\astrobridge.cmd run examples/catalog/ceres_elements.json
```

- `mars_vectors.json`: Марс `499` относительно геоцентра `500@399`, 1–3 января 2026, шаг 1 день, TDB, без световых коррекций.
- `mars_observer.json`: та же цель/центр, UT, наблюдательные коды `1,9,20,23`.
- `ceres_elements.json`: Церера `1;` относительно центра Солнца `500@10`, TDB, эклиптическая плоскость. Точка с запятой отличает поиск малого тела от числового кода крупного тела.
- Допустимые шкалы текущего адаптера: vectors — UT/TDB; ephemerides — UT/TT; elements — TDB.
- `limit` обрезает уже полученную таблицу, **не уменьшает расчётный диапазон на сервере**. Для большой задачи делите `start/stop` на интервалы.
- Табличные значения Horizons намеренно сохранены строками. Читайте `horizons.txt`: программа не угадывает физические единицы и не приводит автоматически всё к SI.
- Не реализованы произвольные параметры Horizons, загрузка собственных орбит/TLE, генерация SPK, отдельный API close approaches или пользовательские координаты наблюдателя через `SITE_COORD`.

## 13. Научная литература

### 13.1. NASA ADS — `ads`

- Возвращаемые адаптером поля: `bibcode`, `title`, `author`, `year`, `doi`, `abstract`, `citation_count`, если они есть у записи.
- Поиск использует [ADS query syntax](https://prod.adsabs.harvard.edu/help/search/search-syntax), включая поля и логические условия.
- Нужен собственный `ADS_TOKEN` в окружении; не записывайте секрет в запрос/README/репозиторий.
- Поисковая страница ограничена 200 записями; `offset` задаёт смещение.
- Полные тексты, списки всех цитирующих работ, экспорт BibTeX и библиотечные операции ADS не реализованы отдельными командами.

```powershell
.\astrobridge.cmd run examples/catalog/ads_exoplanets.json
```

В примере: `title:"exoplanet" year:2020-2026 property:refereed`, `offset: 0`, `limit: 5`. Без токена получите явную ошибку авторизации, не пустой «успешный» результат. При подготовке приложения ADS не проверен с токеном.

### 13.2. Crossref — `crossref`

- DOI, название, авторы, журнал/издатель, даты и тип публикации.
- Библиографические ссылки, лицензии, связи, URL, информация о финансировании и аннотация — **только если издатель передал их**.
- Адаптер сохраняет поля объектов `items` ответа; вложенные структуры в нормализованной таблице могут быть JSON-строками.
- Поиск текстовый через `query`; это не ADS-синтаксис и не гарантированное точное разрешение DOI.
- До 1 000 записей за страницу; `offset`, без отдельного cursor API.
- Числа ссылок/цитирований разных индексов нельзя считать взаимозаменяемыми.

```powershell
.\astrobridge.cmd run examples/catalog/crossref_exoplanets.json
```

### 13.3. arXiv — `arxiv`

- Нормализованные поля текущей реализации: `id`, `title`, `abstract`, `published`, `authors`.
- В исходном Atom-ответе могут быть дополнительные поля/ссылки; адаптер не обещает их отдельными колонками.
- Поиск по категориям, заголовкам, авторам и другим полям [arXiv API search syntax](https://github.com/arXiv/arxiv-docs/blob/develop/source/help/api/user-manual.md).
- До 1 000 записей за страницу; продолжение через `offset`.
- PDF не скачивается поиском автоматически. Если найден открытый прямой HTTP(S)-URL, его можно передать отдельной команде `download`.
- arXiv-препринт не обязательно прошёл рецензирование.

```powershell
.\astrobridge.cmd run examples/catalog/arxiv_cosmology.json
```

В примере: `cat:astro-ph.CO AND ti:dark`. Для других задач можно использовать `astro-ph.EP`, `astro-ph.GA`, `astro-ph.HE`, `astro-ph.IM`, `astro-ph.SR`. Во время предыдущих сетевых проверок endpoint arXiv отвечал timeout; успешный доступ из вашей сети не гарантирован.

Для всех трёх поисков смотрите `metadata.total`, `next_offset` и `warnings`; изменяйте `params.offset` для следующей страницы. Наличие DOI/ссылки не обходит подписку издателя.

## 14. VO Registry и дополнительные сервисы

### 14.1. RegTAP — `registry`

- Описания ресурсов, идентификаторы IVOID, названия, предметные области и другие опубликованные метаданные.
- Возможности сервисов: TAP, SIA, SSA и другие зарегистрированные протоколы.
- Адреса интерфейсов, роли и версии протоколов.
- Регистрация сервиса не доказывает, что он сейчас работает или что AstroBridge поддерживает весь его интерфейс.

```powershell
.\astrobridge.cmd run examples/catalog/registry_tap.json
.\astrobridge.cmd run examples/catalog/registry_sia.json
.\astrobridge.cmd run examples/catalog/registry_ssa.json
.\astrobridge.cmd columns registry rr.resource --limit 1000
```

Это реальные RegTAP-запросы поиска адресов, не заранее придуманные URL. Не подставляйте автоматически первый ответ в запрос на загрузку: проверьте назначение, версию и права доступа.

### 14.2. Подключаемые TAP, SIA 1 и SSA

- **TAP**: любые опубликованные табличные данные совместимого сервиса, поддерживаемые его ADQL-реализацией. Доступны те же query/tables/columns/cone.
- **SIA 1**: поиск изображений по положению и размеру области; метаданные/URL продуктов, если сервер их предоставляет.
- **SSA**: поиск спектров по положению и диаметру области; метаданные спектрального покрытия и доступа.
- Это возможности после конфигурации, **не дополнительные встроенные архивы**. Не поддержаны SIA 2, DataLink/SODA, TAP_UPLOAD и автоматический обход VO Registry с подключением всех адресов.

Пример без фиктивного адреса: добавлен конфигурационный файл [custom_tap.json](examples/catalog/custom_tap.json) с реальным endpoint IRSA под новым ключом `my_irsa`. Он демонстрирует подключение любого совместимого TAP по проверенному URL:

```powershell
.\astrobridge.cmd --config examples/catalog/custom_tap.json tables my_irsa --contains "2MASS" --limit 20
.\astrobridge.cmd --config examples/catalog/custom_tap.json query my_irsa --adql "SELECT TOP 5 * FROM fp_psc" --limit 5
```

Для найденного и проверенного SIA1/SSA адреса создайте запись `services` с `kind: "sia"` или `kind: "ssa"`, а `url` возьмите из результата registry. Затем получите схему/шаблон:

```powershell
.\astrobridge.cmd example vo.sia
.\astrobridge.cmd example vo.ssa
```

- `vo.sia` требует `ra`, `dec`, `size` — градусы; `size` — размер области, не радиус cone.
- `vo.ssa` требует `ra`, `dec`, `diameter` — градусы; `diameter` — диаметр, не радиус.
- Вывод `example` — **шаблон для редактирования**, а не обещание существования примерного сервера.
- Плагины Python могут добавлять новые адаптеры, но их гипотетические возможности не входят в список доступного «сейчас». См. [EXTENDING.md](docs/EXTENDING.md).

## 15. Результаты, экспорт и воспроизводимость

Помимо научной таблицы программа позволяет получить:

- JSON-описание запуска: статус, `run_id`, каталог результата, запрос, сервис и endpoint.
- UTC-время начала/окончания, версию приложения и используемых библиотек.
- Сведения о сети, HTTP-ответах и повторном использовании кэша.
- Исходные ответы сервера, точный ADQL, нормализованный ECSV.
- Типы/единицы/UCD колонок, если они опубликованы и перенесены из ответа.
- Число строк, признаки ограничения и предупреждения.
- Имена, размеры и SHA-256 сохранённых файлов.
- Для Horizons — исходный `horizons.txt`; для загрузки — исходный файл без научной переработки.

Команды с автоматически взятым реальным `run_id`, без ручного копирования:

```powershell
$run = .\astrobridge.cmd resolve M31 --preview 1 | ConvertFrom-Json
if ($run.status -ne 'success') { throw 'Запрос завершился ошибкой' }
.\astrobridge.cmd result $run.run_id --offset 0 --limit 20
.\astrobridge.cmd export $run.run_id --output exports/m31_catalog.csv --format csv
.\astrobridge.cmd export $run.run_id --output exports/m31_catalog.ecsv --format ecsv
.\astrobridge.cmd history --limit 10
```

- Экспорт: `csv`, `ecsv`, `fits`, `votable`, `json`. Экспорт FITS создаёт **табличный FITS**, а не синтезирует изображение объекта.
- Существующий файл назначения не должен перезаписываться случайно: выбирайте новое имя при повторе.
- `result --offset` листает **локально сохранённый ответ**, а не догружает следующие строки сервера.
- При другом `--workspace` тот же параметр нужен и для `result/history/export`.
- Для ECSV/FITS/VOTable сохраняется больше структурной информации, чем в простом CSV; всегда храните manifest и исходный ответ рядом.

### 15.1. Полный перечень операций версии 0.1.0

- `tap.query` — произвольная разрешённая ADQL SELECT-выборка.
- `tap.tables` — таблицы и их описания.
- `tap.columns` — поля и их метаданные.
- `tap.cone` — круговая координатная выборка TAP.
- `simbad.resolve` — разрешение имени объекта.
- `mast.cone` — наблюдения MAST в области.
- `mast.search` — наблюдения MAST по фильтрам.
- `mast.products` — перечень продуктов наблюдения.
- `horizons.query` — векторы, элементы или наблюдательные эфемериды.
- `literature.search` — ADS/Crossref/arXiv.
- `vo.sia` — поиск изображений SIA 1 после настройки сервиса.
- `vo.ssa` — поиск спектров SSA после настройки сервиса.
- `download` — один публичный HTTP(S)-файл или поддерживаемый `mast:` URI.

Локальная история и чтение таблиц доступны отдельными CLI-командами `history` и `result`, не через вымышленные операции `local.*` в JSON. Команды `export`, `providers`, `doctor`, `gui`, `init`, `example`, `schema` — вспомогательный интерфейс, а не дополнительные научные архивы.

### 15.2. Пакетные примеры и инвентаризация

```powershell
.\astrobridge.cmd --workspace workspace/catalog_repeat --timeout 60 batch examples/catalog/smoke.jsonl --preview 0
.\astrobridge.cmd --workspace workspace/inventory_repeat --timeout 120 batch examples/catalog/inventory.jsonl --preview 0
```

- [smoke.jsonl](examples/catalog/smoke.jsonl) — небольшие сетевые примеры по источникам, без ADS/Gaia/arXiv; запросы выполняются последовательно. Набор не включает загрузку большого файла.
- [inventory.jsonl](examples/catalog/inventory.jsonl) — семь запросов полных списков таблиц, по 100 000 строк максимум. VizieR возвращает десятки тысяч строк; не запускайте часто без необходимости.
- `--preview 0` скрывает строки stdout, но не сокращает запрос, ответ сервера или метаданные колонок.
- Отдельные готовые JSON находятся в [examples/catalog](examples/catalog). Для изменения задачи редактируйте копию файла и запускайте `run`.

## 16. Чего текущая программа не обещает

- Все функции astroquery только потому, что библиотека известна или установлена: возможности определены адаптерами AstroBridge.
- Автоматический доступ ко всем данным Gaia/MAST/ESO/ALMA/SDSS/Rubin и другим архивам целиком.
- Выгрузку закрытых наблюдений, обход подписок, OAuth, MAST-токены, CADC-сертификаты, облачную авторизацию/requester-pays.
- Специализированные API TNS, MPC/SBDB, GWOSC, Fermi Science Tools, IllustrisTNG, потоковые alert brokers или управление телескопами — без отдельного расширения.
- Все поля внешнего API: например, ADS запрашивает фиксированный набор, arXiv нормализует пять полей, Horizons принимает только перечисленные параметры.
- Автоматическую обработку FITS, фотометрию, извлечение спектров, редукцию событий, исправление систематики, обучение моделей или научные выводы.
- Автоматическое сопоставление объектов между разными серверами. ADQL JOIN работает внутри сервиса; перенос таблиц через TAP_UPLOAD не реализован.
- Бесконечную выгрузку: `limit` максимум 100 000, ограничения ответа/загрузки и квоты сервера действуют независимо. По умолчанию лимиты HTTP-ответа/файла — 64/512 MiB в настройках (поля названы `*_mb`).
- Полноту по одному `truncated=false`: проверяйте TOP, `limit_reached`, пагинацию, серверные квоты и временные/пространственные фильтры.
- Унифицированные единицы, эпохи и шкалы времени всех архивов. Не смешивайте MJD, JD, UTC/UT, TT/TDB, градусы/часы, nm/m и различные определения потоков.
- Достоверную лицензию по факту успешного HTTP-ответа: проверяйте правила архива, цитирование каталога/миссии и права на конкретные данные.

## 17. Практический порядок работы LLM

- Определить физическую величину, тип объекта, область, время и требуемый релиз.
- Найти подходящий источник в этом документе; проверить реальный `providers`.
- Для TAP найти таблицу через CSV/`tables`, затем запросить `columns`.
- Сделать маленький запрос с явными полями и лимитом; проверить единицы, null, флаги и описание.
- Для файлов сначала получить метаданные/продукты, выбрать подходящий публичный URL и оценить размер.
- Проверить статус, предупреждения, полноту и необходимость следующей страницы.
- Сохранить запрос, manifest, исходный ответ и использованный релиз; не считать пользовательскую метку `release` доказательством релиза сервера.
- Только после этого выполнять анализ отдельным научным кодом; в выводах отделять измеренное от модельного и отсутствующее от нулевого.

Статусы проверок конкретных примеров и оговорки доступны в [CATALOG_VALIDATION.md](docs/CATALOG_VALIDATION.md). Этот каталог не обещает успешного ответа архива в будущем: права доступа, схема и доступность endpoint могут измениться.
