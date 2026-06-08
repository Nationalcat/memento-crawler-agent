# Memento-Skills 爬蟲 Agent

> Agent 藉由自主學習提升能力來有效爬蟲電商網站與分析

## 專案簡介

本專案建構一個具備**自我修復（Self-Healing）**與**自主擴張能力**的爬蟲與分析 Agent。透過結合大型語言模型的語意理解能力與 Memento-Skills 的動態技能庫架構，實現：

- **技能模組化儲存**：將爬蟲策略儲存為可重複使用的技能檔案
- **讀寫反思學習迴圈**：失敗時自動分析原因並生成新技能
- **零模型更新成本**：所有能力進化皆來自外部技能與提示詞演進
- **即時 WebSocket 通訊**：任務執行狀態即時推送給前端使用者
- **會話臨時記憶**：使用 sessionId 管理任務狀態，無需用戶帳號

## 系統架構

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          Memento-Skills 爬蟲 Agent                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   ┌─────────────┐        ┌─────────────────────────────────────────────┐  │
│   │   前端頁面   │◀─ WS ─▶│              FastAPI 伺服器                  │  │
│   │  (Browser)  │        │  ┌─────────────┐  ┌─────────────────────┐  │  │
│   └─────────────┘        │  │  Session    │  │   WebSocket         │  │  │
│                          │  │  Manager    │  │   Observer          │  │  │
│                          │  └─────────────┘  └─────────────────────┘  │  │
│                          └─────────────────────────────────────────────┘  │
│                                            │                               │
│                                            ▼                               │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│   │   Harness    │───▶│   Executor   │───▶│   Analyzer   │                │
│   │   控制層     │    │   執行層     │    │   分析層     │                │
│   └──────────────┘    └──────────────┘    └──────────────┘                │
│          │                   │                   │                         │
│          ▼                   ▼                   ▼                         │
│   ┌──────────────────────────────────────────────────────────────────┐    │
│   │                    技能記憶庫 (Skill Memory)                      │    │
│   └──────────────────────────────────────────────────────────────────┘    │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## 核心功能

| 功能編號 | 功能描述                                 | 使用案例 |
|---------|----------------------------------------|---------|
| F01     | 自然語言任務解析與排程                      | UC1     |
| F02     | 向量化技能檢索 (RAG)                      | UC2     |
| F03     | 無頭瀏覽器自動化操作                        | UC3     |
| F04     | LLM 動態腳本生成與自癒機制                  | UC4     |
| F05     | 非結構化文本語意萃取                        | UC5     |
| F06     | 異常偵測與自動重試（最多 20 次）              | UC6     |
| F07     | DOM 結構變動時自動尋找替代路徑                | UC6     |
| F08     | WebSocket 即時狀態推送                    | UC7     |
| F09     | 操作日誌與瀏覽器截圖記錄                     | UC7     |
| F10     | REST API 任務管理介面                      | UC1     |
| F11     | 會話臨時記憶管理                           | UC7     |
| F12     | 輸入驗證與 URL 補全                        | UC1     |
| F13     | URL 可訪問性檢查（404/500 中斷）             | UC1     |
| F14     | 任務拒絕與重新輸入機制                       | UC1     |
| F15     | 技能持久化到檔案系統                        | UC6     |
| F16     | 提示詞配置檔案管理                         | UC4     |

## 三個設計模式

### 1. 策略模式 (Strategy Pattern)

**檔案位置**：`skills/strategy.py`

策略模式用於實現不同網站的爬蟲邏輯切換，系統可根據目標網址自動選擇最合適的爬蟲策略。

```python
# 抽象策略介面
class CrawlStrategy(ABC):
    @abstractmethod
    async def crawl(self, url: str, selectors: Dict[str, str]) -> Dict:
        pass

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        pass

# 具體策略實作
class EcommerceCrawlStrategy(CrawlStrategy):   # 電商網站策略
class AntiBotCrawlStrategy(CrawlStrategy):     # 反爬蟲繞過策略
class DefaultCrawlStrategy(CrawlStrategy):     # 預設通用策略

# 策略註冊中心（單例）
class StrategyRegistry:
    def get_strategy(self, url: str) -> CrawlStrategy:  # 自動選擇策略
    def register(self, strategy: CrawlStrategy):        # 註冊新策略
```

### 2. 觀察者模式 (Observer Pattern)

**檔案位置**：`observers/monitor.py`

觀察者模式用於任務狀態監控與事件通知，實現系統各元件間的鬆耦合通訊。

```python
# 觀察者介面
class Observer(ABC):
    @abstractmethod
    def update(self, state: AgentState) -> None:
        pass

# 被觀察主題
class Subject:
    def attach(self, observer: Observer) -> None:   # 訂閱
    def detach(self, observer: Observer) -> None:   # 取消訂閱
    def notify(self, state: AgentState) -> None:    # 通知

# 具體觀察者
class ConsoleLogger(Observer):       # 控制台日誌輸出
class ErrorAlert(Observer):          # 錯誤告警收集
class WebSocketObserver(Observer):   # WebSocket 即時推送（新增）

# 任務監控器
class TaskMonitor(Subject):
    def update_state(self, state: AgentState) -> None:  # 更新並通知
    def get_task_history(self, task_id: str):            # 獲取歷史記錄
    def get_active_tasks(self) -> List[str]:             # 獲取進行中任務
```

### 3. 工廠模式 (Factory Pattern)

**檔案位置**：`agents/factory.py`

工廠模式用於統一建立與管理不同類型的 Agent，確保系統的可擴展性。

```python
# Agent 類型列舉
class AgentType(str, Enum):
    HARNESS = "harness"    # 控制層
    EXECUTOR = "executor"  # 執行層
    ANALYZER = "analyzer"  # 分析層

# Agent 抽象基類
class BaseAgent(ABC):
    @abstractmethod
    async def process(self, state: AgentState) -> AgentState:
        pass

# Agent 工廠（單例）
class AgentFactory:
    @classmethod
    def register(cls, agent_type: AgentType, agent_class: Type[BaseAgent]):  # 註冊
    @classmethod
    def create(cls, agent_type: AgentType, agent_id: str) -> BaseAgent:      # 建立
```

### 4. 模板模式 (Template Pattern)

**檔案位置**：`skills/loaders/base.py`

模板模式用於定義技能載入的演算法骨架，將具體解析邏輯延遲到子類別實現。結合工廠模式，支持多種技能格式的擴展。

```python
# 抽象載入器（模板基類）
class BaseSkillLoader(ABC):
    # 模板方法（固定流程）
    def load_all(self, directory: Path) -> List[CommunitySkill]
    def load_skill(self, path: Path) -> Optional[CommunitySkill]
    
    # 抽象方法（子類別實現）
    @abstractmethod
    def _is_skill(self, path: Path) -> bool
    @abstractmethod
    def _read_content(self, path: Path) -> str
    @abstractmethod
    def _parse_content(self, content: str) -> dict
    @abstractmethod
    def _build_skill(self, data: dict, path: Path) -> CommunitySkill

# 具體實現
class YamlSkillLoader(BaseSkillLoader):  # YAML 格式載入器（SKILL.md）
class JsonSkillLoader(BaseSkillLoader):  # JSON 格式載入器

# 載入器工廠
class SkillLoaderFactory:
    @classmethod
    def create(cls, format_type: SkillFormat) -> BaseSkillLoader
    @classmethod
    def register(cls, format_type: SkillFormat, loader_class: type)
```

#### 載入流程

```
SkillLoaderFactory.create(format_type)
        │
        ▼
BaseSkillLoader.load_all(directory)
        │
        ├── _is_skill()      # 判斷是否是技能
        │
        └── load_skill()
                │
                ├── _read_content()    # 讀取內容
                ├── _parse_content()   # 解析內容
                ├── _build_skill()     # 構建對象
                └── _validate_skill()  # 驗證技能
```

## 專案結構

```
demo/
├── main.py                    # 主程式入口（支援 CLI/Web 模式）
├── run.py                     # FastAPI 啟動腳本
├── config.py                  # 系統配置
├── prompts.yml                # 提示詞配置文件
├── requirements.txt           # 依賴套件
├── README.md                  # 專案說明文件
│
├── api/                       # FastAPI 模組
│   ├── __init__.py
│   ├── app.py                # FastAPI 應用主體
│   └── session.py            # 會話管理器
│
├── static/                    # 靜態檔案
│   └── index.html            # 前端測試頁面
│
├── models/                    # 資料模型
│   ├── __init__.py
│   ├── state.py              # Agent 狀態模型
│   └── skill.py              # 技能資料模型
│
├── agents/                    # Agent 模組
│   ├── __init__.py
│   ├── harness.py            # Harness 控制層
│   ├── executor.py           # Agent 執行層
│   └── factory.py            # 工廠模式
│
├── skills/                    # 技能模組
│   ├── __init__.py
│   ├── models.py             # 結構化技能模型
│   ├── executor.py           # 技能執行器
│   ├── memory.py             # 技能記憶庫
│   ├── strategy.py           # 策略模式
│   ├── base.py               # 基礎技能類
│   ├── loaders/              # 技能載入器（模板模式 + 工廠模式）
│   │   ├── __init__.py
│   │   ├── base.py           # 模板基類
│   │   ├── yaml_loader.py    # YAML 格式載入器
│   │   ├── json_loader.py    # JSON 格式載入器
│   │   └── factory.py        # 載入器工廠
│   ├── community/            # 結構化技能目錄
│   │   └── skill-example/
│   │       ├── SKILL.md      # 技能描述（YAML + Markdown）
│   │       ├── requirements.txt
│   │       ├── resources/
│   │       └── scripts/
│   │           └── helper.py
│   └── data/                 # 自動生成技能目錄
│       └── *.json
│
├── graph/                     # 工作流模組
│   ├── __init__.py
│   ├── workflow.py           # LangGraph 工作流
│   └── nodes/                # 工作流節點
│       ├── __init__.py
│       ├── validation.py     # 驗證節點
│       ├── execution.py      # 執行節點
│       ├── skill.py          # 技能節點
│       └── output.py         # 輸出節點
│
├── observers/                 # 觀察者模組
│   ├── __init__.py
│   └── monitor.py            # 觀察者模式
│
└── utils/                     # 工具模組
    ├── __init__.py
    ├── browser.py            # 瀏覽器管理器
    └── prompts.py            # 提示詞載入器
```
│   ├── strategy.py           # 策略模式
│   └── base.py               # 基礎技能類
│
├── graph/                     # 工作流模組
│   ├── __init__.py
│   └── workflow.py           # LangGraph 工作流
│
├── observers/                 # 觀察者模組
│   ├── __init__.py
│   └── monitor.py            # 觀察者模式
│
└── utils/                     # 工具模組
    ├── __init__.py
    └── browser.py            # 瀏覽器管理器
```

## API 接口文檔

### REST API

#### 1. 建立會話

**端點**：`POST /api/session/create`

**說明**：建立新的會話，返回 sessionId 用於後續 WebSocket 連接

**請求**：無需請求體

**回應**：
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "會話建立成功"
}
```

**狀態碼**：
- `200`：成功建立會話

---

#### 2. 獲取會話狀態

**端點**：`GET /api/session/{session_id}/status`

**說明**：查詢指定會話的詳細狀態資訊

**路徑參數**：
| 參數 | 類型 | 說明 |
|------|------|------|
| session_id | string | 會話識別碼 |

**回應**：
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "is_connected": true,
    "created_at": "2026-06-08T14:30:00.000000",
    "last_active": "2026-06-08T14:35:00.000000",
    "task_history_count": 2,
    "current_state": {
        "task_id": "abc123",
        "status": "completed",
        "extracted_data": [...]
    }
}
```

**錯誤回應**：
```json
{
    "error": "會話不存在"
}
```

---

#### 3. 獲取系統統計

**端點**：`GET /api/stats`

**說明**：獲取系統整體統計資訊

**回應**：
```json
{
    "active_sessions": 5,
    "server_time": "2026-06-08T14:35:00.000000"
}
```

---

#### 4. 前端頁面

**端點**：`GET /`

**說明**：返回前端測試頁面（HTML）

---

### WebSocket API

#### 連接端點

**端點**：`WS /ws/{session_id}`

**說明**：建立 WebSocket 即時通訊連接

**路徑參數**：
| 參數 | 類型 | 說明 |
|------|------|------|
| session_id | string | 會話識別碼（需先透過 REST API 建立） |

**連接流程**：
1. 呼叫 `POST /api/session/create` 取得 sessionId
2. 使用 `ws://host/ws/{sessionId}` 建立 WebSocket 連接
3. 接收 `connected` 訊息確認連接成功

---

#### 客戶端 → 伺服器訊息

##### 1. 啟動任務

```json
{
    "type": "start_task",
    "url": "https://www.example.com/products",
    "instruction": "抓取所有商品名稱、價格和評價"
}
```

##### 2. 取消任務

```json
{
    "type": "cancel_task"
}
```

##### 3. 心跳檢測

```json
{
    "type": "ping"
}
```

---

#### 伺服器 → 客戶端訊息

##### 1. 連接成功

```json
{
    "type": "connected",
    "message": "WebSocket 連接成功",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

##### 2. 狀態更新

```json
{
    "type": "status_update",
    "task_id": "abc123",
    "status": "executing",
    "current_step": 2,
    "total_steps": 6,
    "extracted_data_count": 0,
    "error_count": 0,
    "timestamp": "2026-06-08T14:30:05.000000"
}
```

**status 狀態值**：
| 值 | 說明 |
|-----|------|
| pending | 待處理 |
| parsing | 解析中 |
| skill_loading | 技能載入中 |
| executing | 執行中 |
| extracting | 提取中 |
| reflecting | 反思中 |
| completed | 已完成 |
| failed | 已失敗 |

##### 3. 任務啟動

```json
{
    "type": "task_started",
    "message": "任務開始執行",
    "url": "https://www.example.com/products",
    "instruction": "抓取所有商品名稱、價格和評價"
}
```

##### 4. 任務完成

```json
{
    "type": "task_completed",
    "task_id": "abc123",
    "status": "completed",
    "extracted_data": [
        {"name": "商品A", "price": 1000},
        {"name": "商品B", "price": 2000}
    ],
    "error_log": [],
    "retry_count": 0
}
```

##### 5. 任務錯誤

```json
{
    "type": "task_error",
    "message": "連線超時"
}
```

##### 6. 任務取消

```json
{
    "type": "task_cancelled",
    "message": "任務已取消"
}
```

##### 7. 心跳回應

```json
{
    "type": "pong",
    "timestamp": "2026-06-08T14:30:30.000000"
}
```

##### 8. 錯誤訊息

```json
{
    "type": "error",
    "message": "缺少必要參數：url 或 instruction"
}
```

---

## LangGraph 工作流程

### v1.2.0 新流程

```
                              ┌─────────────┐
                              │   開始任務   │
                              └─────────────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │  驗證輸入   │
                              │ URL/指令    │
                              └─────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     │                               │
                     ▼ 失敗                           ▼ 通過
              ┌─────────────┐                 ┌─────────────┐
              │  拒絕任務   │                 │ 檢查URL     │
              │  返回錯誤   │                 │ 可訪問性    │
              └─────────────┘                 └─────────────┘
                                                     │
                                     ┌───────────────┴───────────────┐
                                     │                               │
                                     ▼ 不可訪問                      ▼ 可訪問
                              ┌─────────────┐                 ┌─────────────┐
                              │  拒絕任務   │                 │  檢索技能   │
                              │  404/500    │                 │  記憶庫     │
                              └─────────────┘                 └─────────────┘
                                                                     │
                                                     ┌───────────────┴───────────────┐
                                                     │                               │
                                                     ▼ 有 Skill                      ▼ 無 Skill
                                              ┌─────────────┐                 ┌─────────────┐
                                              │ 使用Skill   │                 │  自動執行   │
                                              │ 執行爬取    │                 │ LLM生成策略 │
                                              └─────────────┘                 └─────────────┘
                                                     │                               │
                                                     └───────────────┬───────────────┘
                                                                     │
                                                                     ▼
                                                             ┌─────────────┐
                                                             │  執行成功？ │
                                                             └─────────────┘
                                                                     │
                                                     ┌───────────────┴───────────────┐
                                                     │ 成功                          │ 失敗
                                                     ▼                               ▼
                                              ┌─────────────┐                 ┌─────────────┐
                                              │  解析數據   │                 │ 錯誤處理    │
                                              │  返回前端   │                 │ retry<20?   │
                                              └─────────────┘                 └─────────────┘
                                                     │                               │
                                                     │                   ┌───────────┴───────────┐
                                                     │                   │ 是                    │ 否
                                                     ▼                   ▼                       ▼
                                              ┌─────────────┐     ┌─────────────┐         ┌─────────────┐
                                              │  更新技能   │     │ LLM分析    │         │  任務失敗   │
                                              │  庫         │     │ 生成新策略  │         │  結束       │
                                              └─────────────┘     └─────────────┘         └─────────────┘
                                                     │                   │
                                                     ▼                   ▼
                                              ┌─────────────┐     ┌─────────────┐
                                              │  輸出結果   │     │  自動執行   │
                                              │  結束       │     │  使用新策略 │
                                              └─────────────┘     └─────────────┘
```

### v1.0.0 原流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ parse_task  │────▶│retrieve_skill│────▶│execute_crawl│
│  任務解析   │     │  技能檢索   │     │  執行爬取   │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          │                    │                    │
                          ▼                    ▼                    ▼
                    ┌──────────┐         ┌──────────┐        ┌──────────┐
                    │  reflect │         │ extract  │        │  output  │
                    │  反思    │         │ _data    │        │ _result  │
                    └──────────┘         └──────────┘        └──────────┘
                          │                    │                    │
                          │                    │                    │
                          ▼                    ▼                    ▼
                    execute_crawl          output_result           END
```

## 安裝與執行

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 設定環境變數

建立 `.env` 檔案：

```env
LLM_API_KEY=your_api_key_here
LLM_MODEL=gpt-4
```

### 3. 提示詞配置

提示詞配置檔案為 `prompts.yml`，包含以下提示詞模板：

| 名稱 | 用途 |
|------|------|
| `analyze_webpage` | 網頁結構分析 |
| `analyze_error` | 錯誤原因分析 |
| `clean_data` | 資料清洗 |
| `validate_url` | URL 驗證 |
| `generate_skill` | 技能生成 |

可根據需求修改提示詞內容，無需更改程式碼。

### 4. 執行程式

#### Web 模式（預設）

```bash
# 方式一：使用 main.py
python main.py

# 方式二：使用 run.py
python run.py
```

啟動後訪問 http://localhost:8000

#### CLI 模式

```bash
python main.py cli
```

## 使用範例

### 1. 瀏覽器操作流程

1. 開啟 http://localhost:8000
2. 系統自動建立 sessionId 並連接 WebSocket
3. 輸入目標網址和爬蟲指令
4. 點擊「開始執行」
5. 即時查看執行日誌和狀態更新

### 2. API 調用範例

#### Python 範例

```python
import asyncio
import websockets
import json
import httpx

async def main():
    # 1. 建立會話
    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:8000/api/session/create")
        session_data = response.json()
        session_id = session_data["session_id"]

    # 2. 連接 WebSocket
    async with websockets.connect(f"ws://localhost:8000/ws/{session_id}") as ws:
        # 3. 啟動任務
        await ws.send(json.dumps({
            "type": "start_task",
            "url": "https://www.example.com/products",
            "instruction": "抓取所有商品名稱和價格"
        }))

        # 4. 接收狀態更新
        while True:
            message = await ws.recv()
            data = json.loads(message)
            print(f"收到訊息: {data}")

            if data.get("type") == "task_completed":
                break

asyncio.run(main())
```

#### JavaScript 範例

```javascript
async function runCrawler() {
    // 1. 建立會話
    const response = await fetch('/api/session/create', { method: 'POST' });
    const { session_id } = await response.json();

    // 2. 連接 WebSocket
    const ws = new WebSocket(`ws://localhost:8000/ws/${session_id}`);

    ws.onopen = () => {
        // 3. 啟動任務
        ws.send(JSON.stringify({
            type: 'start_task',
            url: 'https://www.example.com/products',
            instruction: '抓取所有商品名稱和價格'
        }));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('收到訊息:', data);

        if (data.type === 'task_completed') {
            console.log('任務完成:', data.extracted_data);
        }
    };
}
```

## 輸出範例

### WebSocket 訊息流

```
[14:30:00] [系統] 會話建立成功
[14:30:01] [系統] WebSocket 連接成功
[14:30:05] [任務] 任務開始執行
[14:30:05] [任務] 目標: https://www.example.com/products
[14:30:05] [任務] 指令: 抓取所有商品名稱和價格
[14:30:06] [狀態] 解析中 - 步驟 0/6
[14:30:07] [狀態] 執行中 - 步驟 0/6
[14:30:08] [狀態] 提取中 - 步驟 0/6
[14:30:09] [完成] 任務 abc123 已完成
[14:30:09] [資料] 提取 10 筆資料
```

### CLI 輸出

```
[2026-06-08 14:30:00] 任務 abc123: TaskStatus.PARSING - 步驟 0/6
[2026-06-08 14:30:01] 任務 abc123: TaskStatus.EXECUTING - 步驟 0/6
[2026-06-08 14:30:02] 任務 abc123: TaskStatus.EXTRACTING - 步驟 0/6
[2026-06-08 14:30:03] 任務 abc123: TaskStatus.COMPLETED - 步驟 0/6

=== 任務執行結果 ===
任務 ID: abc123
狀態: TaskStatus.COMPLETED
提取資料數量: 1
重試次數: 0
```

## 技術堆疊

- **LangGraph**: 工作流引擎
- **LangChain**: LLM 整合框架
- **FastAPI**: Web 框架
- **WebSocket**: 即時通訊
- **Pydantic**: 資料驗證與模型定義
- **Uvicorn**: ASGI 伺服器
- **PyYAML**: 提示詞配置解析
- **HTTPX**: 非同步 HTTP 客戶端
- **Python Async**: 非同步執行

## 版本

### v1.0.0 (2026-06-08)

初始版本，包含完整功能：

- LangGraph 工作流引擎
- 三個設計模式（策略、觀察者、工廠）
- 結構化技能系統（SKILL.md 格式）
- 技能記憶庫（支援兩種格式）
- FastAPI + WebSocket 即時通訊
- LLM 整合（錯誤分析、策略生成、數據清洗）
- 輸入驗證與 URL 可訪問性檢查
- 錯誤重試機制（最多 20 次）
- 技能自動生成與更新

## 授權條款

MIT License
