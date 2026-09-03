# backend/app/services/unsplash_service.py
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.models.common_model import Attraction

logger = logging.getLogger(__name__)

DEFAULT_PLACEHOLDER_IMAGES = [
    "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=800&h=600&fit=crop",
    "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?w=800&h=600&fit=crop",
    "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=800&h=600&fit=crop",
    "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&h=600&fit=crop",
    "https://images.unsplash.com/photo-1523906834658-6e24ef2386f9?w=800&h=600&fit=crop",
]


class UnsplashService:
    """Unsplash image search with retry, cache, and graceful fallback."""

    def __init__(self, access_key: Optional[str], cache_size: int = 1000):
        self.access_key = access_key
        self.base_url = "https://api.unsplash.com"
        self.cache_size = cache_size
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.session = self._create_session()
        logger.info("Unsplash service initialized", extra={"cache_size": cache_size})

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def search_photos(self, query: str, per_page: int = 10, use_cache: bool = True) -> List[Dict]:
        if use_cache:
            return self._search_photos_cached(query, per_page)
        return self._search_photos_internal(query, per_page)

    @lru_cache(maxsize=1000)
    def _search_photos_cached(self, query: str, per_page: int = 10) -> List[Dict]:
        logger.debug("Searching photos from cache", extra={"query": query, "per_page": per_page})
        return self._search_photos_internal(query, per_page)

    def _search_photos_internal(self, query: str, per_page: int = 10) -> List[Dict]:
        if not self.access_key:
            logger.warning("Unsplash access key missing, skipping remote image search")
            return []

        try:
            logger.info("Searching Unsplash images", extra={"query": query, "per_page": per_page})
            response = self.session.get(
                f"{self.base_url}/search/photos",
                params={
                    "query": query,
                    "per_page": per_page,
                    "client_id": self.access_key,
                },
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
                timeout=10,
            )
            response.raise_for_status()

            results = response.json().get("results", [])
            photos = [
                {
                    "url": result["urls"]["regular"],
                    "description": result.get("description", ""),
                    "photographer": result["user"]["name"],
                }
                for result in results
            ]
            logger.info("Unsplash images found", extra={"query": query, "count": len(photos)})
            return photos
        except requests.RequestException as exc:
            logger.warning("Unsplash request failed", extra={"query": query, "error": str(exc)})
            return []
        except Exception as exc:
            logger.error("Unsplash image search failed", extra={"query": query, "error": str(exc)})
            return []

    def _build_query_candidates(self, query: str) -> List[str]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []

        candidates: List[str] = [normalized_query]
        query_parts = normalized_query.split()

        if len(query_parts) > 1:
            city_query = query_parts[-1]
            attraction_query = " ".join(query_parts[:-1]).strip()
            if attraction_query:
                candidates.append(attraction_query)
                candidates.append(f"{attraction_query} landmark")
            candidates.append(f"{city_query} landmark")
            candidates.append(f"{city_query} attraction")
            candidates.append(city_query)

        seen: set[str] = set()
        deduped_candidates: List[str] = []
        for candidate in candidates:
            if candidate and candidate not in seen:
                deduped_candidates.append(candidate)
                seen.add(candidate)
        return deduped_candidates

    def _resolve_first_photo_url(
        self,
        query: str,
        *,
        use_cache: bool,
    ) -> Optional[str]:
        search = self._search_photos_cached if use_cache else self._search_photos_internal

        for candidate in self._build_query_candidates(query):
            photos = search(candidate, per_page=1)
            if photos:
                logger.info(
                    "Resolved attraction image",
                    extra={"query": query, "resolved_query": candidate},
                )
                return photos[0].get("url")

        return None

    @lru_cache(maxsize=2000)
    def get_photo_url(self, query: str, use_fallback: bool = True) -> Optional[str]:
        logger.debug("Getting photo URL", extra={"query": query})

        resolved_url = self._resolve_first_photo_url(query, use_cache=True)
        if resolved_url:
            return resolved_url

        if use_fallback:
            logger.warning("Image search failed, using placeholder", extra={"query": query})
            return self._get_placeholder_image(query)

        logger.warning("Image search failed without fallback", extra={"query": query})
        return None

    def get_photo_url_async(self, query: str, use_fallback: bool = True) -> Optional[str]:
        return self.get_photo_url(query, use_fallback)

    def build_attraction_query(self, attraction_name: str, destination: str) -> str:
        attraction_name = " ".join((attraction_name or "").split())
        destination = " ".join((destination or "").split())
        return " ".join(part for part in [attraction_name, destination] if part)

    async def fetch_images_batch(
        self,
        queries: List[str],
        use_fallback: bool = True,
        use_cache: bool = True,
    ) -> List[Optional[str]]:
        loop = asyncio.get_event_loop()
        resolver = self.get_photo_url_async if use_cache else self._get_photo_url_without_cache
        tasks = [
            loop.run_in_executor(
                self.executor,
                resolver,
                query,
                use_fallback,
            )
            for query in queries
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results: List[Optional[str]] = []
        for index, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Batch image fetch failed", extra={"query": queries[index], "error": str(result)})
                final_results.append(self._get_placeholder_image(queries[index]) if use_fallback else None)
            else:
                final_results.append(result)

        logger.info(
            "Batch image fetch completed",
            extra={
                "success_count": len([item for item in final_results if item]),
                "total_count": len(queries),
            },
        )
        return final_results

    def enrich_attractions(
        self,
        attractions: List[Attraction],
        destination: str,
        use_fallback: bool = True,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        if not attractions:
            return {
                "total_attractions": 0,
                "unique_queries": 0,
                "resolved_count": 0,
                "empty_count": 0,
            }

        attraction_queries: List[str] = []
        unique_queries: List[str] = []
        seen_queries: set[str] = set()
        for attraction in attractions:
            query = self.build_attraction_query(attraction.name, destination)
            attraction_queries.append(query)
            if query and query not in seen_queries:
                unique_queries.append(query)
                seen_queries.add(query)

        image_url_by_query: Dict[str, Optional[str]] = {}
        if unique_queries:
            image_urls = asyncio.run(
                self.fetch_images_batch(
                    queries=unique_queries,
                    use_fallback=use_fallback,
                    use_cache=use_cache,
                )
            )
            image_url_by_query = dict(zip(unique_queries, image_urls))

        resolved_count = 0
        empty_count = 0
        for attraction, query in zip(attractions, attraction_queries):
            image_url = image_url_by_query.get(query)
            if image_url:
                attraction.image_urls = [image_url]
                resolved_count += 1
            else:
                attraction.image_urls = []
                empty_count += 1

        stats = {
            "total_attractions": len(attractions),
            "unique_queries": len(unique_queries),
            "resolved_count": resolved_count,
            "empty_count": empty_count,
        }
        logger.info("Attraction image enrichment completed", extra=stats)
        return stats

    def _get_photo_url_without_cache(self, query: str, use_fallback: bool = True) -> Optional[str]:
        resolved_url = self._resolve_first_photo_url(query, use_cache=False)
        if resolved_url:
            return resolved_url

        return self._get_placeholder_image(query) if use_fallback else None

    def _get_placeholder_image(self, seed: str) -> str:
        index = abs(hash(seed)) % len(DEFAULT_PLACEHOLDER_IMAGES)
        return DEFAULT_PLACEHOLDER_IMAGES[index]

    def clear_cache(self):
        self._search_photos_cached.cache_clear()
        self.get_photo_url.cache_clear()
        logger.info("Unsplash cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        return {
            "search_photos_cache_info": self._search_photos_cached.cache_info()._asdict(),
            "get_photo_url_cache_info": self.get_photo_url.cache_info()._asdict(),
        }
