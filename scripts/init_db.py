import sys
from pathlib import Path

from flask_migrate import upgrade

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import create_app


def main():
    app = create_app()
    with app.app_context():
        upgrade()
    print("WorldMap Live database migrations applied successfully.")


if __name__ == "__main__":
    main()
