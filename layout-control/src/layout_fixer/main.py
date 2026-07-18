from converter import to_english, to_ukrainian


def main() -> None:
    text = input("Введіть текст: ")

    print(f"Український варіант: {to_ukrainian(text)}")
    print(f"Англійський варіант: {to_english(text)}")


if __name__ == "__main__":
    main()
