#!/usr/bin/env python3
"""
Generate Fake TXT Attachments
============================

Creates .txt attachments for every YAML item in a given collection.
Each attachment filename follows the convention:

  <item>_<tag>-<hash>.txt

where <hash> is a short random hex string. The file content contains a
simple Lorem Ipsum paragraph with a small header.

Usage examples
- One attachment per item in _works under ./db:
  python3 src/gen_fake_attachments.py --root db --collection works

- Two attachments per item with custom tag and longer hash:
  python3 src/gen_fake_attachments.py --root db --collection _works \
      --tag demo --per-item 2 --hash-len 8

Notes
- The script writes attachments next to each item YAML (same directory).
- It will not overwrite existing files unless --overwrite is set.
"""
import argparse
from pathlib import Path
import secrets
from datetime import datetime


LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed non risus. "
    "Suspendisse lectus tortor, dignissim sit amet, adipiscing nec, ultricies sed, dolor. "
    "Cras elementum ultrices diam. Maecenas ligula massa, varius a, semper congue, euismod non, mi. "
    "Proin porttitor, orci nec nonummy molestie, enim est eleifend mi, non fermentum diam nisl sit amet erat."
)


def short_hex(n: int) -> str:
    # n hex chars -> n//2 bytes (round up).
    byte_len = (n + 1) // 2
    h = secrets.token_hex(byte_len)
    return h[:n]


def iter_items(collection_dir: Path):
    # Yield (item_id, yaml_path) for all YAML files under the collection dir.
    for yml in collection_dir.rglob("*.yaml"):
        yield yml.stem, yml


def make_attachment_name(item_id: str, tag: str, h: str) -> str:
    return f"{item_id}_{tag}-{h}.txt"


def write_attachment(dst: Path, item_id: str, tag: str, h: str, overwrite: bool) -> bool:
    if dst.exists() and not overwrite:
        return False
    meta = f"Generated: {datetime.utcnow().isoformat()}Z\nItem: {item_id}\nTag: {tag}-{h}\n\n"
    body = LOREM + "\n"
    dst.write_text(meta + body, encoding="utf-8")
    return True


def normalize_collection(name: str) -> str:
    return name if name.startswith("_") else f"_{name}"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Generate fake TXT attachments for a collection")
    ap.add_argument("--root", required=True, help="DB root path (contains underscore collections)")
    ap.add_argument("--collection", required=True, help="Collection name (e.g., works or _works)")
    ap.add_argument("--tag", default="fake", help="Base tag to use before the hash (default: fake)")
    ap.add_argument("--per-item", type=int, default=1, help="Number of attachments per item (default: 1)")
    ap.add_argument("--hash-len", type=int, default=5, help="Length of the random hex suffix (default: 5)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing attachments with the same name")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Root not found: {root}")
        return 2
    coll = normalize_collection(args.collection)
    coll_dir = root / coll
    if not coll_dir.exists() or not coll_dir.is_dir():
        print(f"Collection directory not found: {coll_dir}")
        return 2

    created = 0
    skipped = 0
    for item_id, yml_path in iter_items(coll_dir):
        for _ in range(max(1, args.per_item)):
            h = short_hex(max(1, args.hash_len))
            name = make_attachment_name(item_id, args.tag, h)
            dst = yml_path.parent / name
            if write_attachment(dst, item_id, args.tag, h, args.overwrite):
                created += 1
            else:
                skipped += 1

    print(f"Fake attachments: created={created}, skipped={skipped} in {coll_dir}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))

