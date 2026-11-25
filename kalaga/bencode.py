"""Minimal bencode reader, enough to read a .torrent manifest.

Torrent files are the only public description of a release's file list, so the
validator can use one as an integrity manifest without shipping any game data.
Only decoding is implemented; keys and strings come back as ``bytes``.
"""

from __future__ import annotations

from pathlib import Path


class BencodeError(ValueError):
    pass


def _decode(data: bytes, index: int):
    if index >= len(data):
        raise BencodeError("unexpected end of data")
    char = data[index : index + 1]
    if char == b"i":
        end = data.index(b"e", index)
        return int(data[index + 1 : end]), end + 1
    if char in (b"l", b"d"):
        index += 1
        out = [] if char == b"l" else {}
        while index < len(data) and data[index : index + 1] != b"e":
            key, index = _decode(data, index)
            if char == b"d":
                value, index = _decode(data, index)
                out[key] = value
            else:
                out.append(key)
        if index >= len(data):
            raise BencodeError("unterminated container")
        return out, index + 1
    if char.isdigit():
        colon = data.index(b":", index)
        length = int(data[index:colon])
        start = colon + 1
        end = start + length
        if end > len(data):
            raise BencodeError("string past end of data")
        return data[start:end], end
    raise BencodeError(f"bad token {char!r} at {index}")


def decode(data: bytes):
    value, _ = _decode(data, 0)
    return value


def load(path: str | Path):
    return decode(Path(path).read_bytes())


def _text(value) -> str:
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


def file_entries(path: str | Path) -> tuple[str, list[tuple[str, int]]]:
    """Return ``(release_name, [(relative_path, length), ...])``.

    Handles both multi-file torrents (``info.files``) and single-file ones.
    """

    meta = load(path)
    info = meta.get(b"info")
    if not isinstance(info, dict):
        raise BencodeError("torrent has no info dictionary")
    name = _text(info.get(b"name", b""))
    entries: list[tuple[str, int]] = []
    files = info.get(b"files")
    if isinstance(files, list):
        for entry in files:
            parts = [_text(p) for p in entry.get(b"path", [])]
            if parts:
                entries.append(("/".join(parts).replace("/", "\\"), int(entry.get(b"length", 0))))
    elif b"length" in info:
        entries.append((name, int(info[b"length"])))
    return name, entries
