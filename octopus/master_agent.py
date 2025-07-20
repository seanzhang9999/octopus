"""
Master Agent - Natural language interface for the Octopus multi-agent system.
"""

import logging
import json
from encodings.punycode import selective_find
from pickle import FALSE
from typing import Any, Dict, List, Optional
from datetime import datetime

from openai import OpenAI, AsyncOpenAI
from pycparser.ply.yacc import resultlimit

from anp_transformer.agent_decorator import agent_class, class_api
from anp_transformer.agent_manager import AgentManager
from anp_transformer.global_router_agent_api import GlobalRouter
from anp_transformer.global_router_agent_message import GlobalMessageManager
from octopus.agents.base_agent import BaseAgent
from octopus.router.agents_router import router
from octopus.config.settings import get_settings


logger = logging.getLogger(__name__)


@agent_class(
    name="master_agent",
    description="Master agent that provides natural language interface and delegates tasks to appropriate sub-agents",
    did="did:wba:localhost%3A9527:wba:user:27c0b1d11180f973",
    shared=True,
    prefix= '/master',
    primary_agent = False,
    version = "1.0.0",
    tags = ["master", "coordinator", "natural_language"]
)
class MasterAgent(BaseAgent):
    """
    Master Agent responsible for:
    1. Providing natural language interface
    2. Agent discovery and selection
    3. Task delegation to appropriate agents
    """
    
    def __init__(self, api_key: str = None, model: str = None, base_url: str = None, **kwargs):
        """
        Initialize the Master Agent.
        
        Args:
            api_key: OpenAI API key (optional, will use settings if not provided)
            model: OpenAI model to use (optional, will use settings if not provided)
            base_url: OpenAI base URL (optional, will use settings if not provided)
            **kwargs: Additional configuration
        """
        super().__init__(name="MasterAgent", description="Natural language interface", **kwargs)
        
        # Get settings
        settings = get_settings()
        
        # Validate model provider
        self.model_provider = settings.model_provider.lower()
        if self.model_provider != "openai":
            raise ValueError(f"Unsupported model provider: {self.model_provider}. Currently only 'openai' is supported.")
        
        # OpenAI setup using settings
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in .env file or pass api_key parameter.")
        
        self.model = model or settings.openai_model
        self.base_url = base_url or settings.openai_base_url
        self.deployment = settings.openai_deployment
        self.api_version = settings.openai_api_version
        self.temperature = settings.openai_temperature
        self.max_tokens = settings.openai_max_tokens
        
        # Create client based on provider
        self._initialize_client()
        
        # For Azure OpenAI, use deployment name if available
        self.effective_model = self.deployment if self.deployment else self.model
        
        self.logger.info(f"MasterAgent initialized with provider: {self.model_provider}, model: {self.effective_model}")
        if self.base_url:
            self.logger.info(f"Using {self.model_provider.upper()} base URL: {self.base_url}")
        if self.api_version:
            self.logger.info(f"Using API version: {self.api_version}")
        if self.deployment:
            self.logger.info(f"Using deployment: {self.deployment}")
        self.logger.info(f"{self.model_provider.upper()} settings - Temperature: {self.temperature}, Max tokens: {self.max_tokens}")
    
    def _initialize_client(self):
        """Initialize the appropriate client based on model provider."""
        if self.model_provider == "openai":
            # Create OpenAI client with proper Azure OpenAI configuration
            client_kwargs = {"api_key": self.api_key}
            client_kwargs["base_url"] = self.base_url
            self.async_client = AsyncOpenAI(**client_kwargs)

            # For Azure OpenAI, construct the full base URL with deployment
            if self.base_url and self.deployment:
                # Azure OpenAI format: https://{resource}.openai.azure.com/openai/deployments/{deployment}/
                base_url = self.base_url.rstrip('/')
                if not base_url.endswith('/openai'):
                    base_url = base_url + '/openai'
                full_url = f"{base_url}/deployments/{self.deployment}/"
                client_kwargs["base_url"] = full_url
            elif self.base_url:
                client_kwargs["base_url"] = self.base_url
                
            if self.api_version:
                client_kwargs["default_query"] = {"api-version": self.api_version}
                
            self.client = OpenAI(**client_kwargs)

        else:
            raise ValueError(f"Unsupported model provider: {self.model_provider}")
    
    def initialize(self):
        """Custom initialization."""
        # Discover available agents
        self._discover_agents()
    
    def cleanup(self):
        """Cleanup resources."""
        pass
    
    def _discover_agents(self):
        """Discover and catalog available agents."""
        agents = router.list_agents()
        self.logger.info(f"Discovered {len(agents)} agents:")
        for agent in agents:
            self.logger.info(f"  - {agent['name']}: {agent['description']}")
    
    def _get_agent_capabilities(self) -> List[Dict[str, Any]]:
        """Get detailed capabilities of all available agents."""
        agents = router.list_agents()
        capabilities = []
        
        for agent in agents:
            # Skip self
            if agent['name'] == 'master_agent':
                continue
                
            # Get agent registration to access methods
            agent_registration = router.get_agent(agent['name'])
            if agent_registration and agent_registration.methods:
                # Convert MethodInfo objects to dict for serialization
                methods_dict = {}
                for method_name, method_info in agent_registration.methods.items():
                    methods_dict[method_name] = {
                        'description': method_info.description,
                        'parameters': method_info.parameters,
                        'returns': method_info.returns
                    }
                
                capabilities.append({
                    'name': agent['name'],
                    'description': agent['description'],
                    'methods': methods_dict
                })
        
        return capabilities
    
    @class_api("/process_nlp",
        description="Process natural language request and delegate to appropriate agent",
        parameters={
           "request": {"type": "string", "description": "Natural language request or task"},
           "request_id": {"type": "string", "description": "Unique identifier for this request"}
        },
        returns="string",
        auto_wrap=True)
    async def process_natural_language(self, request: str, request_id: str) -> str:
        """
        Process natural language request and delegate to appropriate agent.
        
        Args:
            request: Natural language request or task
            request_id: Unique identifier for this request
            
        Returns:
            String response from the delegated agent
        """
        self.logger.info(f"Processing natural language request [{request_id}]: {request}")
        
        try:
            # Get available agents and their capabilities
            available_agents = self._get_agent_capabilities()
            
            # Use OpenAI to analyze the request and select the appropriate agent
            agent_selection = await self._select_agent_for_request(request, available_agents)
            
            if not agent_selection:
                return f"Sorry, I couldn't find an appropriate agent to handle your request: {request}"
            
            # Execute the selected agent method
            result = self._execute_agent_method(agent_selection)
            
            # Return the result as a string
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                return str(result)
                
        except Exception as e:
            self.logger.error(f"Error processing natural language request [{request_id}]: {str(e)}")
            return f"Sorry, I encountered an error while processing your request: {str(e)}"
    
    async def _select_agent_for_request(self, request: str, available_agents: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Use OpenAI to select the most appropriate agent for the request."""
        system_prompt = """You are an intelligent agent selector for a multi-agent system.
Given a natural language request, analyze it and select the most appropriate agent and method to handle it.

Available agents and their capabilities:
{agents_info}

Respond in JSON format with the following structure:
{{
    "agent_name": "selected_agent_name",
    "method_name": "selected_method_name",
    "parameters": {{}},
    "confidence": 0.95,
    "reasoning": "explanation of why this agent was selected"
}}

If no suitable agent is found, respond with:
{{
    "agent_name": null,
    "method_name": null,
    "parameters": null,
    "confidence": 0.0,
    "reasoning": "no suitable agent found"
}}"""
        
        user_prompt = f"Request: {request}"
        
        try:
            response = await self.async_client.chat.completions.create(
                model=self.effective_model,
                messages=[
                    {"role": "system", "content": system_prompt.format(agents_info=json.dumps(available_agents, indent=2, ensure_ascii=False))},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            response_text = response.choices[0].message.content
            self.logger.debug(f"OpenAI response text: {response_text}")
            
            # Try to parse the JSON response
            try:
                # Clean the response text (remove extra whitespace)
                clean_response = response_text.strip()
                self.logger.debug(f"Clean response text: {clean_response}")
                
                selection_result = json.loads(clean_response)
                self.logger.debug(f"Parsed JSON: {selection_result}")
                
                # Validate the response structure
                if not isinstance(selection_result, dict):
                    self.logger.error(f"Response is not a dict: {type(selection_result)}")
                    return None
                    
                if "agent_name" not in selection_result:
                    self.logger.error(f"Missing 'agent_name' in response: {selection_result}")
                    return None

                # Handle case where agent_name is explicitly None (no suitable agent found)
                if selection_result["agent_name"] is None:
                    self.logger.info(
                        f"No suitable agent found: {selection_result.get('reasoning', 'No reason provided')}")
                    return None
                    
                return selection_result
                
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {e}")
                self.logger.error(f"Raw response: {repr(response_text)}")
                # Try to find the JSON part if there's extra text
                try:
                    # Look for JSON-like structure in the response
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        json_part = response_text[start_idx:end_idx]
                        self.logger.debug(f"Extracted JSON part: {json_part}")
                        selection_result = json.loads(json_part)
                        return selection_result
                except:
                    pass
                return None
                
        except Exception as e:
            self.logger.error(f"Error in agent selection: {e}")
            return None
    
    def _execute_agent_method(self, agent_selection: Dict[str, Any]) -> Any:
        """Execute the selected agent method."""
        agent_name = agent_selection['agent_name']
        method_name = agent_selection['method_name']
        parameters = agent_selection.get('parameters', {})
        
        self.logger.info(f"Executing {agent_name}.{method_name} with parameters: {parameters}")
        
        try:
            # Call the agent method through the router
            result = router.execute_agent_method(agent_name, method_name, parameters)
            
            self.logger.info(f"Agent execution completed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing agent method: {str(e)}")
            raise

    @class_api("/get_status",
        description="Get current status of the master agent",
        parameters={},
        returns="dict",
        auto_wrap=True)
    def get_status(self) -> Dict[str, Any]:
        # Get system status as a string and parse it
        system_status_str = self.get_system_status()
        import json
        system_status = json.loads(system_status_str)

        # Get available agents
        available_agents = self._get_agent_capabilities()

        # Create the complete response
        response = {
            "name": "MasterAgent",
            "status": "active",
            "model": self.effective_model,
            "model_provider": self.model_provider,
            "available_agents": len(available_agents),
            "agents": [agent['name'] for agent in available_agents],
            "timestamp": datetime.now().isoformat(),
            "system_status": system_status
        }

        return json.dumps(response, ensure_ascii=False, indent=2)

    def get_system_status(self):
        status_data = {
            "agent_manager": [],
            "global_router": [],
            "global_message_manager": [],
            "api_routes": []
        }

        # 收集Agent管理器状态
        agents_info = AgentManager.list_agents()
        for did, agent_dict in agents_info.items():
            logger.debug(f" DID: {did}共有{len(agent_dict)}个agent")
            for agent_name, agent_info in agent_dict.items():
                status_data["agent_manager"].append({
                    "did": did,
                    "agent_name": agent_name,
                    "mode": "shared" if agent_info['shared'] else "exclusive",
                    "is_primary": agent_info.get('primary_agent', False),
                    "prefix": agent_info.get('prefix', "")
                })

        # 收集全局路由器状态
        routes = GlobalRouter.list_routes()
        for route in routes:
            status_data["global_router"].append({
                "did": route['did'],
                "path": route['path'],
                "agent_name": route['agent_name']
            })

        # 收集全局消息管理器状态
        handlers = GlobalMessageManager.list_handlers()
        for handler in handlers:
            status_data["global_message_manager"].append({
                "did": handler['did'],
                "msg_type": handler['msg_type'],
                "agent_name": handler['agent_name']
            })

            # 🔧 修复：正确收集API路由信息
        for did, agent_dict in agents_info.items():
            for agent_name, agent_info in agent_dict.items():
                # 通过 AgentManager 获取实际的 Agent 实例
                try:
                    agent_instance = AgentManager.get_agent(did, agent_name)
                    if agent_instance and hasattr(agent_instance, 'anp_user'):
                        agent_routes = []
                        for path, handler in agent_instance.anp_user.api_routes.items():
                            handler_name = handler.__name__ if hasattr(handler, '__name__') else 'unknown'
                            agent_routes.append({
                                "path": path,
                                "handler": handler_name
                            })

                        status_data["api_routes"].append({
                            "agent_name": agent_name,
                            "did": did,
                            "routes_count": len(agent_instance.anp_user.api_routes),
                            "routes": agent_routes
                        })
                except Exception as e:
                    logger.error(f"Error getting agent instance for {did}/{agent_name}: {e}")
        import json
        return json.dumps(status_data, ensure_ascii=False, indent=2)