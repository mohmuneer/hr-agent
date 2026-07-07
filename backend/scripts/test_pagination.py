"""Test pagination."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.application_store import list_applications
from app.services.employee_store import list_employees
from app.services.job_store import list_jobs
from app.services.audit_logger import list_logs

items, total = list_applications(2, 0)
print(f"applications: items={len(items)}, total={total}")
for i in items:
    print(f"  - {i['full_name']} ({i['status']}) score={i['overall_score']}")

items2, total2 = list_applications(2, 2)
print(f"applications page2: items={len(items2)}, total={total2}")

items, total = list_employees(10, 0)
print(f"employees: items={len(items)}, total={total}")

items, total = list_jobs(None, 10, 0)
print(f"jobs: items={len(items)}, total={total}")

items, total = list_logs(10, 0)
print(f"audit_logs: items={len(items)}, total={total}")
