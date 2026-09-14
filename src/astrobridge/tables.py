from dataclasses import dataclass, field
from io import BytesIO
import warnings

from astropy.io.votable import parse
from astropy.table import Table, MaskedColumn
import numpy as np
from defusedxml import ElementTree

from .errors import BridgeError
from .util import jsonable


@dataclass
class Result:
    table: Table | None = None
    metadata: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    truncated: bool = False


def normalize_columns(table):
    """VOTable variable strings and nullable JSON scalars need concrete dtypes."""
    for name in table.colnames:
        col = table[name]
        if col.dtype.kind != "O":
            continue
        mask = np.ma.getmaskarray(col) | np.array([value is None for value in col], dtype=bool)
        values = [value for value, masked in zip(col, mask) if not masked]
        if all(isinstance(value, (str, bytes)) for value in values):
            data = ["" if masked else value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value for value, masked in zip(col, mask)]
            dtype = "U" + str(max([len(value) for value in data] + [1]))
        elif values and all(isinstance(value, (int, float, bool, np.number)) for value in values):
            data = [0 if masked else value for value, masked in zip(col, mask)]
            dtype = np.asarray(values).dtype
        else:
            continue
        replacement = MaskedColumn(data, name=name, dtype=dtype, mask=mask, unit=col.unit, description=col.description, meta=col.meta)
        table.replace_column(name, replacement)
    return table


def from_votable(content, limit):
    try:
        root = ElementTree.fromstring(content)
    except Exception:
        raise BridgeError("parse", "Сервис не вернул корректный безопасный VOTable XML.") from None
    status = [(node.attrib.get("value", "").upper(), node.text or "") for node in root.iter()
              if node.tag.rsplit("}", 1)[-1] == "INFO" and node.attrib.get("name", "").upper() == "QUERY_STATUS"]
    for value, message in status:
        if value == "ERROR":
            # Service message contains the user's ADQL, not authentication headers.
            raise BridgeError("query", "Ошибка TAP: " + message[:1500])
    try:
        with warnings.catch_warnings(record=True) as notices:
            vot = parse(BytesIO(content), verify="warn")
            vt = vot.get_first_table()
            table = vt.to_table(use_names_over_ids=True)
        for field_info, column in zip(vt.fields, table.itercols()):
            column.meta.update({"ucd": field_info.ucd, "utype": field_info.utype})
        overflow = any(value == "OVERFLOW" for value, _ in status) or len(table) > limit
        messages = list(dict.fromkeys(str(w.message) for w in notices))[:20]
        if overflow:
            messages.append("Результат усечён сервером или локальным лимитом; не используйте как полную выборку.")
        elif len(table) == limit:
            messages.append("Достигнут лимит строк. Полнота выборки не гарантируется.")
        return Result(normalize_columns(table[:limit]), warnings=messages, truncated=overflow)
    except BridgeError:
        raise
    except Exception:
        raise BridgeError("parse", "Не удалось разобрать таблицу. Исходный ответ сохранён в каталоге запуска.") from None


def from_rows(rows, fields=None, limit=1000):
    names = [f["name"] for f in fields] if fields else list(dict.fromkeys(key for row in rows for key in row))
    normalized = [{name: row.get(name) for name in names} for row in rows[:limit]]
    if normalized:
        # Nested API values are retained as JSON text in tabular exports.
        from .util import dumps
        normalized = [{k: dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in normalized]
        table = Table(rows=normalized, names=names)
    else:
        table = Table(names=names, dtype=["U1"] * len(names))
    for field_info in fields or []:
        column = table[field_info["name"]]
        column.description = field_info.get("description")
        column.meta["source_type"] = field_info.get("type")
        if field_info.get("unit"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                column.unit = field_info["unit"]
    return Result(normalize_columns(table), truncated=len(rows) > limit)


def columns(table):
    if table is None:
        return []
    return [{"name": name, "dtype": str(table[name].dtype), "unit": str(table[name].unit) if table[name].unit else None,
             "description": table[name].description, "ucd": table[name].meta.get("ucd")} for name in table.colnames]


def table_rows(table, offset=0, limit=100):
    if table is None:
        return []
    return [{name: jsonable(row[name]) for name in table.colnames} for row in table[offset:offset + limit]]
