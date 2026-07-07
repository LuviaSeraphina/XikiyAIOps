"""
执行 Agent - 按计划逐步执行工具调用

职责：
- 接收 TaskPlan，逐步执行每个步骤
- 从前面步骤的结果中提取动态参数
- 处理工具失败和回退机制
- 返回所有步骤的执行结果
"""
import logging
from typing import List, Dict, Any, Optional
from app.agents.base import BaseAgent
from app.agents.types import TaskPlan, TaskStep, StepResult, StepStatus
from app.agents.prompts_new import EXECUTOR_PROMPT

logger = logging.getLogger("xikiy_aiops.executor")


class ExecutorAgent(BaseAgent):
    """执行 Agent - 按计划逐步执行"""
    
    agent_name = "executor"
    system_prompt = EXECUTOR_PROMPT
    allowed_tools = []  # Executor 使用 TaskPlan 中的工具，不预定义
    
    def __init__(self):
        super().__init__()
    
    async def execute(self, plan: TaskPlan) -> List[StepResult]:
        """
        执行任务计划
        
        Args:
            plan: TaskPlan 对象
            
        Returns:
            List[StepResult]: 所有步骤的执行结果
        """
        results = []
        
        for step in plan.steps:
            logger.info(f"[Executor] 执行步骤 {step.id}: {step.tool}")
            
            # 检查依赖
            if step.depends_on:
                dep_results = self._get_dependency_results(step.depends_on, results)
                if not self._check_dependencies_success(dep_results):
                    logger.warning(f"[Executor] 步骤 {step.id} 依赖失败，跳过")
                    results.append(StepResult(
                        step_id=step.id,
                        tool_name=step.tool,
                        status=StepStatus.SKIPPED,
                        error="依赖步骤失败"
                    ))
                    continue
            
            # 解析动态参数
            params = self._resolve_params(step.params, results)
            
            # 执行工具
            result = await self._execute_step(step.tool, params)
            
            # 检查是否需要回退
            if result.status == StepStatus.FAILED and step.fallback_tool:
                logger.info(f"[Executor] 步骤 {step.id} 失败，尝试回退: {step.fallback_tool}")
                fallback_params = self._resolve_fallback_params(step, params, results)
                result = await self._execute_step(step.fallback_tool, fallback_params)
                result.tool_name = step.fallback_tool  # 更新工具名
            
            results.append(result)
        
        return results
    
    def _get_dependency_results(self, depends_on: List[int], results: List[StepResult]) -> List[StepResult]:
        """获取依赖步骤的结果"""
        return [r for r in results if r.step_id in depends_on]
    
    def _check_dependencies_success(self, dep_results: List[StepResult]) -> bool:
        """检查所有依赖是否成功"""
        return all(r.status == StepStatus.SUCCESS for r in dep_results)
    
    def _resolve_params(self, params: Dict[str, Any], results: List[StepResult]) -> Dict[str, Any]:
        """
        解析动态参数
        
        支持格式: ${stepN.data.field.path}
        例如: ${step2.data.files[0].path}
        """
        import re
        
        resolved = {}
        
        for key, value in params.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                # 提取引用路径
                ref_path = value[2:-1]  # 去掉 ${ 和 }
                
                # 解析路径: step2.data.files[0].path
                match = re.match(r'step(\d+)\.(.+)', ref_path)
                if match:
                    step_id = int(match.group(1))
                    field_path = match.group(2)
                    
                    # 查找对应的结果
                    step_result = next((r for r in results if r.step_id == step_id), None)
                    if step_result:
                        # 提取字段值
                        resolved_value = self._extract_field(step_result.tool_result, field_path)
                        if resolved_value is not None:
                            resolved[key] = resolved_value
                        else:
                            logger.warning(f"[Executor] 无法解析参数 {key}: {value}")
                    else:
                        logger.warning(f"[Executor] 未找到步骤 {step_id} 的结果")
            else:
                resolved[key] = value
        
        return resolved
    
    def _extract_field(self, data: Any, field_path: str) -> Any:
        """
        从嵌套数据结构中提取字段
        
        例如: data = {"files": [{"path": "/tmp/test"}]}
              field_path = "files[0].path"
              返回: "/tmp/test"
        """
        import re
        
        parts = re.split(r'\.|\[(\d+)\]', field_path)
        parts = [p for p in parts if p]  # 过滤空字符串
        
        current = data
        
        for part in parts:
            if part.isdigit():
                # 数组索引
                index = int(part)
                if isinstance(current, list) and index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                # 字典键
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
        
        return current
    
    def _resolve_fallback_params(self, step: TaskStep, original_params: Dict, results: List[StepResult]) -> Dict:
        """
        解析回退工具的参数 — 返回空 dict
        
        回退工具 (如 disk_cleanup) 通常与原工具 (如 file_truncate) 有完全不同的签名，
        因此不传递原参数，让回退工具使用自己的默认值。
        """
        return {}
    
    async def _execute_step(self, tool_name: str, params: Dict[str, Any]) -> StepResult:
        """
        执行单个工具
        
        Args:
            tool_name: 工具名称
            params: 工具参数
            
        Returns:
            StepResult: 执行结果
        """
        from app.mcp_plugins.base import registry
        
        try:
            # 调用工具
            result = registry.call(tool_name, **params)
            
            # 检查结果
            if result is None:
                return StepResult(
                    step_id=0,  # 会在外层更新
                    tool_name=tool_name,
                    status=StepStatus.FAILED,
                    error="工具返回 None"
                )
            
            # 检查是否有错误（error_response 将错误放在 summary.error 中）
            if isinstance(result, dict):
                summary = result.get("summary", {})
                if isinstance(summary, dict) and summary.get("error"):
                    return StepResult(
                        step_id=0,
                        tool_name=tool_name,
                        status=StepStatus.FAILED,
                        error=summary.get("error"),
                        tool_result=result
                    )
                # 也检查 data 中的 error 字段
                data = result.get("data", {})
                if isinstance(data, dict) and data.get("error"):
                    return StepResult(
                        step_id=0,
                        tool_name=tool_name,
                        status=StepStatus.FAILED,
                        error=data.get("error"),
                        tool_result=result
                    )
            
            return StepResult(
                step_id=0,
                tool_name=tool_name,
                status=StepStatus.SUCCESS,
                tool_result=result
            )
            
        except Exception as e:
            logger.error(f"[Executor] 工具 {tool_name} 执行异常: {e}")
            return StepResult(
                step_id=0,
                tool_name=tool_name,
                status=StepStatus.FAILED,
                error=str(e)
            )
