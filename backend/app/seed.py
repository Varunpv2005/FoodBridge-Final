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
    dict(email="ngo.demo01@foodbridge.demo", name="Mysuru Community Kitchen Demo 01", role="ngo",
         lat=12.3058, lng=76.6465, ngo_capacity_total=120, ngo_capacity_available=120,
         ngo_tier=2, ngo_has_cold_storage=True, ngo_sentiment_score=0.82),
    dict(email="ngo.demo02@foodbridge.demo", name="Kuvempunagar Food Relief Demo 02", role="ngo",
         lat=12.2848, lng=76.6538, ngo_capacity_total=90, ngo_capacity_available=90,
         ngo_tier=1, ngo_has_cold_storage=False, ngo_sentiment_score=0.76),
    dict(email="ngo.demo03@foodbridge.demo", name="Vijayanagar Meals Network Demo 03", role="ngo",
         lat=12.3224, lng=76.6108, ngo_capacity_total=160, ngo_capacity_available=160,
         ngo_tier=2, ngo_has_cold_storage=True, ngo_sentiment_score=0.88),
    dict(email="ngo.demo04@foodbridge.demo", name="Saraswathipuram Food Bank Demo 04", role="ngo",
         lat=12.3210, lng=76.6380, ngo_capacity_total=75, ngo_capacity_available=75,
         ngo_tier=1, ngo_has_cold_storage=False, ngo_sentiment_score=0.72),
    dict(email="ngo.demo05@foodbridge.demo", name="Jayalakshmipuram Relief Centre Demo 05", role="ngo",
         lat=12.3310, lng=76.6205, ngo_capacity_total=110, ngo_capacity_available=110,
         ngo_tier=1, ngo_has_cold_storage=True, ngo_sentiment_score=0.80),
    dict(email="ngo.demo06@foodbridge.demo", name="Hebbal Community Support Demo 06", role="ngo",
         lat=12.3505, lng=76.6350, ngo_capacity_total=140, ngo_capacity_available=140,
         ngo_tier=2, ngo_has_cold_storage=True, ngo_sentiment_score=0.86),

    dict(email="volunteer1@foodbridge.demo", name="Suresh (Bike)", role="volunteer",
         lat=12.3080, lng=76.6480, volunteer_capacity_plates=40, volunteer_is_available=True),
    dict(email="volunteer2@foodbridge.demo", name="Priya (Van)", role="volunteer",
         lat=12.3000, lng=76.6600, volunteer_capacity_plates=150, volunteer_is_available=True),
    dict(email="volunteer.demo01@foodbridge.demo", name="Mysuru Volunteer Demo 01", role="volunteer",
         lat=12.3020, lng=76.6480, volunteer_capacity_plates=60, volunteer_is_available=True),
    dict(email="volunteer.demo02@foodbridge.demo", name="Mysuru Volunteer Demo 02", role="volunteer",
         lat=12.2890, lng=76.6500, volunteer_capacity_plates=80, volunteer_is_available=True),
    dict(email="volunteer.demo03@foodbridge.demo", name="Mysuru Volunteer Demo 03", role="volunteer",
         lat=12.3160, lng=76.6350, volunteer_capacity_plates=60, volunteer_is_available=True),
    dict(email="volunteer.demo04@foodbridge.demo", name="Mysuru Volunteer Demo 04", role="volunteer",
         lat=12.3280, lng=76.6200, volunteer_capacity_plates=120, volunteer_is_available=True),
    dict(email="volunteer.demo05@foodbridge.demo", name="Mysuru Volunteer Demo 05", role="volunteer",
         lat=12.3000, lng=76.6300, volunteer_capacity_plates=50, volunteer_is_available=True),
    dict(email="volunteer.demo06@foodbridge.demo", name="Mysuru Volunteer Demo 06", role="volunteer",
         lat=12.3400, lng=76.6450, volunteer_capacity_plates=100, volunteer_is_available=True),
    dict(email="volunteer.demo07@foodbridge.demo", name="Mysuru Volunteer Demo 07", role="volunteer",
         lat=12.2750, lng=76.6600, volunteer_capacity_plates=70, volunteer_is_available=True),
    dict(email="volunteer.demo08@foodbridge.demo", name="Mysuru Volunteer Demo 08", role="volunteer",
         lat=12.3130, lng=76.6750, volunteer_capacity_plates=90, volunteer_is_available=True),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
                    for u in USERS:
                              if not db.query(User).filter(User.email == u["email"]).first():
                                        db.add(User(hashed_password=hash_password(DEMO_PASSWORD), **u))
                    db.commit()
                    print(f"Ensured {len(USERS)} demo users (password for new users: '{DEMO_PASSWORD}').")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
