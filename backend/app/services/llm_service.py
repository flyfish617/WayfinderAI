import os
import threading
from typing import Iterator, Literal, Optional

from openai import OpenAI

from ..config import settings
from ..observability.logger import default_logger as logger

Provider = Literal["openai", "zhipu", "modelscope", "ollama", "vllm", "custom"]


def _empty_usage_stats() -> dict[str, int]:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "request_count": 0,
    }

class LLMService:
    """
    一个智能的、支持多服务商的LLM服务。
    它能根据环境变量自动检测并配置LLM提供商。
    """
    def __init__(self,
                 temperature: float = 0.7,
                 max_tokens: int = 4096,
                 timeout: Optional[int] = None,
                 **kwargs):
        """
        初始化服务，自动检测并配置客户端。
        """
        self.provider: Provider = "custom"
        self.api_key: str | None = None
        self.base_url: str | None = None
        self.model: str | None = None


        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout or int(os.getenv("LLM_TIMEOUT", "60"))
        self.kwargs = kwargs
        self._usage_lock = threading.Lock()
        self._usage_by_key: dict[str, dict[str, int]] = {}
        self._current_usage_key: Optional[str] = None
        # 核心逻辑：自动检测和解析凭证
        self._auto_detect_provider()
        self._resolve_credentials()

        if not self.api_key:
            logger.warning("LLM API Key 未配置，LLM服务可能无法正常工作。")

        # 初始化OpenAI客户端（兼容多种服务）
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=settings.LLM_TIMEOUT
        )
        # 思考模式控制：仅对支持 enable_thinking 的服务商生效（ModelScope/DashScope 等），
        # OpenAI 官方 API 会拒绝未知参数，需排除
        self._extra_body: dict = (
            {"enable_thinking": bool(settings.LLM_ENABLE_THINKING)}
            if self.provider != "openai"
            else {}
        )
        logger.info(f"LLM服务初始化完成。Provider: {self.provider}, Model: {self.model}, Base URL: {self.base_url}")

    def _auto_detect_provider(self):
        """
        根据环境变量自动推断LLM服务商。
        """
        # 最高优先级：根据 base_url 进行判断
        base_url = settings.LLM_BASE_URL
        if base_url:
            if "api.openai.com" in base_url: self.provider = "openai"; return
            if "open.bigmodel.cn" in base_url: self.provider = "zhipu"; return
            if "api-inference.modelscope.cn" in base_url: self.provider = "modelscope"; return
            if ":11434" in base_url: self.provider = "ollama"; return
            if ":8000" in base_url: self.provider = "vllm"; return # 假设vllm在8000端口

        # 次高优先级：检查特定服务商的环境变量
        if settings.OPENAI_API_KEY: self.provider = "openai"; return
        if settings.ZHIPU_API_KEY: self.provider = "zhipu"; return
        if settings.MODELSCOPE_API_KEY: self.provider = "modelscope"; return

        # 辅助判断：分析通用API密钥格式 (示例)
        api_key = settings.LLM_API_KEY
        if api_key:
            if api_key.startswith("sk-"): self.provider = "openai"; return
            # Zhipu和ModelScope的key格式不如此独特，此处省略以避免误判

        logger.info("未能自动检测到特定的LLM Provider，将使用 'custom' 模式。")

    def _resolve_credentials(self):
        """
        根据检测到的服务商，解析并设置最终的api_key, base_url, 和 model。
        """
        # 1. 解析API Key
        provider_key = getattr(settings, f"{self.provider.upper()}_API_KEY", None)
        self.api_key = provider_key or settings.LLM_API_KEY

        # 2. 解析Base URL
        if self.provider == "openai" and not settings.LLM_BASE_URL:
            self.base_url = "https://api.openai.com/v1"
        elif self.provider == "zhipu" and not settings.LLM_BASE_URL:
            self.base_url = "https://open.bigmodel.cn/api/paas/v4/"
        elif self.provider == "modelscope" and not settings.LLM_BASE_URL:
            self.base_url = "https://api-inference.modelscope.cn/v1"
        else:
            self.base_url = settings.LLM_BASE_URL

        # 3. 解析模型ID
        self.model = settings.LLM_MODEL_ID or "gpt-4-turbo" # 提供一个默认值

    def reset_usage_stats(self, usage_key: str) -> None:
        with self._usage_lock:
            self._usage_by_key[usage_key] = _empty_usage_stats()
        # 流式调用无法逐请求传usage_key，记录当前请求key供think()使用
        self._current_usage_key = usage_key

    def get_usage_stats(self, usage_key: str) -> dict[str, int]:
        with self._usage_lock:
            stats = self._usage_by_key.get(usage_key, _empty_usage_stats())
            return dict(stats)

    def _record_usage(self, response, usage_key: Optional[str]) -> None:
        if not usage_key:
            return

        usage = getattr(response, "usage", None)
        if not usage:
            return

        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", 0) or 0)

        with self._usage_lock:
            current = self._usage_by_key.setdefault(usage_key, _empty_usage_stats())
            current["prompt_tokens"] += prompt_tokens
            current["completion_tokens"] += completion_tokens
            current["total_tokens"] += total_tokens
            current["request_count"] += 1

    def generate_json_plan(self, prompt: str) -> str:
        """
        调用LLM生成JSON格式的行程计划。此方法保持接口不变。
        """
        if not self.api_key:
            logger.error("LLM API Key 未配置，无法发起请求。")
            return ""

        logger.info(f"向LLM ({self.provider}) 发起行程规划请求...")
        try:
            usage_key = self.kwargs.get("usage_key")
            response = self.client.chat.completions.create(
                model=self.model, # 使用解析后的模型
                messages=[
                    {"role": "system", "content": "You are a helpful travel planner. You will output a travel plan in JSON format based on user requirements."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                **({"extra_body": self._extra_body} if self._extra_body else {}),
            )
            self._record_usage(response, usage_key)
            json_output = response.choices[0].message.content
            logger.info("成功从LLM获取到行程规划JSON数据。")
            return json_output or ""
        except Exception as e:
            logger.error(f"调用LLM API时发生错误: {e}", exc_info=True)
            return ""
    def think(self, messages: list[dict[str, str]], temperature: Optional[float] = None) -> Iterator[str]:
        """
        调用大语言模型进行思考，并返回流式响应。
        这是主要的调用方法，默认使用流式响应以获得更好的用户体验。

        Args:
            messages: 消息列表
            temperature: 温度参数，如果未提供则使用初始化时的值

        Yields:
            str: 流式响应的文本片段
        """
        print(f"🧠 正在调用 {self.model} 模型...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
                **({"extra_body": self._extra_body} if self._extra_body else {}),
            )

            # 处理流式响应（部分服务商会把usage放在最后一个chunk）
            print("✅ 大语言模型响应成功:")
            for chunk in response:
                if getattr(chunk, "usage", None):
                    self._record_usage(chunk, self._current_usage_key)
                content = chunk.choices[0].delta.content if chunk.choices else None
                if content:
                    print(content, end="", flush=True)
                    yield content
            print()  # 在流式输出结束后换行

        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            raise Exception(f"LLM调用失败: {str(e)}")

    def invoke(self, messages: list[dict[str, str]], **kwargs) -> str:
        """
        非流式调用LLM，返回完整响应。
        适用于不需要流式输出的场景。
        """
        try:
            usage_key = kwargs.pop('usage_key', None)
            temperature = kwargs.pop('temperature', self.temperature)
            max_tokens = kwargs.pop('max_tokens', self.max_tokens)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **({"extra_body": self._extra_body} if self._extra_body else {}),
                **kwargs
            )
            self._record_usage(response, usage_key)
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"LLM调用失败: {str(e)}")

    def stream_invoke(self, messages: list[dict[str, str]], **kwargs) -> Iterator[str]:
        """
        流式调用LLM的别名方法，与think方法功能相同。
        保持向后兼容性。
        """
        temperature = kwargs.get('temperature')
        yield from self.think(messages, temperature)
# 创建一个服务实例，FastAPI的依赖注入系统将使用它
llm_service = LLMService()
