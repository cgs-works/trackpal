"""Flush ALL keys from the target Redis instance.

WARNING: This deletes every key in the database. Irreversible.
Use only when you need a clean slate (e.g. stale WhatsApp sessions after
deployment changes).
"""

import asyncio
import os
from redis.asyncio import Redis


async def main() -> None:
    url = os.environ.get(
        "REDIS_URL",
        "redis://user:_WCWFZJ6JKQnya0@redis-16178.c57.us-east-1-4.ec2.cloud.redislabs.com:16178",
    )

    r = Redis.from_url(url, decode_responses=False)

    try:
        info = await r.info("server")
        print(f"Connected: redis_version={info.get('redis_version', '?')}")

        dbsize = await r.dbsize()
        print(f"Keys before flush: {dbsize}")

        confirm = input(f"Type 'yes' to flush all {dbsize} keys: ")
        if confirm.strip().lower() != "yes":
            print("Cancelled.")
            return

        await r.flushall()
        print("FLUSHALL complete.")

        dbsize = await r.dbsize()
        print(f"Keys after flush: {dbsize}")
    finally:
        await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
