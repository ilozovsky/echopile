import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from echopile.app import build_app
else:
    from .app import build_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch echopile Dash app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = build_app()
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug,
    )

if __name__ == "__main__":
    main()
