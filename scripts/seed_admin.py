import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
from uuid import uuid4
from src.config.database import session_factory
from src.config.models import User as UserModel, UserRole as UserRoleModel


async def seed_admin():
    email = "admin@autotech.com"
    password = "Admin123!"

    session = session_factory()
    try:
        from sqlalchemy import select
        stmt = select(UserModel).where(UserModel.email == email)
        r = await session.execute(stmt)
        existing = r.scalars().first()
        if existing:
            print(f"Admin already exists: {email}")
            return

        user_id = uuid4()
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = UserModel(
            id=user_id,
            email=email,
            password_hash=password_hash,
            first_name="Admin",
            last_name="AutoTech",
            ci="V-00000000",
            phone="04120000000",
        )
        session.add(user)

        role = UserRoleModel(user_id=user_id, role="ADMIN")
        session.add(role)

        await session.commit()
        print(f"Admin created: {email} / {password}")
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(seed_admin())
