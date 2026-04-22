"""
Booking service – manages appointment slots and confirmed bookings.

Reads/writes:
  - app/data/slots.json        (available time slots)
  - bookings_log.json          (confirmed bookings, append-only)
"""

import json
from datetime import datetime
from pathlib import Path

from app.config import BOOKINGS_FILE, SLOTS_FILE


class BookingService:
    """Thin service that wraps slot look-ups and booking persistence."""

    def __init__(self, slots_file: Path | None = None, bookings_file: Path | None = None):
        self.slots_file = slots_file or SLOTS_FILE
        self.bookings_file = bookings_file or BOOKINGS_FILE
        self._ensure_files()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_files(self):
        if not self.bookings_file.exists():
            self.bookings_file.write_text("[]")

    def _read_slots(self) -> list[dict]:
        with open(self.slots_file) as f:
            data = json.load(f)
        return data.get("slots", [])

    def _write_slots(self, slots: list[dict]):
        with open(self.slots_file, "w") as f:
            json.dump({"slots": slots}, f, indent=2, ensure_ascii=False)

    def _read_bookings(self) -> list[dict]:
        try:
            content = self.bookings_file.read_text().strip()
            if not content:
                return []
            if content.startswith("["):
                return json.loads(content)
            # Legacy: one JSON object per line
            return [json.loads(line) for line in content.splitlines() if line.strip()]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_bookings(self, bookings: list[dict]):
        with open(self.bookings_file, "w") as f:
            json.dump(bookings, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_slots(self) -> list[dict]:
        """Return every slot (booked or not)."""
        return self._read_slots()

    def check_availability(self, appointment_type: str | None = None) -> str:
        """Return a human-readable Finnish string listing open slots.

        If *appointment_type* is given, only matching slots are shown.
        """
        slots = self._read_slots()
        available = [s for s in slots if s["available"]]

        if appointment_type:
            norm = appointment_type.lower().strip()
            available = [s for s in available if s["appointment_type"].lower() == norm]

        if not available:
            if appointment_type:
                return f"Ei vapaita aikoja varaus tyypille '{appointment_type}'."
            return "Ei vapaita aikoja tällä hetkellä."

        lines: list[str] = []
        for s in available:
            dt = datetime.fromisoformat(s["datetime"])
            date_str = dt.strftime("%d.%m.%Y klo %H:%M")
            lines.append(f"- {s['appointment_type']}: {date_str} (tunnus: {s['id']})")

        return "Vapaat ajat:\n" + "\n".join(lines)

    def book_appointment(
        self,
        patient_name: str,
        appointment_type: str,
        slot_id: str = "",
    ) -> str:
        """Book a slot and persist the record. Returns confirmation or error."""
        if not patient_name or not patient_name.strip():
            return "Virhe: Potilaan nimi puuttuu. Kysy potilaan koko nimi ennen varauksen tekemistä."

        patient_name = patient_name.strip()
        if len([part for part in patient_name.split() if part]) < 2:
            return "Virhe: Potilaan etu- ja sukunimi vaaditaan ennen varauksen tekemistä."

        slots = self._read_slots()

        # 1. Try exact slot_id match
        target = None
        for s in slots:
            if s["id"] == slot_id and s["available"]:
                target = s
                break

        # 2. Fallback: first available slot of the same type
        if target is None:
            norm = appointment_type.lower().strip()
            for s in slots:
                if s["available"] and s["appointment_type"].lower() == norm:
                    target = s
                    break

        if target is None:
            avail = self.check_availability()
            return f"Valitettavasti aikaa ei löydy. {avail}"

        # Mark booked
        target["available"] = False
        self._write_slots(slots)

        booking = {
            "patient_name": patient_name,
            "appointment_type": target["appointment_type"],
            "slot_time": target["datetime"],
            "slot_id": target["id"],
            "booked_at": datetime.now().isoformat(),
        }

        bookings = self._read_bookings()
        bookings.append(booking)
        self._write_bookings(bookings)

        dt = datetime.fromisoformat(target["datetime"])
        date_str = dt.strftime("%d.%m.%Y klo %H:%M")
        return (
            f"Varaus vahvistettu! {patient_name}, "
            f"{target['appointment_type']} {date_str}."
        )

    def get_bookings(self) -> list[dict]:
        return self._read_bookings()

    def reset_slots(self):
        """Mark every slot available again (useful for demos/tests)."""
        slots = self._read_slots()
        for s in slots:
            s["available"] = True
        self._write_slots(slots)
