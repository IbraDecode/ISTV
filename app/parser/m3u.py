import re
from dataclasses import dataclass, field


@dataclass
class ChannelEntry:
    name: str = ""
    tvg_id: str = ""
    logo: str = ""
    group: str = "Lainnya"
    url: str = ""
    stream_type: str = "hls"
    has_drm: bool = False
    drm_info: dict | None = None
    headers: dict = field(default_factory=dict)
    kodiprops: dict = field(default_factory=dict)


ATTR_RE = re.compile(r'([a-zA-Z0-9_-]+)="([^"]*)"')
STREAM_TYPE_RE = re.compile(r"\.(m3u8|mpd|ts)(?:\?|$)", re.I)


def parse_attrs(line: str) -> dict:
    return dict(ATTR_RE.findall(line))


def detect_stream_type(url: str) -> str:
    m = STREAM_TYPE_RE.search(url.split("|")[0].split("?")[0])
    if m:
        raw = m.group(1).lower()
        return {"m3u8": "hls", "mpd": "dash", "ts": "ts"}.get(raw, "hls")
    return "hls"


def parse_m3u(text: str) -> list[ChannelEntry]:
    channels: list[ChannelEntry] = []
    pending = ChannelEntry()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF"):
            attrs = parse_attrs(line)
            pending.tvg_id = attrs.get("tvg-id", "")
            pending.logo = attrs.get("tvg-logo", "")
            pending.group = attrs.get("group-title", "Lainnya")
            name_start = line.rfind(",")
            pending.name = line[name_start + 1 :].strip() if name_start >= 0 else ""
            continue

        if line.startswith("#EXTVLCOPT:"):
            val = line[len("#EXTVLCOPT:"):]
            eq = val.find("=")
            if eq > 0:
                key = val[:eq].strip().lower()
                v = val[eq + 1 :].strip()
                if key in ("http-referrer", "http-referer"):
                    pending.headers["Referer"] = v
                elif key == "http-user-agent":
                    pending.headers["User-Agent"] = v
                elif key == "http-origin":
                    pending.headers["Origin"] = v
            continue

        if line.startswith("#KODIPROP:"):
            val = line[len("#KODIPROP:"):]
            eq = val.find("=")
            if eq > 0:
                key = val[:eq].strip()
                v = val[eq + 1 :].strip()
                pending.kodiprops[key] = v
                if key == "inputstream.adaptive.license_type":
                    pending.has_drm = True
                    pending.drm_info = {"type": v}
                elif key == "inputstream.adaptive.license_key":
                    if pending.drm_info is None:
                        pending.drm_info = {}
                    pending.drm_info["key"] = v
                    pending.has_drm = True
            continue

        if line.startswith("#"):
            continue

        pipe_parts = line.split("|")
        pending.url = pipe_parts[0]
        if len(pipe_parts) > 1 and pipe_parts[1]:
            for kv in pipe_parts[1].split("&"):
                eq = kv.find("=")
                if eq > 0:
                    k = kv[:eq].strip()
                    v = kv[eq + 1 :].strip()
                    pending.headers[k] = v

        pending.stream_type = detect_stream_type(pending.url)
        channels.append(pending)
        pending = ChannelEntry()

    return channels
