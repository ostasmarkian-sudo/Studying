import keyboard
from detector import process_word


word_buffer = []


def handle_key(event):
    key = event.name
    if key == "backspace":
        if word_buffer:
            word_buffer.pop()

        return

    if key in ("space", "enter"):
        word = "".join(word_buffer)
        word_buffer.clear()

        if not word:
            return

        process_word(word)

    if len(key) == 1:
        word_buffer.append(key)
        return


keyboard.on_press(handle_key)
keyboard.wait("esc")
keyboard.unhook_all()
