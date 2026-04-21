"""
Unit tests for the booking service and session manager.

Run:  uv run pytest tests/ -v
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from app.services.booking import BookingService
from app.services.session import Session, SessionManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SLOTS = {
    "slots": [
        {
            "id": "slot-1",
            "datetime": "2026-04-21T09:00:00",
            "appointment_type": "Hammaslääkäriaika",
            "available": True,
        },
        {
            "id": "slot-2",
            "datetime": "2026-04-21T14:00:00",
            "appointment_type": "Hammaslääkäriaika",
            "available": True,
        },
        {
            "id": "slot-3",
            "datetime": "2026-04-22T10:00:00",
            "appointment_type": "Suuhygienistiaika",
            "available": True,
        },
        {
            "id": "slot-4",
            "datetime": "2026-04-23T08:30:00",
            "appointment_type": "Työterveysaika",
            "available": True,
        },
    ]
}


@pytest.fixture()
def tmp_dir():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d)


@pytest.fixture()
def svc(tmp_dir: Path) -> BookingService:
    slots_file = tmp_dir / "slots.json"
    bookings_file = tmp_dir / "bookings.json"
    slots_file.write_text(json.dumps(SAMPLE_SLOTS, ensure_ascii=False))
    return BookingService(slots_file=slots_file, bookings_file=bookings_file)


# ---------------------------------------------------------------------------
# BookingService tests
# ---------------------------------------------------------------------------


class TestCheckAvailability:
    def test_all_slots(self, svc: BookingService):
        result = svc.check_availability()
        assert "Vapaat ajat" in result
        assert "slot-1" in result

    def test_filter_by_type(self, svc: BookingService):
        result = svc.check_availability("Hammaslääkäriaika")
        assert "Hammaslääkäriaika" in result
        assert "Suuhygienistiaika" not in result

    def test_no_matches(self, svc: BookingService):
        result = svc.check_availability("Ei-olemassa")
        assert "Ei vapaita" in result

    def test_case_insensitive(self, svc: BookingService):
        result = svc.check_availability("hammaslääkäriaika")
        assert "Hammaslääkäriaika" in result


class TestBookAppointment:
    def test_book_by_slot_id(self, svc: BookingService):
        result = svc.book_appointment(
            patient_name="Matti Virtanen",
            appointment_type="Hammaslääkäriaika",
            slot_id="slot-1",
        )
        assert "vahvistettu" in result.lower()
        assert "Matti Virtanen" in result

        # Slot should no longer be available
        avail = svc.check_availability("Hammaslääkäriaika")
        assert "slot-1" not in avail
        # slot-2 should still be there
        assert "slot-2" in avail

    def test_book_fallback_to_type(self, svc: BookingService):
        """When slot_id is empty, pick first available of that type."""
        result = svc.book_appointment(
            patient_name="Liisa Korhonen",
            appointment_type="Työterveysaika",
            slot_id="",
        )
        assert "vahvistettu" in result.lower()

    def test_book_no_availability(self, svc: BookingService):
        # Book the only Työterveysaika slot
        svc.book_appointment("A A", "Työterveysaika", "slot-4")
        # Try again
        result = svc.book_appointment("B B", "Työterveysaika", "")
        assert "ei löydy" in result.lower() or "Ei vapaita" in result

    def test_booking_persisted(self, svc: BookingService):
        svc.book_appointment("Test User", "Hammaslääkäriaika", "slot-1")
        bookings = svc.get_bookings()
        assert len(bookings) == 1
        assert bookings[0]["patient_name"] == "Test User"
        assert bookings[0]["slot_id"] == "slot-1"


class TestResetSlots:
    def test_reset(self, svc: BookingService):
        svc.book_appointment("X X", "Hammaslääkäriaika", "slot-1")
        # After reset, slot-1 should be available again
        svc.reset_slots()
        avail = svc.check_availability()
        assert "slot-1" in avail

    def test_book_requires_first_and_last_name(self, svc: BookingService):
        result = svc.book_appointment("Matti", "Hammaslääkäriaika", "slot-1")
        assert "etu- ja sukunimi" in result.lower() or "koko nimi" in result.lower()


# ---------------------------------------------------------------------------
# SessionManager tests
# ---------------------------------------------------------------------------

class TestSessionManager:
    def test_create_and_retrieve(self):
        mgr = SessionManager()
        s = mgr.get_or_create("abc")
        assert isinstance(s, Session)
        assert s.session_id == "abc"
        assert mgr.get("abc") is s

    def test_messages(self):
        mgr = SessionManager()
        s = mgr.get_or_create("s1")
        s.add_message("user", "Moi")
        s.add_message("assistant", "Hei!")
        assert len(s.messages) == 2
        assert s.messages[0]["role"] == "user"
        assert len(s.log) == 2

    def test_tool_event(self):
        mgr = SessionManager()
        s = mgr.get_or_create("s2")
        s.add_tool_event("check_availability", {"type": "X"}, "result")
        assert len(s.log) == 1
        assert s.log[0]["event"] == "tool_call"

    def test_to_dict(self):
        mgr = SessionManager()
        s = mgr.get_or_create("s3")
        s.add_message("user", "hello")
        d = s.to_dict()
        assert d["session_id"] == "s3"
        assert len(d["messages"]) == 1
        assert "log" in d

    def test_list_sessions(self):
        mgr = SessionManager()
        mgr.get_or_create("a")
        mgr.get_or_create("b")
        assert set(mgr.list_sessions()) == {"a", "b"}
