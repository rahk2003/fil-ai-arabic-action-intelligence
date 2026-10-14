from fil_ai.normalization import normalize_arabic


def test_arabic_unicode_and_digits_normalization():
    assert normalize_arabic("  إِرْسَالُ  التـقرير  الساعة ٩  ") == "ارسال التقرير الساعة 9"


def test_negation_is_preserved():
    assert "ما يحتاج" in normalize_arabic("ما يحتاج ترفعين النموذج")
