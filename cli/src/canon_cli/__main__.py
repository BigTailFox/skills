import argparse
from importlib.metadata import version


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="canon", description="Work with Canon project documentation."
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('canon-cli')}"
    )
    parser.parse_args()
    parser.print_help()


if __name__ == "__main__":
    main()
