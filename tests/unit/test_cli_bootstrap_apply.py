from __future__ import annotations

from typer.testing import CliRunner

from autolab.cli import app as cli_app


class _DummyResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_apply_bootstrap_cli(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_post(url: str, json: dict[str, object], timeout: int) -> _DummyResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _DummyResponse(
            {
                "ok": True,
                "bootstrap_mode": "add_demo",
                "resources": ["wsl-local"],
                "capabilities": ["add_two", "add_three"],
                "workflows": ["add_two_then_three"],
                "bootstrap_error": None,
            }
        )

    import httpx

    monkeypatch.setattr(httpx, "post", _fake_post)
    runner = CliRunner()
    result = runner.invoke(cli_app, ["apply-bootstrap", "add_demo"])

    assert result.exit_code == 0, result.output
    assert captured["url"] == "http://127.0.0.1:8000/bootstraps/apply"
    assert captured["json"] == {"mode": "add_demo"}
    assert '"bootstrap_mode": "add_demo"' in result.output
