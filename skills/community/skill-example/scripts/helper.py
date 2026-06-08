"""
通用電商爬蟲輔助腳本
提供額外的處理邏輯，如分頁、動態加載等
"""
from typing import Dict, Any, List, Optional


async def execute(url: str, params: Dict, skill) -> Dict:
    """
    主執行函數
    如果需要自定義執行邏輯，在這裡實現
    
    參數:
        url: 目標網址
        params: 執行參數
        skill: 技能實例
    回傳:
        執行結果
    """
    # 這裡可以實現自定義的執行邏輯
    # 例如：處理分頁、動態加載、API 調用等
    
    # 如果不需要自定義邏輯，返回 None 讓系統使用預設執行
    return None


def preprocess_page(html_content: str) -> str:
    """
    頁面預處理
    在提取數據之前對頁面內容進行處理
    
    參數:
        html_content: 原始 HTML 內容
    回傳:
        處理後的 HTML 內容
    """
    # 移除廣告、彈窗等無關元素
    # 可以使用 BeautifulSoup 進行處理
    
    return html_content


def postprocess_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    數據後處理
    在提取數據之後對數據進行處理
    
    參數:
        data: 提取的原始數據
    回傳:
        處理後的數據
    """
    results = []
    
    for item in data:
        processed_item = {}
        
        # 處理價格
        if 'price' in item and item['price']:
            processed_item['price'] = _parse_price(item['price'])
        else:
            processed_item['price'] = None
            
        # 處理原價
        if 'original_price' in item and item['original_price']:
            processed_item['original_price'] = _parse_price(item['original_price'])
        else:
            processed_item['original_price'] = None
            
        # 處理評分
        if 'rating' in item and item['rating']:
            processed_item['rating'] = _parse_rating(item['rating'])
        else:
            processed_item['rating'] = None
            
        # 處理評論數
        if 'review_count' in item and item['review_count']:
            processed_item['review_count'] = _parse_review_count(item['review_count'])
        else:
            processed_item['review_count'] = None
            
        # 複製其他字段
        for key, value in item.items():
            if key not in processed_item:
                processed_item[key] = value
                
        results.append(processed_item)
    
    return results


def _parse_price(price_str: str) -> Optional[float]:
    """
    解析價格字符串
    參數:
        price_str: 價格字符串
    回傳:
        價格數值
    """
    if not price_str:
        return None
        
    import re
    # 移除貨幣符號和空格
    cleaned = re.sub(r'[^\d.]', '', str(price_str))
    
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_rating(rating_str: str) -> Optional[float]:
    """
    解析評分字符串
    參數:
        rating_str: 評分字符串
    回傳:
        評分數值
    """
    if not rating_str:
        return None
        
    import re
    # 提取數字部分
    match = re.search(r'(\d+\.?\d*)', str(rating_str))
    
    if match:
        try:
            return float(match.group(1))
        except (ValueError, TypeError):
            return None
    return None


def _parse_review_count(review_str: str) -> Optional[int]:
    """
    解析評論數量字符串
    參數:
        review_str: 評論數量字符串
    回傳:
        評論數量
    """
    if not review_str:
        return None
        
    import re
    # 提取數字部分
    match = re.search(r'(\d+)', str(review_str).replace(',', ''))
    
    if match:
        try:
            return int(match.group(1))
        except (ValueError, TypeError):
            return None
    return None


def validate_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    驗證數據完整性
    參數:
        data: 提取的數據
    回傳:
        驗證結果 {"valid": bool, "errors": list}
    """
    errors = []
    
    # 檢查必填字段
    if not data.get('product_name'):
        errors.append("缺少商品名稱")
        
    if not data.get('price'):
        errors.append("缺少商品價格")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }
