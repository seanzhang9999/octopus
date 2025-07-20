"""
FastAPI application main module.
"""
import asyncio
import os
import sys
import threading

from anp_foundation.config import UnifiedConfig, set_global_config, get_global_config
from anp_foundation.utils.log_base import setup_logging
app_config = UnifiedConfig(config_file='unified_config_framework_demo.yaml')
set_global_config(app_config)
setup_logging()



from anp_workbench_server.baseline.anp_middleware_baseline.anp_auth_middleware import auth_middleware
from anp_workbench_server.baseline.anp_router_baseline import router_did, router_publisher, router_agent



import uvicorn
from anp_transformer.agent_manager import LocalAgentManager

from anp_transformer.agent_manager import AgentManager
from starlette.middleware.cors import CORSMiddleware

from anp_transformer.anp_service.agent_api_call import agent_api_call_post
from octopus.api.agent_loader import initialize_agents
from octopus.master_agent import MasterAgent


import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI


# 现在导入项目模块
from octopus.utils.log_base import (setup_enhanced_logging)
from octopus.config.settings import get_settings

# Initialize logging using setup_enhanced_logging at the main entry point
settings = get_settings()
logger = setup_enhanced_logging(level=getattr(logging, settings.log_level))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Octopus FastAPI application (main module)")
    logger.info("Application startup completed successfully")
    yield
    # Shutdown
    logger.info("Shutting down Octopus FastAPI application")



app = FastAPI(
    title=settings.app_name,
    description="A FastAPI application for the Octopus project",
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan
)

@app.middleware("http")
async def auth_middleware_wrapper(request, call_next):
    return await auth_middleware(request, call_next)
app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

app.include_router(router_did.router)
app.include_router(router_publisher.router)
app.include_router(router_agent.router)

@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("Root endpoint accessed")
    return {"message": "Hello World from Octopus!"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check endpoint accessed")
    return {"status": "healthy"}


@app.get("/api/v1/info")
async def get_info():
    """Get application information."""
    logger.info("Application info endpoint accessed")
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "A FastAPI application for the Octopus project"
    }

async def start_server_in_thread():
    logger.info(f"Starting {settings.app_name} FastAPI server on {settings.host}:{settings.port}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"OpenAI Model: {settings.openai_model}")
    if settings.openai_base_url:
        logger.info(f"OpenAI Base URL: {settings.openai_base_url}")

        # 创建一个线程来运行服务器
        def run_server():
            uvicorn.run(
                app,
                host=settings.host,
                port=settings.port,
                log_level=settings.log_level.lower()
            )

        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True  # 设置为守护线程，这样主线程结束时它也会结束
        server_thread.start()

        # 给服务器一些启动时间
        await asyncio.sleep(0.1)
        logger.info("Server started in background thread")

async def main():
    """Main function to run the FastAPI application."""

    AgentManager.clear_all_agents()
    AgentManager.initialize_router()
    # Initialize all agents
    initialize_agents()

    master_agent = MasterAgent().agent
    await LocalAgentManager.generate_and_save_agent_interfaces(master_agent)



    # 使用线程启动服务器，不阻塞主线程
    await start_server_in_thread()
    # 服务器已在后台运行，现在可以执行测试代码
    logger.info("执行测试API调用...")



    result = await agent_api_call_post(
        caller_agent="did:wba:localhost%3A9527:wba:user:e0959abab6fc3c3d",
        target_agent="did:wba:localhost%3A9527:wba:user:27c0b1d11180f973",
        api_path="/master/process_nlp",
        params={"request": "ANP网络协议可以用在哪里", "request_id": 8848}
    )
    logger.info(f"✅ master智能体调用结果: {result}")

    result = await agent_api_call_post(
        caller_agent="did:wba:localhost%3A9527:wba:user:e0959abab6fc3c3d",
        target_agent="did:wba:localhost%3A9527:wba:user:27c0b1d11180f973",
        api_path="/master/get_status",
        params={}
    )
    logger.info(f"✅ master智能体调用结果: {result}")

    # 保持主线程运行，直到用户中断
    try:
        logger.info("服务器正在后台运行。按Ctrl+C退出...")
        # 无限循环保持主线程运行
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("程序被用户中断")




if __name__ == "__main__":
    asyncio.run(main())