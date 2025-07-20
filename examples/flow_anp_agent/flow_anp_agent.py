import glob
import json
import os
import sys
import asyncio
import threading


# 添加路径以便导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anp_transformer.anp_service.agent_api_call import agent_api_call_post
from anp_transformer.anp_service.agent_message_p2p import agent_msg_post


from anp_foundation.config import UnifiedConfig, set_global_config, get_global_config
from anp_foundation.utils.log_base import setup_logging
import logging
app_config = UnifiedConfig(config_file='unified_config_framework_demo.yaml')
set_global_config(app_config)
setup_logging()
logger = logging.getLogger(__name__)

from anp_workbench_server.baseline.anp_server_baseline import ANP_Server


# 导入新的Agent系统
from anp_transformer.agent_manager import AgentManager, LocalAgentManager
from anp_transformer.global_router_agent_api import GlobalRouter
from anp_transformer.global_router_agent_message import GlobalMessageManager

from anp_transformer.local_service.local_methods_doc import LocalMethodsDocGenerator




async def create_agents_with_cfg_path():
    """使用新的Agent系统创建Agent"""
    logger.debug("🔧 使用新Agent系统创建Agent...")
    
    # 清理之前的状态
    AgentManager.clear_all_agents()
    GlobalRouter.clear_routes()
    GlobalMessageManager.clear_handlers()
    
    created_agents = []
    lifecycle_modules = {}
    shared_did_configs = {}

    # 1. 加载现有的Agent配置文件
    agent_files = glob.glob("data_user/localhost_9527/agents_config/*/agent_mappings.yaml")
    if not agent_files:
        logger.warning("未找到Agent配置文件，将创建代码生成的Agent")
    
    # 2. 使用现有配置创建Agent
    for agent_file in agent_files:
        try:
            anp_agent, handler_module, share_did_config = await LocalAgentManager.load_agent_from_module(agent_file)
            if anp_agent:
                created_agents.append(anp_agent)
            if handler_module:
                lifecycle_modules[anp_agent.name] = handler_module
            if share_did_config:
                shared_did_configs[anp_agent.name] = share_did_config
        except PermissionError as e:
            if "共享DID模式下，只有主Agent可以处理消息" in str(e):
                logger.info(f"ℹ️ 预期行为: {agent_file} - {e}")
                # 不要尝试重新加载Agent，直接继续使用已经创建的Agent
                # Agent已经创建成功，只是消息处理器注册失败了
                # 这里不需要做任何事情，因为Agent已经在created_agents中
            else:
                logger.error(f"❌ 转换Agent失败 {agent_file}: {e}")
        except Exception as e:
            logger.error(f"❌ 转换Agent失败 {agent_file}: {e}")

    return created_agents,lifecycle_modules,shared_did_configs


async def create_agents_with_code():
    """创建代码生成的Agent"""
    logger.debug("🤖 创建代码生成的Agent...")

    # 导入新的装饰器和函数
    from anp_transformer.agent_decorator import (
        agent_class, class_api, class_message_handler, agent_api, create_shared_agent
    )
        
    code_agents = []
    
    try:
        # 使用装饰器创建计算器Agent
        @agent_class(
            name="代码生成计算器",
            description="提供基本的计算功能",
            did="did:wba:localhost%3A9527:wba:user:27c0b1d11180f973",
            shared=False
        )
        class CalculatorAgent:
            @class_api("/add",auto_wrap=True)
            async def add_api(self, request_data, request):
                """加法计算API"""
                # 从params中获取参数
                params = request_data.get('params', {})
                a = params.get('a', 0)
                b = params.get('b', 0)
                result = a + b
                logger.debug(f"🔢 计算: {a} + {b} = {result}")
                return {"result": result, "operation": "add", "inputs": [a, b]}
            
            @class_api("/multiply")
            async def multiply_api(self, request_data, request):
                """乘法计算API"""
                # 从params中获取参数
                params = request_data.get('params', {})
                a = params.get('a', 1)
                b = params.get('b', 1)
                result = a * b
                logger.debug(f"🔢 计算: {a} × {b} = {result}")
                return {"result": result, "operation": "multiply", "inputs": [a, b]}
            
            @class_message_handler("text")
            async def handle_calc_message(self, msg_data):
                content = msg_data.get('content', '')
                logger.debug(f"💬 代码生成计算器收到消息: {content}")
                
                # 简单的计算解析
                if '+' in content:
                    try:
                        parts = content.split('+')
                        if len(parts) == 2:
                            a = float(parts[0].strip())
                            b = float(parts[1].strip())
                            result = a + b
                            return {"reply": f"计算结果: {a} + {b} = {result}"}
                    except:
                        pass
                
                return {"reply": f"代码生成计算器收到: {content}。支持格式如 '5 + 3'"}
        
        # 实例化计算器Agent
        calc_agent = CalculatorAgent().agent
        code_agents.append(calc_agent)
        logger.debug("✅ 创建代码生成计算器Agent成功")
        
        # 使用装饰器创建天气Agent
        @agent_class(
            name="代码生成天气",
            description="提供天气信息服务",
            did="did:wba:localhost%3A9527:wba:user:5fea49e183c6c211",
            shared=True,
            prefix="/weather",
            primary_agent=True
        )
        class WeatherAgent:
            @class_api("/current")
            async def weather_current_api(self, request_data, request):
                """获取当前天气API"""
                # 从params中获取参数
                params = request_data.get('params', {})
                city = params.get('city', '北京')
                # 模拟天气数据
                weather_data = {
                    "city": city,
                    "temperature": "22°C",
                    "condition": "晴天",
                    "humidity": "65%",
                    "wind": "微风"
                }
                logger.debug(f"🌤️ 查询天气: {city} - {weather_data['condition']}")
                return weather_data
            
            @class_api("/forecast")
            async def weather_forecast_api(self, request_data, request):
                """获取天气预报API"""
                # 从params中获取参数
                params = request_data.get('params', {})
                city = params.get('city', '北京')
                days = params.get('days', 3)
                
                forecast = []
                conditions = ["晴天", "多云", "小雨"]
                for i in range(days):
                    forecast.append({
                        "date": f"2024-01-{15+i:02d}",
                        "condition": conditions[i % len(conditions)],
                        "high": f"{20+i}°C",
                        "low": f"{10+i}°C"
                    })
                
                result = {"city": city, "forecast": forecast}
                logger.debug(f"🌤️ 查询{days}天预报: {city}")
                return result
            
            @class_message_handler("text")
            async def handle_weather_message(self, msg_data):
                content = msg_data.get('content', '')
                logger.debug(f"💬 代码生成天气Agent收到消息: {content}")
                
                if '天气' in content:
                    return {"reply": f"天气查询服务已收到: {content}。可以查询任何城市的天气信息。"}
                
                return {"reply": f"代码生成天气Agent收到: {content}"}
        
        # 实例化天气Agent
        weather_agent = WeatherAgent().agent
        code_agents.append(weather_agent)
        logger.debug("✅ 创建代码生成天气Agent成功")
        
        # 使用函数式方法创建助手Agent（共享DID，非主Agent）
        assistant_agent = create_shared_agent(
            did_str="did:wba:localhost%3A9527:wba:user:5fea49e183c6c211",  # 使用相同的DID
            name="代码生成助手",
            prefix="/assistant",
            primary_agent=False
        )

        # 注册API
        @agent_api(assistant_agent,"/help")
        async def help_api(request_data, request):
            """帮助信息API"""
            # 从params中获取参数
            params = request_data.get('params', {})
            topic = params.get('topic', 'general')
            
            help_info = {
                "general": "我是代码生成助手，可以提供各种帮助信息",
                "weather": "天气相关帮助：使用 /weather/current 查询当前天气",
                "calc": "计算相关帮助：使用 /add 或 /multiply 进行计算"
            }
            
            response = {
                "topic": topic,
                "help": help_info.get(topic, help_info["general"]),
                "available_topics": list(help_info.keys())
            }
            
            logger.debug(f"❓ 提供帮助: {topic}")
            return response

        code_agents.append(assistant_agent)
        logger.debug("✅ 创建代码生成助手Agent成功")



        
        
    except Exception as e:
        logger.error(f"❌ 创建代码生成Agent失败: {e}")
        import traceback
        traceback.print_exc()
    
    return code_agents




async def main():
    logger.debug("🚀 Starting Agent System Demo...")
    if os.getcwd() not in sys.path:
        sys.path.append(os.getcwd())
    config = get_global_config()

    # 清除之前的Agent注册记录，初始化路由
    AgentManager.clear_all_agents()
    AgentManager.initialize_router()
    logger.debug("🧹 已清除之前的Agent注册记录")
    # 初始化三个列表 agent列表 需要init和clean的agent 共享did的agent
    all_agents = []
    lifecycle_agents = {}
    shared_did_configs = {}

    # 从配置目录动态加载Agent
    all_agents,lifecycle_agents,shared_did_configs = await create_agents_with_cfg_path()
    # --- 后期初始化循环 ---
    for agent in all_agents:
        module = lifecycle_agents.get(agent.name)
        if module and hasattr(module, "initialize_agent"):
            logger.debug(f"  - 调用 initialize_agent: {agent.name}...")
            await module.initialize_agent(agent)  # 传入agent实例
    # 用代码直接生成Agent
    code_generated_agents = await create_agents_with_code()
    all_agents.extend(code_generated_agents)
    # 生成接口文档
    processed_dids = set()  # 用于跟踪已处理的 DID
    for agent in all_agents:
        if hasattr(agent, 'anp_user'):
            did = agent.anp_user_id
            if did not in processed_dids:
                await LocalAgentManager.generate_and_save_agent_interfaces(agent)
                processed_dids.add(did)
                logger.debug(f"✅ 为 DID '{did}' 生成接口文档")
    if not all_agents:
        logger.debug("No agents were created. Exiting.")
        return
    # 生成本地方法文档
    script_dir = os.path.dirname(os.path.abspath(__file__))
    doc_path = os.path.join(script_dir, "local_methods_doc.json")
    LocalMethodsDocGenerator.generate_methods_doc(doc_path)


    # --- 启动SDK ---
    logger.debug("\n✅ All agents created with new system. Creating SDK instance...")
    svr = ANP_Server()
    host = config.anp_sdk.host
    port = config.anp_sdk.port
    logger.debug(f"⏳ 等待服务器启动 {host}:{port} ...")
    await launch_anp_server(host, port,svr)
    logger.debug("✅ 服务器就绪，开始执行任务。")


    # 显示Agent管理器状态
    logger.debug("\n📊 Agent管理器状态:")
    agents_info = AgentManager.list_agents()
    for did, agent_dict in agents_info.items():
        logger.debug(f"  DID: {did}共有{len(agent_dict)}个agent")
        for agent_name, agent_info in agent_dict.items():
            mode = "共享" if agent_info['shared'] else "独占"
            primary = " (主)" if agent_info.get('primary_agent') else ""
            prefix = f" prefix:{agent_info['prefix']}" if agent_info['prefix'] else ""
            logger.debug(f"    - {agent_name}: {mode}{primary}{prefix}")


    # 显示全局路由器状态
    logger.debug("\n🔗 全局路由器状态:")
    routes = GlobalRouter.list_routes()
    for route in routes:
        logger.debug(f"  🔗 {route['did']}{route['path']} <- {route['agent_name']}")

    # 显示全局消息管理器状态
    logger.debug("\n💬 全局消息管理器状态:")
    handlers = GlobalMessageManager.list_handlers()
    for handler in handlers:
        logger.debug(f"  💬 {handler['did']}:{handler['msg_type']} <- {handler['agent_name']}")

    # 调试：检查API路由
    logger.debug("\n🔍 调试：检查Agent的API路由注册情况...")
    for agent in all_agents:
        if hasattr(agent, 'anp_user'):
            logger.debug(f"Agent: {agent.name}")
            logger.debug(f"  DID: {agent.anp_user_id}")
            logger.debug(f"  API路由数量: {len(agent.anp_user.api_routes)}")
            for path, handler in agent.anp_user.api_routes.items():
                handler_name = handler.__name__ if hasattr(handler, '__name__') else 'unknown'
                logger.debug(f"    - {path}: {handler_name}")

    # 测试新Agent系统功能
    await test_new_agent_system(all_agents)

    await test_discovery_agent(all_agents,svr)

    input("\n🔥 Demo completed. Press anykey to stop.")

    await stop_server(svr, all_agents, lifecycle_agents)


async def test_discovery_agent(all_agents,svr):
    logger.debug("\n🔍 Searching for an agent with discovery capabilities...")
    discovery_agent = None
    for agent in all_agents:
        if hasattr(agent, 'discover_and_describe_agents'):
            discovery_agent = agent
            break
    if discovery_agent:
        logger.debug(f"✅ Found discovery agent: '{discovery_agent.name}'. Starting its discovery task...")
        # 直接调用 agent 实例上的方法
        publisher_url = "http://localhost:9527/publisher/agents"
        # agent中的自动抓取函数，自动从主地址搜寻所有did/ad/yaml文档
        # result = await discovery_agent.discover_and_describe_agents(publisher_url)
        # agent中的联网调用函数，调用计算器
        result = await discovery_agent.run_calculator_add_demo()
        # agent中的联网调用函数，相当于发送消息
        # result = await discovery_agent.run_hello_demo()
        # agent中的AI联网爬取函数，从一个did地址开始爬取
        # result = await discovery_agent.run_ai_crawler_demo()
        # agent中的AI联网爬取函数，从多个did汇总地址开始爬取
        # result = await discovery_agent.run_ai_root_crawler_demo()
        # agent中的本地api去调用另一个agent的本地api
        result = await discovery_agent.run_agent_002_demo()
        # agent中的本地api通过搜索本地api注册表去调用另一个agent的本地api
        result = await discovery_agent.run_agent_002_demo_new()

    else:
        logger.debug("⚠️ No agent with discovery capabilities was found.")


async def launch_anp_server(host, port,svr):
    # 用线程启动 anp_servicepoint
    def run_server():
        svr.start_server()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    import time
    import socket
    def wait_for_port(host, port, timeout=10.0):
        start = time.time()
        while time.time() - start < timeout:
            try:
                with socket.create_connection((host, port), timeout=1):
                    return True
            except (OSError, ConnectionRefusedError):
                time.sleep(0.2)
        raise RuntimeError(f"Server on {host}:{port} did not start within {timeout} seconds")

    wait_for_port(host, port, timeout=15)


async def test_new_agent_system(agents):
    """测试新Agent系统的功能"""
    logger.debug("\n🧪 开始测试新Agent系统功能...")
    
    # 找到不同类型的Agent
    calc_agent = None
    weather_agent = None
    assistant_agent = None
    llm_agent = None
    discovery_agent = None
    
    for agent in agents:
        if "计算器" in agent.name:
            calc_agent = agent
        elif "天气" in agent.name:
            weather_agent = agent
        elif "助手" in agent.name:
            assistant_agent = agent
        elif "llm" in agent.name.lower() or "language" in agent.name.lower():
            llm_agent = agent
        elif hasattr(agent.anp_user, 'discover_and_describe_agents'):
            discovery_agent = agent
    
    # 基础测试
    logger.debug("\n🔍 基础功能测试...")
    
    # 测试1: 计算器API调用
    calc_api_success = False
    if calc_agent:
        logger.info(f"\n🔧 测试计算器Agent API调用...")
        try:
            # 模拟API调用
            calc_did = calc_agent.anp_user_id if hasattr(calc_agent, 'anp_user') else calc_agent.did
            result = await agent_api_call_post(
                caller_agent="did:wba:localhost%3A9527:wba:user:e0959abab6fc3c3d",
                target_agent=calc_did,
                api_path="/add",
                params={"a": 15, "b": 25}
            )
            logger.info(f"✅ 计算器API调用成功: {result}")
            calc_api_success = True
        except Exception as e:
            logger.info(f"❌ 计算器API调用失败: {e}")
    
    # 测试2: 消息发送
    msg_success = False
    if weather_agent:
        logger.info(f"\n📨 测试天气Agent消息发送...")
        try:
            weather_did = weather_agent.anp_user_id if hasattr(weather_agent, 'anp_user') else weather_agent.did
            result = await agent_msg_post(
                caller_agent="did:wba:localhost%3A9527:wba:user:e0959abab6fc3c3d",
                target_agent=weather_did,
                content="请问今天北京的天气怎么样？",
                message_type="text"
            )
            logger.info(f"✅ 天气Agent消息发送成功: {result}")
            msg_success = True
        except Exception as e:
            logger.info(f"❌ 天气Agent消息发送失败: {e}")
    
    # === 共享DID功能测试 ===
    logger.debug(f"\n🧪 开始共享DID功能测试...")
    
    # 测试3: 共享DID API调用
    shared_api_success = False
    if weather_agent and assistant_agent:
        logger.info(f"\n🔗 测试共享DID API调用...")
        try:
            # 调用天气API
            weather_did = weather_agent.anp_user_id if hasattr(weather_agent, 'anp_user') else weather_agent.did
            weather_result = await agent_api_call_post(
                caller_agent="did:wba:localhost%3A9527:wba:user:e0959abab6fc3c3d",
                target_agent=weather_did,
                api_path="/weather/current",
                params={"city": "上海"}
            )
            logger.info(f"✅ 天气API调用成功: {weather_result}")
            
            # 调用助手API
            assistant_did = assistant_agent.anp_user_id if hasattr(assistant_agent, 'anp_user') else assistant_agent.did
            help_result = await agent_api_call_post(
                caller_agent="did:wba:localhost%3A9527:wba:user:e0959abab6fc3c3d",
                target_agent=assistant_did,
                api_path="/assistant/help",
                params={"topic": "weather"}
            )
            logger.info(f"✅ 助手API调用成功: {help_result}")
            shared_api_success = True
            
        except Exception as e:
            logger.info(f"❌ 共享DID API调用失败: {e}")
    
    # 测试4: 冲突检测
    conflict_test_success = False
    logger.info(f"\n⚠️  测试冲突检测...")
    try:
        # 尝试创建冲突的Agent
        from anp_foundation.anp_user import ANPUser
        test_user = ANPUser.from_did("did:wba:localhost%3A9527:wba:user:3ea884878ea5fbb1")
        
        # 这应该失败，因为DID已被独占使用
        conflict_agent = AgentManager.create_agent(test_user, "冲突测试Agent", shared=False)
        logger.error("❌ 冲突检测失败：应该阻止创建冲突Agent")
        
    except ValueError as e:
        logger.info(f"✅ 冲突检测成功: {e}")
        conflict_test_success = True
    except Exception as e:
        logger.info(f"❌ 冲突检测异常: {e}")
    
    # === 从framework_demo.py移植的测试 ===
    
    # 测试5: Calculator共享DID API调用
    logger.debug(f"\n🔧 测试Calculator共享DID API调用...")
    calc_api_success = await test_shared_did_api()
    
    # 测试6: LLM共享DID API调用
    logger.debug(f"\n🤖 测试LLM共享DID API调用...")
    llm_api_success = await test_llm_shared_did_api()
    
    # 测试7: 共享DID消息发送
    logger.debug(f"\n📨 测试共享DID消息发送...")
    msg_success = await test_message_sending()
    
    # 测试结果总结
    logger.debug(f"\n📊 共享DID测试结果总结:")
    logger.info(f"  🔧 Calculator共享DID API: {'✅ 成功' if calc_api_success else '❌ 失败'}")
    logger.info(f"  🤖 LLM共享DID API: {'✅ 成功' if llm_api_success else '❌ 失败'}")
    logger.info(f"  📨 共享DID消息发送: {'✅ 成功' if msg_success else '❌ 失败'}")
    logger.info(f"  🔗 共享DID API调用: {'✅ 成功' if shared_api_success else '❌ 失败'}")
    logger.info(f"  ⚠️  冲突检测: {'✅ 成功' if conflict_test_success else '❌ 失败'}")
    
    success_count = sum([calc_api_success, llm_api_success, msg_success, shared_api_success, conflict_test_success])
    total_count = 5
    
    if success_count == total_count:
        logger.info(f"\n🎉 所有共享DID测试通过! ({success_count}/{total_count}) 架构重构验证成功!")
    else:
        logger.info(f"\n⚠️  部分共享DID测试失败 ({success_count}/{total_count})，需要进一步调试")
    
    logger.debug(f"\n🎉 新Agent系统测试完成!")


async def test_shared_did_api():
    """测试共享DID的API调用"""
    logger.info("\n🧪 测试共享DID API调用...")

    # 测试参数
    caller_agent = "did:wba:localhost%3A9527:wba:user:e0959abab6fc3c3d"  # Orchestrator Agent
    target_agent = "did:wba:localhost%3A9527:wba:user:28cddee0fade0258"  # 共享DID
    api_path = "/calculator/add"  # 共享DID路径
    params = {"a": 10, "b": 20}

    try:
        logger.info(f"📞 调用API: {target_agent}{api_path}")
        logger.info(f"📊 参数: {params}")

        # 调用API
        result = await agent_api_call_post(
            caller_agent=caller_agent,
            target_agent=target_agent,
            api_path=api_path,
            params=params
        )

        logger.info(f"✅ API调用成功!")
        logger.info(f"📋 响应: {json.dumps(result, ensure_ascii=False, indent=2)}")

        # 验证结果
        if isinstance(result, dict) and "result" in result:
            expected_result = 30  # 10 + 20
            actual_result = result["result"]
            if actual_result == expected_result:
                logger.info(f"🎉 计算结果正确: {actual_result}")
                return True
            else:
                logger.info(f"❌ 计算结果错误: 期望 {expected_result}, 实际 {actual_result}")
                return False
        else:
            logger.info(f"❌ 响应格式不正确: {result}")
            return False

    except Exception as e:
        logger.info(f"❌ API调用失败: {e}")
        return False


async def test_message_sending():
    """测试消息发送功能"""
    logger.info("\n📨 测试消息发送...")

    caller_agent = "did:wba:localhost%3A9527:wba:user:e0959abab6fc3c3d"  # Orchestrator Agent
    target_agent = "did:wba:localhost%3A9527:wba:user:28cddee0fade0258"  # 共享DID (Calculator Agent)
    message = "测试消息：请问你能帮我计算 5 + 3 吗？"

    try:
        logger.info(f"📞 发送消息到: {target_agent}")
        logger.info(f"💬 消息内容: {message}")

        # 发送消息
        result = await agent_msg_post(
            caller_agent=caller_agent,
            target_agent=target_agent,
            content=message,
            message_type="text"
        )

        logger.info(f"✅ 消息发送成功!")
        logger.info(f"📋 响应: {json.dumps(result, ensure_ascii=False, indent=2)}")

        # 验证响应
        if isinstance(result, dict) and "anp_result" in result:
            anp_result = result["anp_result"]
            if isinstance(anp_result, dict) and "reply" in anp_result:
                logger.info(f"💬 Agent回复: {anp_result['reply']}")
                return True

        logger.info(f"❌ 消息响应格式不正确: {result}")
        return False

    except Exception as e:
        logger.info(f"❌ 消息发送失败: {e}")
        return False


async def test_llm_shared_did_api():
    """测试LLM Agent的共享DID API调用"""
    logger.info("\n🤖 测试LLM Agent共享DID API调用...")

    # 测试参数
    caller_agent = "did:wba:localhost%3A9527:wba:user:e0959abab6fc3c3d"  # Orchestrator Agent
    target_agent = "did:wba:localhost%3A9527:wba:user:28cddee0fade0258"  # 共享DID
    api_path = "/llm/chat"  # LLM共享DID路径
    params = {"message": "你好，请介绍一下你自己"}

    try:
        logger.info(f"📞 调用LLM API: {target_agent}{api_path}")
        logger.info(f"📊 参数: {params}")

        # 调用API
        result = await agent_api_call_post(
            caller_agent=caller_agent,
            target_agent=target_agent,
            api_path=api_path,
            params=params
        )

        logger.info(f"✅ LLM API调用成功!")
        logger.info(f"📋 响应: {json.dumps(result, ensure_ascii=False, indent=2)}")

        # 验证结果
        if isinstance(result, dict) and ("response" in result or "reply" in result or "content" in result):
            logger.info(f"🎉 LLM响应成功!")
            return True
        else:
            logger.info(f"❌ LLM响应格式不正确: {result}")
            return False

    except Exception as e:
        logger.info(f"❌ LLM API调用失败: {e}")
        return False


async def stop_server(svr, all_agents, lifecycle_agents):
    # --- 清理 ---
    logger.debug("\n🛑 收到关闭信号，开始清理...")
    # 停止服务器
    if hasattr(svr, "stop_server"):
        logger.debug("  - 停止anp_server...")
        svr.stop_server()
        logger.debug("  - 服务器已停止")
    else:
        logger.debug("  - SDK实例没有stop_server方法，无法主动停止服务")
    # 清理Agent
    cleanup_tasks = []
    for agent in all_agents:
        module = lifecycle_agents.get(agent.name)
        if module and hasattr(module, "cleanup_agent"):
            logger.debug(f"  - 安排清理Agent模块: {agent.name}...")
            cleanup_tasks.append(module.cleanup_agent())
    if cleanup_tasks:
        await asyncio.gather(*cleanup_tasks)
    logger.debug("✅ 所有Agent已清理完成，退出程序")


if __name__ == "__main__":

       asyncio.run(main())


