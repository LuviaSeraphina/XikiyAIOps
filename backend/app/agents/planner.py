"""
Planner Agent - 规划器

职责：分析用户意图，生成结构化的任务计划
不调用任何工具，只负责思考和规划
"""
import json
import re
import logging
from typing import Optional
from app.agents.base import BaseAgent
from app.agents.types import TaskPlan, TaskStep, PlanType
from app.agents.prompts_new import PLANNER_PROMPT

logger = logging.getLogger("xikiy_aiops.planner")


class PlannerAgent(BaseAgent):
    """规划 Agent - 只思考不调用工具"""
    
    # 使用类属性，遵循 BaseAgent 模式
    agent_name = "planner"
    system_prompt = PLANNER_PROMPT
    allowed_tools = []  # Planner 不调用任何工具
    
    def __init__(self):
        """初始化 PlannerAgent"""
        # BaseAgent 使用类属性，不需要调用 super().__init__()
        pass
    
    async def plan(self, user_input: str) -> TaskPlan:
        """
        分析用户意图，生成任务计划
        
        Args:
            user_input: 用户输入的自然语言请求
            
        Returns:
            TaskPlan: 结构化的任务计划
        """
        logger.info(f"[Planner] 开始规划任务: {user_input}")
        
        # RAG 知识注入 — 检索相关 SRE 知识 + 场景模板
        system_content = self.system_prompt
        try:
            from app.rag.inject import inject_context
            rag_ctx = inject_context(user_input)
            if rag_ctx:
                system_content += rag_ctx
                logger.info(f"[Planner] RAG 注入: {len(rag_ctx)} 字符")
        except Exception:
            pass  #RAG 不可用时静默降级
        
        # 调用 LLM 生成任务计划（纯文本，不调工具）
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_input}
        ]
        
        response = await self._call_llm(messages)
        
        # 解析 LLM 返回的 JSON
        try:
            plan = self._parse_plan(response, user_input)
            logger.info(f"[Planner] 生成计划: {plan.intent}, {len(plan.steps)} 个步骤")
            return plan
        except Exception as e:
            logger.warning(f"[Planner] JSON 解析失败: {e}, 使用模板回退")
            # 解析失败，使用模板回退
            plan = self._get_fallback_plan(user_input)
            logger.info(f"[Planner] 使用模板计划: {plan.intent}, {len(plan.steps)} 个步骤")
            return plan
    
    async def _call_llm(self, messages: list) -> str:
        """
        调用 LLM 生成文本响应（不使用工具）
        
        Args:
            messages: 对话消息列表
            
        Returns:
            str: LLM 的文本响应
        """
        from app.llm.providers import get_llm_provider
        
        provider = get_llm_provider()
        
        # 调用 LLM，tools=[] 表示不使用工具
        full_response = ""
        async for event in provider.chat_stream(messages, tools=[]):
            if event["type"] == "token":
                full_response += event["content"]
            elif event["type"] == "done":
                break
        
        return full_response
    
    def _parse_plan(self, response: str, user_input: str) -> TaskPlan:
        """
        解析 LLM 返回的 JSON 为 TaskPlan 对象
        
        Args:
            response: LLM 的文本响应
            user_input: 用户原始输入
            
        Returns:
            TaskPlan: 解析后的任务计划
            
        Raises:
            ValueError: JSON 解析失败
        """
        # 尝试从响应中提取 JSON
        json_str = self._extract_json(response)
        if not json_str:
            raise ValueError("未找到 JSON 内容")
        
        # 解析 JSON
        plan_data = json.loads(json_str)
        
        # 验证必需字段
        if "intent" not in plan_data:
            raise ValueError("缺少 intent 字段")
        if "strategy" not in plan_data:
            raise ValueError("缺少 strategy 字段")
        if "steps" not in plan_data or not isinstance(plan_data["steps"], list):
            raise ValueError("缺少 steps 字段或格式错误")
        
        # 构建 TaskStep 列表
        steps = []
        for step_data in plan_data["steps"]:
            # 自动检测数组索引引用，设置 max_retries
            max_retries = step_data.get("max_retries", 0)
            if max_retries == 0:
                # 检查参数中是否有数组索引引用 (如 ${step2.data.files[0].path})
                for v in step_data.get("params", {}).values():
                    if isinstance(v, str) and re.search(r'\[\d+\]', v):
                        max_retries = 2
                        break
            
            step = TaskStep(
                id=step_data["id"],
                tool=step_data["tool"],
                description=step_data.get("description", ""),
                params=step_data.get("params", {}),
                depends_on=step_data.get("depends_on", []),
                fallback_tool=step_data.get("fallback_tool", ""),
                max_retries=max_retries,
            )
            steps.append(step)
        
        # 构建 TaskPlan
        plan = TaskPlan(
            intent=plan_data["intent"],
            strategy=plan_data["strategy"],
            steps=steps,
            user_input=user_input
        )
        
        return plan
    
    def _extract_json(self, response: str) -> Optional[str]:
        """
        从 LLM 响应中提取 JSON 字符串
        
        Args:
            response: LLM 的文本响应
            
        Returns:
            Optional[str]: 提取的 JSON 字符串，失败返回 None
        """
        # 尝试直接解析（LLM 可能直接返回 JSON）
        try:
            json.loads(response)
            return response
        except json.JSONDecodeError:
            pass
        
        # 尝试从 markdown 代码块中提取
        import re
        
        # 匹配 ```json ... ``` 或 ``` ... ```
        json_block_pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
        matches = re.findall(json_block_pattern, response)
        
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue
        
        # 尝试提取花括号包围的 JSON 对象
        brace_pattern = r'\{[\s\S]*\}'
        matches = re.findall(brace_pattern, response)
        
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _get_fallback_plan(self, user_input: str) -> TaskPlan:
        """LLM 输出格式错误时的回退 — 通用系统诊断, 不匹配场景模板"""
        return TaskPlan(
            intent=PlanType.CUSTOM,
            strategy="LLM 规划失败, 回退到通用系统诊断",
            steps=[
                TaskStep(id=1, tool="system_info", description="获取系统基本信息", params={}),
                TaskStep(id=2, tool="system_load", description="检查系统负载", params={}),
                TaskStep(id=3, tool="memory_info", description="检查内存使用", params={}),
                TaskStep(id=4, tool="disk_inspect", description="检查磁盘使用", params={}),
            ],
            user_input=user_input
        )

