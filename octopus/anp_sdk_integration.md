# Octopus 项目 ANP 框架集成改造计划

## 项目概述

将 `octopus/` 项目全面集成 `external/` 中的 ANP (Agent Network Protocol) 框架，实现从简单的多智能体系统升级为功能完整的 ANP 网络节点，同时保持现有的 OpenAI 集成和自然语言处理能力。

## 改造目标

1. __全面导入 ANP 框架__：集成 `external/anp_sdk`、`external/anp_server`、`external/anp_server_framework`
2. __保持轻量架构__：ANP 核心组件保持轻量，通过分层架构实现功能增强
3. __主智能体架构__：MasterAgent 作为主智能体处理消息接收，MessageAgent 作为消息处理器
4. __网络通信能力__：获得真正的跨网络智能体通信能力
5. __向下兼容__：保持现有 API 和功能的兼容性

## 阶段一：项目结构重组和依赖整合

### 1.1 目录结构调整

```javascript
octopus/
├── anp_integration/           # 新增：ANP框架集成层
│   ├── anp_sdk/              # 从 external/anp_sdk/ 导入
│   ├── anp_server/           # 从 external/anp_server/ 导入  
│   ├── anp_server_framework/ # 从 external/anp_server_framework/ 导入
│   ├── config_integration.py # 配置系统集成
│   ├── agent_integration.py  # 智能体集成层
│   └── __init__.py
├── agents/                   # 现有：智能体模块（需要改造）
│   ├── base_agent.py        # 升级：支持ANP协议
│   ├── master_agent.py      # 移动：从根目录移入
│   ├── message_agent/       # 增强：集成网络发送能力
│   └── text_processor_agent.py
├── api/                      # 现有：API模块（需要升级）
├── config/                   # 现有：配置模块（需要整合ANP配置）
│   ├── settings.py          # 升级：集成ANP配置
│   └── anp_config.py        # 新增：ANP专用配置
├── core/                     # 现有：核心模块（需要ANP集成）
├── data_user/               # 新增：从 external/data_user/ 导入
├── octopus.py              # 现有：需要ANP服务器集成
└── ...
```

### 1.2 依赖管理整合

__任务__：

- [ ] 合并 `external/pyproject.toml` 的依赖到 octopus 项目
- [ ] 创建统一的 `pyproject.toml`
- [ ] 更新 `.gitignore` 和 `.gitmodules`

__文件修改__：

- `pyproject.toml`：添加 ANP 框架依赖
- `requirements.txt`：更新依赖列表

### 1.3 配置系统整合

__任务__：

- [ ] 创建 `octopus/config/anp_config.py`
- [ ] 集成 `external/unified_config_framework_demo.yaml` 的配置结构
- [ ] 升级 `octopus/config/settings.py` 支持 ANP 配置

__新增文件__：

```python
# octopus/config/anp_config.py
from anp_sdk.config import UnifiedConfig
from octopus.config.settings import get_settings

class OctopusANPConfig:
    def __init__(self):
        self.octopus_settings = get_settings()
        self.anp_config = UnifiedConfig(config_file='octopus_anp_config.yaml')
    
    def get_unified_config(self):
        # 合并两个配置系统
        pass
```

## 阶段二：核心组件 ANP 化改造

### 2.1 主应用模块改造 (octopus.py)

__目标__：从简单的 FastAPI 应用升级为完整的 ANP 多智能体服务器

__文件修改__：`octopus/octopus.py`

__改造内容__：

```python
# 新的 octopus.py 架构
import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from anp_server.anp_server import ANP_Server
from anp_server.server_mode import ServerMode
from anp_sdk.config import UnifiedConfig, set_global_config

from octopus.anp_integration.agent_integration import OctopusAgentManager
from octopus.config.anp_config import OctopusANPConfig
from octopus.utils.log_base import setup_enhanced_logging

# 全局变量
anp_server = None
agent_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global anp_server, agent_manager
    
    # Startup
    logger.info("Starting Octopus ANP application")
    
    # 1. 加载统一配置
    config_manager = OctopusANPConfig()
    unified_config = config_manager.get_unified_config()
    set_global_config(unified_config)
    
    # 2. 创建和加载智能体
    agent_manager = OctopusAgentManager()
    agents = await agent_manager.load_all_agents()
    
    # 3. 启动ANP服务器
    anp_server = ANP_Server(mode=ServerMode.MULTI_AGENT_ROUTER)
    await launch_anp_server(
        unified_config.anp_sdk.host, 
        unified_config.anp_sdk.port, 
        anp_server
    )
    
    logger.info("Octopus ANP application startup completed")
    yield
    
    # Shutdown
    logger.info("Shutting down Octopus ANP application")
    if anp_server:
        anp_server.stop_server()
    if agent_manager:
        await agent_manager.cleanup_all_agents()

# 保持 FastAPI 兼容性
app = FastAPI(
    title="Octopus ANP Multi-Agent System",
    description="ANP-powered multi-agent system with natural language interface",
    version="0.2.0",
    lifespan=lifespan
)

# 保持现有的 API 端点
@app.get("/")
async def root():
    return {"message": "Octopus ANP Multi-Agent System", "version": "0.2.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "anp_server": "active" if anp_server else "inactive"}

async def launch_anp_server(host: str, port: int, svr: ANP_Server):
    """启动 ANP 服务器"""
    def run_server():
        svr.start_server()
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # 等待服务器启动
    import time, socket
    def wait_for_port(host, port, timeout=15.0):
        start = time.time()
        while time.time() - start < timeout:
            try:
                with socket.create_connection((host, port), timeout=1):
                    return True
            except (OSError, ConnectionRefusedError):
                time.sleep(0.2)
        raise RuntimeError(f"ANP Server on {host}:{port} did not start within {timeout} seconds")
    
    wait_for_port(host, port)

def main():
    """主函数"""
    import uvicorn
    
    config_manager = OctopusANPConfig()
    settings = config_manager.octopus_settings
    
    logger.info(f"Starting Octopus ANP server on {settings.host}:{settings.port}")
    
    uvicorn.run(
        "octopus.octopus:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
```

### 2.2 智能体系统升级

#### 2.2.1 BaseAgent 升级

__文件修改__：`octopus/agents/base_agent.py`

__改造内容__：

- [ ] 集成 ANP 用户系统 (`ANPUser`)
- [ ] 支持 DID (Decentralized Identifier)
- [ ] 添加网络通信能力
- [ ] 支持共享DID架构

```python
# 升级后的 BaseAgent
from anp_sdk.anp_user import ANPUser
from anp_server_framework.agent_manager import AgentManager

class BaseAgent(ABC):
    def __init__(self, name: str = None, description: str = None, 
                 did: str = None, shared: bool = False, **kwargs):
        # 原有初始化
        self.agent_id = str(uuid.uuid4())
        self.info = AgentInfo(...)
        
        # ANP 集成
        if did:
            self.anp_user = ANPUser.from_did(did)
            self.anp_user_id = did
        else:
            # 生成默认 DID
            self.anp_user_id = f"did:wba:octopus.ai:agents:{self.agent_id}"
            self.anp_user = ANPUser.from_did(self.anp_user_id)
        
        self.shared_did = shared
        
        # 注册到 ANP 系统
        if shared:
            AgentManager.create_shared_agent(self.anp_user, name, **kwargs)
        else:
            AgentManager.create_agent(self.anp_user, name, **kwargs)
```

#### 2.2.2 MasterAgent ANP 化改造

__文件移动__：`octopus/master_agent.py` → `octopus/agents/master_agent.py`

__改造内容__：

- [ ] 集成 ANP 装饰器系统
- [ ] 添加消息接收处理器
- [ ] 保持 OpenAI 自然语言处理能力
- [ ] 集成 MessageAgent 作为消息处理组件

```python
# 升级后的 MasterAgent
from anp_server_framework.agent_decorator import agent_class, class_api, class_message_handler

@agent_class(
    name="octopus_master",
    description="Octopus主智能体 - 自然语言接口和任务协调",
    did="did:wba:octopus.ai:master",
    shared=True,
    prefix="/master",
    primary_agent=True  # 主智能体，可以接收消息
)
class MasterAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="OctopusMaster",
            description="Natural language interface with ANP support",
            **kwargs
        )
        
        # 保持原有的 OpenAI 集成
        self._initialize_openai_client()
        
        # 集成 MessageAgent 作为消息处理器
        from octopus.agents.message_agent import MessageAgent
        self.message_handler = MessageAgent()
    
    @class_message_handler("text")
    async def handle_incoming_message(self, msg_data):
        """接收外部消息并智能处理"""
        sender_did = msg_data.get("sender_did")
        content = msg_data.get("content")
        
        # 转发给 MessageAgent 进行记录
        await self.message_handler.receive_message(
            message_content=content,
            sender_did=sender_did,
            metadata={"forwarded_by": "master_agent"}
        )
        
        # 使用 OpenAI 进行智能处理
        if self._needs_intelligent_processing(content):
            ai_response = await self._process_with_openai(content)
            return {"reply": ai_response, "processed_by": "master_agent"}
        else:
            return {"reply": f"收到消息: {content}", "processed_by": "master_agent"}
    
    @class_api("/process_natural_language", auto_wrap=True)
    async def process_natural_language_api(self, request_data, request):
        """自然语言处理API"""
        params = request_data.get('params', {})
        request_text = params.get('request', '')
        request_id = params.get('request_id', str(uuid.uuid4()))
        
        # 保持原有的自然语言处理逻辑
        result = self.process_natural_language(request_text, request_id)
        return {"result": result, "request_id": request_id}
    
    @class_api("/send_message", auto_wrap=True)
    async def send_message_api(self, request_data, request):
        """消息发送API - 委托给 MessageAgent"""
        params = request_data.get('params', {})
        
        result = await self.message_handler.send_message(
            message_content=params.get('content'),
            recipient_did=params.get('recipient_did'),
            metadata=params.get('metadata')
        )
        
        return result
```

#### 2.2.3 MessageAgent 增强

__文件修改__：`octopus/agents/message_agent/message_agent.py`

__改造内容__：

- [ ] 集成 `agent_message_p2p` 获得网络发送能力
- [ ] 保持现有的存储和统计功能
- [ ] 移除直接的网络消息接收逻辑（由 MasterAgent 处理）

```python
# 增强后的 MessageAgent
from anp_server_framework.anp_service.agent_message_p2p import agent_msg_post

@register_agent(
    name="message_processor",
    description="消息处理和存储组件 - 集成ANP网络发送能力",
    version="2.0.0",
    tags=["message", "communication", "anp", "storage"]
)
class MessageAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="MessageProcessor",
            description="Handles message processing, storage and network sending"
        )
        
        # 保持原有的存储结构
        self.sent_messages: List[Message] = []
        self.received_messages: List[Message] = []
        self.message_history: Dict[str, List[Message]] = {}
        self.stats = {...}
    
    @agent_method(
        description="发送消息到指定接收方（支持网络发送）",
        parameters={
            "message_content": {"description": "消息内容"},
            "recipient_did": {"description": "接收方DID"},
            "metadata": {"description": "消息元数据"}
        },
        returns="dict"
    )
    async def send_message(self, message_content: str, recipient_did: str, 
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送消息 - 集成真正的网络发送能力"""
        try:
            message_id = str(uuid.uuid4())
            
            # 1. 使用 ANP 进行网络发送
            network_result = await agent_msg_post(
                caller_agent=self.anp_user_id,  # 使用 ANP DID
                target_agent=recipient_did,
                content=message_content,
                message_type="text"
            )
            
            # 2. 根据网络发送结果创建本地记录
            message = Message(
                id=message_id,
                content=message_content,
                sender_did=self.anp_user_id,
                recipient_did=recipient_did,
                timestamp=datetime.now(),
                status="sent" if network_result.get("success") else "failed",
                metadata=metadata or {}
            )
            
            # 3. 本地存储和统计（保持原有功能）
            self.sent_messages.append(message)
            self._update_conversation_history(message)
            self._update_statistics(message.status == "sent")
            
            self.logger.info(f"Message sent via ANP: {message_id} to {recipient_did}")
            
            return {
                "success": network_result.get("success", False),
                "message_id": message_id,
                "recipient_did": recipient_did,
                "content": message_content,
                "timestamp": message.timestamp.isoformat(),
                "status": message.status,
                "network_result": network_result,
                "metadata": message.metadata
            }
            
        except Exception as e:
            self.stats["failed_deliveries"] += 1
            self.logger.error(f"Failed to send message via ANP: {str(e)}")
            
            return {
                "success": False,
                "error": str(e),
                "recipient_did": recipient_did,
                "content": message_content,
                "timestamp": datetime.now().isoformat(),
                "status": "failed"
            }
    
    # 保持原有的其他方法：receive_message, get_message_history, get_statistics, clear_history
```

### 2.3 智能体集成管理器

__新增文件__：`octopus/anp_integration/agent_integration.py`

```python
# 智能体集成管理器
from anp_server_framework.agent_manager import AgentManager, LocalAgentManager
from anp_server_framework.global_router import GlobalRouter
from anp_server_framework.global_message_manager import GlobalMessageManager

class OctopusAgentManager:
    def __init__(self):
        self.agents = []
        self.lifecycle_modules = {}
        
    async def load_all_agents(self):
        """加载所有智能体"""
        # 清理之前的状态
        AgentManager.clear_all_agents()
        GlobalRouter.clear_routes()
        GlobalMessageManager.clear_handlers()
        
        # 1. 加载配置文件中的智能体
        config_agents = await self._load_config_agents()
        
        # 2. 加载代码定义的智能体
        code_agents = await self._load_code_agents()
        
        # 3. 合并所有智能体
        self.agents = config_agents + code_agents
        
        # 4. 初始化智能体
        await self._initialize_agents()
        
        return self.agents
    
    async def _load_code_agents(self):
        """加载代码定义的智能体"""
        agents = []
        
        # 导入并实例化 MasterAgent
        from octopus.agents.master_agent import MasterAgent
        master_agent = MasterAgent()
        agents.append(master_agent)
        
        # 导入其他智能体
        from octopus.agents.text_processor_agent import TextProcessorAgent
        text_agent = TextProcessorAgent()
        agents.append(text_agent)
        
        return agents
    
    async def cleanup_all_agents(self):
        """清理所有智能体"""
        for agent in self.agents:
            if hasattr(agent, 'cleanup'):
                await agent.cleanup()
```

## 阶段三：API 和网络通信集成

### 3.1 API 层升级

__文件修改__：`octopus/api/ad_router.py`

__改造内容__：

- [ ] 集成 ANP 智能体描述协议
- [ ] 支持 ANP 网络调用
- [ ] 自动生成智能体能力描述

### 3.2 配置文件创建

__新增文件__：`octopus_anp_config.yaml`

```yaml
# Octopus ANP 配置文件
multi_agent_mode:
  agents_cfg_path: '{APP_ROOT}/data_user/octopus_9527/agents_config'

did_config:
  method: wba
  format_template: did:{method}:octopus.ai:{method}:{user_type}:{user_id}
  hosts:
    octopus.ai: 9527
    localhost: 9527

anp_sdk:
  debug_mode: true
  host: localhost
  port: 9527
  user_did_path: '{APP_ROOT}/data_user/octopus_9527/anp_users'

llm:
  api_url: https://api.openai.com/v1
  default_model: gpt-4o
  max_tokens: 4000
  system_prompt: 你是Octopus多智能体系统的主智能体，负责协调和处理各种任务。
```

## 阶段四：测试和验证

### 4.1 单元测试

__新增文件__：`tests/test_anp_integration.py`

```python
import pytest
from octopus.anp_integration.agent_integration import OctopusAgentManager

@pytest.mark.asyncio
async def test_agent_loading():
    """测试智能体加载"""
    manager = OctopusAgentManager()
    agents = await manager.load_all_agents()
    assert len(agents) > 0

@pytest.mark.asyncio
async def test_message_sending():
    """测试消息发送"""
    # 测试网络消息发送功能
    pass

@pytest.mark.asyncio
async def test_master_agent_processing():
    """测试主智能体处理"""
    # 测试自然语言处理和任务委派
    pass
```

### 4.2 集成测试

__新增文件__：`tests/test_full_integration.py`

```python
@pytest.mark.asyncio
async def test_full_anp_integration():
    """完整的ANP集成测试"""
    # 1. 启动ANP服务器
    # 2. 加载智能体
    # 3. 测试网络通信
    # 4. 测试消息处理
    # 5. 测试API调用
    pass
```

## 实施时间表

### 第1周：基础设施

- [ ] 目录结构调整
- [ ] 依赖管理整合
- [ ] 配置系统集成

### 第2周：核心改造

- [ ] octopus.py ANP 集成
- [ ] BaseAgent 升级
- [ ] 智能体集成管理器

### 第3周：智能体升级

- [ ] MasterAgent ANP 化
- [ ] MessageAgent 网络能力集成
- [ ] TextProcessorAgent 升级

### 第4周：测试和优化

- [ ] 单元测试编写
- [ ] 集成测试
- [ ] 性能优化
- [ ] 文档更新

## 风险评估和缓解

### 风险1：配置复杂性

__缓解措施__：

- 创建配置迁移工具
- 提供详细的配置文档
- 保持向下兼容性

### 风险2：网络通信稳定性

__缓解措施__：

- 实现重试机制
- 添加连接状态监控
- 提供降级方案

### 风险3：性能影响

__缓解措施__：

- 保持ANP核心轻量
- 实现异步处理
- 添加性能监控

## 成功标准

1. __功能完整性__：所有现有功能正常工作
2. __网络通信__：支持跨网络智能体通信
3. __性能指标__：响应时间不超过原系统的150%
4. __稳定性__：7x24小时稳定运行
5. __可扩展性__：支持动态添加新智能体

## 后续规划

1. __Web UI 界面__：开发智能体管理界面
2. __更多智能体__：添加更多专业领域智能体
3. __分布式部署__：支持多节点部署
4. __监控系统__：完善监控和日志系统
5. __文档完善__：用户手册和开发文档

---

__注意__：此计划需要在实施过程中根据实际情况进行调整和优化。建议采用敏捷开发方式，分阶段实施并及时反馈调整。
