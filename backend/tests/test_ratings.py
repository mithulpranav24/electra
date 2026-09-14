import uuid
from unittest.mock import MagicMock

import pytest


def _payload(**overrides):
    from app.schemas.rating_schema import RatingCreate

    defaults = dict(overall_score=5, cleanliness_score=4, access_score=5, experience_score=4, comment="Great station")
    defaults.update(overrides)
    return RatingCreate(**defaults)


def test_submit_rating_rejects_station_not_found():
    from fastapi import HTTPException
    from app.services.rating_service import RatingService

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        RatingService.submit_rating(db, MagicMock(user_id=uuid.uuid4()), uuid.uuid4(), _payload())
    assert exc_info.value.status_code == 404


def test_submit_rating_rejects_user_without_completed_session():
    """FR-20: only drivers who actually completed a session at the station may rate it."""
    from fastapi import HTTPException
    from app.services.rating_service import RatingService

    db = MagicMock()
    station = MagicMock()
    # First query() call resolves the station; the has-completed-session check
    # is a separate query chain (join/join/filter/first) that must resolve to None.
    db.query.return_value.filter.return_value.first.return_value = station
    db.query.return_value.join.return_value.join.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        RatingService.submit_rating(db, MagicMock(user_id=uuid.uuid4()), uuid.uuid4(), _payload())
    assert exc_info.value.status_code == 403


def test_submit_rating_creates_new_rating_when_none_exists():
    from app.services.rating_service import RatingService

    db = MagicMock()
    station = MagicMock()
    call_count = {"n": 0}

    def first_side_effect():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return station
        return None  # no existing rating for this (user, station)

    db.query.return_value.filter.return_value.first.side_effect = first_side_effect
    db.query.return_value.join.return_value.join.return_value.filter.return_value.first.return_value = MagicMock()  # has completed session

    current_user = MagicMock(user_id=uuid.uuid4())
    station_id = uuid.uuid4()

    RatingService.submit_rating(db, current_user, station_id, _payload(overall_score=3))

    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.user_id == current_user.user_id
    assert added.station_id == station_id
    assert added.overall_score == 3
    db.commit.assert_called_once()


def test_submit_rating_updates_existing_rating_in_place():
    from app.services.rating_service import RatingService

    db = MagicMock()
    station = MagicMock()
    existing_rating = MagicMock(overall_score=2, cleanliness_score=2, access_score=2, experience_score=2, comment="meh")
    call_count = {"n": 0}

    def first_side_effect():
        call_count["n"] += 1
        return station if call_count["n"] == 1 else existing_rating

    db.query.return_value.filter.return_value.first.side_effect = first_side_effect
    db.query.return_value.join.return_value.join.return_value.filter.return_value.first.return_value = MagicMock()

    RatingService.submit_rating(db, MagicMock(user_id=uuid.uuid4()), uuid.uuid4(), _payload(overall_score=5, comment="Much better now"))

    db.add.assert_not_called()
    assert existing_rating.overall_score == 5
    assert existing_rating.comment == "Much better now"
    db.commit.assert_called_once()


def test_get_station_ratings_computes_averages_and_handles_no_ratings():
    from app.services.rating_service import RatingService

    db = MagicMock()
    # summary aggregate query
    db.query.return_value.filter.return_value.first.return_value = (0, None, None, None, None)
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    result = RatingService.get_station_ratings(db, uuid.uuid4(), current_user=None)

    assert result["summary"] == {
        "rating_count": 0,
        "average_overall": None,
        "average_cleanliness": None,
        "average_access": None,
        "average_experience": None,
    }
    assert result["ratings"] == []
    assert result["my_rating"] is None
