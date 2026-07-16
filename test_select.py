import sys, termios, tty, re
class C:
    BLD = "\033[1m"; DIM = "\033[2m"; RST = "\033[0m"; BLU = "\033[0;34m"; GRN = "\033[0;32m"; YLW = "\033[1;33m"; CYN = "\033[0;36m"

def get_char():
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

def interactive_select(options):
    selected = [False] * len(options)
    cursor = 0
    window_start = 0
    max_display = 5
    search_mode = False
    search_query = ""
    
    sys.stdout.write("\033[?25l")
    
    def render():
        nonlocal window_start, cursor
        filtered_indices = [i for i, (title, _) in enumerate(options) if search_query.lower() in title.lower()]
        
        if cursor >= len(filtered_indices):
            cursor = max(0, len(filtered_indices) - 1)
            
        if cursor < window_start:
            window_start = cursor
        elif cursor >= window_start + max_display:
            window_start = cursor - max_display + 1
            
        display_indices = filtered_indices[window_start:window_start + max_display]
        
        if getattr(render, "rendered", False):
            sys.stdout.write(f"\033[{max_display + 3}A")
            
        print(f"\n  {C.BLD}Select releases to download (Space to toggle, Enter to confirm, / to search, Up/Down to navigate):{C.RST}\033[K")
        if search_mode or search_query:
            cursor_char = "█" if search_mode else ""
            print(f"  {C.CYN}Search:{C.RST} {search_query}{cursor_char}\033[K")
        else:
            print(f"  {C.DIM}(Press / to search){C.RST}\033[K")
            
        for i in range(max_display):
            if i < len(display_indices):
                actual_idx = display_indices[i]
                title = options[actual_idx][0]
                marker = f"{C.BLU}❯{C.RST}" if i + window_start == cursor else " "
                checkbox = f"[{C.GRN}x{C.RST}]" if selected[actual_idx] else "[ ]"
                color = C.BLD if i + window_start == cursor else C.DIM
                prefix = "  "
                print(f"  {marker} {checkbox} {prefix}{color}{title}{C.RST}\033[K")
            else:
                print("\033[K")
                
        sys.stdout.flush()
        render.rendered = True

    render()
    
    while True:
        c = get_char()
        if search_mode:
            if c == '\r' or c == '\n' or c == '\x1b':
                search_mode = False
            elif c in ('\x7f', '\x08'):
                search_query = search_query[:-1]
            elif len(c) == 1 and c.isprintable():
                search_query += c
                cursor = 0
                window_start = 0
        else:
            if c == '\r' or c == '\n':
                break
            elif c == '/':
                search_mode = True
            elif c == ' ':
                filtered_indices = [i for i, (title, _) in enumerate(options) if search_query.lower() in title.lower()]
                if filtered_indices:
                    actual_idx = filtered_indices[cursor]
                    selected[actual_idx] = not selected[actual_idx]
            elif c == '\x1b[A': # Up
                cursor = max(0, cursor - 1)
            elif c == '\x1b[B': # Down
                filtered_indices = [i for i, (title, _) in enumerate(options) if search_query.lower() in title.lower()]
                cursor = min(len(filtered_indices) - 1, cursor + 1)
            elif c == 'q':
                sys.stdout.write("\033[?25h\n")
                sys.exit(0)
        render()
        
    sys.stdout.write("\033[?25h\n")
    return [options[i][1] for i, is_sel in enumerate(selected) if is_sel]

options = [(f"Album {i}", f"url{i}") for i in range(10)]
interactive_select(options)
