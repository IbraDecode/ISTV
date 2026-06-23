import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import re


@dataclass
class ProgramEntry:
    channel_tvg_id: str
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    category: str


BAD_TITLE_RE = re.compile(
    r"^(Tidak ada|No info|Jadwal|Schedule|Channel|Siaran|"
    r".*Tidak Tersedia|.*Not Available|Coming Soon)$",
    re.I,
)

XMLTV_TS_RE = re.compile(
    r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\s*([+-]\d{2})(\d{2})"
)


def _parse_timestamp(ts: str) -> datetime:
    clean = ts.strip()
    m = XMLTV_TS_RE.match(clean)
    if m:
        year, month, day, hour, minute, second = map(int, m.group(1, 2, 3, 4, 5, 6))
        tz_sign = 1 if m.group(7)[0] == "+" else -1
        tz_hour, tz_min = int(m.group(7)), int(m.group(8))
        offset = timedelta(hours=tz_hour * tz_sign, minutes=tz_min * tz_sign)
        tz = timezone(offset)
        return datetime(year, month, day, hour, minute, second, tzinfo=tz)

    try:
        return datetime.fromisoformat(clean)
    except ValueError:
        return datetime.now(timezone.utc)


def _is_bad_title(title: str) -> bool:
    return bool(BAD_TITLE_RE.match(title.strip()))


def parse_epg(xml_text: str) -> list[ProgramEntry]:
    programs: list[ProgramEntry] = []
    root = ET.fromstring(xml_text)

    for prog in root.findall("programme"):
        ch_id = prog.get("channel", "")
        start_str = prog.get("start", "")
        stop_str = prog.get("stop", "")

        title_el = prog.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        if _is_bad_title(title):
            continue

        desc_el = prog.find("desc")
        desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

        cat_el = prog.find("category")
        cat = cat_el.text.strip() if cat_el is not None and cat_el.text else ""

        start_dt = _parse_timestamp(start_str)
        end_dt = _parse_timestamp(stop_str) if stop_str else start_dt

        programs.append(
            ProgramEntry(
                channel_tvg_id=ch_id,
                title=title,
                description=desc,
                start_time=start_dt,
                end_time=end_dt,
                category=cat,
            )
        )

    return programs
