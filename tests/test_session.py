from lock_in.session import DEFAULT_TERMINOLOGY, Phase, label_for


def test_phase_labels_are_serious_tokusatsu_tone():
    assert Phase.IDLE.label == "Standing By"
    assert Phase.FOCUS.label == "Henshin"
    assert Phase.SHORT_BREAK.label == "Recovery"
    assert Phase.LONG_BREAK.label == "Stand Down"


def test_professional_phase_labels_are_plain():
    assert Phase.IDLE.professional_label == "Idle"
    assert Phase.FOCUS.professional_label == "Focus"
    assert Phase.SHORT_BREAK.professional_label == "Short Break"
    assert Phase.LONG_BREAK.professional_label == "Long Break"


def test_break_phases_are_still_flagged_as_breaks():
    assert Phase.SHORT_BREAK.is_break
    assert Phase.LONG_BREAK.is_break
    assert not Phase.FOCUS.is_break
    assert not Phase.IDLE.is_break


def test_default_terminology_is_professional():
    assert DEFAULT_TERMINOLOGY == "professional"
    assert label_for(Phase.FOCUS) == "Focus"


def test_label_for_tokusatsu_gives_the_flavored_name():
    assert label_for(Phase.FOCUS, "tokusatsu") == "Henshin"
    assert label_for(Phase.IDLE, "tokusatsu") == "Standing By"


def test_label_for_unknown_terminology_falls_back_to_professional():
    assert label_for(Phase.FOCUS, "not a real mode") == "Focus"
