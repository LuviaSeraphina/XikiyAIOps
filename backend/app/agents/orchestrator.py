"""
Orchestrator — 三阶段流水线编排器

v4.0: Planner → Executor → Summarizer

阶段 1: Planner 分析意图，生成任务计划
阶段 2: Executor 按计划逐步执行工具
阶段 3: Summarizer 整合结果，生成报告
"""
import json
import asyncio
import logging
from typing import List, Dict, AsyncGenerator
from .security import SecurityAgent
from .planner import PlannerAgent
from .executor import ExecutorAgent
from .summarizer import SummarizerAgent
from .types import StepResult, StepStatus

_logger=logging.getLogger("xikiy_aiops.orchestrator")


class Orchestrator:
    """三阶段流水线编排器"""

    def __init__(self):
        self.security = SecurityAgent()
        self.planner = PlannerAgent()
        self.executor = ExecutorAgent()
        self.summarizer = SummarizerAgent()

    async def run(self, user_input: str, history: List[Dict] = None, session_id: str = "") -> AsyncGenerator:
        """
        三阶段流水线编排流程:
          阶段 0: Security 审查输入
          阶段 1: Planner 生成任务计划
          阶段 2: Executor 逐步执行
          阶段 3: Summarizer 生成报告
        """
        # ── 阶段 0: 安全审查 ──────────────────
        allowed, reason, risk_level = await self.security.review_input(user_input)
        if not allowed:
            yield {"event": "error", "data": {"message": reason}}
            return
        
        _logger.info(f"[阶段 0] 安全审查通过: risk_level={risk_level}")

        # ── 阶段 1: Planner 生成任务计划 ──────
        yield {"event": "phase", "data": {"phase": "planning", "message": "正在分析您的请求..."}}
        
        plan = await self.planner.plan(user_input)
        _logger.info(f"[阶段 1] 生成计划: {plan.intent}, {len(plan.steps)} 个步骤")
        
        # 发送计划事件
        yield {
            "event": "plan",
            "data": {
                "intent": plan.intent,
                "strategy": plan.strategy,
                "steps": [
                    {
                        "id": step.id,
                        "tool": step.tool,
                        "description": step.description,
                        "params": step.params,
                        "depends_on": step.depends_on
                    }
                    for step in plan.steps
                ]
            }
        }

        # ── 阶段 2: Executor 逐步执行 ─────────
        yield {"event": "phase", "data": {"phase": "executing", "message": "开始执行计划..."}}
        
        results = []
        
        for step in plan.steps:
            # 发送步骤开始事件
            yield {
                "event": "step_start",
                "data": {
                    "step_id": step.id,
                    "tool": step.tool,
                    "description": step.description
                }
            }
            
            # 检查依赖
            deps_ok = True
            if step.depends_on:
                dep_results = self.executor._get_dependency_results(step.depends_on, results)
                if not self.executor._check_dependencies_success(dep_results):
                    deps_ok = False
            
            # 依赖失败时的处理: 有 fallback 则执行 fallback, 有 max_retries 则尝试跳过依赖执行
            if not deps_ok:
                if step.fallback_tool:
                    _logger.info(f"[阶段 2] 步骤 {step.id} 依赖失败，执行 fallback: {step.fallback_tool}")
                    fallback_params = self.executor._resolve_fallback_params(step, step.params, results)
                    fallback_result = await self.executor._execute_step(step.fallback_tool, fallback_params)
                    fallback_result.step_id = step.id
                    fallback_result.tool_name = step.fallback_tool
                    results.append(fallback_result)
                    yield {
                        "event": "step_result",
                        "data": {
                            "step_id": step.id,
                            "tool": step.fallback_tool,
                            "status": fallback_result.status.value,
                            "error": fallback_result.error,
                            "summary": fallback_result.tool_result.get("summary", {}) if fallback_result.tool_result else {}
                        }
                    }
                    continue
                elif step.max_retries > 0:
                    # 有重试但依赖失败 — 跳过依赖检查直接执行（可能是参数引用失败）
                    pass
                else:
                    _logger.warning(f"[阶段 2] 步骤 {step.id} 依赖失败，跳过")
                    result = StepResult(
                        step_id=step.id, tool_name=step.tool,
                        status=StepStatus.SKIPPED, error='依赖步骤失败'
                    )
                    results.append(result)
                    yield {
                        "event": "step_result",
                        "data": {
                            "step_id": step.id, "tool": step.tool,
                            "status": "SKIPPED", "error": "依赖步骤失败"
                        }
                    }
                    continue
            
            # 解析动态参数
            params = self.executor._resolve_params(step.params, results)
            
            # 安全审批 - 从注册表获取工具的风险等级
            from app.mcp_plugins.base import registry
            tool_obj = registry.get_tool(step.tool)
            tool_risk = tool_obj.risk_level.value if tool_obj and hasattr(tool_obj, 'risk_level') else "read_only"
            
            approved, reason = self.security.approve_tool(step.tool, params, tool_risk)
            if not approved:
                _logger.warning(f"[阶段 2] 步骤 {step.id} 安全审批未通过: {reason}")
                result = StepResult(
                    step_id=step.id, tool_name=step.tool,
                    status=StepStatus.BLOCKED, error=f'安全审批未通过: {reason}'
                )
                results.append(result)
                yield {
                    "event": "step_result",
                    "data": {
                        "step_id": step.id, "tool": step.tool,
                        "status": "BLOCKED", "error": reason
                    }
                }
                continue
            
            # 需要用户确认
            if reason == "NEED_CONFIRM":
                _logger.info(f"[阶段 2] 步骤 {step.id} 需要用户确认, 等待前端...")
                from app.services.confirm_state import PENDING_CONFIRMS, CONFIRM_RESULTS
                
                # 生成 tool_call_id
                tool_call_id = f"{session_id}_{step.id}_{step.tool}"
                
                # 1. 发送 security_check (收集到待确认列表)
                yield {
                    "event": "security_check",
                    "data": {
                        "tool_call_id": tool_call_id,
                        "tool_name": step.tool,
                        "summary": step.description,
                        "details": str(step.params),
                        "risk_level": tool_risk,
                    }
                }
                # 2. 发送 awaiting_confirmation (触发前端弹窗)
                yield {
                    "event": "awaiting_confirmation",
                    "data": {"message": "有高危操作需要您确认"}
                }
                
                # 3. 暂停等待用户确认
                event = asyncio.Event()
                PENDING_CONFIRMS[session_id] = event
                try:
                    await asyncio.wait_for(event.wait(), timeout=120.0)
                    decisions = CONFIRM_RESULTS.get(session_id, {})
                    confirmed = decisions.get(tool_call_id, False)
                    CONFIRM_RESULTS.pop(session_id, None)
                except asyncio.TimeoutError:
                    _logger.warning(f"[阶段 2] 确认超时, 跳过步骤 {step.id}")
                    PENDING_CONFIRMS.pop(session_id, None)
                    CONFIRM_RESULTS.pop(session_id, None)
                    result = StepResult(
                        step_id=step.id, tool_name=step.tool,
                        status=StepStatus.SKIPPED, error='确认超时'
                    )
                    results.append(result)
                    yield {
                        "event": "step_result",
                        "data": {
                            "step_id": step.id, "tool": step.tool,
                            "status": "SKIPPED", "error": "确认超时"
                        }
                    }
                    continue
                
                if not confirmed:
                    _logger.info(f"[阶段 2] 用户拒绝步骤 {step.id}")
                    result = StepResult(
                        step_id=step.id, tool_name=step.tool,
                        status=StepStatus.SKIPPED, error='用户取消'
                    )
                    results.append(result)
                    yield {
                        "event": "step_result",
                        "data": {
                            "step_id": step.id, "tool": step.tool,
                            "status": "SKIPPED", "error": "用户取消"
                        }
                    }
                    continue
                
                _logger.info(f"[阶段 2] 用户已确认步骤 {step.id}, 继续执行")
            
            # 执行工具（支持重试）
            max_attempts = step.max_retries + 1
            retry_count = 0
            result = None
            
            while retry_count < max_attempts:
                _logger.info(f"[阶段 2] 执行步骤 {step.id}: {step.tool}({params})"
                    + (f" (重试 {retry_count}/{step.max_retries})" if retry_count > 0 else ""))
                
                result = await self.executor._execute_step(step.tool, params)
                
                if result.status != StepStatus.FAILED or retry_count >= max_attempts - 1:
                    break
                
                # 尝试推进到列表中的下一个元素
                if not self._advance_to_next_item(step, params, results):
                    break
                
                retry_count += 1
                yield {
                    "event": "step_start",
                    "data": {
                        "step_id": step.id, "tool": step.tool,
                        "description": f"{step.description} (重试 {retry_count})"
                    }
                }
            
            result.step_id = step.id
            result.tool_name = step.tool
            results.append(result)
            
            # 检查是否需要回退
            if result.status == StepStatus.FAILED and step.fallback_tool:
                _logger.info(f"[阶段 2] 步骤 {step.id} 失败，尝试回退: {step.fallback_tool}")
                fallback_params = self.executor._resolve_fallback_params(step, params, results)
                fallback_result = await self.executor._execute_step(step.fallback_tool, fallback_params)
                fallback_result.step_id = step.id
                fallback_result.tool_name = step.fallback_tool
                results[-1] = fallback_result  # 替换原结果
                result = fallback_result
            
            # 发送步骤结果事件
            yield {
                "event": "step_result",
                "data": {
                    "step_id": step.id,
                    "tool": result.tool_name,
                    "status": result.status.value,
                    "error": result.error if result.status == StepStatus.FAILED else None,
                    "summary": result.tool_result.get("summary", {}) if result.tool_result else {}
                }
            }
        
        _logger.info(f"[阶段 2] 执行完成: {len(results)} 个步骤")

        # ── 阶段 3: Summarizer 生成报告 ───────
        yield {"event": "phase", "data": {"phase": "summarizing", "message": "正在生成报告..."}}
        
        report = await self.summarizer.summarize(plan, results, user_input)
        _logger.info(f"[阶段 3] 报告生成完成: {len(report)} 字符")
        
        # 流式输出报告
        for char in report:
            yield {"event": "token", "data": {"text": char}}
        
        # 完成
        yield {"event": "done", "data": {"total_steps": len(plan.steps), "report_length": len(report)}}

    # ── 重试辅助: 推进到列表中的下一个元素 ──

    def _advance_to_next_item(self, step, params, results):
        """
        当步骤失败且参数引用了数组元素 (如 files[0].path) 时，
        将索引 +1 尝试下一个元素。成功则原地修改 params 并返回 True。
        """
        import re
        for key, val in step.params.items():
            if not isinstance(val, str) or not val.startswith('${'):
                continue
            m = re.search(r'\[(\d+)\]', val)
            if not m:
                continue
            old_idx = int(m.group(1))
            new_val = val[:m.start(1)] + str(old_idx + 1) + val[m.end(1):]
            # 检查目标元素是否存在
            ref_path = new_val[2:-1]
            ref_m = re.match(r'step(\d+)\.(.+)', ref_path)
            if not ref_m:
                continue
            step_id = int(ref_m.group(1))
            field_path = ref_m.group(2)
            prev_result = next((r for r in results if r.step_id == step_id), None)
            if prev_result and prev_result.tool_result:
                val_check = self.executor._extract_field(prev_result.tool_result, field_path)
                if val_check is not None:
                    params[key] = val_check
                    step.params[key] = new_val
                    _logger.info(f"重试推进: {key} [{old_idx}] → [{old_idx + 1}]")
                    return True
        return False
