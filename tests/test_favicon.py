"""Icon wiring is easy to break silently, since a 404 favicon looks like nothing at all."""

import pytest
from httpx import AsyncClient

ICONS = [
    "/static/favicon/favicon.ico",
    "/static/favicon/favicon-16x16.png",
    "/static/favicon/favicon-32x32.png",
    "/static/favicon/apple-touch-icon.png",
    "/static/favicon/android-chrome-192x192.png",
    "/static/favicon/android-chrome-512x512.png",
]


@pytest.mark.parametrize("path", ICONS)
async def test_icon_files_are_served(client: AsyncClient, path: str) -> None:
    assert (await client.get(path)).status_code == 200


async def test_root_favicon_ico(client: AsyncClient) -> None:
    """Browsers probe /favicon.ico even when link tags point elsewhere."""
    response = await client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"] in {
        "image/vnd.microsoft.icon",
        "image/x-icon",
    }


async def test_manifest_declares_existing_icons(client: AsyncClient) -> None:
    response = await client.get("/static/favicon/site.webmanifest")
    assert response.status_code == 200

    for icon in response.json()["icons"]:
        assert (await client.get(icon["src"])).status_code == 200


async def test_pages_link_the_icons(client: AsyncClient) -> None:
    page = await client.get("/transactions")
    assert 'rel="manifest"' in page.text
    assert "/static/favicon/favicon-32x32.png" in page.text
    assert "/static/favicon/apple-touch-icon.png" in page.text
