"""Generate a synthetic Lumen Analytics data room (and its gold key, kept outside the room)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agora.dataroom.generate import generate_dataroom


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="make_dataroom")
    p.add_argument("--variant", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--gold", required=True)
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    try:
        generate_dataroom(args.variant, args.out, args.gold)
    except (ValueError, OSError) as e:
        print(f"error: {' '.join(str(e).split())}", file=sys.stderr)
        return 1
    n = sum(1 for f in Path(args.out).rglob("*") if f.is_file())
    print(f"wrote {n} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
