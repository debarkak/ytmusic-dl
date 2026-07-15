import sys

def get_char():
    try:
        import msvcrt
        return msvcrt.getch().decode('utf-8')
    except ImportError:
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch += sys.stdin.read(2)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

print("Press a key (q to quit)")
while True:
    c = get_char()
    print(f"\r\nYou pressed: {repr(c)}")
    if c == 'q':
        break
