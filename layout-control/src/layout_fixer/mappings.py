EN_KEYS = "qwertyuiop[]asdfghjkl;'zxcvbnm,."
UK_KEYS = "йцукенгшщзхїфівапролджєячсмитьбю"

EN_TO_UK = str.maketrans(
    EN_KEYS + EN_KEYS.upper(),
    UK_KEYS + UK_KEYS.upper(),
)

UK_TO_EN = str.maketrans(
    UK_KEYS + UK_KEYS.upper(),
    EN_KEYS + EN_KEYS.upper(),
)
