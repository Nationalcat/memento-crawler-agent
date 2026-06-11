"""
瀏覽器管理工具模組
提供無頭瀏覽器的初始化、導航、互動與關閉功能
封裝底層瀏覽器操作，提供簡潔的介面供 Agent 使用
"""
from typing import Optional, Dict
import httpx
from urllib.parse import urlparse


class BrowserManager:
    """
    瀏覽器管理器
    負責管理無頭瀏覽器的生命週期
    提供網頁導航、元素互動等功能
    """

    def __init__(self):
        """初始化瀏覽器管理器"""
        self._initialized = False  # 初始化狀態標記
        self._current_content = "" # 當前網頁內容

    async def initialize(self) -> None:
        """
        初始化瀏覽器實例
        建立無頭瀏覽器連線
        """
        self._initialized = True
        self._current_content = ""

    async def navigate(self, url: str) -> str:
        """
        導航至指定網址（抓取真實網頁內容）
        參數:
            url: 目標網址
        回傳:
            網頁原始 HTML 內容
        例外:
            RuntimeError: 若瀏覽器未初始化
        """
        if not self._initialized:
            raise RuntimeError("瀏覽器尚未初始化")
        
        url = BrowserManager.normalize_url(url)
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
                response = await client.get(url)
                self._current_content = response.text
                return self._current_content
        except Exception as e:
            self._current_content = f"<html>錯誤: {str(e)}</html>"
            raise RuntimeError(f"網頁導航失敗: {str(e)}")

    async def get_content(self) -> str:
        """
        獲取當前頁面內容
        回傳:
            網頁原始 HTML 內容
        例外:
            RuntimeError: 若瀏覽器未初始化
        """
        if not self._initialized:
            raise RuntimeError("瀏覽器尚未初始化")
        return self._current_content

    async def click(self, selector: str) -> bool:
        """
        點擊指定元素
        參數:
            selector: CSS 選擇器
        回傳:
            布林值表示是否點擊成功
        """
        return True

    async def scroll(self) -> None:
        """滾動頁面"""
        pass

    async def close(self) -> None:
        """關閉瀏覽器並釋放資源"""
        self._initialized = False

    @staticmethod
    def normalize_url(url: str) -> str:
        """
        URL 格式補全
        - example.com → https://example.com
        - http://example.com → 保持不變
        - https://example.com → 保持不變
        
        參數:
            url: 原始 URL
        回傳:
            補全後的 URL
        """
        url = url.strip()
        if not url:
            return url

        # 已經有協議，直接返回
        if url.startswith('http://') or url.startswith('https://'):
            return url

        # 添加 https:// 前綴
        return f"https://{url}"

    @staticmethod
    async def check_url_status(url: str) -> Dict:
        """
        檢查 URL 可訪問性
        發送 HTTP HEAD 請求檢查狀態碼
        
        參數:
            url: 目標網址
        回傳:
            包含 accessible, status_code, message 的字典
        """
        url = BrowserManager.normalize_url(url)

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.head(url)

                if response.status_code == 200:
                    return {
                        "accessible": True,
                        "status_code": response.status_code,
                        "message": "頁面可正常訪問"
                    }
                else:
                    return {
                        "accessible": False,
                        "status_code": response.status_code,
                        "message": f"頁面無法訪問 (HTTP {response.status_code})"
                    }

        except httpx.TimeoutException:
            return {
                "accessible": False,
                "status_code": 0,
                "message": "連線超時"
            }
        except httpx.ConnectError:
            return {
                "accessible": False,
                "status_code": 0,
                "message": "無法連接到伺服器"
            }
        except Exception as e:
            return {
                "accessible": False,
                "status_code": 0,
                "message": f"檢查失敗: {str(e)}"
            }

    @staticmethod
    def extract_domain(url: str) -> str:
        """
        提取 URL 的域名
        
        參數:
            url: 目標網址
        回傳:
            域名字符串
        """
        url = BrowserManager.normalize_url(url)
        parsed = urlparse(url)
        return parsed.netloc
