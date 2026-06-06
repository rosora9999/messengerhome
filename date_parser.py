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
    text = text.strip().lower()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Hôm nay / tối nay / trưa nay / chiều nay
    if any(kw in text for kw in ["hôm nay", "hom nay", "tối nay", "toi nay",
                                   "trưa nay", "trua nay", "chiều nay", "chieu nay",
                                   "sáng nay", "sang nay"]):
        return today

    # Ngày mai / tối mai / trưa mai / chiều mai / sáng mai
    if any(kw in text for kw in ["ngày mai", "ngay mai", "tối mai", "toi mai",
                                   "trưa mai", "trua mai", "chiều mai", "chieu mai",
                                   "sáng mai", "sang mai", " mai"]):
        return today + timedelta(days=1)

    # Ngày kia
    if any(kw in text for kw in ["ngày kia", "ngay kia", "ngày mốt", "ngay mot"]):
        return today + timedelta(days=2)

    # Cuối tuần này
    if any(kw in text for kw in ["cuối tuần", "cuoi tuan"]):
        days_to_saturday = (5 - today.weekday()) % 7
        if days_to_saturday == 0:
            days_to_saturday = 7
        return today + timedelta(days=days_to_saturday)

    # Thứ X
    for day_name, weekday in WEEKDAYS_VI.items():
        if day_name in text:
            days_ahead = weekday - today.weekday()
            if "tuần sau" in text or "tuan sau" in text:
                days_ahead += 7
            elif days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    # DD/MM/YYYY hoặc DD/MM
    patterns = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
        r"(\d{1,2})[/-](\d{1,2})",
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
    text_lower = text.lower().strip()

    # Tách 2 ngày bằng dấu phân cách
    separators = [" đến ", " den ", " tới ", " toi ", " to ", " - ", "-"]
    for sep in separators:
        if sep in text_lower:
            parts = text_lower.split(sep, 1)
            if len(parts) == 2:
                d1 = parse_single_date(parts[0].strip())
                d2 = parse_single_date(parts[1].strip())
                if d1 and d2 and d2 > d1:
                    return d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d")

    # Tìm 2 ngày dạng DD/MM trong cùng 1 câu
    matches = re.findall(r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{4})?", text_lower)
    if len(matches) >= 2:
        d1 = parse_single_date(matches[0])
        d2 = parse_single_date(matches[1])
        if d1 and d2 and d2 > d1:
            return d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d")

    # Chỉ 1 ngày → mặc định 1 đêm
    d1 = parse_single_date(text_lower)
    if d1:
        return d1.strftime("%Y-%m-%d"), (d1 + timedelta(days=1)).strftime("%Y-%m-%d")

    return None, None
