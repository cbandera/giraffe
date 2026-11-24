import sys


def main() -> int:
    from .app import GiraffeApp
    return GiraffeApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
