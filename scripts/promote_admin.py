import argparse
import sys

from backend import create_app
from backend.models.user import User
from extensions import db


def main():
    parser = argparse.ArgumentParser(description="Promote an existing WorldMapLive account to admin.")
    parser.add_argument("email", help="Email address of an existing account")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            print(f"No account found for {args.email}.", file=sys.stderr)
            return 1
        user.role = "admin"
        db.session.commit()
        print(f"Promoted {user.email} to admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
