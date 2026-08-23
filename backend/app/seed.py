"""
Seeds demo accounts across all 4 roles so the platform is immediately
explorable without a lengthy manual signup flow. Coordinates are spread
around Mysuru, Karnataka. Run automatically on backend startup if the
users table is empty (see app/main.py) or manually via:
    python3 -m app.seed
"""
from app.db import SessionLocal, Base, engine
from app.models_db import User
from app.auth import hash_password

DEMO_PASSWORD = "demo1234"

USERS = [
    dict(email="admin@foodbridge.demo", name="Platform Admin", role="admin",
         lat=12.3052, lng=76.6552),

    dict(email="donor1@foodbridge.demo", name="Ravi Kumar (Wedding Caterer)", role="donor",
         lat=12.3150, lng=76.6450, trust_score=82),
    dict(email="donor2@foodbridge.demo", name="Anjali Events", role="donor",
         lat=12.2950, lng=76.6600, trust_score=75),

    dict(email="ngo1@foodbridge.demo", name="Sparsh NGO", role="ngo",
         lat=12.3010, lng=76.6500, ngo_capacity_total=150, ngo_capacity_available=150,
         ngo_tier=2, ngo_has_cold_storage=True, ngo_sentiment_score=0.85),
    dict(email="ngo2@foodbridge.demo", name="Green Hope Foundation", role="ngo",
         lat=12.3200, lng=76.6700, ngo_capacity_total=80, ngo_capacity_available=80,
         ngo_tier=1, ngo_has_cold_storage=False, ngo_sentiment_score=0.6),
    dict(email="ngo3@foodbridge.demo", name="Akshaya Trust", role="ngo",
         lat=12.2900, lng=76.6350, ngo_capacity_total=200, ngo_capacity_available=200,
         ngo_tier=2, ngo_has_cold_storage=True, ngo_sentiment_score=0.9),

    dict(email="volunteer1@foodbridge.demo", name="Suresh (Bike)", role="volunteer",
         lat=12.3080, lng=76.6480, volunteer_capacity_plates=40, volunteer_is_available=True),
    dict(email="volunteer2@foodbridge.demo", name="Priya (Van)", role="volunteer",
         lat=12.3000, lng=76.6600, volunteer_capacity_plates=150, volunteer_is_available=True),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("Users already exist -- skipping seed.")
            return
        for u in USERS:
            user = User(hashed_password=hash_password(DEMO_PASSWORD), **u)
            db.add(user)
        db.commit()
        print(f"Seeded {len(USERS)} demo users (password for all: '{DEMO_PASSWORD}').")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
