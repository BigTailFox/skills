# Canon CLI

The `canon-cli` Python distribution installs the `canon` command. Run `canon --version` to see its installed package version and `canon --help` to see its available options. The `canon` skill provides the document management commands through its `scripts/canon.py` entry point.

## Development

Run these commands from the `cli/` directory.

```sh
uv sync --locked
uv run canon --version
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python -m unittest discover -s tests
uv build
```

`uv build` writes the source distribution and wheel to `dist/`.
