"""The running app should report which version it is, so a deployed box can be identified."""

import tomllib
from pathlib import Path

from httpx import AsyncClient

from jyyfinhub_spendtracker.main import create_app

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _declared_version() -> str:
    return tomllib.loads(PYPROJECT.read_text())["project"]["version"]


def test_openapi_reports_the_packaged_version() -> None:
    assert create_app().openapi()["info"]["version"] == _declared_version()


async def test_docs_page_serves(client: AsyncClient) -> None:
    assert (await client.get("/docs")).status_code == 200
