from wordfreq import zipf_frequency

from converter import to_english, to_ukrainian


MIN_WORD_LENGTH = 3
MIN_FREQUENCY = 2.5
MIN_DIFFERENCE = 1.0

PUNCTUATION = " \t\n.,!?;:()[]{}\"'«»“”"


def clean_word(word: str) -> str:
    return word.strip(PUNCTUATION).lower()


def should_skip(word: str) -> bool:
    cleaned = clean_word(word)

    if len(cleaned) < MIN_WORD_LENGTH:
        return True

    if any(character.isdigit() for character in cleaned):
        return True

    if "@" in word or "/" in word or "\\" in word:
        return True

    return False


def detect_word(word: str) -> dict:
    result = {
        "original": word,
        "suggestion": word,
        "language": None,
        "english_score": 0.0,
        "ukrainian_score": 0.0,
        "should_replace": False,
        "reason": "",
    }

    if should_skip(word):
        result["reason"] = "Слово пропущено"
        return result

    english_variant = to_english(word)
    ukrainian_variant = to_ukrainian(word)

    english_score = zipf_frequency(
        clean_word(english_variant),
        "en",
    )
    ukrainian_score = zipf_frequency(
        clean_word(ukrainian_variant),
        "uk",
    )

    result["english_score"] = english_score
    result["ukrainian_score"] = ukrainian_score

    best_score = max(english_score, ukrainian_score)
    difference = abs(english_score - ukrainian_score)

    if best_score < MIN_FREQUENCY:
        result["reason"] = "Обидва варіанти невідомі"
        return result

    if difference < MIN_DIFFERENCE:
        result["reason"] = "Недостатня різниця між варіантами"
        return result

    if english_score > ukrainian_score:
        suggestion = english_variant
        language = "en"
    else:
        suggestion = ukrainian_variant
        language = "uk"

    result["suggestion"] = suggestion
    result["language"] = language
    result["should_replace"] = suggestion.casefold() != word.casefold()

    return result


def process_word(word: str) -> dict:
    result = detect_word(word)

    print(f"Original: {result['original']}")
    print(f"suggestion: {result['suggestion']}")
    print(f"language: {result['language']}")
    print(f"should_replace: {result['should_replace']}")
    print()

    return result
