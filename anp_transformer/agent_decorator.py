# Copyright 2024 ANP Open SDK Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import functools
import logging
from typing import Optional, Dict, Any, Callable, Type, List

from anp_foundation.anp_user import ANPUser
from anp_foundation.anp_user_local_data import get_user_data_manager
from anp_transformer.agent_manager import AgentManager

logger = logging.getLogger(__name__)

# ===== DID 获取工具函数 =====

def get_user_by_name(name: str) -> str:
    """根据用户名获取 DID 字符串"""
    user_data_manager = get_user_data_manager()
    user_data = user_data_manager.get_user_data_by_name(name)
    if not user_data:
        raise ValueError(f"找不到名称为 '{name}' 的用户")
    return user_data.did

def get_first_available_user() -> str:
    """获取第一个可用用户的 DID"""
    user_data_manager = get_user_data_manager()
    all_users = user_data_manager.get_all_users()
    if not all_users:
        raise ValueError("系统中没有可用的用户")
    return all_users[0].did

def get_user_by_index(index: int = 0) -> str:
    """根据索引获取用户 DID"""
    user_data_manager = get_user_data_manager()
    all_users = user_data_manager.get_all_users()
    if not all_users:
        raise ValueError("系统中没有可用的用户")
    
    if index < 0 or index >= len(all_users):
        raise ValueError(f"索引 {index} 超出范围 (0-{len(all_users)-1})")
    
    return all_users[index].did

def list_available_users() -> List[Dict[str, str]]:
    """列出所有可用用户的信息"""
    user_data_manager = get_user_data_manager()
    all_users = user_data_manager.get_all_users()
    return [{"name": user.name, "did": user.did} for user in all_users]

# ===== 面向对象风格装饰器 =====

def agent_class(
    name: str,
    description: str = "",
    version: str = "1.0.0",
    tags: List[str] = None,  # 新增参数
    did: str = None,
    shared: bool = False,
    prefix: str = None,
    primary_agent: bool = False
):
    """
    Agent 类装饰器，用于创建和注册 Agent
    
    参数:
        name: Agent 名称
        description: Agent 描述
        version: Agent 版本
        did: 用户 DID 字符串，可以直接提供或通过辅助函数获取
        shared: 是否共享 DID
        prefix: API 路径前缀
        primary_agent: 是否为主 Agent
        
    Example:
        @agent_class(
            name="计算器Agent",
            did="did:wba:localhost%3A9527:wba:user:27c0b1d11180f973",
            shared=False
        )
        class CalculatorAgent:
            @api_method("/add")
            async def add_api(self, request_data, request):
                # 实现...
                pass
    """
    def decorator(cls):
        # 保存原始的 __init__ 方法
        original_init = cls.__init__
        
        @functools.wraps(original_init)
        def init_wrapper(self, *args, **kwargs):
            # 调用原始的 __init__
            original_init(self, *args, **kwargs)
            
            # 创建 agent 实例
            self._initialize_agent()
        
        # 替换 __init__ 方法
        cls.__init__ = init_wrapper
        
        # 添加 agent 初始化方法
        def _initialize_agent(self):
            # 获取 DID
            user_did = did
            if not user_did:
                # 如果没有提供 DID，使用第一个可用用户
                user_did = get_first_available_user()
            
            # 创建 ANPUser
            anp_user = ANPUser.from_did(user_did)
            
            # 创建 Agent
            self._agent = AgentManager.create_agent(
                anp_user=anp_user,
                name=name,
                shared=shared,
                prefix=prefix,
                primary_agent=primary_agent
            )

                        
            # 存储 tags 到实例
            self._tags = tags or []
            
            # 注册已定义的方法
            self._register_methods()
            
            logger.debug(f"✅ Agent '{name}' 已创建 (DID: {user_did})")
        
        # 添加方法注册
        def _register_methods(self):

            # 在方法开始就定义完整的 create_api_wrapper 函数
            def create_api_wrapper(method, is_class_method):
                @functools.wraps(method)
                async def api_wrapper(request_data, request):  # 🔧 只接受2个参数
                    # 🔧 优先检查是否需要实例绑定
                    if hasattr(method, '_needs_instance_binding') and method._needs_instance_binding:
                        logger.debug(f"🔧 调用需要实例绑定的方法: {method.__name__}")
                        bound_wrapper = method._create_bound_wrapper(self)
                        return await bound_wrapper(request_data, request)
                    elif hasattr(method, '_capability_meta') or hasattr(method, '_is_wrapped'):
                        logger.debug(f"🔧 调用已包装的方法: {method.__name__}")
                        return await method(self, request_data, request)
                    else:
                        logger.debug(f"🔧 调用未包装的方法: {method.__name__}")
                        if is_class_method:
                            import inspect
                            sig = inspect.signature(method)
                            param_names = list(sig.parameters.keys())
                            if param_names and param_names[0] == 'self':
                                param_names = param_names[1:]
                            
                            kwargs = {}
                            params = request_data.get('params', {})
                            for param_name in param_names:
                                if param_name in params:
                                    kwargs[param_name] = params[param_name]
                                elif param_name in request_data:
                                    kwargs[param_name] = request_data[param_name]
                            
                            logger.debug(f"🔧 调用类方法参数: {kwargs}")
                            return await method(self, **kwargs)
                        else:
                            return await method(request_data, request)
                return api_wrapper

            # 定义消息包装器函数
            def create_msg_wrapper(method):
                @functools.wraps(method)
                async def msg_wrapper(msg_data):  # 🔧 只接受1个参数
                    # 🔧 优先检查是否需要实例绑定（类似API的处理）
                    if hasattr(method, '_needs_instance_binding') and method._needs_instance_binding:
                        logger.debug(f"🔧 调用需要实例绑定的消息方法: {method.__name__}")
                        bound_wrapper = method._create_bound_wrapper(self)
                        return await bound_wrapper(msg_data)
                    elif hasattr(method, '_capability_meta') or hasattr(method, '_is_wrapped'):
                        logger.debug(f"🔧 调用已包装的消息方法: {method.__name__}")
                        return await method(msg_data)
                    else:
                        logger.debug(f"🔧 调用未包装的消息方法: {method.__name__}")
                        return await method(self, msg_data)

                return msg_wrapper
            
                # 定义事件包装器函数
            def create_event_wrapper(method):
                @functools.wraps(method)
                async def event_wrapper(group_id, event_type, event_data):  # 🔧 固定参数
                    if hasattr(method, '_capability_meta') or hasattr(method, '_is_wrapped'):
                        return await method(group_id=group_id, event_type=event_type, event_data=event_data)
                    else:
                        return await method(self, group_id, event_type, event_data)
                return event_wrapper
            
            # 查找所有标记了装饰器的方法
            for attr_name in dir(self):
                if attr_name.startswith('_'):
                    continue
                
                attr = getattr(self, attr_name)
                if hasattr(attr, '_api_path'):
                    # 注册 API
                    path = getattr(attr, '_api_path')
                    logger.debug(f"  - 注册 API: {path} -> {attr_name}")
                    
                    # 检查是否是类方法
                    is_class_method = getattr(attr, '_is_class_method', False)
                    
                    # 关键改进：检查是否需要实例绑定
                    if hasattr(attr, '_needs_instance_binding') and attr._needs_instance_binding:
                        logger.debug(f"🔧 创建实例绑定包装器: {attr_name}")
                        # 创建绑定到当前实例的包装器
                        bound_wrapper = attr._create_bound_wrapper(self)
                        # 注册绑定后的包装器
                        self._agent._api(path)(bound_wrapper)
                    else:
                        # 创建并注册包装函数
                        wrapped_handler = create_api_wrapper(attr, is_class_method)
                        self._agent._api(path)(wrapped_handler)
                    

                
                elif hasattr(attr, '_message_type'):
                    # 消息处理器的处理...
                    msg_type = getattr(attr, '_message_type')
                    logger.debug(f"  - 注册消息处理器: {msg_type} -> {attr_name}")

                    # 🔧 检查是否需要实例绑定（类似API的处理）
                    if hasattr(attr, '_needs_instance_binding') and attr._needs_instance_binding:
                        logger.debug(f"🔧 创建实例绑定消息包装器: {attr_name}")
                        # 创建绑定到当前实例的包装器
                        bound_wrapper = attr._create_bound_wrapper(self)
                        # 注册绑定后的包装器
                        self._agent._message_handler(msg_type)(bound_wrapper)
                    else:
                        # 创建并注册包装函数
                        wrapped_handler = create_msg_wrapper(attr)
                        self._agent._message_handler(msg_type)(wrapped_handler)
                
                # 检查是否有群组事件信息
                elif hasattr(attr, '_group_event_info'):
                    # 群组事件处理器的处理...
                    group_info = getattr(attr, '_group_event_info')
                    group_id = group_info.get('group_id')
                    event_type = group_info.get('event_type')
                    logger.debug(f"  - 注册群组事件处理器: {group_id or 'all'}/{event_type or 'all'} -> {attr_name}")
                    
                    wrapped_handler = create_event_wrapper(attr)
                    self._agent._group_event_handler(group_id, event_type)(wrapped_handler)
        # 添加属性访问器
        def get_agent(self):
            return self._agent
        
        # 将方法绑定到类
        cls._initialize_agent = _initialize_agent
        cls._register_methods = _register_methods
        cls.agent = property(get_agent)
        
        return cls
    
    return decorator

def class_api(path, methods=None, description=None,parameters=None, returns=None, auto_wrap=True):
    """类方法API装饰器（原api_method的增强版）
    
    Args:
        path: API路径
        methods: HTTP方法列表，默认为["GET", "POST"]
        description: API描述
        parameters: 参数定义字典
        returns: 返回值类型描述
        auto_wrap: 是否自动应用wrap_business_handler
        
    Example:
        @class_api("/add")
        async def add_api(self, a: float, b: float):
            return {"result": a + b}
        
        @class_api(
            "/coordinate",
            parameters={
                "request": {"type": "string", "description": "Natural language request or task"},
                "request_id": {"type": "string", "description": "Unique identifier for this request"}
            },
            returns="string"
        )
        async def coordinate_api(self, request: str, request_id: str):
            return "Task coordinated successfully"
    """
    def decorator(method):
        # 设置API路径
        setattr(method, '_api_path', path)
        setattr(method, '_is_class_method',True)

        # 设置能力元数据
        capability_meta = {
            'name': method.__name__,
            'description': description or method.__doc__ or f"API: {path}",
            'publish_as': "expose_api",
            'parameters': parameters or {},  # 新增
            'returns': returns or "object"   # 新增
        }
        setattr(method, '_capability_meta', capability_meta)

        # 如果需要自动包装，应用wrap_business_handler
        if auto_wrap:
            from anp_transformer.anp_service.anp_tool import wrap_business_handler
            
            # 🔧 修复：返回一个可以直接调用的函数，而不是实例方法
            def create_bound_wrapper(instance):
                # 创建绑定到特定实例的方法
                # 只负责绑定self，保持标准接口
                def bound_method(request_data, request):
                    return method(instance, request_data, request)
                
                # 保存原始方法信息，供 wrap_business_handler 使用
                bound_method._original_method = method
                bound_method._bound_instance = instance
                wrapped = wrap_business_handler(bound_method)

                # 复制原始方法的属性到包装后的方法
                wrapped._is_class_method = True
                if hasattr(method, '_capability_meta'):
                    wrapped._capability_meta = method._capability_meta
                if hasattr(method, '_api_path'):
                    wrapped._api_path = method._api_path
                    
                return wrapped

            # 设置特殊标记，表示需要实例绑定
            setattr(method, '_needs_instance_binding', True)
            setattr(method, '_create_bound_wrapper', create_bound_wrapper)
            setattr(method, '_is_wrapped', True)
            
            return method

        return method
    return decorator

def class_message_handler(msg_type, description=None, auto_wrap=True):
    """类方法消息处理器装饰器（原message_method的增强版）
    
    Args:
        msg_type: 消息类型
        description: 处理器描述
        auto_wrap: 是否自动应用wrap_business_handler
        
    Example:
        @class_message_handler("text")
        async def handle_text(self, content: str, sender_id: str = None):
            return {"reply": f"收到消息: {content}"}
    """
    def decorator(method):
        # 设置消息类型
        setattr(method, '_message_type', msg_type)
        
        # 设置能力元数据（如果提供了描述）
        if description:
            capability_meta = {
                'name': method.__name__,
                'description': description or method.__doc__ or f"消息处理器: {msg_type}",
                'publish_as': "message_handler"
            }
            setattr(method, '_capability_meta', capability_meta)

        # 如果需要自动包装，应用wrap_business_handler
        if auto_wrap:
            def create_bound_wrapper(instance):
                async def bound_method(msg_data):
                    return await method(instance, msg_data)

                # 🔧 不使用 wrap_business_handler，直接返回绑定方法
                return bound_method

            setattr(method, '_needs_instance_binding', True)
            setattr(method, '_create_bound_wrapper', create_bound_wrapper)
            setattr(method, '_is_wrapped', True)

            return method
        return method
    return decorator



def group_event_method(group_id=None, event_type=None):
    """群组事件处理器装饰器，用于标记类方法为群组事件处理函数
    
    Args:
        group_id: 群组ID，如果为None则处理所有群组
        event_type: 事件类型，如果为None则处理所有类型
        
    Example:
        @group_event_method(group_id="group1", event_type="join")
        async def handle_join(self, group_id, event_type, event_data):
            return {"status": "success"}
    """
    def decorator(method):
        setattr(method, '_group_event_info', {
            'group_id': group_id,
            'event_type': event_type
        })
        return method
    return decorator

# ===== 函数式风格工厂函数 =====

def create_agent(did_str: str, name: str, shared: bool = False, prefix: Optional[str] = None, primary_agent: bool = True):
    """从DID字符串创建Agent实例
    
    Args:
        did_str: DID字符串
        name: Agent名称
        shared: 是否共享DID
        prefix: 共享模式下的API前缀
        primary_agent: 是否为主Agent
        
    Returns:
        Agent实例
        
    Example:
        agent = create_agent(
            "did:wba:localhost%3A9527:wba:user:27c0b1d11180f973",
            "计算器Agent"
        )
        
        @agent.api("/add")
        async def add_api(request_data, request):
            return {"result": 42}
    """
    anp_user = ANPUser.from_did(did_str)
    return AgentManager.create_agent(
        anp_user=anp_user,
        name=name,
        shared=shared,
        prefix=prefix,
        primary_agent=primary_agent
    )

def create_agent_from_name(user_name: str, agent_name: str, shared: bool = False, prefix: Optional[str] = None, primary_agent: bool = True):
    """从用户名创建Agent实例
    
    Args:
        user_name: 用户名
        agent_name: Agent名称
        shared: 是否共享DID
        prefix: 共享模式下的API前缀
        primary_agent: 是否为主Agent
        
    Returns:
        Agent实例
        
    Example:
        agent = create_agent_from_name(
            "calculator_user",
            "计算器Agent"
        )
    """
    did_str = get_user_by_name(user_name)
    return create_agent(did_str, agent_name, shared, prefix, primary_agent)

def create_shared_agent(did_str: str, name: str, prefix: str, primary_agent: bool = False):
    """创建共享DID的Agent实例
    
    Args:
        did_str: DID字符串
        name: Agent名称
        prefix: API路径前缀
        primary_agent: 是否为主Agent
        
    Returns:
        Agent实例
        
    Example:
        assistant_agent = create_shared_agent(
            "did:wba:localhost%3A9527:wba:user:5fea49e183c6c211",
            "助手Agent",
            "/assistant"
        )
    """
    return create_agent(did_str, name, shared=True, prefix=prefix, primary_agent=primary_agent)

# ===== 函数式风格装饰器适配函数 =====
# 函数式风格 - 更名并增强
def agent_api(agent, path, methods=None, description=None, auto_wrap=True):
    """函数式API装饰器（原register_api的增强版）
    
    Args:
        agent: Agent实例
        path: API路径
        methods: HTTP方法列表，默认为["GET", "POST"]
        description: API描述
        auto_wrap: 是否自动应用wrap_business_handler
        
    Example:
        @agent_api(agent, "/add")
        async def add_handler(a: float, b: float):
            return {"result": a + b}
    """
    def decorator(func):
        # 设置能力元数据（如果提供了描述）
        if description:
            capability_meta = {
                'name': func.__name__,
                'description': description or func.__doc__ or f"API: {path}",
                'publish_as': "expose_api"
            }
            setattr(func, '_capability_meta', capability_meta)
        
        # 如果需要自动包装，应用wrap_business_handler
        if auto_wrap:
            from anp_transformer.anp_service.anp_tool import wrap_business_handler
            wrapped_func = wrap_business_handler(func)
        else:
            wrapped_func = func
        
        # 使用agent.api注册
        return agent._api(path, methods)(wrapped_func)
    
    return decorator

def agent_message_handler(agent, msg_type, description=None, auto_wrap=True):
    """函数式消息处理器装饰器（原register_message_handler的增强版）
    
    Args:
        agent: Agent实例
        msg_type: 消息类型
        description: 处理器描述
        auto_wrap: 是否自动应用wrap_business_handler
        
    Example:
        @agent_message_handler(agent, "text")
        async def handle_text(content: str, sender_id: str = None):
            return {"reply": f"收到消息: {content}"}
    """
    def decorator(func):
        # 设置能力元数据（如果提供了描述）
        if description:
            capability_meta = {
                'name': func.__name__,
                'description': description or func.__doc__ or f"消息处理器: {msg_type}",
                'publish_as': "message_handler"
            }
            setattr(func, '_capability_meta', capability_meta)
        
        # 如果需要自动包装，应用wrap_business_handler
        if auto_wrap:
            from anp_transformer.anp_service.anp_tool import wrap_business_handler
            wrapped_func = wrap_business_handler(func)
        else:
            wrapped_func = func
        
        # 使用agent.message_handler注册
        return agent._message_handler(msg_type)(wrapped_func)
    
    return decorator


def register_group_event_handler(agent_instance, group_id=None, event_type=None):
    """
    为指定的Agent实例注册群组事件处理函数
    
    Args:
        agent_instance: Agent实例
        group_id: 群组ID
        event_type: 事件类型
    
    Returns:
        装饰器函数
        
    Example:
        @register_group_event_handler(agent, "group1", "join")
        async def join_handler(group_id, event_type, event_data):
            return {"status": "success"}
    """
    return agent_instance._group_event_handler(group_id, event_type)




def class_capability(
    name=None, 
    description=None, 
    input_schema=None,
    output_schema=None,
    tags=None,
    publish_as="api",  # "api", "message", "group_event", "local_method", "multiple"
    path=None,
    msg_type=None,
    group_id=None,
    event_type=None,
    auto_wrap=True
):
    """类方法能力装饰器
    
    Args:
        name: 能力名称，默认使用方法名
        description: 能力描述，默认使用方法文档
        input_schema: 输入参数的JSON Schema
        output_schema: 输出结果的JSON Schema
        tags: 标签列表
        publish_as: 发布方式（api/message/group_event/local_method/multiple）
        path: API路径（当publish_as为api或multiple时使用）
        msg_type: 消息类型（当publish_as为message或multiple时使用）
        group_id: 群组ID（当publish_as为group_event或multiple时使用）
        event_type: 事件类型（当publish_as为group_event或multiple时使用）
        auto_wrap: 是否自动应用wrap_business_handler
        
    Example:
        @class_capability(
            name="天气查询",
            description="查询指定城市的天气信息",
            publish_as="api",
            path="/weather"
        )
        async def query_weather(self, city: str = "北京"):
            return {"temperature": "22°C", "condition": "晴天"}
    """
    def decorator(method):
        # 设置能力元数据
        capability_meta = {
            'name': name or method.__name__,
            'description': description or method.__doc__ or f"能力: {name or method.__name__}",
            'input_schema': input_schema or {},
            'output_schema': output_schema or {},
            'tags': tags or [],
            'publish_as': publish_as
        }
        setattr(method, '_capability_meta', capability_meta)
        
        # 根据发布方式设置额外属性
        if publish_as in ["api", "multiple"] and path:
            setattr(method, '_api_path', path)
        
        if publish_as in ["message", "multiple"] and msg_type:
            setattr(method, '_message_type', msg_type)
        
        if publish_as in ["group_event", "multiple"]:
            setattr(method, '_group_event_info', {
                'group_id': group_id,
                'event_type': event_type
            })
        
        # 如果需要自动包装，应用wrap_business_handler
        if auto_wrap:
            from anp_transformer.anp_service.anp_tool import wrap_business_handler
            
            @functools.wraps(method)
            async def wrapped_method(self, *args, **kwargs):
                # 调用wrap_business_handler并传入self
                wrapped_func = wrap_business_handler(lambda **kw: method(self, **kw))
                return await wrapped_func(*args, **kwargs)
            
            # 复制元数据到包装方法
            for attr_name in ['_capability_meta', '_api_path', '_message_type', '_group_event_info']:
                if hasattr(method, attr_name):
                    setattr(wrapped_method, attr_name, getattr(method, attr_name))
            
            return wrapped_method
        
        return method
    
    return decorator

def agent_capability(
    agent,
    name=None, 
    description=None, 
    input_schema=None,
    output_schema=None,
    tags=None,
    publish_as="api",  # "api", "message", "group_event", "local_method", "multiple"
    path=None,
    msg_type=None,
    group_id=None,
    event_type=None,
    auto_wrap=True
):
    """函数式能力装饰器
    
    Args:
        agent: Agent实例
        name: 能力名称，默认使用函数名
        description: 能力描述，默认使用函数文档
        input_schema: 输入参数的JSON Schema
        output_schema: 输出结果的JSON Schema
        tags: 标签列表
        publish_as: 发布方式（api/message/group_event/local_method/multiple）
        path: API路径（当publish_as为api或multiple时使用）
        msg_type: 消息类型（当publish_as为message或multiple时使用）
        group_id: 群组ID（当publish_as为group_event或multiple时使用）
        event_type: 事件类型（当publish_as为group_event或multiple时使用）
        auto_wrap: 是否自动应用wrap_business_handler
        
    Example:
        @agent_capability(
            agent,
            name="天气查询",
            description="查询指定城市的天气信息",
            publish_as="api",
            path="/weather"
        )
        async def query_weather(city: str = "北京"):
            return {"temperature": "22°C", "condition": "晴天"}
    """
    def decorator(func):
        # 设置能力元数据
        capability_meta = {
            'name': name or func.__name__,
            'description': description or func.__doc__ or f"能力: {name or func.__name__}",
            'input_schema': input_schema or {},
            'output_schema': output_schema or {},
            'tags': tags or [],
            'publish_as': publish_as
        }
        setattr(func, '_capability_meta', capability_meta)
        
        # 如果需要自动包装，应用wrap_business_handler
        if auto_wrap:
            from anp_transformer.anp_service.anp_tool import wrap_business_handler
            wrapped_func = wrap_business_handler(func)
        else:
            wrapped_func = func
        
        # 复制元数据到包装函数
        setattr(wrapped_func, '_capability_meta', capability_meta)
        
        # 根据发布方式注册
        if publish_as in ["api", "multiple"] and path:
            agent._api(path)(wrapped_func)
            
        if publish_as in ["message", "multiple"] and msg_type:
            agent._message_handler(msg_type)(wrapped_func)
            
        if publish_as in ["group_event", "multiple"]:
            agent._group_event_handler(group_id, event_type)(wrapped_func)
        
        return wrapped_func
    
    return decorator