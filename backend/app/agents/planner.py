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
        """
        当 LLM 输出格式错误时，使用预定义模板回退
        
        Args:
            user_input: 用户原始输入
            
        Returns:
            TaskPlan: 回退的任务计划
        """
        # 根据关键词匹配场景
        input_lower = user_input.lower()
        
        # 场景 A: 清理系统垃圾
        if any(keyword in input_lower for keyword in ["清理", "垃圾", "磁盘", "空间"]):
            return self._template_clean_garbage(user_input)
        
        # 场景 B: 配置漂移
        if any(keyword in input_lower for keyword in ["配置", "漂移", "nginx", "恢复"]):
            return self._template_config_drift(user_input)
        
        # 场景 C: I/O 异常
        if any(keyword in input_lower for keyword in ["i/o", "io", "读写", "磁盘慢"]):
            return self._template_io_anomaly(user_input)
        
        # 场景 D: 僵尸进程
        if any(keyword in input_lower for keyword in ["僵尸", "zombie"]):
            return self._template_zombie_cleanup(user_input)

        # 场景 E: 服务故障
        if any(keyword in input_lower for keyword in ["服务", "挂了", "宕机", "启动", "重启", "nginx", "apache"]):
            return self._template_service_recovery(user_input)

        # 场景 F: 安全审计
        if any(keyword in input_lower for keyword in ["安全", "审计", "巡检", "扫描"]):
            return self._template_security_audit(user_input)

        # 场景 G: OOM
        if any(keyword in input_lower for keyword in ["oom", "内存不足", "内存溢出", "内存爆了", "内存满"]):
            return self._template_oom_diagnosis(user_input)

        # 场景 H: 网络
        if any(keyword in input_lower for keyword in ["网络", "连不上", "不通", "ping", "dns"]):
            return self._template_network_diagnosis(user_input)

        # 场景 I: Swap
        if any(keyword in input_lower for keyword in ["swap", "交换", "卡顿", "卡", "慢", "换页"]):
            return self._template_swap_diagnosis(user_input)

        # 场景 J: FD 泄漏
        if any(keyword in input_lower for keyword in ["fd", "句柄", "打开文件", "too many open"]):
            return self._template_fd_leak(user_input)

        # 默认：系统诊断
        return self._template_system_diagnosis(user_input)
    
    def _template_clean_garbage(self, user_input: str) -> TaskPlan:
        """清理系统垃圾模板"""
        return TaskPlan(
            intent=PlanType.CLEAN_GARBAGE,
            strategy="先感知磁盘状态，定位大文件，识别性质，逐个安全清理，最后验证",
            steps=[
                TaskStep(id=1, tool="disk_inspect", description="检查磁盘使用率", params={}),
                TaskStep(id=2, tool="disk_large_files", description="定位大文件 (>100MB)", 
                        params={"min_size_mb": 100, "top_n": 5}, depends_on=[1]),
                TaskStep(id=3, tool="file_identify", description="识别大文件的性质", 
                        params={"path": "${step2.data.files[0].path}"}, depends_on=[2],
                        max_retries=2),
                TaskStep(id=4, tool="file_truncate", description="安全清理非关键文件", 
                        params={"path": "${step3.data.path}"}, depends_on=[3],
                        fallback_tool="disk_cleanup"),
                TaskStep(id=5, tool="disk_inspect", description="验证清理效果", params={}, depends_on=[4])
            ],
            user_input=user_input
        )
    
    def _template_config_drift(self, user_input: str) -> TaskPlan:
        """配置漂移模板"""
        return TaskPlan(
            intent=PlanType.CONFIG_DRIFT,
            strategy="对比配置差异，备份当前配置，恢复原始配置，重载服务",
            steps=[
                TaskStep(id=1, tool="config_diff", description="对比当前配置与备份", 
                        params={"path": "/etc/nginx/nginx.conf", "compare_to": "/etc/nginx/nginx.conf.original"}),
                TaskStep(id=2, tool="config_backup", description="备份当前漂移配置", 
                        params={"path": "/etc/nginx/nginx.conf", "tag": "drift_backup"}, depends_on=[1]),
                TaskStep(id=3, tool="config_restore", description="恢复原始配置", 
                        params={"backup_path": "${step2.data.backup_path}"}, depends_on=[2]),
                TaskStep(id=4, tool="service_control", description="重载服务", 
                        params={"service": "nginx", "action": "reload"}, depends_on=[3])
            ],
            user_input=user_input
        )
    
    def _template_io_anomaly(self, user_input: str) -> TaskPlan:
        """I/O 异常模板"""
        return TaskPlan(
            intent=PlanType.IO_ANOMALY,
            strategy="确认 I/O 异常，定位元凶进程，降低优先级，验证效果",
            steps=[
                TaskStep(id=1, tool="disk_io_stats", description="检查磁盘 I/O 统计", params={}),
                TaskStep(id=2, tool="process_io_top", description="定位 I/O 最高的进程", 
                        params={"top_n": 5}, depends_on=[1]),
                TaskStep(id=3, tool="process_ionice", description="降低进程 I/O 优先级", 
                        params={"pid": "${step2.data.processes[0].pid}", "class": "idle"}, depends_on=[2]),
                TaskStep(id=4, tool="disk_io_stats", description="验证 I/O 改善", params={}, depends_on=[3])
            ],
            user_input=user_input
        )
    
    def _template_zombie_cleanup(self, user_input: str) -> TaskPlan:
        """僵尸进程清理模板"""
        return TaskPlan(
            intent=PlanType.ZOMBIE_CLEANUP,
            strategy="扫描僵尸进程，清理父进程，验证结果",
            steps=[
                TaskStep(id=1, tool="process_zombie_scan", description="扫描僵尸进程", params={}),
                TaskStep(id=2, tool="process_zombie_cleanup", description="清理僵尸进程", 
                        params={"pid": "${step1.data.zombies[0].pid}"}, depends_on=[1]),
                TaskStep(id=3, tool="process_zombie_scan", description="验证清理结果", params={}, depends_on=[2])
            ],
            user_input=user_input
        )
    
    def _template_system_diagnosis(self, user_input: str) -> TaskPlan:
        """系统诊断模板（默认）"""
        return TaskPlan(
            intent=PlanType.SYSTEM_DIAGNOSIS,
            strategy="全面检查系统状态，发现问题，提供建议",
            steps=[
                TaskStep(id=1, tool="system_info", description="获取系统基本信息", params={}),
                TaskStep(id=2, tool="disk_inspect", description="检查磁盘使用率", params={}, depends_on=[1]),
                TaskStep(id=3, tool="memory_info", description="检查内存使用情况", params={}, depends_on=[1]),
                TaskStep(id=4, tool="process_top_cpu", description="查看 CPU 占用最高的进程", 
                        params={"top_n": 5}, depends_on=[1]),
                TaskStep(id=5, tool="system_failed_services", description="检查失败的服务", params={}, depends_on=[1])
            ],
            user_input=user_input
        )

    def _template_service_recovery(self, user_input: str) -> TaskPlan:
        """服务故障自愈模板"""
        return TaskPlan(
            intent=PlanType.SERVICE_RECOVERY,
            strategy="确认状态→查看日志→重启→验证端口",
            steps=[
                TaskStep(id=1, tool="service_control", description="检查服务状态",
                        params={"service": "nginx", "action": "status"}),
                TaskStep(id=2, tool="system_journal_tail", description="查看服务最近日志",
                        params={"service": "nginx", "lines": 50}, depends_on=[1]),
                TaskStep(id=3, tool="service_control", description="重启服务",
                        params={"service": "nginx", "action": "restart"}, depends_on=[2]),
                TaskStep(id=4, tool="service_control", description="确认恢复",
                        params={"service": "nginx", "action": "status"}, depends_on=[3]),
                TaskStep(id=5, tool="network_listening_ports", description="验证监听端口",
                        params={}, depends_on=[4])
            ],
            user_input=user_input
        )

    def _template_security_audit(self, user_input: str) -> TaskPlan:
        """安全基线审计模板"""
        return TaskPlan(
            intent=PlanType.SECURITY_AUDIT,
            strategy="7项安全基线审计: 用户→SUID→crontab→内核→密码→认证→会话",
            steps=[
                TaskStep(id=1, tool="security_user_audit", description="审计用户权限", params={}),
                TaskStep(id=2, tool="security_suid_scan", description="扫描SUID", params={}),
                TaskStep(id=3, tool="security_crontab_audit", description="审计定时任务", params={}),
                TaskStep(id=4, tool="security_kernel_modules", description="检查内核模块", params={}),
                TaskStep(id=5, tool="security_password_policy", description="检查密码策略", params={}),
                TaskStep(id=6, tool="security_auth_failures", description="查看认证失败", params={}),
                TaskStep(id=7, tool="security_active_sessions", description="检查活跃会话", params={})
            ],
            user_input=user_input
        )

    def _template_oom_diagnosis(self, user_input: str) -> TaskPlan:
        """OOM 排查模板"""
        return TaskPlan(
            intent=PlanType.OOM_DIAGNOSIS,
            strategy="OOM历史→内存TOP→Swap→内存总览",
            steps=[
                TaskStep(id=1, tool="memory_oom_history", description="查看OOM历史", params={}),
                TaskStep(id=2, tool="process_top_memory", description="内存TOP10",
                        params={"top_n": 10}),
                TaskStep(id=3, tool="swap_info", description="查看Swap", params={}),
                TaskStep(id=4, tool="memory_info", description="内存总览", params={})
            ],
            user_input=user_input
        )

    def _template_network_diagnosis(self, user_input: str) -> TaskPlan:
        """网络诊断模板"""
        return TaskPlan(
            intent=PlanType.NETWORK_DIAGNOSIS,
            strategy="ping→DNS→端口→TCP重传→网卡",
            steps=[
                TaskStep(id=1, tool="network_ping", description="连通性测试", params={}),
                TaskStep(id=2, tool="network_dns_check", description="DNS检查",
                        params={"domain": "baidu.com"}),
                TaskStep(id=3, tool="network_listening_ports", description="监听端口", params={}),
                TaskStep(id=4, tool="network_tcp_retrans", description="TCP重传率", params={}),
                TaskStep(id=5, tool="network_interface_stats", description="网卡状态", params={})
            ],
            user_input=user_input
        )

    def _template_swap_diagnosis(self, user_input: str) -> TaskPlan:
        """Swap 抖动诊断模板"""
        return TaskPlan(
            intent=PlanType.SWAP_DIAGNOSIS,
            strategy="Swap→内存→TOP进程→VMstat→OOM历史",
            steps=[
                TaskStep(id=1, tool="swap_info", description="Swap状态", params={}),
                TaskStep(id=2, tool="memory_info", description="内存总览", params={}),
                TaskStep(id=3, tool="process_top_memory", description="内存TOP10",
                        params={"top_n": 10}),
                TaskStep(id=4, tool="vmstat_stats", description="虚拟内存统计", params={}),
                TaskStep(id=5, tool="memory_oom_history", description="OOM历史", params={})
            ],
            user_input=user_input
        )

    def _template_fd_leak(self, user_input: str) -> TaskPlan:
        """FD 泄漏排查模板"""
        return TaskPlan(
            intent=PlanType.FD_LEAK,
            strategy="打开文件→系统FD上限→进程详情",
            steps=[
                TaskStep(id=1, tool="security_open_files", description="查看打开文件", params={}),
                TaskStep(id=2, tool="system_info", description="系统信息", params={}),
                TaskStep(id=3, tool="process_top_cpu", description="TOP进程", params={"top_n": 10})
            ],
            user_input=user_input
        )
