"""Identify CommonMark quotations and public finding blocks on report lines."""
import hashlib
from pathlib import Path
import subprocess
import sys

QUOTED = 1
FIELD_START = 2
PROSE = 4
REPORT_BREAKS = str.maketrans(dict.fromkeys("\v\f\x1c\x1d\x1e\x85\u2028\u2029", "\n"))


def block_mask(text, count):
    # The isolated interpreter loads the same parser even if the operator has
    # a different version installed or the controller was run with Python -S.
    result = subprocess.run([sys.executable, "-I", "-S", __file__],
                            input=text.encode("utf-8", "surrogatepass"), capture_output=True)
    if result.returncode or len(result.stdout) != count or max(result.stdout, default=0) > (QUOTED | FIELD_START | PROSE):
        from replay_git import ReplayError
        raise ReplayError("cannot verify Markdown quotation boundaries for blinded evidence")
    return result.stdout


def load_parser():
    directory = Path(__file__).with_name("replay_vendor")
    wheels = {
        "markdown_it_py-3.0.0-py3-none-any.whl": "355216845c60bd96232cd8d8c40e8f9765cc86f46880e43a8fd22dc1a1a8cab1",
        "mdurl-0.1.2-py3-none-any.whl": "84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8",
    }
    for name, digest in wheels.items():
        path = directory / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("invalid bundled Markdown parser")
        sys.path.insert(0, str(path))
    from markdown_it import MarkdownIt
    return MarkdownIt("commonmark").disable("inline")


def source_mask(parser, text):
    # Here every CommonMark physical line ending has been normalized to LF.
    mask = bytearray(text.count("\n") + bool(text and not text.endswith("\n")))
    for token in parser.parse(text):
        if token.type == "blockquote_open":
            start, stop = token.map
            mask[start:stop] = bytes([QUOTED]) * (stop - start)
        elif token.type in ("paragraph_open", "heading_open"):
            start, stop = token.map
            for index in range(start, stop):
                mask[index] |= PROSE
            mask[start] |= FIELD_START
    return mask


def parse_blocks(text):
    parser = load_parser()
    physical = text.replace("\r\n", "\n").replace("\r", "\n")
    logical = physical.translate(REPORT_BREAKS)
    mask = source_mask(parser, logical)
    if physical != logical:
        # The first-round report reader also recognizes Unicode line separators.
        # An apparent field in a physical code or HTML block stays private,
        # even when a separator makes it look like prose to the report reader.
        original = source_mask(parser, physical)
        index = 0
        first = True
        for number, line in enumerate(physical.splitlines(keepends=True)):
            report, source = mask[number], original[index]
            mask[number] = (report | source) & QUOTED
            starts = report & FIELD_START or (first and source & FIELD_START)
            if report & source & PROSE and starts:
                mask[number] |= FIELD_START | PROSE
            first = line.endswith("\n")
            if first:
                index += 1
    return mask


if __name__ == "__main__":
    sys.stdout.buffer.write(parse_blocks(sys.stdin.buffer.read().decode("utf-8", "surrogatepass")))
