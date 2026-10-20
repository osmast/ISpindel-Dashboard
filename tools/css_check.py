"""Guard against a stale Tailwind build (the "my classes do nothing" trap).

`app/assets/tailwind.css` is a **build artefact**: Tailwind runs once and Dash then serves the
finished file statically - there is no JIT in the browser. A class that is added to
`app/main.py` or `app/components/*.py` therefore does **nothing** until the CSS is rebuilt.
The symptom is confusing, because only *new* classes are affected while everything else still
looks styled: `className="... bg-black ..."` shows no black background, `hover:bg-amber-500`
never fires, and the element looks half broken.

This script rebuilds the CSS into a temporary file with exactly the same arguments as
`npm run css` and compares it with the committed `app/assets/tailwind.css`. Identical output =
the artefact matches the sources. Different output = the CSS is stale, and it prints the
classes that the rebuild would add or remove.

Run:  python tools/css_check.py           check (exit 1 = rebuild needed)
      python tools/css_check.py --fix     rebuild app/assets/tailwind.css in place
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "app/assets/input.pcss"
OUTPUT = ROOT / "app/assets/tailwind.css"
ARGS = ["-i", str(INPUT), "-o", None, "--minify"]        # the arguments of `npm run css`

# The Tailwind CLI as npm installs it, then the standalone binary of README section 4.
CLI_CANDIDATES = [ROOT / "node_modules/.bin/tailwindcss", ROOT / "tailwindcss"]


def find_cli():
    for path in CLI_CANDIDATES:
        if path.is_file():
            return str(path)
    return shutil.which("tailwindcss")


def build(target):
    cli = find_cli()
    if not cli:
        print("SKIP  no tailwindcss CLI found (npm ci, or the standalone binary of README 4)")
        raise SystemExit(2)
    args = [a if a is not None else str(target) for a in ARGS]
    result = subprocess.run([cli] + args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout + result.stderr)
        raise SystemExit(2)


def selectors(css):
    """The class selectors of a compiled stylesheet (for a readable difference).

    Token names always contain a letter; the filter keeps decimals of colour functions
    (`oklch(.08 0 0)`) out of the report.
    """
    names = re.findall(r"\.((?:[-\w]|\\.)+)", css)
    return {n for n in names if re.search(r"[a-zA-Z]", n)}


def main():
    fix = "--fix" in sys.argv

    if fix:
        build(OUTPUT)
        print(f"rebuilt {OUTPUT.relative_to(ROOT)} from {INPUT.relative_to(ROOT)}")
        return 0

    if not OUTPUT.is_file():
        print(f"FAIL  {OUTPUT.relative_to(ROOT)} is missing - run:  npm run css")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "tailwind.css"
        build(fresh)
        rebuilt, committed = fresh.read_text(), OUTPUT.read_text()

    if rebuilt == committed:
        print("RESULT: ALL PASS  (the compiled CSS matches the sources)")
        return 0

    added = sorted(selectors(rebuilt) - selectors(committed))
    removed = sorted(selectors(committed) - selectors(rebuilt))
    for name in added:
        print(f"NOT IN THE CSS YET  .{name}")
    for name in removed:
        print(f"NO LONGER USED     .{name}")
    print(f"\n{len(added)} class(es) would be added, {len(removed)} removed "
          f"(committed {len(committed)} B, rebuilt {len(rebuilt)} B)")
    print("the compiled CSS is stale ->  python tools/css_check.py --fix   "
          "(or: npm run css)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
