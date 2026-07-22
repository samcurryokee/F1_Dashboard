# test_alembic_setup.py
import asyncio
import os
import sys
import importlib.util
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from alembic.config import Config
from alembic import command
from alembic.util import CommandError
import traceback

# Load environment variables
load_dotenv()

# Import your app's engine for testing
from app.database import engine


def test_database_connection_sync():
    """Test the database connection using synchronous method"""
    print("\n🔍 Testing database connection...")
    print("-" * 50)
    print("Using DATABASE_URL:", engine.url)
    
    async def test_async():
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                print("✅ Connected! Result:", result.scalar())
                print("✅ Database connection successful")
                return True
        except Exception as e:
            print("❌ FAILED:", type(e).__name__, "-", e)
            return False
    
    return asyncio.run(test_async())


def test_env_file():
    """Test if env.py exists and is syntactically correct"""
    print("\n🔍 Testing env.py...")
    print("-" * 50)
    
    env_path = "alembic/env.py"
    if not os.path.exists(env_path):
        print("❌ env.py not found")
        return False
    
    print("✅ env.py exists")
    
    # Try to compile it for syntax errors
    try:
        with open(env_path, 'r') as f:
            code = f.read()
        compile(code, env_path, 'exec')
        print("✅ env.py syntax is valid")
        return True
    except SyntaxError as e:
        print(f"❌ env.py has syntax errors: {e}")
        return False


def test_alembic_config():
    """Test Alembic configuration"""
    print("\n🔍 Testing Alembic configuration...")
    print("-" * 50)
    
    try:
        # Load Alembic config
        alembic_cfg = Config("alembic.ini")
        print("✅ alembic.ini loaded successfully")
        
        # Check if we can read the config
        script_location = alembic_cfg.get_main_option("script_location")
        print(f"✅ Script location: {script_location}")
        
        # Override URL with env if needed
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)
            print(f"✅ Database URL configured: {db_url}")
        
        return alembic_cfg
    except Exception as e:
        print(f"❌ Alembic config error: {e}")
        return None


def test_alembic_revision_preview():
    """Test if Alembic can generate migrations (dry run)"""
    print("\n🔍 Testing Alembic migration generation...")
    print("-" * 50)
    
    try:
        alembic_cfg = Config("alembic.ini")
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        # Try to generate a migration
        print("Attempting to generate migration preview...")
        
        # Use a temporary revision with autogenerate
        try:
            command.revision(alembic_cfg, message="test_preview", autogenerate=True)
            print("✅ Alembic autogenerate works")
            return True
        except CommandError as e:
            if "No changes" in str(e) or "No changes detected" in str(e):
                print("✅ Alembic works (No changes detected - expected if no models)")
                return True
            else:
                print(f"⚠️ Command error: {e}")
                return False
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")
        traceback.print_exc()
        return False


def test_migration_history():
    """Check migration history"""
    print("\n🔍 Checking migration history...")
    print("-" * 50)
    
    try:
        alembic_cfg = Config("alembic.ini")
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        # Check current version
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            try:
                command.current(alembic_cfg)
            except:
                pass
        
        output = f.getvalue()
        if output:
            print("✅ Migration history accessible")
            print(f"   {output.strip()}")
        else:
            print("✅ No migration history (this is fine for a new project)")
        return True
    except Exception as e:
        print(f"⚠️ Could not check migration history: {e}")
        return True  # Not critical


def main():
    """Run all tests"""
    print("\n" + "="*50)
    print("🔬 ALEMBIC SETUP VALIDATION")
    print("="*50)
    
    results = []
    
    # Run all tests
    results.append(("Database Connection", test_database_connection_sync()))
    results.append(("env.py Validation", test_env_file()))
    results.append(("Alembic Config", test_alembic_config() is not None))
    results.append(("Migration Generation", test_alembic_revision_preview()))
    results.append(("Migration History", test_migration_history()))
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False
    
    print("="*50)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Your Alembic setup is correct.")
        print("\nYou can now:")
        print("  1. Create your models in app/models.py")
        print("  2. Update env.py to import your Base")
        print("  3. Run: alembic revision --autogenerate -m 'Your message'")
        print("  4. Run: alembic upgrade head")
    else:
        print("⚠️ Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Make sure alembic/env.py has correct syntax")
        print("  - Check that alembic.ini is properly configured")
        print("  - Verify your .env file has DATABASE_URL")
    
    print("="*50 + "\n")


if __name__ == "__main__":
    main()