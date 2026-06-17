import asyncio
import bcrypt

from src.config.database import session_factory
from src.config.models import User as UserModel


async def create_admin(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    ci: str,
    phone: str | None = None,
) -> None:
    session = session_factory()
    async with session:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        admin = UserModel(
            email=email,
            password_hash=password_hash,
            role="ADMIN",
            first_name=first_name,
            last_name=last_name,
            ci=ci,
            phone=phone,
        )
        session.add(admin)
        await session.commit()

    print(f"Admin created: {email}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--last-name", required=True)
    parser.add_argument("--ci", required=True)
    parser.add_argument("--phone")

    args = parser.parse_args()

    asyncio.run(
        create_admin(
            email=args.email,
            password=args.password,
            first_name=args.first_name,
            last_name=args.last_name,
            ci=args.ci,
            phone=args.phone,
        )
    )
