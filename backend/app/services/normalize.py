"""Нормализация сырых полей телеметрии и справочников (INTEGRATION_SPEC §1.2-1.4, DATA_AUDIT §2.3)."""
from __future__ import annotations

import re

NORMAL_STATES = {
    "норма", "движения нет", "дыма нет", "в норме от +3 до +40", "есть питание", "включен", "выключен",
    "замкнут", "закрыт", "закрыта", "газа нет", "движение отсутствует",
}
FAILURE_STATES = {
    "неисправен", "обесточен", "затоплен", "отключено устройство", "много неисправных устройств",
    "батарея неисправна", "батарея разряжена", "нет питания", "неисправность",
}
ALARM_STATES = {
    "обнаружен дым", "обнаружен газ", "обнаружено движение", "не замкнут", "температура ниже 3ºc",
    "температура ниже 3°c", "открыт", "открыта", "тревога", "пожар", "внимание",
}
UNKNOWN_STATES = {"неопределен", "не определено", "неопределён", "нет данных"}

_NUM_RE = re.compile(r"^[-+]?\d+(?:[.,]\d+)?$")
_PIKET_RE = re.compile(r"ПК\s*(\d+)(?:\s*[+](\d+))?(?:\s*[,.](\d+))?", re.IGNORECASE)
_PIKET_RANGE_RE = re.compile(r"ПК\s*(\d+)\s*-\s*ПК\s*(\d+)", re.IGNORECASE)


def parse_numeric(raw: str) -> float | None:
    s = raw.strip()
    if _NUM_RE.match(s):
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return None
    return None


def status_code(raw: str, numeric: float | None, is_alarm: bool) -> str:
    """normal | failure | alarm | unknown."""
    if numeric is not None:
        return "alarm" if is_alarm else "normal"
    s = raw.strip().lower()
    if s in FAILURE_STATES:
        return "failure"
    if s in ALARM_STATES:
        return "alarm"
    if s in NORMAL_STATES:
        return "normal"
    if s in UNKNOWN_STATES:
        return "unknown"
    # Даты постановки на охрану/сброса контроллера ("01.01.1970 03:00:00") и прочие незнакомые строки
    if is_alarm:
        return "alarm"
    return "unknown"


def parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"t", "true", "1"}


def parse_piket(name: str) -> tuple[str | None, float | None]:
    """'ТЕМП ПК275+9' -> ('ПК275+9', 275.09); 'Темп. ВШ ПК88,5' -> ('ПК88,5', 88.5); 'ТД ПК86-85' -> ('ПК86', 86.0)."""
    m = _PIKET_RE.search(name)
    if not m:
        return None, None
    base = int(m.group(1))
    value = float(base)
    if m.group(2):  # ПК275+9 -> +9 метров при шаге пикета 100 м
        value = base + int(m.group(2)) / 100.0
    elif m.group(3):  # ПК88,5
        value = float(f"{base}.{m.group(3)}")
    return m.group(0).replace(" ", ""), value


def parse_piket_range(object_name: str) -> tuple[float | None, float | None]:
    m = _PIKET_RANGE_RE.search(object_name)
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


def tag_root(tag: str) -> str:
    return tag.split("-", 1)[0].strip()
