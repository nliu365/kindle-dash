#!/usr/bin/env python3
"""Render a 600x800 grayscale dashboard PNG for a Kindle 4.

Inputs (environment variables):
  ICAL_URL   Google Calendar "Secret address in iCal format" (one or more, comma-separated)
  LAT, LON   Weather location (default: Sunnyvale, CA)
  TZ_NAME    IANA time zone (default: America/Los_Angeles)
  UNITS      "imperial" (default) or "metric"
  ALARMS     Same string the Worker uses, shown on screen, e.g. "06:45@1-5,08:30@6-7"
  OUT        Output path (default: dash.png)
  SAMPLE_ICS Optional local .ics file instead of ICAL_URL (for testing)
"""
import datetime as dt
import math
import os
import sys
from zoneinfo import ZoneInfo

import recurring_ical_events
import requests
from icalendar import Calendar
from PIL import Image, ImageDraw, ImageFont

W, H = 600, 800
TZ = ZoneInfo(os.environ.get("TZ_NAME", "America/Los_Angeles"))
LAT = float(os.environ.get("LAT", "37.3688"))
LON = float(os.environ.get("LON", "-122.0363"))
UNITS = os.environ.get("UNITS", "imperial")
OUT = os.environ.get("OUT", "dash.png")

FONT_DIRS = [
    "/usr/share/fonts/opentype/noto/",
    "/usr/share/fonts/truetype/noto/",
]


def font(size, bold=False):
    name = "NotoSansCJK-Bold.ttc" if bold else "NotoSansCJK-Regular.ttc"
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


# ---------------------------------------------------------------- data
def fetch_events(now):
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + dt.timedelta(days=4)
    sources = []
    if os.environ.get("SAMPLE_ICS"):
        sources.append(open(os.environ["SAMPLE_ICS"], "rb").read())
    for url in filter(None, (u.strip() for u in os.environ.get("ICAL_URL", "").split(","))):
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        sources.append(r.content)

    events = []
    for raw in sources:
        cal = Calendar.from_ical(raw)
        for ev in recurring_ical_events.of(cal).between(start, end):
            s = ev.get("DTSTART").dt
            e = ev.get("DTEND").dt if ev.get("DTEND") else s
            all_day = not isinstance(s, dt.datetime)
            if all_day:
                s = dt.datetime.combine(s, dt.time(0), TZ)
                e = dt.datetime.combine(e, dt.time(0), TZ)
            else:
                s = s.astimezone(TZ) if s.tzinfo else s.replace(tzinfo=TZ)
                e = e.astimezone(TZ) if e.tzinfo else e.replace(tzinfo=TZ)
            if e <= now and not all_day:
                continue  # already finished today
            events.append({
                "title": str(ev.get("SUMMARY", "(no title)")),
                "start": s, "end": e, "all_day": all_day,
            })
    events.sort(key=lambda x: (x["start"].date(), not x["all_day"], x["start"]))
    return events


def fetch_weather():
    if os.environ.get("WX_FIXTURE"):
        import json
        return json.load(open(os.environ["WX_FIXTURE"]))
    params = {
        "latitude": LAT, "longitude": LON, "timezone": str(TZ),
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
        "hourly": "temperature_2m,weather_code,precipitation_probability",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        "forecast_days": 4,
    }
    if UNITS == "imperial":
        params.update(temperature_unit="fahrenheit", wind_speed_unit="mph")
    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- weather icons
def icon_kind(code):
    if code == 0: return "sun"
    if code in (1, 2): return "partly"
    if code == 3: return "cloud"
    if code in (45, 48): return "fog"
    if code in (71, 73, 75, 77, 85, 86): return "snow"
    if code in (95, 96, 99): return "storm"
    if 51 <= code <= 82: return "rain"
    return "cloud"


def draw_sun(d, cx, cy, r, w):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=w)
    for i in range(8):
        a = i * math.pi / 4
        d.line([cx + math.cos(a) * r * 1.4, cy + math.sin(a) * r * 1.4,
                cx + math.cos(a) * r * 1.85, cy + math.sin(a) * r * 1.85], fill=0, width=w)


def draw_cloud(d, cx, cy, s, w, fill=255):
    parts = [(-0.45, 0.05, 0.38), (0.0, -0.18, 0.48), (0.45, 0.08, 0.34)]
    for dx, dy, r in parts:
        d.ellipse([cx + (dx - r) * s, cy + (dy - r) * s, cx + (dx + r) * s, cy + (dy + r) * s],
                  fill=fill, outline=0, width=w)
    d.rectangle([cx - 0.45 * s, cy + 0.05 * s, cx + 0.45 * s, cy + 0.42 * s], fill=fill)
    d.line([cx - 0.5 * s, cy + 0.42 * s, cx + 0.5 * s, cy + 0.42 * s], fill=0, width=w)
    # re-cover inner outlines
    for dx, dy, r in parts:
        rr = r - w / s
        d.ellipse([cx + (dx - rr) * s, cy + (dy - rr) * s, cx + (dx + rr) * s, cy + (dy + rr) * s], fill=fill)
    d.rectangle([cx - 0.45 * s, cy + 0.05 * s, cx + 0.45 * s, cy + 0.42 * s - w], fill=fill)


def draw_icon(d, kind, cx, cy, size):
    w = max(2, size // 18)
    s = size * 0.9
    if kind == "sun":
        draw_sun(d, cx, cy, size * 0.25, w)
        return
    if kind == "partly":
        draw_sun(d, cx + size * 0.2, cy - size * 0.22, size * 0.15, w)
        draw_cloud(d, cx - size * 0.06, cy + size * 0.06, s * 0.72, w)
        return
    draw_cloud(d, cx, cy, s * 0.9, w)
    base = cy + 0.42 * s
    if kind == "rain":
        for i in (-1, 0, 1):
            x = cx + i * s * 0.25
            d.line([x, base + s * 0.08, x - s * 0.07, base + s * 0.3], fill=0, width=w)
    elif kind == "snow":
        for i in (-1, 0, 1):
            x = cx + i * s * 0.25
            r = s * 0.05
            d.ellipse([x - r, base + s * 0.15 - r, x + r, base + s * 0.15 + r], fill=0)
    elif kind == "storm":
        x, y = cx, base + s * 0.05
        d.line([x, y, x - s * 0.1, y + s * 0.15, x + s * 0.06, y + s * 0.15, x - s * 0.05, y + s * 0.32],
               fill=0, width=w)
    elif kind == "fog":
        for i in range(2):
            y = base + s * (0.12 + i * 0.12)
            d.line([cx - s * 0.4, y, cx + s * 0.4, y], fill=0, width=w)


# ---------------------------------------------------------------- layout helpers
def fit(d, text, f, max_w):
    if d.textlength(text, font=f) <= max_w:
        return text
    while text and d.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text + "…"


def fmt_time(t):
    return t.strftime("%-I:%M").replace(":00", "") + ("a" if t.hour < 12 else "p")


def day_label(day, today):
    if day == today: return "Today"
    if day == today + dt.timedelta(days=1): return "Tomorrow"
    return day.strftime("%A")


def parse_alarms(s):
    out = []
    for item in filter(None, (x.strip() for x in s.split(","))):
        hm, _, days = item.partition("@")
        out.append((hm, days or "1-7"))
    return out


def next_alarm(now, alarms):
    best = None
    for hm, days in alarms:
        h, m = map(int, hm.split(":"))
        allowed = set()
        for part in days.split(";"):
            a, _, b = part.partition("-")
            allowed.update(range(int(a), int(b or a) + 1))
        for add in range(8):
            day = (now + dt.timedelta(days=add)).date()
            t = dt.datetime.combine(day, dt.time(h, m), TZ)
            if t > now and day.isoweekday() in allowed:
                if best is None or t < best:
                    best = t
                break
    return best


# ---------------------------------------------------------------- render
def render(now, events, wx, error=None):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    M = 24
    today = now.date()

    # Header: date
    d.text((M, 18), now.strftime("%A"), font=font(44, True), fill=0)
    d.text((M, 72), now.strftime("%B %-d, %Y"), font=font(26), fill=0)

    # Header: current weather
    if wx:
        cur = wx["current"]
        unit = "°"
        draw_icon(d, icon_kind(cur["weather_code"]), W - 210, 62, 80)
        t = f"{round(cur['temperature_2m'])}{unit}"
        f = font(60, True)
        d.text((W - M - d.textlength(t, font=f), 14), t, font=f, fill=0)
        dl = wx["daily"]
        sub = f"H {round(dl['temperature_2m_max'][0])}°  L {round(dl['temperature_2m_min'][0])}°"
        f2 = font(20)
        d.text((W - M - d.textlength(sub, font=f2), 88), sub, font=f2, fill=0)

    y = 124
    d.line([M, y, W - M, y], fill=0, width=3)

    # Hourly strip (next 6 slots, every 2 h)
    if wx:
        hr = wx["hourly"]
        times = [dt.datetime.fromisoformat(t).replace(tzinfo=TZ) for t in hr["time"]]
        idx = next(i for i, t in enumerate(times) if t >= now.replace(minute=0, second=0, microsecond=0))
        slots = [idx + 2 * k for k in range(6) if idx + 2 * k < len(times)]
        col = (W - 2 * M) / len(slots)
        for k, i in enumerate(slots):
            cx = M + col * k + col / 2
            lab = "Now" if k == 0 else fmt_time(times[i])
            f = font(18)
            d.text((cx - d.textlength(lab, font=f) / 2, y + 10), lab, font=f, fill=0)
            draw_icon(d, icon_kind(hr["weather_code"][i]), cx, y + 62, 44)
            tt = f"{round(hr['temperature_2m'][i])}°"
            f = font(22, True)
            d.text((cx - d.textlength(tt, font=f) / 2, y + 92), tt, font=f, fill=0)
            pp = hr["precipitation_probability"][i]
            if pp and pp >= 20:
                s = f"{pp}%"
                f = font(15)
                d.text((cx - d.textlength(s, font=f) / 2, y + 120), s, font=f, fill=90)
        y += 146
        d.line([M, y, W - M, y], fill=0, width=1)

    # Agenda
    y += 12
    title_f, time_f, head_f = font(24), font(20, True), font(20, True)
    bottom = H - 120
    shown_any = False
    current_day = None
    for ev in events:
        day = ev["start"].date() if not ev["all_day"] else ev["start"].date()
        if ev["all_day"] and ev["start"].date() < today:
            day = today
        if day != current_day:
            if y + 34 > bottom: break
            current_day = day
            label = day_label(day, today)
            if day != today:
                label += "  " + day.strftime("%b %-d")
            d.rectangle([M, y, W - M, y + 30], fill=0)
            d.text((M + 10, y + 2), label.upper(), font=head_f, fill=255)
            y += 38
        if y + 34 > bottom:
            break
        tlabel = "All day" if ev["all_day"] else fmt_time(ev["start"])
        d.text((M + 4, y + 3), tlabel, font=time_f, fill=0)
        d.text((M + 110, y), fit(d, ev["title"], title_f, W - 2 * M - 110), font=title_f, fill=0)
        y += 36
        shown_any = True
    if not shown_any:
        d.text((M + 4, y + 4), "No upcoming events", font=title_f, fill=110)

    # Footer: 3-day forecast + alarm + update stamp
    fy = H - 112
    d.line([M, fy, W - M, fy], fill=0, width=3)
    if wx:
        dl = wx["daily"]
        col = (W - 2 * M - 170) / 3
        for k in range(1, 4):
            if k >= len(dl["time"]): break
            cx = M + col * (k - 1) + col / 2
            name = dt.date.fromisoformat(dl["time"][k]).strftime("%a")
            f = font(18, True)
            d.text((cx - d.textlength(name, font=f) / 2, fy + 8), name, font=f, fill=0)
            draw_icon(d, icon_kind(dl["weather_code"][k]), cx, fy + 52, 38)
            s = f"{round(dl['temperature_2m_max'][k])}° / {round(dl['temperature_2m_min'][k])}°"
            f = font(17)
            d.text((cx - d.textlength(s, font=f) / 2, fy + 78), s, font=f, fill=0)

    na = next_alarm(now, parse_alarms(os.environ.get("ALARMS", "")))
    ax = W - M - 160
    d.text((ax, fy + 10), "ALARM", font=font(16, True), fill=0)
    if na:
        when = na.strftime("%a ") if na.date() != today else ""
        d.text((ax, fy + 30), when + na.strftime("%-I:%M %p"), font=font(26, True), fill=0)
    else:
        d.text((ax, fy + 30), "Off", font=font(26, True), fill=0)
    stamp = "Updated " + now.strftime("%-I:%M %p")
    if error:
        stamp = "! " + error[:28]
    d.text((ax, fy + 70), stamp, font=font(15), fill=90)

    return img


def render_alarm(now):
    """Black full-screen alarm card; the Kindle flips between this and the dashboard."""
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    # simple bell
    cx, cy = W // 2, 250
    d.pieslice([cx - 110, cy - 120, cx + 110, cy + 100], 180, 360, fill=255)
    d.rectangle([cx - 110, cy - 10, cx + 110, cy + 90], fill=255)
    d.polygon([(cx - 110, cy + 90), (cx - 150, cy + 130), (cx + 150, cy + 130), (cx + 110, cy + 90)], fill=255)
    d.ellipse([cx - 28, cy + 130, cx + 28, cy + 180], fill=255)
    d.ellipse([cx - 18, cy - 150, cx + 18, cy - 114], fill=255)
    f = font(96, True)
    t = "WAKE UP"
    d.text(((W - d.textlength(t, font=f)) / 2, 470), t, font=f, fill=255)
    f = font(40)
    t = now.strftime("%A, %B %-d")
    d.text(((W - d.textlength(t, font=f)) / 2, 610), t, font=f, fill=255)
    return img


def main():
    now = dt.datetime.now(TZ)
    errors = []
    try:
        events = fetch_events(now)
    except Exception as e:  # keep rendering even if one source fails
        events, _ = [], errors.append(f"calendar: {e}")
    try:
        wx = fetch_weather()
    except Exception as e:
        wx, _ = None, errors.append(f"weather: {e}")
    for e in errors:
        print("WARN", e, file=sys.stderr)
    img = render(now, events, wx, error=errors[0] if errors else None)
    # Kindle 4 eips wants an 8-bit grayscale PNG at native resolution
    img.save(OUT, optimize=True)
    alarm_out = os.environ.get("ALARM_OUT", os.path.join(os.path.dirname(OUT) or ".", "alarm.png"))
    render_alarm(now).save(alarm_out, optimize=True)
    print("wrote", OUT, alarm_out)


if __name__ == "__main__":
    main()
