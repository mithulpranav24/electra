import app.main
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.station import Station
from sqlalchemy import func

def test_search():
    db = SessionLocal()
    try:
        point = 'SRID=4326;POINT(77.5946 12.9716)'
        stations = db.query(Station).filter(
            func.ST_DWithin(Station.gps_coordinates, func.ST_GeogFromText(point), 10000)
        ).all()
        print(f"Found {len(stations)} stations")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_search()
