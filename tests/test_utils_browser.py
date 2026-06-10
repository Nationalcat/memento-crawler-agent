import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from utils.browser import BrowserManager


@pytest.mark.asyncio
async def test_browser_lifecycle_and_navigation():
    bm = BrowserManager()
    
    # 1. Before initialization, navigate should raise RuntimeError
    with pytest.raises(RuntimeError, match="瀏覽器尚未初始化"):
        await bm.navigate("http://example.com")
        
    # 2. After initialization, navigate should return mock html content
    await bm.initialize()
    html = await bm.navigate("http://example.com")
    assert "來自 http://example.com 的模擬內容" in html
    
    # 3. click and scroll behavior
    assert await bm.click(".btn") is True
    await bm.scroll()
    
    # 4. close should de-initialize
    await bm.close()
    with pytest.raises(RuntimeError, match="瀏覽器尚未初始化"):
        await bm.navigate("http://example.com")


def test_normalize_url():
    # Empty url
    assert BrowserManager.normalize_url("  ") == ""
    
    # Already has prefix
    assert BrowserManager.normalize_url("http://google.com") == "http://google.com"
    assert BrowserManager.normalize_url("https://google.com") == "https://google.com"
    
    # Missing prefix
    assert BrowserManager.normalize_url("google.com") == "https://google.com"
    assert BrowserManager.normalize_url("  google.com  ") == "https://google.com"


def test_extract_domain():
    assert BrowserManager.extract_domain("google.com/search?q=123") == "google.com"
    assert BrowserManager.extract_domain("http://yahoo.com/news") == "yahoo.com"


@pytest.mark.asyncio
async def test_check_url_status():
    url = "example.com"
    
    # Setup the HTTP client mocks
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    
    # 1. HTTP 200 OK
    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    mock_client.head = AsyncMock(return_value=mock_response_200)
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await BrowserManager.check_url_status(url)
        assert res["accessible"] is True
        assert res["status_code"] == 200
        assert "正常訪問" in res["message"]

    # 2. HTTP 404 Not Found
    mock_response_404 = MagicMock()
    mock_response_404.status_code = 404
    mock_client.head = AsyncMock(return_value=mock_response_404)
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await BrowserManager.check_url_status(url)
        assert res["accessible"] is False
        assert res["status_code"] == 404
        assert "無法訪問" in res["message"]

    # 3. TimeoutException
    mock_client.head = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await BrowserManager.check_url_status(url)
        assert res["accessible"] is False
        assert res["status_code"] == 0
        assert "連線超時" in res["message"]

    # 4. ConnectError
    mock_client.head = AsyncMock(side_effect=httpx.ConnectError("connect error"))
    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await BrowserManager.check_url_status(url)
        assert res["accessible"] is False
        assert res["status_code"] == 0
        assert "無法連接到伺服器" in res["message"]

    # 5. Generic Exception
    mock_client.head = AsyncMock(side_effect=RuntimeError("unknown issue"))
    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await BrowserManager.check_url_status(url)
        assert res["accessible"] is False
        assert res["status_code"] == 0
        assert "檢查失敗: unknown issue" in res["message"]
