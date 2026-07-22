import os
#this is used to connect to postgres database,create new sessions on command and to rep 
#the actual session that is being used
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker,AsyncSession
from dotenv import load_dotenv

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/f1_dashboard")

#connection to postgres and echo = true is only when you want to see the sql statements being executed in the console
engine = create_async_engine(DATABASE_URL,echo=False,pool_size=10,max_overflow=5)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session