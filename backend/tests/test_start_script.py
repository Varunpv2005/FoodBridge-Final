from pathlib import Path


def test_start_script_keeps_backend_running():
    root = Path(__file__).resolve().parents[2]
    script = root / "start.sh"
    content = script.read_text(encoding="utf-8")

    assert "kill $BACKEND_PID" not in content
    assert "wait" in content.lower()
