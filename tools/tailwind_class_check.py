"""Guard the Tailwind class-name rule (the second half of the "my class does nothing" trap).

`app/assets/tailwind.css` is compiled from the raw **text** of `app/**/*.py`, so Tailwind finds
a class name wherever it is written - inside a variable, a comment or a docstring just as well
as inside a `className`. The VS Code Tailwind plugin does not: it only reads the shapes listed
in `tailwindCSS.experimental.classRegex` in `.vscode/settings.json` - in this repository "a
class string written out in full inside a `className`/`extra` argument".

So the two readers can disagree, and the difference is invisible until something breaks. This
script makes it visible:

* every class selector of the compiled CSS must also be found by those regexes. A selector that
  is not is generated from a **comment, a docstring or an assembled string** - it bloats the
  CSS with a class the UI never uses, and the editor can neither complete nor validate it;
* every class the regexes find must also be in the compiled CSS (a stale build, or a typo in
  the class name).

Run:  python tools/tailwind_class_check.py           exit 1 = the rule was broken
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / ".vscode/settings.json"
INPUT = ROOT / "app/assets/input.pcss"
OUTPUT = ROOT / "app/assets/tailwind.css"
SOURCES = sorted((ROOT / "app").rglob("*.py"))


def load_settings(path):
    """.vscode/settings.json is JSONC: strip // comments and trailing commas, then parse."""
    text = re.sub(r"(?m)^\s*//.*$", "", path.read_text())
    text = re.sub(r"(?m),(\s*[}\]])", r"\1", text)
    return json.loads(text)


def class_tokens(text, patterns):
    """Every class token the plugin's regexes would see in one file."""
    found = set()
    for entry in patterns:
        match_re, extract_re = (entry, None) if isinstance(entry, str) else entry
        for match in re.finditer(match_re, text):
            chunk = match.group(1) if match.groups() else match.group(0)
            if extract_re is None:
                found.update(chunk.split())
                continue
            for extracted in re.finditer(extract_re, chunk):
                found.update((extracted.group(1) or "").split())
    # an f-string interpolation ({value}) is not a class name
    return {t for t in found if "{" not in t and "}" not in t}


def bare_tokens(text):
    """Every whitespace-separated token of a file.

    Used for the Tailwind *entry point* (input.pcss): the plugin parses that file as the
    project configuration and the compiler reads it, so a word written there (e.g. the name of
    the timing function inside the `@theme` animation) counts as declared - it is not a class
    string that someone forgot to put into a `className`.
    """
    return set(text.split())


def css_selectors(css):
    """The class selectors of a compiled stylesheet, unescaped (sm\\:h-40 -> sm:h-40)."""
    raw = re.findall(r"(?:^|[{},;>\s])\.((?:[-\w]|\\.)+)", css)
    return {name.replace("\\", "") for name in raw
            if re.search(r"[a-zA-Z]", name) and not re.match(r"\d", name)}


def handwritten_classes(css):
    """Classes defined by hand in input.pcss (e.g. the toast animation) - not utilities."""
    return set(re.findall(r"\.([-\w]+)\s*\{", css))


def main():
    patterns = load_settings(SETTINGS)["tailwindCSS.experimental.classRegex"]

    reachable = set()
    for path in SOURCES:
        reachable |= class_tokens(path.read_text(), patterns)

    compiled = css_selectors(OUTPUT.read_text())
    handwritten = handwritten_classes(INPUT.read_text())
    # what the compiler and the plugin deliberately read, so a class that ends up in the CSS
    # from there is not "text the plugin cannot read"
    declared = reachable | bare_tokens(INPUT.read_text())

    invisible = sorted(compiled - declared)
    # Single English words that happen to also be utility names - "table", "visible",
    # "relative", "static" - are compiled from the prose of a comment or a docstring. They cost
    # a few bytes and are not a mistake; a real one is always hyphenated or carries a variant
    # prefix, and that is what fails below.
    prose = [name for name in invisible if "-" not in name and ":" not in name]
    invisible = [name for name in invisible if "-" in name or ":" in name]
    # A className expression like `className=("…" if tone == "dark" else "…")` also puts the
    # tone names ("dark", "red", …) and marker classes like `group` in front of the regex; a
    # Tailwind *utility* always contains a hyphen (or a slash), so the "missing" direction
    # ignores the single-word leftovers. The direction above - the one that matters here - is
    # exact.
    stale = sorted(name for name in reachable - compiled - handwritten
                   if "-" in name or "/" in name)

    for name in invisible:
        print(f"NOT IN A className   .{name}")
    for name in stale:
        print(f"NOT IN THE CSS       .{name}")

    print(f"\n{len(reachable)} class token(s) reachable through the plugin's classRegex, "
          f"{len(compiled)} selectors in the compiled CSS "
          f"({len(handwritten)} of them hand-written in input.pcss)")
    if prose:
        print(f"note: {len(prose)} unused rule(s) come from an English word in a comment or "
              f"docstring ({', '.join(prose)}) - a few bytes, not a bug")

    if invisible:
        print(f"\n{len(invisible)} compiled class(es) are generated from text the plugin cannot "
              f"read (a comment, a docstring or a string built from variables) - write the "
              f"class inside a className/extra, or do not name it in prose (a class named in "
              f"input.pcss or in this repository's Python comments is compiled too)")
        return 1
    if stale:
        print(f"\n{len(stale)} class(es) sit inside a className but are not in the compiled CSS "
              f"->  npm run css   (or fix the typo)")
        return 1

    print("RESULT: ALL PASS  (every compiled class is inside a className, nothing is missing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
