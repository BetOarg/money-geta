_TIME = re.compile(r"^(\d{2,}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2,}:\d{2}:\d{2}[,.]\d{3})(?:\s+.*)?$")
_TIME = re.compile(r"^((?:\\d{2,}:)?\\d{2}:\\d{2}[,.]\\d{3})\\s*-->\\s*((?:\\d{2,}:)?\\d{2}:\\d{2}[,.]\\d{3})(?:\\s+.*)?$")\def _seconds(value: str) -> float:
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        hours = 0
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError("invalid timestamp")
    if int(minutes) >= 60 or float(seconds) >= 60:
        raise ValueError("timestamp minute/second fields must be below 60")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)n