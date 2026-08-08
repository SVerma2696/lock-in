from lock_in.session import Phase


def test_phase_labels_are_serious_tokusatsu_tone():
    assert Phase.IDLE.label == "Standing By"
    assert Phase.FOCUS.label == "Henshin"
    assert Phase.SHORT_BREAK.label == "Recovery"
    assert Phase.LONG_BREAK.label == "Stand Down"


def test_break_phases_are_still_flagged_as_breaks():
    assert Phase.SHORT_BREAK.is_break
    assert Phase.LONG_BREAK.is_break
    assert not Phase.FOCUS.is_break
    assert not Phase.IDLE.is_break
