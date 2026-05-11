"""Seed the database with initial Master user."""

import asyncio
import os

import sqlalchemy

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models import MasterProfile, User


async def seed():
    username = os.environ["MASTER_USERNAME"]
    password = os.environ["MASTER_PASSWORD"]
    name = os.environ["MASTER_NAME"]
    phone = os.environ.get("MASTER_PHONE")

    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            sqlalchemy.select(User).where(
                (User.username == username) | (User.role == "master")
            )
        )
        if existing.scalar_one_or_none():
            print("Master already exists, skipping.")
            return

        user = User(
            username=username,
            password_hash=get_password_hash(password),
            role="master",
        )
        db.add(user)
        await db.flush()

        profile = MasterProfile(id=user.id, name=name, phone=phone)
        db.add(profile)
        await db.commit()
        print(f"Master created: {username}")


if __name__ == "__main__":
    asyncio.run(seed())
