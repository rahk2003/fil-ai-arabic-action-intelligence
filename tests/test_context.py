from fil_ai.context import rank_context_candidates, similarity, suggest_context_action


def test_exact_duplicate_detection():
    tasks = [{"id": 1, "title": "ارسلي التقرير قبل الخميس"}]
    candidates = rank_context_candidates("ارسلي التقرير قبل الخميس", tasks)
    assert candidates[0]["is_probable_duplicate"] is True


def test_reschedule_is_only_a_confirmation_suggestion():
    tasks = [
        {"id": 1, "title": "اجتماع الفريق يوم الأحد"},
        {"id": 2, "title": "إرسال التقرير المالي"},
    ]
    candidates = rank_context_candidates("اجتماع الفريق خلوه الخميس", tasks)
    result = suggest_context_action("reschedule", candidates)
    assert result["suggestion"] in {"possible_reschedule", "possibly_related"}
    assert result["requires_confirmation"] is True


def test_unrelated_messages_have_low_similarity():
    assert similarity("اجتماع الفريق يوم الأحد", "وصلت نتائج الاستبيان") < 0.3
