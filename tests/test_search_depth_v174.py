from __future__ import annotations

from pathlib import Path

import app
import app.service as service_module
from app.service_v174 import DeepNameLabService


ROOT = Path(__file__).resolve().parents[1]


def test_v174_remains_search_v2_safety_baseline():
    assert app.__version__ == "1.7.4"
    assert issubclass(service_module.NameLabService, DeepNameLabService)


def test_v174_keeps_quality_threshold_and_progressively_checks_domains():
    text = (ROOT / "app" / "service_v174.py").read_text(encoding="utf-8")
    assert "score < min_score" in text
    assert "batch_size = max(1, domain_checks)" in text
    assert "while cursor < max_checks" in text
    assert "len(available) < target_available" in text
    assert "deep_limit = min(400" in text
    assert "Progi jakości nie są obniżane" in text


def test_v174_never_promotes_nonavailable_domain_status():
    text = (ROOT / "app" / "service_v174.py").read_text(encoding="utf-8")
    assert 'c.domain_status == "available"' in text
    assert "_screen_available(available" in text
