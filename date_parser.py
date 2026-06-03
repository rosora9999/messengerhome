import re
from datetime import datetime, timedelta

WEEKDAYS_VI = {
    "thứ 2": 0, "thu 2": 0, "thứ hai": 0, "thu hai": 0,
    "thứ 3": 1, "thu 3": 1, "thứ ba": 1, "thu ba": 1,
    "thứ 4": 2, "thu 4": 2, "thứ tư": 2, "thu tu": 2,
    "thứ 5": 3, "thu 5": 3, "thứ năm": 3, "thu nam": 3,
    "thứ 6": 4, "thu 6": 4, "thứ sáu": 4, "thu sau": 4,
    "thứ 7": 5, "thu 7": 5, "thứ bảy": 5, "thu bay": 5,
    "chủ nhật": 6, "chu nhat": 6, "cn": 6,
}

def parse_single_date(text: str) -> datetime | None:
    """Parse 1 ngày từ text tiếng Việt."""
    text = text.strip().lower()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Hôm nay, ngày mai, ngày kia
    if text in ("hôm nay", "hom nay"):
        return today
    if text in ("ngày mai", "ngay mai", "mai"):
        return today + timedelta(days=1)
    if text in ("ngày kia", "ngay kia", "kia"):
        return today + timedelta(days=2)

    # Thứ X tuần này / tuần sau
    for day_name, weekday in WEEKDAYS_VI.items():
        if day_name in text:
            days_ahead = weekday - today.weekday()
            if "tuần sau" in text or "tuan sau" in text:
                days_ahead += 7
            elif days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    # Cuối tuần
    if "cuối tuần" in text or "cuoi tuan" in text:
        days_to_saturday = (5 - today.weekday()) % 7
        if days_to_saturday == 0:
            days_to_saturday = 7
        return today + timedelta(days=days_to_saturday)

    # DD/MM/YYYY hoặc D/M/YYYY hoặc DD/MM hoặc D/M
    patterns = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",  # DD/MM/YYYY
        r"(\d{1,2})[/-](\d{1,2})",               # DD/MM (năm hiện tại)
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                if len(m.groups()) == 3:
                    return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                else:
                    year = today.year
                    dt = datetime(year, int(m.group(2)), int(m.group(1)))
                    if dt < today:
                        dt = datetime(year + 1, int(m.group(2)), int(m.group(1)))
                    return dt
            except:
                pass

    return None


def parse_date_range(text: str):
    """
    Parse khoảng ngày từ text tiếng Việt.
    Trả về (checkin_str, checkout_str) dạng YYYY-MM-DD hoặc (None, None).
    """
    text_lower = text.lower().strip()

    # Tách 2 ngày bằng dấu "-", "đến", "tới", "to"
    separators = [" đến ", " den ", " tới ", " toi ", " to ", " - ", "-"]
    parts = None
    for sep in separators:
        if sep in text_lower:
            parts = text_lower.split(sep, 1)
            break

    if parts and len(parts) == 2:
        d1 = parse_single_date(parts[0].strip())
        d2 = parse_single_date(parts[1].strip())
        if d1 and d2 and d2 > d1:
            return d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d")

    # Chỉ 1 ngày → mặc định ở 1 đêm
    d1 = parse_single_date(text_lower)
    if d1:
        d2 = d1 + timedelta(days=1)
        return d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d")

    return None, None
