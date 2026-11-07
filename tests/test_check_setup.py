from unittest.mock import MagicMock, patch

from pipeline import check_setup


def _resp(status, json_data=None, headers=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    r.headers = headers or {}
    return r


def test_missing_salary_token_fails():
    status, _ = check_setup.check_salary_repo(None, "csorcic/dk_salary", "salaries")
    assert status == check_setup.FAIL


def test_salary_repo_reports_latest_csv():
    files = [{"name": "DKSalaries_NBA_2026-11-06_1.csv"}, {"name": "DKSalaries_NBA_2026-11-07_2.csv"},
             {"name": "README.md"}]
    with patch.object(check_setup.requests, "get", return_value=_resp(200, files)):
        status, msg = check_setup.check_salary_repo("t", "csorcic/dk_salary", "salaries")
    assert status == check_setup.OK
    assert "2026-11-07" in msg and "2 salary files" in msg


def test_salary_token_rejected():
    with patch.object(check_setup.requests, "get", return_value=_resp(401)):
        status, _ = check_setup.check_salary_repo("bad", "csorcic/dk_salary", "salaries")
    assert status == check_setup.FAIL


def test_missing_odds_key_is_only_a_warning():
    status, _ = check_setup.check_odds_api(None)
    assert status == check_setup.WARN


def test_odds_key_reports_remaining_quota():
    resp = _resp(200, [{"key": "basketball_nba"}], {"x-requests-remaining": "498"})
    with patch.object(check_setup.requests, "get", return_value=resp):
        status, msg = check_setup.check_odds_api("k")
    assert status == check_setup.OK and "498" in msg
