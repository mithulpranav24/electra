import os
import sys

# Ensure the backend directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base

# Import all models to ensure they are registered with Base.metadata
from app.models.user import User
from app.models.company import Company
from app.models.vehicle import Vehicle
from app.models.station import Station, ChargingPort
from app.models.reservation import Reservation
from app.models.wallet import WalletTransaction
from app.models.transient import Waitlist, SearchHistory, Favorite, RecentStation

def setup_database():
    print("Creating all database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    setup_database()
