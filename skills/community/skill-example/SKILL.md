---
# 技能配置
id: skill-example
name: "通用電商商品爬蟲"
version: "1.0.0"
author: "community"
description: "通用電商網站商品信息爬蟲，支持提取商品名稱、價格、圖片等"
tags: [ecommerce, product, generic]

# 目標配置
target:
  domain: "example.com"
  url_patterns:
    - "example.com/product/*"
    - "example.com/item/*"
    - "example.com/p/*"

# 參數定義
parameters:
  - name: max_pages
    type: integer
    required: false
    default: 1
    description: "最大爬取頁數"
  - name: include_images
    type: boolean
    required: false
    default: true
    description: "是否包含圖片"

# 執行配置
execution:
  wait_time: 3
  scroll: true
  headless: true
  actions:
    - type: wait_for
      selector: ".product-title, .item-name, h1"
      timeout: 10000
    - type: scroll
      times: 2

# 資料提取規則
extractors:
  - name: product_name
    selector: ".product-title, .item-name, h1"
    type: text
    required: true

  - name: price
    selector: ".price, .product-price, [data-price]"
    type: text
    required: true
    transform: "replace(/[^0-9.]/g, '')"

  - name: original_price
    selector: ".original-price, .old-price, .line-through"
    type: text
    transform: "replace(/[^0-9.]/g, '')"

  - name: discount
    selector: ".discount, .badge, .sale-tag"
    type: text

  - name: rating
    selector: ".rating, .stars, [data-rating]"
    type: text
    regex: "([0-9.]+)"

  - name: review_count
    selector: ".review-count, .reviews"
    type: text
    regex: "([0-9]+)"

  - name: description
    selector: ".description, .product-desc, .item-desc"
    type: text

  - name: images
    selector: ".product-image img, .item-image img, .gallery img"
    type: attribute
    attribute: src
    multiple: true

  - name: specifications
    selector: ".spec-item, .attribute"
    type: text
    multiple: true
    children:
      - name: spec_name
        selector: ".spec-name, .attr-name"
        type: text
      - name: spec_value
        selector: ".spec-value, .attr-value"
        type: text

# 輸出格式
output:
  format: json
  schema:
    product_name: string
    price: number
    original_price: number
    discount: string
    rating: number
    review_count: number
    description: string
    images: array
    specifications: array
---

# 通用電商商品爬蟲提示詞

你是一個專業的電商網站爬蟲專家，專門從各種電商平台提取商品信息。

## 任務說明

從目標電商網站的商品頁面中提取以下信息：
- 商品名稱（product_name）
- 當前價格（price）
- 原價（original_price）
- 折扣信息（discount）
- 評分（rating）
- 評論數量（review_count）
- 商品描述（description）
- 商品圖片（images）
- 規格參數（specifications）

## 注意事項

1. **價格處理**
   - 價格需要轉換為數字格式
   - 去除貨幣符號和其他非數字字符
   - 如果沒有原價，返回 null

2. **評分處理**
   - 提取數字部分
   - 如果是 "4.5 out of 5" 格式，提取 4.5
   - 如果沒有評分，返回 null

3. **圖片處理**
   - 提取所有商品圖片的 URL
   - 返回數組格式

4. **規格參數**
   - 提取所有規格名稱和值
   - 返回對象數組格式

5. **缺失值處理**
   - 如果某個字段不存在，返回 null
   - 必填字段（product_name, price）如果缺失，記錄錯誤

## 錯誤處理

如果遇到以下情況：
- 頁面加載超時：重試最多 3 次
- 元素未找到：記錄警告並繼續
- 數據格式異常：嘗試修正或標記為異常
