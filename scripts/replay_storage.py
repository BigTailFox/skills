"""Durable case-local publications shared by the controller and its dispatch supervisor."""
import json
import math
import os
from pathlib import Path
import tempfile

from replay_git import ReplayError, json_bytes


def sync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".publish-", delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
    sync_directory(path.parent)


def publish_json(path, body):
    publish(path, json_bytes(body))


def decode(data, label):
    def unique(pairs):
        fields = dict(pairs)
        if len(fields) != len(pairs):
            raise ValueError("duplicate field")
        return fields

    def invalid(value):
        raise ValueError(value)

    def finite(raw):
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError("non-finite number")
        return number

    try:
        value = json.loads(data, object_pairs_hook=unique, parse_constant=invalid, parse_float=finite)
        if not isinstance(value, dict):
            raise ValueError("expected an object")
        return value
    except (ValueError, UnicodeError) as exc:
        raise ReplayError(f"invalid {label}: {exc}") from exc
