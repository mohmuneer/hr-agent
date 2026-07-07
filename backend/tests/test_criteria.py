"""اختبارات لا تحتاج مفتاح API — تتحقق من صحة المعايير والحساب."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.criteria_loader import load_criteria, list_available_domains


def test_accounting_criteria_loads():
    data = load_criteria("accounting")
    assert data["domain"] == "accounting"
    assert len(data["criteria"]) > 0


def test_weights_sum_correctly():
    data = load_criteria("accounting")
    total = sum(c["weight"] for c in data["criteria"])
    assert total == data["weights_sum_to"]


def test_domains_listed():
    domains = list_available_domains()
    assert "accounting" in domains


def test_weighted_score_math():
    """يحاكي حساب الدرجة الموزونة بدرجات وهمية."""
    data = load_criteria("accounting")
    fake_scores = {c["key"]: 80.0 for c in data["criteria"]}
    weighted = sum(
        fake_scores[c["key"]] * c["weight"] / 100 for c in data["criteria"]
    )
    # كل الدرجات 80 → الموزون لازم يساوي 80
    assert round(weighted, 1) == 80.0
