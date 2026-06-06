"""One-command demo seed for publication / Render.

Run from the project root after DATABASE_URL is configured:

    python backend/seed_demo.py

What it does:
1. Creates the protected demo accounts if they do not exist.
2. Fills the database with realistic demo courses, groups, schedule, materials,
   assignments, submissions, grades and messages.

Demo accounts:
- admin@school.com / admin123
- teacher@example.com / password
- student@example.com / password
"""

import asyncio
import sys
from pathlib import Path

# Allow imports when the script is started as: python backend/seed_demo.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.seed import seed_data  # noqa: E402
from backend.seed_realistic import main as seed_realistic_main  # noqa: E402


async def main() -> None:
    print("[SEED_DEMO] Step 1/2: creating protected demo accounts...")
    await seed_data()
    print("[SEED_DEMO] Step 2/2: creating realistic demo data...")
    await seed_realistic_main()
    print("[SEED_DEMO] Done. You can log in with:")
    print("  admin@school.com / admin123")
    print("  teacher@example.com / password")
    print("  student@example.com / password")


if __name__ == "__main__":
    asyncio.run(main())
