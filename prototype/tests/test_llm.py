"""Regression tests for LLM raw tool-call recovery helpers."""

from app.services.llm import _extract_failed_generation, _parse_raw_tool_calls


class DummyBadRequestError(Exception):
    """Minimal stub with the same attributes used by the helper."""

    def __init__(self, body=None, message=""):
        super().__init__(message)
        self.body = body


def test_parse_standard_raw_tool_call():
    text = (
        'Selvä. <function=check_availability>\n'
        '{"appointment_type":"Hammaslääkäriaika"}\n'
        '</function>'
    )

    assert _parse_raw_tool_calls(text) == [
        ("check_availability", {"appointment_type": "Hammaslääkäriaika"})
    ]



def test_parse_inline_raw_tool_call_with_colon_separator():
    text = (
        'Selvä. <function=check_availability:{"appointment_type":"Suuhygienistiaika"}'
        '</function>'
    )

    assert _parse_raw_tool_calls(text) == [
        ("check_availability", {"appointment_type": "Suuhygienistiaika"})
    ]


def test_parse_inline_raw_tool_call_with_space_separator():
    text = (
        'Selvä. <function=check_availability {"appointment_type":"Hammaslääkäriaika"}>'
        '</function>'
    )

    assert _parse_raw_tool_calls(text) == [
        ("check_availability", {"appointment_type": "Hammaslääkäriaika"})
    ]


def test_extract_failed_generation_from_error_body():
    exc = DummyBadRequestError(
        body={
            "error": {
                "failed_generation": (
                    'Hieno! <function=check_availability={"appointment_type":"Hammaslääkäriaika"}'
                    '</function>'
                )
            }
        }
    )

    assert "<function=check_availability=" in _extract_failed_generation(exc)