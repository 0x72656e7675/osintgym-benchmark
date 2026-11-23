from __future__ import annotations

import colorsys
import io
from fractions import Fraction

from PIL import Image, ImageDraw, ImageFont

from ..rng import keyed
from .model import Photo


def _rgb(hue: int, saturation: float, value: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb((hue % 360) / 360, saturation, value)
    return int(r * 255), int(g * 255), int(b * 255)


def _dms(value: float) -> tuple[Fraction, Fraction, Fraction]:
    value = abs(value)
    degrees = int(value)
    minutes = int((value - degrees) * 60)
    seconds = Fraction(round(((value - degrees) * 60 - minutes) * 60 * 100), 100)
    return Fraction(degrees), Fraction(minutes), seconds


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def _fit(draw: ImageDraw.ImageDraw, text: str, width: int, start: int) -> ImageFont.FreeTypeFont:
    size = start
    while size > 12:
        font = _font(size)
        if draw.textlength(text, font=font) <= width:
            return font
        size -= 2
    return _font(12)


def _portrait(photo: Photo, seed: int) -> Image.Image:
    rng = keyed(seed, "portrait", photo.key)
    image = Image.new("RGB", (400, 400), _rgb(photo.hue, 0.25, 0.75))
    draw = ImageDraw.Draw(image)
    tone = _rgb(photo.hue + 180, 0.35, 0.35)
    for _ in range(18):
        x, y = rng.randint(0, 400), rng.randint(0, 400)
        r = rng.randint(10, 60)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=_rgb(photo.hue + rng.randint(-30, 30), 0.2, rng.uniform(0.6, 0.9)))
    draw.ellipse((140, 80, 260, 210), fill=tone)
    draw.rounded_rectangle((90, 220, 310, 420), radius=80, fill=tone)
    return image


def _scene(photo: Photo, seed: int) -> Image.Image:
    rng = keyed(seed, "scene", photo.key)
    width, height = 960, 640
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    sky_top, sky_bottom = _rgb(photo.hue, 0.35, 0.95), _rgb(photo.hue + 20, 0.15, 0.85)
    for y in range(height // 2):
        t = y / (height / 2)
        draw.line([(0, y), (width, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(sky_top, sky_bottom)))
    draw.rectangle((0, height // 2, width, height), fill=_rgb(photo.hue + 40, 0.1, 0.35))
    facade = _rgb(rng.randint(0, 359), 0.25, 0.7)
    left, right = rng.randint(60, 160), rng.randint(780, 900)
    draw.rectangle((left, 110, right, height - 90), fill=facade)
    for row in range(3):
        for column in range(6):
            x = left + 40 + column * (right - left - 80) // 6
            y = 140 + row * 70
            draw.rectangle((x, y, x + 48, y + 44), fill=_rgb(photo.hue + 200, 0.2, 0.3 + 0.1 * ((row + column) % 3)))
    if photo.sign:
        board = (left + 30, height - 230, right - 30, height - 130)
        draw.rectangle(board, fill=(24, 24, 28))
        font = _fit(draw, photo.sign[0], board[2] - board[0] - 40, 64)
        draw.text((board[0] + 20, board[1] + 14), photo.sign[0], font=font, fill=(245, 240, 225))
        if len(photo.sign) > 1:
            small = _fit(draw, photo.sign[1], 420, 26)
            plate = (right - 470, height - 80, right - 20, height - 36)
            draw.rectangle(plate, fill=(28, 70, 52))
            draw.text((plate[0] + 12, plate[1] + 8), photo.sign[1], font=small, fill=(235, 245, 235))
    draw.rectangle((0, height - 30, width, height), fill=_rgb(photo.hue + 60, 0.05, 0.25))
    return image


_cache: dict[tuple[int, str, bool], bytes] = {}


def _encode(photo: Photo, seed: int, exif: bool) -> bytes:
    image = _portrait(photo, seed) if not photo.sign and photo.venue is None else _scene(photo, seed)
    buffer = io.BytesIO()
    if not exif:
        image.save(buffer, "JPEG", quality=82)
        return buffer.getvalue()
    meta = Image.Exif()
    meta[0x010F] = photo.make
    meta[0x0110] = photo.model
    meta[0x0132] = photo.taken.strftime("%Y:%m:%d %H:%M:%S")
    if photo.comment:
        meta[0x010E] = photo.comment
    sub = meta.get_ifd(0x8769)
    sub[0x9003] = photo.taken.strftime("%Y:%m:%d %H:%M:%S")
    sub[0xA431] = photo.serial
    if photo.gps:
        gps = meta.get_ifd(0x8825)
        gps[1] = "S" if photo.lat < 0 else "N"
        gps[2] = _dms(photo.lat)
        gps[3] = "W" if photo.lon < 0 else "E"
        gps[4] = _dms(photo.lon)
    image.save(buffer, "JPEG", quality=82, exif=meta)
    return buffer.getvalue()


def render(photo: Photo, seed: int, *, exif: bool) -> bytes:
    key = (seed, photo.key, exif)
    data = _cache.get(key)
    if data is None:
        if len(_cache) > 1024:
            _cache.clear()
        data = _cache[key] = _encode(photo, seed, exif)
    return data
