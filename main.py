import os
import random
import re
import time
import subprocess
import tempfile
import shutil
import logging
import argparse
import sys
from collections import defaultdict

# Try to import Figlet for fancy banner
try:
    from pyfiglet import Figlet
except ImportError:
    Figlet = None

# Configuration via environment variables
SANITIZE_DEFAULT = os.getenv('COMBOSORTER_SANITIZE', '1') != '0'
ENFORCE_STRICT_DEFAULT = os.getenv('COMBOSORTER_STRICT', '0') == '1'
LOWERCASE_PASSWORD_DEFAULT = os.getenv('COMBOSORTER_LOWERCASE_PASSWORD', '0') == '1'
LOG_LEVEL = os.getenv('COMBOSORTER_LOG_LEVEL', 'INFO').upper()

# Setup logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format='[%(levelname)s] %(message)s')

def find_gsort():
    # Prefer 'gsort' (GNU coreutils on macOS), fallback to 'sort'
    for cmd in ['gsort', 'sort']:
        path = shutil.which(cmd)
        if path:
            try:
                if "--version" in subprocess.check_output([path, "--version"], text=True, stderr=subprocess.STDOUT).lower():
                    return path
            except:
                pass
    return shutil.which('sort')

GSORT_PATH = find_gsort()

# Regex for email validation
EMAIL_SIMPLE_RE = re.compile(r".+@.+\..+")
EMAIL_STRICT_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

def sanitize_left_part(left):
    original = left
    left = left.strip()
    if not left: return left, False
    if '@' in left:
        parts = left.split('@', 1)
        local, domain = parts[0], parts[1] if len(parts) > 1 else ""
        local = re.sub(r'^[^A-Za-z0-9]+', '', local)
        local = re.sub(r'[^A-Za-z0-9._%+\-]+', '', local)
        local = re.sub(r'\.{2,}', '.', local)
        domain = domain.lower()
        domain = re.sub(r'[^A-Za-z0-9.\-]+', '', domain)
        domain = re.sub(r'\.{2,}', '.', domain)
        sanitized = f"{local}@{domain}" if local and domain else original
    else:
        s = re.sub(r'^[^A-Za-z0-9]+', '', left)
        s = re.sub(r'[^A-Za-z0-9._%+\-]+', '', s)
        sanitized = s if s else original
    return sanitized, (sanitized != original)

def split_combo(line):
    parts = re.split(r"\s*:\s*", line.rstrip('\n'), maxsplit=1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], '')

def join_combo(left, right):
    return f"{left}:{right}" if right != '' else left

def make_outpath(input_path, module_key):
    base = os.path.splitext(os.path.basename(input_path))[0]
    directory = os.path.dirname(input_path) or os.getcwd()
    return os.path.join(directory, f"{base}_{module_key}.txt")

def report_progress(count, text="Processing", finished=False):
    """Visual progress counter that updates on the same line."""
    if finished:
        sys.stdout.write(f"\r[+] {text}: {count:,} lines completed.                            \n")
    else:
        # Update more frequently for a "live" feel
        if count % 10000 == 0:
            sys.stdout.write(f"\r[*] {text}: {count:,} lines...")
            sys.stdout.flush()

# --- TRULY STREAMING PROCESSING MODULES ---

def normal_edit_stream(in_path, out_path):
    p = o = 0
    with open(in_path, 'r', encoding='utf-8', errors='ignore') as inf, open(out_path, 'w', encoding='utf-8') as outf:
        for line in inf:
            p += 1; report_progress(p)
            s = line.strip()
            if s: outf.write(s + '\n'); o += 1
    report_progress(p, "Normal Edit", finished=True)
    return p, o

def strong_edit_stream(in_path, out_path, enforce_strict=False, sanitize=False):
    p = o = 0
    with open(in_path, 'r', encoding='utf-8', errors='ignore') as inf, open(out_path, 'w', encoding='utf-8') as outf:
        for line in inf:
            p += 1; report_progress(p)
            s = line.strip()
            if not s: continue
            left, right = split_combo(s)
            if sanitize:
                new_left, changed = sanitize_left_part(left)
                if changed: left = new_left
            ok = EMAIL_STRICT_RE.fullmatch(left) if enforce_strict else EMAIL_SIMPLE_RE.fullmatch(left)
            if ok: outf.write(join_combo(left, right) + '\n'); o += 1
    report_progress(p, "Strong Edit", finished=True)
    return p, o

def extreme_edit_stream(in_path, out_path, enforce_strict=True, sanitize=True):
    p = o = 0
    seen = set()
    with open(in_path, 'r', encoding='utf-8', errors='ignore') as inf, open(out_path, 'w', encoding='utf-8') as outf:
        for line in inf:
            p += 1
            if p % 10000 == 0:
                sys.stdout.write(f"\r[*] Extreme Edit: {p:,} lines (Unique: {len(seen):,})...")
                sys.stdout.flush()
            s = line.strip()
            if not s: continue
            left, right = split_combo(s)
            if sanitize:
                new_left, changed = sanitize_left_part(left)
                if changed: left = new_left
            ok = EMAIL_STRICT_RE.fullmatch(left) if enforce_strict else EMAIL_SIMPLE_RE.fullmatch(left)
            if ok:
                left_out = left.lower()
                dedupe_key = hash((left_out, right))
                if dedupe_key not in seen:
                    seen.add(dedupe_key)
                    outf.write(join_combo(left_out, right) + '\n')
                    o += 1
    report_progress(p, "Extreme Edit", finished=True)
    return p, o

def domain_filter_stream(in_path, out_path, domain):
    p = o = 0
    domain = domain.lower().lstrip('@')
    with open(in_path, 'r', encoding='utf-8', errors='ignore') as inf, open(out_path, 'w', encoding='utf-8') as outf:
        for line in inf:
            p += 1; report_progress(p)
            left, _ = split_combo(line)
            if '@' in left and left.lower().endswith(domain):
                outf.write(line.strip() + '\n'); o += 1
    report_progress(p, f"Domain Filter (@{domain})", finished=True)
    return p, o

def country_filter_stream(in_path, out_path, code):
    p = o = 0
    code = code.lower()
    if not code.startswith('.'): code = '.' + code
    with open(in_path, 'r', encoding='utf-8', errors='ignore') as inf, open(out_path, 'w', encoding='utf-8') as outf:
        for line in inf:
            p += 1; report_progress(p)
            left, _ = split_combo(line)
            if '@' in left:
                dom = left.split('@', 1)[1].lower()
                if dom.endswith(code):
                    outf.write(line.strip() + '\n'); o += 1
    report_progress(p, f"Country Filter ({code})", finished=True)
    return p, o

def password_length_stream(in_path, out_path, mn, mx):
    p = o = 0
    with open(in_path, 'r', encoding='utf-8', errors='ignore') as inf, open(out_path, 'w', encoding='utf-8') as outf:
        for line in inf:
            p += 1; report_progress(p)
            _, right = split_combo(line)
            if mn <= len(right) <= mx:
                outf.write(line.strip() + '\n'); o += 1
    report_progress(p, f"Password Filter ({mn}-{mx})", finished=True)
    return p, o

def email_length_stream(in_path, out_path, mn, mx):
    p = o = 0
    with open(in_path, 'r', encoding='utf-8', errors='ignore') as inf, open(out_path, 'w', encoding='utf-8') as outf:
        for line in inf:
            p += 1; report_progress(p)
            left, _ = split_combo(line)
            if mn <= len(left) <= mx:
                outf.write(line.strip() + '\n'); o += 1
    report_progress(p, f"Email Filter ({mn}-{mx})", finished=True)
    return p, o

def remove_custom_stream(in_path, out_path, part, pattern, is_regex=False):
    p = o = 0
    prog = re.compile(pattern) if is_regex else None
    with open(in_path, 'r', encoding='utf-8', errors='ignore') as inf, open(out_path, 'w', encoding='utf-8') as outf:
        for line in inf:
            p += 1; report_progress(p)
            left, right = split_combo(line)
            if part == 'left':
                left = prog.sub('', left) if is_regex else left.replace(pattern, '')
            else:
                right = prog.sub('', right) if is_regex else right.replace(pattern, '')
            outf.write(join_combo(left, right) + '\n'); o += 1
    report_progress(p, "Remove Custom", finished=True)
    return p, o

def split_domain_files_stream(in_path, out_dir):
    p = o = 0
    os.makedirs(out_dir, exist_ok=True)
    handles = {}
    total_domains = 0
    try:
        with open(in_path, 'r', encoding='utf-8', errors='ignore') as inf:
            for line in inf:
                p += 1
                if p % 10000 == 0:
                    sys.stdout.write(f"\r[*] Splitting: {p:,} lines ({len(handles)} domains)...")
                    sys.stdout.flush()
                left, right = split_combo(line)
                domain = 'no_domain'
                if '@' in left:
                    domain = left.split('@', 1)[1].lower()
                    domain = re.sub(r'[^a-z0-9._\-]', '', domain)
                if domain not in handles:
                    handles[domain] = open(os.path.join(out_dir, f"{domain}.txt"), 'a', encoding='utf-8')
                handles[domain].write(join_combo(left, right) + '\n'); o += 1
    finally:
        for h in handles.values(): h.close()
    report_progress(p, "Split Domain", finished=True)
    return p, o, [os.path.join(out_dir, f"{d}.txt") for d in handles.keys()]

def run_gsort_dedupe(in_path, out_path):
    if not GSORT_PATH: raise RuntimeError('No sort binary available')
    env = dict(os.environ); env['LC_ALL'] = 'C'
    sys.stdout.write(f"[*] Starting External Dedupe (GNU Sort)...\n")
    # Parallelize for performance on Mac
    cmd = [GSORT_PATH, '-u', in_path, '-o', out_path, '--parallel=4', '-S', '2G']
    subprocess.run(cmd, check=True, env=env)
    p = sum(1 for _ in open(in_path, 'r', errors='ignore'))
    o = sum(1 for _ in open(out_path, 'r', errors='ignore'))
    report_progress(p, "External Dedupe", finished=True)
    return p, o

# --- CHAIN PROCESSING LOGIC ---

def process_chain(in_path, choices, params=None):
    if params is None: params = {}
    if isinstance(choices, str): choices = choices.split(',')
    choices = [c.strip().upper() for c in choices if c.strip()]
    temp_in = in_path
    prev_temp = None
    try:
        for idx, ch in enumerate(choices):
            is_last = (idx == len(choices) - 1)
            out_path = make_outpath(in_path, ch) if is_last else tempfile.NamedTemporaryFile(delete=False).name
            
            if ch == '0': p, o = normal_edit_stream(temp_in, out_path)
            elif ch == '1': p, o = strong_edit_stream(temp_in, out_path, params.get('strict', False), params.get('sanitize', True))
            elif ch == '2': p, o = extreme_edit_stream(temp_in, out_path, True, True)
            elif ch in ('3', '4'):
                p = o = 0
                label = "Capitalize" if ch == '3' else "Decapitalize"
                with open(temp_in, 'r', errors='ignore') as f, open(out_path, 'w') as out:
                    for l in f:
                        p += 1; report_progress(p, label)
                        left, right = split_combo(l)
                        left = left.upper() if ch == '3' else left.lower()
                        out.write(join_combo(left, right) + '\n'); o += 1
                report_progress(p, label, finished=True)
            elif ch == '5':
                sys.stdout.write("[!] Randomizing in RAM (may be slow)...\n")
                with open(temp_in, 'r', errors='ignore') as f: lines = f.readlines()
                random.shuffle(lines)
                with open(out_path, 'w') as out: out.writelines(lines)
                p = o = len(lines)
                report_progress(p, "Randomize", finished=True)
            elif ch == '6':
                sys.stdout.write("[*] Sorting Alphabetically...\n")
                if GSORT_PATH:
                    env = dict(os.environ); env['LC_ALL'] = 'C'
                    subprocess.run([GSORT_PATH, temp_in, '-o', out_path], env=env, check=True)
                    p = o = 0
                else:
                    with open(temp_in, 'r', errors='ignore') as f: lines = f.readlines()
                    lines.sort(key=lambda x: x.lower())
                    with open(out_path, 'w') as out: out.writelines(lines)
                    p = o = len(lines)
                report_progress(o, "Alphabetize", finished=True)
            elif ch == '7': p, o = domain_filter_stream(temp_in, out_path, params.get('domain', ''))
            elif ch == '8': p, o = country_filter_stream(temp_in, out_path, params.get('country', ''))
            elif ch == '9':
                p = o = 0; dom = params.get('domain', '')
                with open(temp_in, 'r', errors='ignore') as f, open(out_path, 'w') as out:
                    for l in f:
                        p += 1; report_progress(p, "Appending Domain")
                        left, right = split_combo(l); 
                        if left and '@' not in left: left = f"{left}@{dom}"
                        out.write(join_combo(left, right) + '\n'); o += 1
                report_progress(p, "U/P to E/P", finished=True)
            elif ch == 'A':
                p = o = 0
                with open(temp_in, 'r', errors='ignore') as f, open(out_path, 'w') as out:
                    for l in f:
                        p += 1; report_progress(p, "Removing Domain")
                        left, right = split_combo(l)
                        if '@' in left: left = left.split('@', 1)[0]
                        out.write(join_combo(left, right) + '\n'); o += 1
                report_progress(p, "E/P to U/P", finished=True)
            elif ch == 'B':
                p = o = 0; app = params.get('append', ''); part = params.get('append_part', 'R')
                with open(temp_in, 'r', errors='ignore') as f, open(out_path, 'w') as out:
                    for l in f:
                        p += 1; report_progress(p, "Appending")
                        left, right = split_combo(l)
                        if part == 'L': left += app
                        else: right += app
                        out.write(join_combo(left, right) + '\n'); o += 1
                report_progress(p, "Custom Append", finished=True)
            elif ch == 'C': p, o = password_length_stream(temp_in, out_path, params.get('min_pass', 0), params.get('max_pass', 999))
            elif ch == 'D': p, o = email_length_stream(temp_in, out_path, params.get('min_email', 0), params.get('max_email', 999))
            elif ch == 'E': p, o = remove_custom_stream(temp_in, out_path, params.get('remove_part', 'L'), params.get('pattern', ''), params.get('pattern_is_regex', False))
            elif ch == 'F': p, o, _ = split_domain_files_stream(temp_in, params.get('out_dir', '.'))
            elif ch == 'G':
                if GSORT_PATH: p, o = run_gsort_dedupe(temp_in, out_path)
                else:
                    seen = set(); p = o = 0
                    with open(temp_in, 'r', errors='ignore') as f, open(out_path, 'w') as out:
                        for l in f:
                            p += 1; h = hash(l)
                            if p % 10000 == 0: sys.stdout.write(f"\r[*] Dedupe: {p:,} lines (Unique: {len(seen):,})..."); sys.stdout.flush()
                            if h not in seen: seen.add(h); out.write(l); o += 1
                    report_progress(p, "Internal Dedupe", finished=True)
            else: continue

            if prev_temp: os.unlink(prev_temp)
            prev_temp = temp_in if temp_in != in_path else None
            temp_in = out_path
        return temp_in
    finally:
        if prev_temp and os.path.exists(prev_temp): os.unlink(prev_temp)

def print_banner():
    """Print a dynamic banner that fits the terminal width."""
    terminal_width = shutil.get_terminal_size((100, 20)).columns
    banner_text = "DK3Y Combo Sorter"
    subtitle_text = "A powerful, streaming combo processing tool"
    
    # ANSI color codes - rotating hacker colors
    COLORS = [
        "\033[92m",  # Bright green
        "\033[96m",  # Bright cyan
        "\033[93m",  # Bright yellow
        "\033[91m",  # Bright red
        "\033[95m",  # Bright magenta
    ]
    RESET = "\033[0m"   # Reset to default color
    
    if Figlet:
        # Try slant font for that cool hacker aesthetic, fall back to others
        fonts_to_try = ['slant', 'banner', 'big']
        
        for font in fonts_to_try:
            try:
                f = Figlet(font=font, width=terminal_width)
                banner = f.renderText(banner_text)
                subtitle = f.renderText(subtitle_text)
                
                # Rotate colors for each line
                banner_lines = banner.split('\n')
                colored_banner = '\n'.join(
                    f"{COLORS[i % len(COLORS)]}{line}{RESET}" 
                    for i, line in enumerate(banner_lines)
                )
                
                subtitle_lines = subtitle.split('\n')
                colored_subtitle = '\n'.join(
                    f"{COLORS[(i + len(banner_lines)) % len(COLORS)]}{line}{RESET}" 
                    for i, line in enumerate(subtitle_lines)
                )
                
                print(colored_banner)
                print(colored_subtitle)
                return
            except:
                continue
        
        # Fallback to default if all fonts fail
        f = Figlet(width=terminal_width)
        banner = f.renderText(banner_text)
        subtitle = f.renderText(subtitle_text)
        
        banner_lines = banner.split('\n')
        colored_banner = '\n'.join(
            f"{COLORS[i % len(COLORS)]}{line}{RESET}" 
            for i, line in enumerate(banner_lines)
        )
        
        subtitle_lines = subtitle.split('\n')
        colored_subtitle = '\n'.join(
            f"{COLORS[(i + len(banner_lines)) % len(COLORS)]}{line}{RESET}" 
            for i, line in enumerate(subtitle_lines)
        )
        
        print(colored_banner)
        print(colored_subtitle)
    else:
        # Fallback if pyfiglet is not available
        separator = "=" * min(len(banner_text) + 4, terminal_width)
        centered_text = f"  {banner_text}  ".center(terminal_width)
        centered_subtitle = f"  {subtitle_text}  ".center(terminal_width)
        
        print(f"{COLORS[0]}{separator}")
        print(f"{COLORS[1]}{centered_text}")
        print(f"{COLORS[2]}{centered_subtitle}")
        print(f"{COLORS[3]}{separator}{RESET}")

def main():
    print_banner()
    print("""
    [0] Normal Edit        [A] E/P to U/P
    [1] Strong Edit        [B] Custom Append
    [2] Extreme Edit       [C] Password Length
    [3] Capitalize         [D] Email Length
    [4] Decapitalize       [E] Remove Custom
    [5] Randomize          [F] Split Domain
    [6] Alphabetize        [G] Remove Duplicate
    [7] Domain Filter      [Q] Quit
    [8] Country Filter
    [9] U/P to E/P
    ==============================
    """)
    while True:
        choice = input('Enter module(s) [e.g. 2,G] or Q to quit: ').strip().upper()
        if not choice or choice == 'Q': break
        
        in_path = input('Enter input file path: ').strip()
        if not os.path.exists(in_path):
            print(f"Error: File '{in_path}' not found.")
            continue
            
        params = {}
        valid = True
        for ch in choice.split(','):
            ch = ch.strip()
            if ch == '7' or ch == '9': params['domain'] = input(f'Module {ch} - Enter domain: ').strip()
            elif ch == '8': params['country'] = input('Module 8 - Enter country code: ').strip()
            elif ch == 'B':
                params['append'] = input('Module B - String to append: ')
                params['append_part'] = input('Part [L]eft or [R]ight: ').upper()
            elif ch == 'C':
                try:
                    params['min_pass'] = int(input('Min Length: ') or 0)
                    params['max_pass'] = int(input('Max Length: ') or 999)
                except ValueError: print("Invalid number."); valid = False
            elif ch == 'D':
                try:
                    params['min_email'] = int(input('Min Email Length: ') or 0)
                    params['max_email'] = int(input('Max Email Length: ') or 999)
                except ValueError: print("Invalid number."); valid = False
            elif ch == 'E':
                params['remove_part'] = input('Part [L]eft or [R]ight: ').upper()
                params['pattern'] = input('Pattern to remove: ')
                params['pattern_is_regex'] = input('Regex? [y/N]: ').lower() == 'y'
            elif ch == 'F': params['out_dir'] = input('Output Directory [Default .]: ').strip() or '.'
        
        if not valid: continue
        
        try:
            start_time = time.time()
            final = process_chain(in_path, choice, params)
            elapsed = time.time() - start_time
            print(f"\n[SUCCESS] Result: {final}")
            print(f"[TIME] Took {elapsed:.2f} seconds.")
        except KeyboardInterrupt:
            print("\n[!] Operation cancelled by user.")
        except Exception as e:
            print(f"\n[ERROR] {e}")

if __name__ == '__main__':
    main()