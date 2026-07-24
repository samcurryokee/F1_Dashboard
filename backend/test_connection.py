import asyncio #inbuild python module to run async functions
from sqlalchemy import text
from app.database import engine


async def main():
    print("Using DATABASE_URL:", engine.url)
    print("Starting connection attempt...")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("Connected! Result:", result.scalar())
    except Exception as e:
        print("FAILED:", type(e).__name__, "-", e)

#this is the entry point of the script, it runs the main function using asyncio.run() to execute the async code
if __name__ == "__main__":
    asyncio.run(main())