"""
总结 Agent - 生成可读的执行报告

职责：
- 接收 TaskPlan 和所有 StepResult
- 整合结果，提取关键信息
- 生成 Markdown 格式的报告
- 用 🟢🟡🔴 标注风险等级
"""
import logging
from typing import List, Dict, Any
from app.agents.base import BaseAgent
from app.agents.types import TaskPlan, StepResult, StepStatus, PlanType
from app.agents.prompts_new import SUMMARIZER_PROMPT

logger = logging.getLogger("xikiy_aiops.summarizer")


class SummarizerAgent(BaseAgent):
    """总结 Agent - 生成可读报告"""
    
    agent_name = "summarizer"
    system_prompt = SUMMARIZER_PROMPT
    allowed_tools = []  # Summarizer 不调用工具
    
    def __init__(self):
        super().__init__()
    
    async def summarize(self, plan: TaskPlan, results: List[StepResult], user_input: str) -> str:
        """
        生成总结报告
        
        Args:
            plan: TaskPlan 对象
            results: 所有步骤的执行结果
            user_input: 用户原始输入
            
        Returns:
            str: Markdown 格式的报告
        """
        logger.info(f"[Summarizer] 开始生成报告: {len(results)} 个步骤")
        
        # 构建上下文
        context = self._build_context(plan, results, user_input)
        
        # 调用 LLM 生成报告
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": context}
        ]
        
        report = await self._call_llm(messages)
        
        logger.info(f"[Summarizer] 报告生成完成: {len(report)} 字符")
        return report
    
    def _build_context(self, plan: TaskPlan, results: List[StepResult], user_input: str) -> str:
        """构建 LLM 上下文"""
        import json
        
        # 统计
        success_count = sum(1 for r in results if r.status == StepStatus.SUCCESS)
        failed_count = sum(1 for r in results if r.status == StepStatus.FAILED)
        skipped_count = sum(1 for r in results if r.status == StepStatus.SKIPPED)
        
        # 构建上下文文本
        context = f"""用户原始请求: {user_input}

任务计划:
- 意图: {plan.intent}
- 策略: {plan.strategy}
- 步骤数: {len(plan.steps)}

执行结果统计:
- 成功: {success_count}
- 失败: {failed_count}
- 跳过: {skipped_count}

步骤详情:
"""
        
        for i, (step, result) in enumerate(zip(plan.steps, results), 1):
            status_emoji = {
                StepStatus.SUCCESS: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️"
            }.get(result.status, "❓")
            
            context += f"\n{i}. {step.description}\n"
            context += f"   工具: {step.tool}\n"
            context += f"   状态: {status_emoji} {result.status.value}\n"
            
            if result.status == StepStatus.SUCCESS and result.tool_result:
                # 提取关键信息
                summary = result.tool_result.get("summary", {})
                data = result.tool_result.get("data", {})
                
                if summary:
                    context += f"   摘要: {json.dumps(summary, ensure_ascii=False, indent=6)}\n"
                
                if data:
                    # 限制数据大小，避免上下文过长
                    data_str = json.dumps(data, ensure_ascii=False)
                    if len(data_str) > 500:
                        data_str = data_str[:500] + "..."
                    context += f"   数据: {data_str}\n"
            
            elif result.status == StepStatus.FAILED:
                context += f"   错误: {result.error}\n"
        
        context += "\n请根据以上信息生成一份清晰、专业的执行报告。"
        
        return context
    
    async def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """调用 LLM 生成报告"""
        from app.llm.providers import get_llm_provider
        
        provider = get_llm_provider()
        full_response = ""
        
        async for event in provider.chat_stream(messages):
            if event["type"] == "token":
                full_response += event["content"]
        
        return full_response
