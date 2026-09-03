"""
总规划
"""
import json
import math
from datetime import datetime
from app.models.trip_model import TripPlanRequest, TripPlanResponse
from app.models.common_model import Attraction, Hotel, Weather
from app.services.llm_service import LLMService
from app.observability.logger import default_logger as logger
from typing import Any, Callable, Dict, List, Optional, Tuple
from app.tools.mcp_tool import MCPTool
from app.config import settings
from app.services.unsplash_service import UnsplashService
from concurrent.futures import ThreadPoolExecutor, as_completed
# from app.services.memory_service import memory_service  # 替换为向量记忆服务
from app.services.vector_memory_service import VectorMemoryService
from app.services.context_manager import ContextManager, get_context_manager
from app.services.city_service import city_support_service
from app.services.redis_service import redis_service
from app.agents.agent_communication import communication_hub
from app.agents.specialized_agents import (
    AttractionSearchAgent,
    HotelRecommendationAgent,
    WeatherQueryAgent,
    PlannerAgent as EnhancedPlannerAgent
)
from hello_agents import ToolRegistry
from app.observability.logger import get_request_id

# 主要城市的经纬度范围（用于验证）- 扩展至30个热门旅游城市
CITY_BOUNDS = {
    # 一线城市
    "北京": {"lat_min": 39.4, "lat_max": 41.1, "lng_min": 115.7, "lng_max": 117.4},
    "上海": {"lat_min": 30.7, "lat_max": 31.9, "lng_min": 120.8, "lng_max": 122.2},
    "广州": {"lat_min": 22.7, "lat_max": 23.8, "lng_min": 112.9, "lng_max": 114.0},
    "深圳": {"lat_min": 22.4, "lat_max": 22.9, "lng_min": 113.7, "lng_max": 114.6},
    
    # 新一线城市
    "成都": {"lat_min": 30.4, "lat_max": 30.9, "lng_min": 103.9, "lng_max": 104.5},
    "杭州": {"lat_min": 30.0, "lat_max": 30.5, "lng_min": 119.5, "lng_max": 120.5},
    "重庆": {"lat_min": 29.3, "lat_max": 29.9, "lng_min": 106.2, "lng_max": 106.8},
    "武汉": {"lat_min": 30.3, "lat_max": 31.0, "lng_min": 113.9, "lng_max": 114.6},
    "西安": {"lat_min": 34.0, "lat_max": 34.5, "lng_min": 108.7, "lng_max": 109.2},
    "苏州": {"lat_min": 31.1, "lat_max": 31.5, "lng_min": 120.3, "lng_max": 121.0},
    "天津": {"lat_min": 38.9, "lat_max": 39.6, "lng_min": 116.9, "lng_max": 117.9},
    "南京": {"lat_min": 31.9, "lat_max": 32.2, "lng_min": 118.4, "lng_max": 119.2},
    "长沙": {"lat_min": 28.1, "lat_max": 28.4, "lng_min": 112.8, "lng_max": 113.2},
    "郑州": {"lat_min": 34.4, "lat_max": 34.9, "lng_min": 113.4, "lng_max": 113.9},
    
    # 热门旅游城市
    "厦门": {"lat_min": 24.4, "lat_max": 24.6, "lng_min": 118.0, "lng_max": 118.2},
    "青岛": {"lat_min": 35.9, "lat_max": 36.4, "lng_min": 119.9, "lng_max": 120.7},
    "大连": {"lat_min": 38.7, "lat_max": 39.2, "lng_min": 121.3, "lng_max": 122.0},
    "三亚": {"lat_min": 18.1, "lat_max": 18.4, "lng_min": 109.3, "lng_max": 109.7},
    "丽江": {"lat_min": 26.8, "lat_max": 27.2, "lng_min": 100.1, "lng_max": 100.5},
    "桂林": {"lat_min": 25.1, "lat_max": 25.5, "lng_min": 110.1, "lng_max": 110.6},
    "昆明": {"lat_min": 24.7, "lat_max": 25.3, "lng_min": 102.5, "lng_max": 103.1},
    "哈尔滨": {"lat_min": 45.5, "lat_max": 46.0, "lng_min": 126.4, "lng_max": 127.1},
    "沈阳": {"lat_min": 41.5, "lat_max": 42.0, "lng_min": 123.2, "lng_max": 123.8},
    "济南": {"lat_min": 36.5, "lat_max": 36.8, "lng_min": 116.8, "lng_max": 117.3},
    
    # 特色旅游城市
    "黄山": {"lat_min": 29.8, "lat_max": 30.2, "lng_min": 118.1, "lng_max": 118.5},
    "张家界": {"lat_min": 28.9, "lat_max": 29.3, "lng_min": 110.2, "lng_max": 110.7},
    "敦煌": {"lat_min": 39.8, "lat_max": 40.3, "lng_min": 94.4, "lng_max": 95.1},
    "拉萨": {"lat_min": 29.5, "lat_max": 30.0, "lng_min": 90.9, "lng_max": 91.5},
    "乌鲁木齐": {"lat_min": 43.7, "lat_max": 44.2, "lng_min": 87.4, "lng_max": 88.0},
    "宁波": {"lat_min": 29.8, "lat_max": 30.0, "lng_min": 121.3, "lng_max": 121.8},
}
# 注意：Agent提示词已移至 specialized_agents.py
class PlannerAgent:
    """
    行程规划专家 (Orchestrator) - 增强版
    负责协调多个增强智能体，整合信息，并生成最终的行程计划。
    支持记忆、上下文、智能体间通信等功能。
    """
    def __init__(self, llm_service: LLMService, memory_service: VectorMemoryService = None):
        self.llm = LLMService()
        self.settings = settings
        self.unsplash_service = UnsplashService(settings.UNSPLASH_ACCESS_KEY)
        self.memory_service = memory_service or VectorMemoryService()
        # 用于工具查询结果缓存（景点/酒店/天气）
        self.redis_service = redis_service
        
        # 创建工具注册表
        self.tool_registry = ToolRegistry()
        
        # 创建高德地图工具
        self.amap_tool = MCPTool(
                name="amap",
                description="高德地图服务",
                server_command=["uvx", "amap-mcp-server"],
                env={"AMAP_MAPS_API_KEY": settings.AMAP_API_KEY},
                auto_expand=True
            )
        self.tool_registry.register_tool(self.amap_tool)
        # 关键修复：将MCP展开后的子工具一并注册，确保可直接调用
        # 例如: amap_maps_text_search / amap_maps_weather
        for expanded_tool in self.amap_tool.get_expanded_tools():
            self.tool_registry.register_tool(expanded_tool)
        
        logger.info("✅ 多智能体系统初始化完成（增强版）")
    def _validate_location_in_city(self, lat: float, lng: float, city: str) -> bool:
        """
        验证位置是否在指定城市范围内
        
        Args:
            lat: 纬度
            lng: 经度
            city: 城市名称
        
        Returns:
            是否在范围内
        """
        bounds = city_support_service.get_bounds(city) or CITY_BOUNDS.get(city)
        if not bounds:
            logger.warning(
                f"⚠️ 城市 '{city}' 暂无可用边界配置，该城市无法进行地理精校验。"
            )
            return False
        is_valid = (
            bounds["lat_min"] <= lat <= bounds["lat_max"] and
            bounds["lng_min"] <= lng <= bounds["lng_max"]
        )
        
        if not is_valid:
            logger.warning(
                f"⚠️ 位置 ({lat}, {lng}) 不在城市 '{city}' 的合理范围内，该景点可能不属于目标城市"
            )
        
        return is_valid
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        计算两点之间的距离（公里）
        
        Args:
            lat1, lng1: 第一个点的经纬度
            lat2, lng2: 第二个点的经纬度
        
        Returns:
            距离（公里）
        """
        # 使用Haversine公式计算两点间距离
        R = 6371  # 地球半径（公里）
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        return R * c
    
    def _validate_and_filter_plan(self, plan: TripPlanResponse, destination: str) -> TripPlanResponse:
        """
        验证并过滤行程计划，移除不在目标城市范围内的景点
        
        Args:
            plan: 行程计划
            destination: 目标城市
        
        Returns:
            验证后的行程计划
        """
        filtered_days = []
        removed_count = 0
        
        for day in plan.days:
            # 过滤景点
            valid_attractions = []
            for attraction in day.attractions:
                if attraction.location:
                    lat = float(attraction.location.lat)
                    lng = float(attraction.location.lng)
                    
                    if self._validate_location_in_city(lat, lng, destination):
                        valid_attractions.append(attraction)
                    else:
                        removed_count += 1
                        logger.warning(
                            f"移除不在目标城市范围内的景点: {attraction.name} "
                            f"(位置: {lat}, {lng}, 目标城市: {destination})"
                        )
                else:
                    # 没有位置信息的景点也移除
                    removed_count += 1
                    logger.warning(f"移除没有位置信息的景点: {attraction.name}")
            
            # 验证同一天景点距离
            if len(valid_attractions) > 1:
                for i in range(len(valid_attractions) - 1):
                    att1 = valid_attractions[i]
                    att2 = valid_attractions[i + 1]
                    if att1.location and att2.location:
                        distance = self._calculate_distance(
                            float(att1.location.lat), float(att1.location.lng),
                            float(att2.location.lat), float(att2.location.lng)
                        )
                        if distance > 50:
                            logger.warning(
                                f"第{day.day}天的景点 {att1.name} 和 {att2.name} 距离较远: {distance:.2f}公里"
                            )
            
            # 过滤餐饮
            valid_dinings = []
            for dining in day.dinings:
                if dining.location:
                    lat = float(dining.location.lat)
                    lng = float(dining.location.lng)
                    if self._validate_location_in_city(lat, lng, destination):
                        valid_dinings.append(dining)
                    else:
                        logger.warning(f"移除不在目标城市范围内的餐饮: {dining.name}")
            
            # 验证酒店
            if day.recommended_hotel and day.recommended_hotel.location:
                lat = float(day.recommended_hotel.location.lat)
                lng = float(day.recommended_hotel.location.lng)
                if not self._validate_location_in_city(lat, lng, destination):
                    logger.warning(f"第{day.day}天的推荐酒店不在目标城市范围内: {day.recommended_hotel.name}")
                    day.recommended_hotel = None
            
            # 更新过滤后的数据
            day.attractions = valid_attractions
            day.dinings = valid_dinings
            filtered_days.append(day)
        
        # 验证相邻天景点距离
        for i in range(len(filtered_days) - 1):
            day1 = filtered_days[i]
            day2 = filtered_days[i + 1]
            
            if day1.attractions and day2.attractions:
                last_att_day1 = day1.attractions[-1]
                first_att_day2 = day2.attractions[0]
                
                if last_att_day1.location and first_att_day2.location:
                    distance = self._calculate_distance(
                        float(last_att_day1.location.lat), float(last_att_day1.location.lng),
                        float(first_att_day2.location.lat), float(first_att_day2.location.lng)
                    )
                    if distance > 100:
                        logger.warning(
                            f"第{day1.day}天和第{day2.day}天的景点距离较远: {distance:.2f}公里"
                        )
        
        plan.days = filtered_days
        
        if removed_count > 0:
            logger.info(f"已移除 {removed_count} 个不在目标城市范围内的景点")
        
        return plan
    
    def _synthesize_agent_output(
        self,
        *,
        role_name: str,
        raw_result: str,
        request: TripPlanRequest,
        output_schema: str,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt = f"""
        你是多智能体协作流程中的结构化整理器。
        当前任务来自 {role_name}，请将原始输出整理成严格 JSON。

        目的地: {request.destination}
        出行日期: {request.start_date} 到 {request.end_date}
        偏好: {', '.join(request.preferences or []) or '无'}
        酒店偏好: {', '.join(request.hotel_preferences or []) or '无'}
        预算: {request.budget}

        输出要求:
        1. 只返回 JSON 对象。
        2. 保留不确定性，无法确认时放入 warnings。
        3. 不要编造原始结果中没有的明确事实。
        4. location 中的经纬度如果无法确定则置为 null。

        JSON 结构:
        {output_schema}

        原始结果:
        {raw_result}
        """

        fallback_payload = {"summary": raw_result[:500], "warnings": ["structured_parse_failed"], "items": []}
        try:
            response = self.llm.invoke(
                [
                    {"role": "system", "content": "You convert agent outputs into strict JSON for downstream orchestration."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                usage_key=request_id,
            )
            return json.loads(response)
        except Exception as exc:
            logger.warning(
                "Failed to synthesize structured agent output",
                extra={"role_name": role_name, "error": str(exc)},
            )
            return fallback_payload

    def _build_structured_collaboration_payload(
        self,
        request: TripPlanRequest,
        *,
        attractions_raw: str,
        hotels_raw: str,
        weather_raw: str,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        attraction_schema = """
        {
          "summary": "string",
          "warnings": ["string"],
          "items": [
            {
              "name": "string",
              "type": "string",
              "address": "string",
              "location": {"lat": 0, "lng": 0}
            }
          ]
        }
        """
        hotel_schema = """
        {
          "summary": "string",
          "warnings": ["string"],
          "items": [
            {
              "name": "string",
              "address": "string",
              "price": "string",
              "rating": "string",
              "location": {"lat": 0, "lng": 0}
            }
          ]
        }
        """
        weather_schema = """
        {
          "summary": "string",
          "warnings": ["string"],
          "forecast": [
            {
              "date": "YYYY-MM-DD",
              "day_weather": "string",
              "night_weather": "string",
              "day_temp": "string",
              "night_temp": "string",
              "day_wind": "string",
              "night_wind": "string"
            }
          ]
        }
        """

        return {
            "attractions": self._synthesize_agent_output(
                role_name="attraction_agent",
                raw_result=attractions_raw,
                request=request,
                output_schema=attraction_schema,
                request_id=request_id,
            ),
            "hotels": self._synthesize_agent_output(
                role_name="hotel_agent",
                raw_result=hotels_raw,
                request=request,
                output_schema=hotel_schema,
                request_id=request_id,
            ),
            "weather": self._synthesize_agent_output(
                role_name="weather_agent",
                raw_result=weather_raw,
                request=request,
                output_schema=weather_schema,
                request_id=request_id,
            ),
        }

    def _construct_prompt(self, request: TripPlanRequest, attractions: Dict[str, Any], hotels: Dict[str, Any], weather: Dict[str, Any]) -> str:
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(request.end_date, "%Y-%m-%d")
        duration = (end_date - start_date).days + 1

        # attraction_details = [f"- {a.name} (评分: {a.rating}, 类型: {a.type})" for a in attractions]
        # hotel_details = [f"- {h.name} (价格: {h.price}, 评分: {h.rating})" for h in hotels]
        # weather_details = [f"- {w.date}: {w.day_weather}, {w.day_temp}°C" for w in weather]

        prompt = f"""
        请为我创建一个前往 {request.destination} 的旅行计划。

        **基本信息:**
        - 旅行天数: {duration} 天 (从 {request.start_date} 到 {request.end_date})
        - 预算水平: {request.budget}
        - 个人偏好: {', '.join(request.preferences) if request.preferences else '无'}
        - 酒店偏好: {', '.join(request.hotel_preferences) if request.hotel_preferences else '无'}

        **可用资源:**
        - **结构化景点候选:**\n{json.dumps(attractions, ensure_ascii=False, indent=2)}
        - **结构化酒店候选:**\n{json.dumps(hotels, ensure_ascii=False, indent=2)}
        - **结构化天气信息:**\n{json.dumps(weather, ensure_ascii=False, indent=2)}

        **输出要求:**
        1. 严格按照系统提示中给定的 JSON 结构和字段名生成行程计划。
        2. 你的输出必须是一个完整的 JSON 对象，包含：
           - trip_title
           - total_budget（含 transport_cost / dining_cost / hotel_cost / attraction_ticket_cost / total）
           - hotels
           - days（其中包含 recommended_hotel / attractions / dinings / budget 等字段）
        3. 不要输出任何额外的解释或 Markdown，只输出 JSON。
        """
        return prompt

    def _build_attraction_query(self, request: TripPlanRequest) -> str:
        """构建景点搜索查询 - 直接包含工具调用"""
        keywords = []
        if request.preferences:
            # 只取第一个偏好作为关键词
            keywords = request.preferences[0]
        else:
            keywords = "景点"

        # 直接返回工具调用格式
        query = f"请使用amap_maps_text_search工具搜索{request.destination}的{keywords}相关景点。\n[TOOL_CALL:amap_maps_text_search:keywords={keywords},city={request.destination}]"
        return query
    def _build_hotel_query(self, request: TripPlanRequest) -> str:
        """构建酒店搜索查询 - 直接包含工具调用"""

        query = f"请使用amap_maps_text_search工具搜索{request.destination}的酒店。请确保返回的酒店信息详细且准确。\n[TOOL_CALL:amap_maps_text_search:keywords=酒店,city={request.destination}]"
        return query

    # ============ 工具直连查询（性能优化：绕过专家LLM） ============

    _TOOL_CACHE_PREFIX = "toolcache"

    def _fetch_tool_data_direct(self, request: TripPlanRequest) -> Dict[str, str]:
        """
        直接调用高德 MCP 工具获取景点/酒店/天气原始数据（不经过LLM）。

        - 单次 MCP 连接顺序调用，避免 uvx 子进程多次冷启动
        - 结果写入 Redis 缓存：POI 6 小时 / 天气 3 小时

        Returns:
            {"attractions": raw_str, "hotels": raw_str, "weather": raw_str}
        """
        import asyncio
        from ..tools.client import MCPClient

        pref_keyword = ((request.preferences[0] if request.preferences else "") or "景点").strip() or "景点"

        specs: Dict[str, Dict[str, Any]] = {
            "attractions": {
                "tool": "maps_text_search",
                "args": {"keywords": pref_keyword, "city": request.destination, "citylimit": "true"},
                "ttl": 6 * 3600,
                "cache_key": f"{self._TOOL_CACHE_PREFIX}:attractions:{request.destination}:{pref_keyword}",
            },
            "hotels": {
                "tool": "maps_text_search",
                "args": {"keywords": "酒店", "city": request.destination, "citylimit": "true"},
                "ttl": 6 * 3600,
                "cache_key": f"{self._TOOL_CACHE_PREFIX}:hotels:{request.destination}:酒店",
            },
            "weather": {
                "tool": "maps_weather",
                "args": {"city": request.destination},
                "ttl": 3 * 3600,
                "cache_key": f"{self._TOOL_CACHE_PREFIX}:weather:{request.destination}",
            },
        }

        results: Dict[str, str] = {}
        missing: Dict[str, Dict[str, Any]] = {}

        # 1. 先查缓存
        for name, spec in specs.items():
            cached = self.redis_service.get_cached_json(spec["cache_key"])
            if cached is not None:
                results[name] = cached if isinstance(cached, str) else json.dumps(cached, ensure_ascii=False)
                logger.info(f"工具数据缓存命中: {name}")
            else:
                missing[name] = spec

        # 2. 未命中的走一次 MCP 连接顺序查询
        if missing:
            async def _run_queries() -> Dict[str, str]:
                fetched: Dict[str, str] = {}
                async with MCPClient(self.amap_tool.server_command, env=self.amap_tool.env) as client:
                    for name, spec in missing.items():
                        try:
                            result = await client.call_tool(spec["tool"], spec["args"])
                            fetched[name] = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                        except Exception as exc:
                            logger.error(f"MCP工具调用失败: {spec['tool']} | {exc}")
                            fetched[name] = ""
                return fetched

            fetched = asyncio.run(_run_queries())
            for name, raw in fetched.items():
                results[name] = raw
                if raw:
                    spec = missing[name]
                    self.redis_service.set_cached_json(spec["cache_key"], raw, spec["ttl"])

        for name in specs:
            results.setdefault(name, "")
        return results

    def _parse_amap_location(self, raw_location: Any) -> Optional[Dict[str, float]]:
        """高德POI的location为"lng,lat"字符串（或dict），转为{lat,lng}；失败返回None"""
        try:
            if isinstance(raw_location, dict):
                lat, lng = raw_location.get("lat"), raw_location.get("lng")
                if lat is None or lng is None:
                    return None
                return {"lat": float(lat), "lng": float(lng)}
            if isinstance(raw_location, str) and "," in raw_location:
                lng_str, lat_str = raw_location.split(",", 1)
                return {"lat": float(lat_str), "lng": float(lng_str)}
        except (TypeError, ValueError):
            pass
        return None

    def _extract_amap_items(self, raw: str, list_keys: tuple) -> list:
        """从工具返回文本提取列表（兼容 dict 包裹与纯数组两种格式）"""
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("工具返回内容不是合法JSON，跳过解析")
            return []
        if isinstance(data, dict):
            # MCP返回可能被包一层（如 ToolResult 序列化），逐层找列表字段
            for key in list_keys:
                value = data.get(key)
                if isinstance(value, list):
                    return value
            for value in data.values():
                if isinstance(value, dict):
                    for key in list_keys:
                        if isinstance(value.get(key), list):
                            return value[key]
            return []
        if isinstance(data, list):
            return data
        return []

    def _parse_tool_data(self, request: TripPlanRequest, tool_results: Dict[str, str]) -> Dict[str, Any]:
        """
        纯代码解析高德工具返回，构造协作payload（替代原LLM结构化整理器，零信息损失）。
        输出结构与 _build_structured_collaboration_payload 的schema保持一致。
        """
        # 景点
        attraction_items = []
        for poi in self._extract_amap_items(tool_results.get("attractions", ""), ("pois", "results", "data", "list"))[:20]:
            attraction_items.append({
                "name": poi.get("name", ""),
                "type": poi.get("type", ""),
                "address": poi.get("address", "") or "",
                "location": self._parse_amap_location(poi.get("location")),
            })
        attractions_payload = {
            "summary": f"高德POI搜索: {request.destination}，偏好[{', '.join(request.preferences or []) or '无'}]，共{len(attraction_items)}条",
            "warnings": [] if attraction_items else ["attractions_empty"],
            "items": attraction_items,
        }

        # 酒店
        hotel_items = []
        for poi in self._extract_amap_items(tool_results.get("hotels", ""), ("pois", "results", "data", "list"))[:10]:
            hotel_items.append({
                "name": poi.get("name", ""),
                "address": poi.get("address", "") or "",
                "price": str(poi.get("price", "N/A")),
                "rating": str(poi.get("rating", "N/A")),
                "location": self._parse_amap_location(poi.get("location")),
            })
        hotels_payload = {
            "summary": f"高德酒店搜索: {request.destination}，共{len(hotel_items)}条",
            "warnings": [] if hotel_items else ["hotels_empty"],
            "items": hotel_items,
        }

        # 天气
        weather_data = None
        raw_weather = tool_results.get("weather", "")
        if raw_weather:
            try:
                weather_data = json.loads(raw_weather)
            except (json.JSONDecodeError, TypeError):
                weather_data = None
        forecast_items = []
        if isinstance(weather_data, dict):
            forecasts = weather_data.get("forecasts") or weather_data.get("forecast") or []
            if isinstance(forecasts, dict):
                forecasts = forecasts.get("list", [])
            for fc in forecasts[:10] if isinstance(forecasts, list) else []:
                forecast_items.append({
                    "date": fc.get("date", ""),
                    "day_weather": fc.get("dayweather", ""),
                    "night_weather": fc.get("nightweather", ""),
                    "day_temp": fc.get("daytemp", ""),
                    "night_temp": fc.get("nighttemp", ""),
                    "day_wind": f"{fc.get('daywind', '')}{fc.get('daypower', '')}".strip() or "N/A",
                    "night_wind": f"{fc.get('nightwind', '')}{fc.get('nightpower', '')}".strip() or "N/A",
                })
        weather_payload = {
            "summary": f"高德天气预报: {request.destination}，共{len(forecast_items)}天",
            "warnings": [] if forecast_items else ["weather_empty"],
            "forecast": forecast_items,
        }

        return {
            "attractions": attractions_payload,
            "hotels": hotels_payload,
            "weather": weather_payload,
        }
    
    def plan_trip(
        self,
        request: TripPlanRequest,
        user_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> TripPlanResponse | None:
        """
        规划行程（增强版）
        
        Args:
            request: 行程规划请求
            user_id: 用户ID（用于记忆检索）
            progress_callback: 进度回调 progress_callback(progress_percent, message)
        
        Returns:
            行程规划响应
        """
        def _report(progress: int, message: str) -> None:
            if not progress_callback:
                return
            try:
                progress_callback(progress, message)
            except Exception:
                logger.debug("进度回调执行失败", exc_info=True)

        _report(25, "Loading user memories")
        # 获取请求ID
        request_id = get_request_id() or f"req_{datetime.now().timestamp()}"
        self.llm.reset_usage_stats(request_id)
        
        # 创建或获取上下文管理器
        context_manager = get_context_manager(request_id)
        
        # 在上下文中存储请求信息
        context_manager.share_data("request", {
            "destination": request.destination,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "preferences": request.preferences,
            "hotel_preferences": request.hotel_preferences,
            "budget": request.budget
        })
        
        # 如果没有提供user_id，使用request_id作为临时user_id
        if not user_id:
            user_id = request_id
        
        # 检索用户记忆并添加到上下文（使用向量记忆服务）
        # 构建查询文本
        query_text = f"{request.destination} {' '.join(request.preferences or [])} {request.budget}"
        
        # 检索用户记忆
        user_memories = self.memory_service.retrieve_user_memories(
            user_id=user_id,
            query=query_text,
            limit=5,
            memory_types=["preference", "trip"]
        )
        if user_memories:
            context_manager.add_memory_context("user_memories", user_memories)
            logger.info(f"已加载 {len(user_memories)} 条用户记忆 - UserID: {user_id}")
        
        # 检索相关知识记忆
        knowledge_memories = self.memory_service.retrieve_knowledge_memories(
            query=f"{request.destination} 旅行 景点 特色",
            limit=3,
            knowledge_types=["destination", "experience"]
        )
        if knowledge_memories:
            context_manager.add_memory_context("knowledge_memories", knowledge_memories)
            logger.info(f"已加载 {len(knowledge_memories)} 条知识记忆")
        
        # 创建总规划智能体（性能优化：专家数据查询不再经过LLM，直接调用高德工具）
        logger.info("创建行程规划智能体...")

        planner_agent = EnhancedPlannerAgent(
            llm=self.llm,
            context_manager=context_manager,
            communication_hub=communication_hub,
            user_id=user_id
        )

        # 执行规划流程
        try:
            # 性能优化：直接调用高德MCP工具获取景点/酒店/天气数据（原方案需6次专家LLM+3次整理LLM调用）
            logger.info("🚀 直接调用高德工具获取数据（景点/酒店/天气）...")
            _report(30, "Querying attractions/hotels/weather data")
            tool_results = self._fetch_tool_data_direct(request)
            _report(45, "Tool data fetched, structuring")
            collaboration_payload = self._parse_tool_data(request, tool_results)
            logger.info("🎯 工具数据获取与结构化完成！")

            context_manager.share_data("structured_collaboration_payload", collaboration_payload, from_agent="orchestrator")
            context_manager.share_data(
                "attraction_locations",
                collaboration_payload.get("attractions", {}).get("items", []),
                from_agent="orchestrator",
            )
            # 4. 行程规划（流式生成：LLM边生成边更新任务进度）
            logger.info("开始行程规划...")
            _report(55, "Generating trip plan with LLM")

            import time as _time
            stream_state = {"last_ts": 0.0, "last_chars": 0}

            def _stream_progress(partial_text: str) -> None:
                """节流回调：每1秒/每300字符上报一次流式生成进度"""
                now = _time.time()
                chars = len(partial_text)
                if now - stream_state["last_ts"] < 1.0 and chars - stream_state["last_chars"] < 300:
                    return
                stream_state["last_ts"] = now
                stream_state["last_chars"] = chars
                # 进度 55→69，按估算总字符(约4000/多日行程)映射
                ratio = min(1.0, chars / 4000.0)
                _report(55 + int(14 * ratio), f"AI generating: {chars} chars")

            prompt = self._construct_prompt(
                request,
                collaboration_payload["attractions"],
                collaboration_payload["hotels"],
                collaboration_payload["weather"],
            )
            json_plan_str = planner_agent.run(prompt, stream_callback=_stream_progress)

            if not json_plan_str:
                logger.error("LLM未能生成有效的行程计划JSON。")
                return None

            # 5. 解析和验证
            _report(70, "Validating plan data")
            if '```json' in json_plan_str:
                json_plan_str = json_plan_str.split('```json')[1].split('```')[0].strip()

            plan_data = json.loads(json_plan_str)
            validated_plan = TripPlanResponse.model_validate(plan_data)

            # 6. 验证和过滤地理位置
            validated_plan = self._validate_and_filter_plan(validated_plan, request.destination)
            
            # 7. Enrich attraction images after validation.
            logger.info("Starting attraction image enrichment")
            attractions = [attraction for day in validated_plan.days for attraction in day.attractions]
            if attractions:
                try:
                    image_stats = self.unsplash_service.enrich_attractions(
                        attractions=attractions,
                        destination=request.destination,
                        use_fallback=True,
                        use_cache=True,
                    )
                    logger.debug(
                        "Unsplash image enrichment stats",
                        extra={
                            "image_stats": image_stats,
                            "cache_stats": self.unsplash_service.get_cache_stats(),
                        },
                    )
                except Exception as e:
                    logger.error(f"Attraction image enrichment failed: {e}")
                    for attraction in attractions:
                        attraction.image_urls = []
            else:
                logger.info("No attractions require image enrichment")
            # 8. 存储用户偏好记忆
            _report(90, "Saving user memories")
            self.memory_service.store_user_preference(
                user_id,
                "trip_request",
                {
                    "destination": request.destination,
                    "preferences": request.preferences,
                    "hotel_preferences": request.hotel_preferences,
                    "budget": request.budget,
                    "trip_title": validated_plan.trip_title
                }
            )
            
            llm_usage = self.llm.get_usage_stats(request_id)
            context_manager.share_data("llm_usage", llm_usage, from_agent="planner")
            logger.info(
                "Trip planning LLM usage summary",
                extra={
                    "request_id": request_id,
                    "destination": request.destination,
                    "llm_usage": llm_usage,
                },
            )
            logger.info(f"成功生成并验证了行程计划: {validated_plan.trip_title}")
            
            # 清理上下文管理器（可选，也可以保留用于后续查询）
            # remove_context_manager(request_id)
            
            return validated_plan
            
        except (json.JSONDecodeError, Exception) as e:
            logger.error(
                f"解析或验证LLM返回的JSON时失败: {e}",
                exc_info=True,
                extra={
                    "request_id": request_id,
                    "destination": request.destination
                }
            )
            return None
