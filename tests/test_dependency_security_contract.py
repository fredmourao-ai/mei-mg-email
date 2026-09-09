from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _requirements() -> str:
    return (ROOT / "requirements.txt").read_text(encoding="utf-8")


def test_runtime_dependencies_use_current_patched_versions():
    requirements = _requirements()
    for pin in (
        "fastapi==0.141.1",
        "uvicorn[standard]==0.52.4",
        "pydantic==2.13.5",
        "python-dotenv==1.2.3",
        "python-multipart==0.0.32",
    ):
        assert pin in requirements


def test_pytest_is_dev_only_and_patched():
    runtime = _requirements()
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "pytest==" not in runtime
    assert "pytest==9.1.1" in dev


def test_ci_runs_dependency_and_static_security_gates():
    ci = (ROOT / ".github" / "workflows" / "email-safety-ci.yml").read_text(encoding="utf-8")
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "pip-audit==2.10.1" in dev
    assert "bandit==1.9.4" in dev
    assert "python -m pip install --upgrade 'pip>=26.2'" in ci
    assert "pip-audit -r requirements.txt --progress-spinner off" in ci
    assert "bandit -q -lll -r app worker scripts -x tests" in ci
