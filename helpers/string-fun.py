import re

# Mapping of IAST characters to ASCII equivalents
IAST_TO_ASCII = {
    # Long vowels
    "ā": "a", "ī": "i", "ū": "u",
    "Ā": "A", "Ī": "I", "Ū": "U",

    # Vocalic r and l
    "ṛ": "r", "ṝ": "r", "ḷ": "l", "ḹ": "l",
    "Ṛ": "R", "Ṝ": "R", "Ḷ": "L", "Ḹ": "L",

    # Anusvara and visarga
    "ṃ": "m", "ṁ": "m", "ḥ": "h",
    "Ṃ": "M", "Ṁ": "M", "Ḥ": "H",

    # Consonants with diacritics
    "ṅ": "n", "ñ": "n", "ṭ": "t", "ḍ": "d", "ś": "s", "ṣ": "s",
    "Ṅ": "N", "Ñ": "N", "Ṭ": "T", "Ḍ": "D", "Ś": "S", "Ṣ": "S",
}

def iast_to_ascii(word: str) -> str:
    """Convert an IAST Sanskrit word to ASCII-only form."""
    return ''.join(IAST_TO_ASCII.get(ch, ch) for ch in word)

# Example usage
words = ["ātmā", "Śiva", "śaktiḥ", "viśva", "Brahmā"]
for w in words:
    print(w, "→", iast_to_ascii(w))
