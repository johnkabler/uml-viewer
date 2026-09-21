from myapp.app.loan import issue


def test_issue():
    assert issue(None, "x") == "x"
