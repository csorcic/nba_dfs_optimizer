import re

from pipeline.config import CONFIG_DIR, load_name_overrides, load_settings


def test_settings_load_with_expected_sections():
    s = load_settings()
    assert set(s) >= {"data", "projections", "optimizer"}
    assert s["optimizer"]["salary_cap"] == 50000
    assert s["projections"]["prior_season_k"] == 10
    assert s["optimizer"]["gpp_min_unique"] == 3
    assert s["optimizer"]["gpp_max_exposure_pct"] == 50


def test_every_setting_line_has_a_plain_english_comment():
    lines = (CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8").splitlines()
    setting = re.compile(r"^\s*[A-Za-z_]+:")
    missing = [ln for ln in lines if setting.match(ln) and " # " not in ln and "  #" not in ln]
    assert not missing, f"Settings without a comment: {missing}"


def test_name_overrides_load_as_dict():
    assert isinstance(load_name_overrides(), dict)
