"""0305 · 配置有效性、工具调用、部署文件完整性。"""

import json
from pathlib import Path

import httpx2
from fastmcp import Client

from helpers import load_server, serve_http

CASE_DIR = Path(__file__).parent
SERVER = load_server("0305-deploy-install")


def test_fastmcp_json_is_valid() -> None:
    config = json.loads((CASE_DIR / "fastmcp.json").read_text(encoding="utf-8"))
    assert config["source"]["path"] == "server.py"
    assert config["source"]["entrypoint"] == "mcp"
    assert config["deployment"]["transport"] == "http"
    assert config["deployment"]["port"] == 8109


async def test_tools_and_health() -> None:
    async with serve_http(SERVER.mcp) as url:
        async with Client(url) as client:
            assert (await client.call_tool("roll_dice", {"sides": 6})).data["sides"] == 6

        async with httpx2.AsyncClient(timeout=5) as http:
            response = await http.get(url.removesuffix("/mcp") + "/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_container_assets_exist() -> None:
    dockerfile = (CASE_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "fastmcp.json" in dockerfile
    assert "EXPOSE 8109" in dockerfile
