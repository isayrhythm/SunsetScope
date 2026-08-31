from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


@dataclass(frozen=True)
class CaptchaImage:
    challenge_id: str
    data_url: str


@dataclass
class _Challenge:
    digest: bytes
    client_ip: str
    expires_at: float


class CaptchaService:
    """Small, single-process image CAPTCHA store with one-time challenges."""

    def __init__(
        self,
        ttl_seconds: int = 300,
        max_challenges: int = 2000,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_challenges = max_challenges
        self._clock = clock
        self._challenges: "OrderedDict[str, _Challenge]" = OrderedDict()
        self._lock = threading.Lock()

    def create(self, client_ip: str) -> CaptchaImage:
        answer = "".join(secrets.choice(ALPHABET) for _ in range(4))
        challenge_id = secrets.token_urlsafe(24)
        digest = hashlib.sha256(answer.encode("ascii")).digest()
        now = self._clock()
        with self._lock:
            self._remove_expired(now)
            while len(self._challenges) >= self.max_challenges:
                self._challenges.popitem(last=False)
            self._challenges[challenge_id] = _Challenge(
                digest=digest,
                client_ip=client_ip,
                expires_at=now + self.ttl_seconds,
            )
        return CaptchaImage(challenge_id, _render_data_url(answer))

    def verify(self, challenge_id: str, answer: str, client_ip: str) -> bool:
        challenge_id = challenge_id.strip()
        normalized = answer.strip().upper()
        if len(challenge_id) > 64 or len(normalized) != 4:
            return False
        now = self._clock()
        with self._lock:
            self._remove_expired(now)
            challenge: Optional[_Challenge] = self._challenges.pop(challenge_id, None)
        if challenge is None or challenge.client_ip != client_ip:
            return False
        candidate = hashlib.sha256(normalized.encode("utf-8")).digest()
        return hmac.compare_digest(challenge.digest, candidate)

    def _remove_expired(self, now: float) -> None:
        expired = [key for key, value in self._challenges.items() if value.expires_at <= now]
        for key in expired:
            del self._challenges[key]


def _render_data_url(answer: str) -> str:
    random = secrets.SystemRandom()
    image = Image.new("RGB", (160, 54), (247, 242, 234))
    draw = ImageDraw.Draw(image)

    for _ in range(5):
        points = [(random.randrange(0, 160), random.randrange(4, 50)) for _ in range(3)]
        draw.line(points, fill=(random.randrange(90, 190), random.randrange(70, 150), random.randrange(90, 180)), width=2)
    for _ in range(110):
        x, y = random.randrange(0, 160), random.randrange(0, 54)
        shade = random.randrange(110, 215)
        draw.point((x, y), fill=(shade, random.randrange(90, 190), random.randrange(100, 205)))

    try:
        font = ImageFont.load_default(size=32)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    for index, character in enumerate(answer):
        glyph = Image.new("RGBA", (42, 48), (0, 0, 0, 0))
        glyph_draw = ImageDraw.Draw(glyph)
        glyph_draw.text(
            (8, 4), character, font=font,
            fill=(random.randrange(30, 85), random.randrange(25, 75), random.randrange(45, 105), 255),
        )
        glyph = glyph.rotate(random.randrange(-18, 19), resample=Image.Resampling.BICUBIC, expand=False)
        image.paste(glyph, (8 + index * 37, random.randrange(2, 8)), glyph)

    image = image.filter(ImageFilter.SMOOTH)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return "data:image/png;base64," + encoded
