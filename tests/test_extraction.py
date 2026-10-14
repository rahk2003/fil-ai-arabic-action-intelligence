from fil_ai.extraction import extract_actions, extract_temporal


REFERENCE = "2026-10-14T12:00:00+03:00"


def test_relative_date_and_riyadh_timezone():
    result = extract_temporal("ارسلي التقرير بكرة الساعة ٩ الصباح", REFERENCE)
    assert result["normalized_datetime"] == "2026-10-15T09:00:00+03:00"
    assert "٩" in result["datetime_text"]


def test_missing_reference_preserves_uncertainty():
    result = extract_temporal("ارسلي التقرير بكرة الساعة 9 الصباح")
    assert result["datetime_text"]
    assert result["normalized_datetime"] is None
    assert result["is_ambiguous"] is True


def test_time_without_date_is_not_invented():
    result = extract_temporal("ارسلي التقرير الساعة 2 الظهر", REFERENCE)
    assert result["normalized_datetime"] is None
    assert result["is_ambiguous"] is True


def test_multiple_actions_are_preserved():
    actions = extract_actions(
        "تأجل الاجتماع للخميس، ولا تنسون ترسلون التقرير قبل الأربعاء.",
        "reschedule",
        REFERENCE,
    )
    assert len(actions) == 2
    assert [action["intent"] for action in actions] == ["reschedule", "new_task"]
    assert all(action["evidence"] for action in actions)
