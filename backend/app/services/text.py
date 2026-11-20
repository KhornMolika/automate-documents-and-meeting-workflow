import re

_KHMER_RANGE = re.compile(r"[\u1780-\u17FF]")


def has_khmer(text: str | None) -> bool:
    return bool(text and _KHMER_RANGE.search(text))


def normalize_khmer_text(text: str | None) -> str:
    """Keep Khmer text natural without changing recognized words."""
    value = re.sub(r"[ \t]+", " ", (text or "").strip())
    value = re.sub(r"(?<=[\u1780-\u17FF])\s+(?=[\u1780-\u17FF])", "", value)
    value = re.sub(r"\s*។\s*", "។", value)
    return re.sub(r"\s+", " ", value).strip()
