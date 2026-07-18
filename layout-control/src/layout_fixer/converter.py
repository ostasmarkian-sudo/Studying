from mappings import EN_TO_UK, UK_TO_EN


def to_ukrainian(text: str) -> str:
    return text.translate(EN_TO_UK)


def to_english(text: str) -> str:
    return text.translate(UK_TO_EN)
