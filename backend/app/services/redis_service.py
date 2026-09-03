"""
Redis服务模块
提供用户数据的持久化存储
"""
import json
import hashlib
from typing import Dict, Optional, Any, List
from contextlib import contextmanager
import redis
from redis.exceptions import WatchError
import bcrypt
from app.observability.logger import default_logger as logger
from app.config import settings
import datetime


# 密码加密轮数
BCRYPT_ROUNDS = settings.BCRYPT_ROUNDS


class RedisService:
    """
    Redis服务类，负责用户数据的持久化存储
    """
    
    def __init__(self):
        """初始化Redis连接"""
        self._redis_client: Optional[redis.Redis] = None
        self._initialize_redis()
    
    def _initialize_redis(self):
        """初始化Redis连接"""
        try:
            self._redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=settings.REDIS_DECODE_RESPONSES,
                socket_connect_timeout=5,
                # socket_timeout 必须大于阻塞命令（BLPOP 等）的超时，
                # 否则空队列轮询时阻塞等待会与套接字读超时竞争，触发
                # "Timeout reading from socket"（BLPOP timeout=5s，取 10s 留余量）
                socket_timeout=10,
                retry_on_timeout=True
            )
            # 测试连接
            self._redis_client.ping()
            logger.info(f"Redis连接成功 - {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            logger.error(f"Redis连接失败: {str(e)}")
            raise RuntimeError(f"无法连接到Redis服务器: {str(e)}")
    
    @property
    def redis(self) -> redis.Redis:
        """获取Redis客户端实例"""
        if self._redis_client is None:
            raise RuntimeError("Redis客户端未初始化")
        return self._redis_client

    # ============ 通用 JSON 缓存（工具查询结果等） ============

    def get_cached_json(self, key: str) -> Optional[Any]:
        """读取通用JSON缓存，未命中或异常返回None"""
        try:
            raw = self.redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"读取缓存失败: {key} | {e}")
            return None

    def set_cached_json(self, key: str, value: Any, ttl_seconds: int) -> bool:
        """写入通用JSON缓存，失败不抛出（缓存是尽力而为的优化）"""
        try:
            self.redis.setex(key, ttl_seconds, json.dumps(value, ensure_ascii=False))
            return True
        except Exception as e:
            logger.warning(f"写入缓存失败: {key} | {e}")
            return False

    def _generate_user_key(self, username: str) -> str:
        """生成用户数据的Redis键"""
        return f"user:{username}"
    
    def _generate_username_index_key(self, user_id: str) -> str:
        """生成用户名索引的Redis键"""
        return f"user_index:{user_id}"
    
    def _generate_trip_key(self, trip_id: str) -> str:
        """生成行程数据的Redis键"""
        return f"trip:{trip_id}"
    
    def _generate_user_trips_list_key(self, user_id: str) -> str:
        """生成用户行程列表的Redis键"""
        return f"user_trips:{user_id}"

    def _generate_guest_session_key(self, guest_id: str) -> str:
        """生成访客会话Redis键"""
        return f"guest_session:{guest_id}"

    def _generate_trip_versions_key(self, trip_id: str) -> str:
        """生成行程版本历史Redis键"""
        return f"trip_versions:{trip_id}"

    def _generate_trip_task_key(self, task_id: str) -> str:
        """生成行程任务Redis键"""
        return f"trip_task:{task_id}"

    def _generate_trip_task_queue_key(self) -> str:
        return "trip_task_queue"
    
    def _hash_password(self, password: str) -> str:
        """
        使用bcrypt加密密码
        
        注意：bcrypt算法有72字节的密码长度限制
        对于长密码，先使用SHA256哈希再进行bcrypt加密
        
        Args:
            password: 明文密码
            
        Returns:
            加密后的密码哈希
        """
        # 处理长密码：如果超过72字节，先使用SHA256哈希
        password_bytes = password.encode('utf-8')
        
        if len(password_bytes) > 72:
            logger.info(f"密码长度超过72字节，使用SHA256预处理")
            # 对于长密码，使用SHA256哈希后再加密
            sha256_hash = hashlib.sha256(password_bytes).digest()
            # 取前72字节
            password_bytes = sha256_hash[:72]
        
        # 使用bcrypt直接加密（避免passlib的兼容性问题）
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password_bytes, salt)
        
        return hashed.decode('utf-8')
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        验证密码
        
        Args:
            plain_password: 明文密码
            hashed_password: 加密后的密码哈希
            
        Returns:
            密码是否匹配
        """
        try:
            # 处理密码编码
            plain_password_bytes = plain_password.encode('utf-8')
            hashed_password_bytes = hashed_password.encode('utf-8')
            
            # 使用bcrypt直接验证
            result = bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)
            return result
        except Exception as e:
            logger.error(f"密码验证失败: {str(e)}")
            return False
    
    def create_user(
        self,
        user_id: str,
        username: str,
        password: str,
        phone: Optional[str] = None,
        gender: str = "other",
        birthday: Optional[str] = None,
        bio: Optional[str] = None,
        travel_preferences: list = None,
        avatar_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建新用户
        
        Args:
            user_id: 用户ID
            username: 用户名
            password: 明文密码
            phone: 手机号
            gender: 性别
            birthday: 生日
            bio: 个人简介
            travel_preferences: 旅行偏好
            avatar_url: 头像URL
            
        Returns:
            创建的用户数据
            
        Raises:
            ValueError: 用户名已存在
        """
        user_key = self._generate_user_key(username)
        
        # 检查用户名是否已存在
        if self.redis.exists(user_key):
            raise ValueError(f"用户名 '{username}' 已存在")
        
        # 加密密码
        hashed_password = self._hash_password(password)
        
        # 构建用户数据
        # 注意：Redis的hset只支持str, int, float, bytes类型
        # 所有字段必须是这些类型之一
        user_data = {
            "user_id": str(user_id),
            "username": str(username),
            "password": str(hashed_password),
            "phone": str(phone) if phone is not None else "",
            "gender": str(gender),
            "birthday": str(birthday) if birthday is not None else "",
            "bio": str(bio) if bio is not None else "",
            "travel_preferences": json.dumps(travel_preferences or []),  # 列表转为JSON字符串
            "avatar_url": str(avatar_url) if avatar_url is not None else "",
            "created_at": ""
        }
        
        # 保存用户数据
        try:
            self.redis.hset(user_key, mapping=user_data)
            # 创建用户名到ID的索引
            self.redis.set(self._generate_username_index_key(user_id), username)
            logger.info(f"用户创建成功 - Username: {username}, UserID: {user_id}")
            return user_data
        except Exception as e:
            logger.error(f"用户创建失败: {str(e)}")
            raise RuntimeError(f"用户创建失败: {str(e)}")
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        根据用户名获取用户数据
        
        Args:
            username: 用户名
            
        Returns:
            用户数据，如果不存在则返回None
        """
        try:
            user_key = self._generate_user_key(username)
            user_data = self.redis.hgetall(user_key)
            
            if not user_data:
                return None
            
            # 处理travel_preferences字段（JSON数组）
            if "travel_preferences" in user_data:
                try:
                    user_data["travel_preferences"] = json.loads(user_data["travel_preferences"])
                except (json.JSONDecodeError, TypeError):
                    user_data["travel_preferences"] = []
            
            return user_data
        except Exception as e:
            logger.error(f"获取用户数据失败: {str(e)}")
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        根据用户ID获取用户数据
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户数据，如果不存在则返回None
        """
        try:
            # 通过索引查找用户名
            username = self.redis.get(self._generate_username_index_key(user_id))
            if not username:
                return None
            
            return self.get_user_by_username(username)
        except Exception as e:
            logger.error(f"通过ID获取用户数据失败: {str(e)}")
            return None
    
    def verify_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        验证用户登录凭证
        
        Args:
            username: 用户名
            password: 明文密码
            
        Returns:
            验证成功返回用户数据，失败返回None
        """
        user_data = self.get_user_by_username(username)
        
        if not user_data:
            logger.warning(f"登录失败 - 用户不存在: {username}")
            return None
        
        hashed_password = user_data.get("password")
        if not hashed_password:
            logger.error(f"用户数据异常 - 没有密码哈希: {username}")
            return None
        
        if not self._verify_password(password, hashed_password):
            logger.warning(f"登录失败 - 密码错误: {username}")
            return None
        
        logger.info(f"用户验证成功 - Username: {username}")
        return user_data
    
    def update_user(
        self,
        username: str,
        **updates
    ) -> Optional[Dict[str, Any]]:
        """
        更新用户数据（密码除外）
        
        Args:
            username: 用户名
            **updates: 要更新的字段
            
        Returns:
            更新后的用户数据
            
        Raises:
            ValueError: 用户不存在
        """
        user_key = self._generate_user_key(username)
        
        # 检查用户是否存在
        if not self.redis.exists(user_key):
            raise ValueError(f"用户 '{username}' 不存在")
        
        # 过滤不允许更新的字段
        updates.pop("user_id", None)
        updates.pop("username", None)
        updates.pop("password", None)
        updates.pop("created_at", None)
        
        # 处理travel_preferences字段
        if "travel_preferences" in updates:
            updates["travel_preferences"] = json.dumps(updates["travel_preferences"])
        
        # 确保所有值都是字符串类型（Redis hset只支持str, int, float, bytes）
        clean_updates = {}
        for key, value in updates.items():
            if value is not None:
                clean_updates[key] = str(value)
            else:
                clean_updates[key] = ""
        
        try:
            # 更新用户数据
            if clean_updates:
                self.redis.hset(user_key, mapping=clean_updates)
            
            # 返回更新后的用户数据
            updated_user = self.get_user_by_username(username)
            logger.info(f"用户数据更新成功 - Username: {username}")
            return updated_user
        except Exception as e:
            logger.error(f"用户数据更新失败: {str(e)}")
            raise RuntimeError(f"用户数据更新失败: {str(e)}")
    
    def update_password(self, username: str, old_password: str, new_password: str) -> bool:
        """
        更新用户密码
        
        Args:
            username: 用户名
            old_password: 原密码
            new_password: 新密码
            
        Returns:
            是否更新成功
            
        Raises:
            ValueError: 用户不存在或原密码错误
        """
        # 验证原密码
        user_data = self.verify_user(username, old_password)
        if not user_data:
            raise ValueError("用户不存在或原密码错误")
        
        # 加密新密码
        hashed_password = self._hash_password(new_password)
        
        try:
            user_key = self._generate_user_key(username)
            self.redis.hset(user_key, "password", hashed_password)
            logger.info(f"用户密码更新成功 - Username: {username}")
            return True
        except Exception as e:
            logger.error(f"用户密码更新失败: {str(e)}")
            raise RuntimeError(f"用户密码更新失败: {str(e)}")
    
    def delete_user(self, username: str) -> bool:
        """
        删除用户
        
        Args:
            username: 用户名
            
        Returns:
            是否删除成功
        """
        try:
            user_data = self.get_user_by_username(username)
            if not user_data:
                return False
            
            user_id = user_data["user_id"]
            user_key = self._generate_user_key(username)
            
            # 删除用户数据和索引
            self.redis.delete(user_key)
            self.redis.delete(self._generate_username_index_key(user_id))
            
            logger.info(f"用户删除成功 - Username: {username}")
            return True
        except Exception as e:
            logger.error(f"用户删除失败: {str(e)}")
            return False
    
    def check_username_exists(self, username: str) -> bool:
        """
        检查用户名是否存在
        
        Args:
            username: 用户名
            
        Returns:
            用户名是否存在
        """
        try:
            user_key = self._generate_user_key(username)
            return self.redis.exists(user_key) > 0
        except Exception as e:
            logger.error(f"检查用户名存在性失败: {str(e)}")
            return False
    
    def get_all_usernames(self) -> list:
        """
        获取所有用户名列表
        
        Returns:
            用户名列表
        """
        try:
            # 使用SCAN遍历所有用户键
            keys = []
            for key in self.redis.scan_iter(match="user:*"):
                keys.append(key)
            
            usernames = [key.replace("user:", "") for key in keys]
            return usernames
        except Exception as e:
            logger.error(f"获取用户名列表失败: {str(e)}")
            return []

    # ============ 访客会话相关方法 ============

    def create_or_get_guest_session(self, guest_id: str, ttl_seconds: int = 30 * 24 * 60 * 60) -> Dict[str, Any]:
        """
        创建或获取访客会话（服务端会话表）
        """
        key = self._generate_guest_session_key(guest_id)
        now = datetime.datetime.now().isoformat()
        user_id = f"guest_{guest_id}"

        try:
            session_data = self.redis.hgetall(key)
            if session_data:
                # 续期
                self.redis.hset(key, mapping={"last_seen_at": now})
                self.redis.expire(key, ttl_seconds)
                return {
                    "user_id": session_data.get("user_id", user_id),
                    "user_type": "guest",
                    "guest_id": guest_id,
                    "created_at": session_data.get("created_at", now)
                }

            # 新建会话
            session_data = {
                "user_id": user_id,
                "user_type": "guest",
                "guest_id": guest_id,
                "created_at": now,
                "last_seen_at": now
            }
            self.redis.hset(key, mapping=session_data)
            self.redis.expire(key, ttl_seconds)
            return {
                "user_id": user_id,
                "user_type": "guest",
                "guest_id": guest_id,
                "created_at": now
            }
        except Exception as e:
            logger.error(f"创建/获取访客会话失败: {str(e)}")
            # 降级返回
            return {
                "user_id": user_id,
                "user_type": "guest",
                "guest_id": guest_id,
                "created_at": now
            }
    
    # ============ 行程相关方法 ============
    
    def store_trip(
        self,
        user_id: str,
        trip_id: str,
        trip_data: Dict[str, Any]
    ) -> bool:
        """
        存储完整行程数据
        
        Args:
            user_id: 用户ID
            trip_id: 行程ID
            trip_data: 行程数据（完整行程详情）
            
        Returns:
            是否存储成功
        """
        try:
            trip_key = self._generate_trip_key(trip_id)
            user_trips_list_key = self._generate_user_trips_list_key(user_id)
            versions_key = self._generate_trip_versions_key(trip_id)

            # 初始化版本信息
            trip_data = dict(trip_data)
            trip_data.setdefault("version", 1)
            trip_data.setdefault("updated_at", trip_data.get("created_at", datetime.datetime.now().isoformat()))
            
            # 存储完整行程数据为JSON字符串
            self.redis.set(
                trip_key,
                json.dumps(trip_data, ensure_ascii=False),
                ex=365 * 24 * 60 * 60  # 1年过期
            )

            # 写入版本快照（保留最近20个版本）
            version_snapshot = {
                "version": int(trip_data.get("version", 1)),
                "snapshot_at": datetime.datetime.now().isoformat(),
                "data": trip_data
            }
            self.redis.lpush(versions_key, json.dumps(version_snapshot, ensure_ascii=False))
            self.redis.ltrim(versions_key, 0, 19)
            self.redis.expire(versions_key, 365 * 24 * 60 * 60)
            
            # 将行程ID添加到用户的行程列表中（使用有序集合，按创建时间排序）
            created_at = trip_data.get('created_at', datetime.datetime.now().isoformat())
            timestamp = int(datetime.datetime.fromisoformat(created_at).timestamp())
            self.redis.zadd(user_trips_list_key, {trip_id: timestamp})
            
            logger.info(f"行程存储成功 - UserID: {user_id}, TripID: {trip_id}")
            return True
        except Exception as e:
            logger.error(f"行程存储失败: {str(e)}")
            return False
    
    def get_trip(self, trip_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定行程的完整数据
        
        Args:
            trip_id: 行程ID
            
        Returns:
            行程数据，如果不存在则返回None
        """
        try:
            trip_key = self._generate_trip_key(trip_id)
            trip_data_str = self.redis.get(trip_key)
            
            if not trip_data_str:
                return None
            
            return json.loads(trip_data_str)
        except Exception as e:
            logger.error(f"获取行程失败: {str(e)}")
            return None
    
    def list_user_trips(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取用户的所有行程列表（按创建时间倒序）
        
        Args:
            user_id: 用户ID
            limit: 返回数量限制
            
        Returns:
            行程列表
        """
        try:
            user_trips_list_key = self._generate_user_trips_list_key(user_id)
            
            # 从有序集合中获取行程ID列表（倒序，最新的在前）
            trip_ids = self.redis.zrevrange(user_trips_list_key, 0, limit - 1)
            
            trips = []
            for trip_id in trip_ids:
                trip_data = self.get_trip(trip_id)
                if trip_data:
                    trips.append(trip_data)
            
            logger.info(f"获取用户行程列表 - UserID: {user_id}, Count: {len(trips)}")
            return trips
        except Exception as e:
            logger.error(f"获取用户行程列表失败: {str(e)}")
            return []
    
    def delete_trip(self, user_id: str, trip_id: str) -> bool:
        """
        删除指定行程
        
        Args:
            user_id: 用户ID
            trip_id: 行程ID
            
        Returns:
            是否删除成功
        """
        try:
            trip_key = self._generate_trip_key(trip_id)
            user_trips_list_key = self._generate_user_trips_list_key(user_id)
            
            # 验证行程是否存在
            if not self.redis.exists(trip_key):
                logger.warning(f"行程不存在 - TripID: {trip_id}")
                return False
            
            # 验证行程是否属于当前用户
            is_member = self.redis.zscore(user_trips_list_key, trip_id)
            if is_member is None:
                logger.warning(f"行程不属于当前用户 - UserID: {user_id}, TripID: {trip_id}")
                return False
            
            # 使用Redis管道确保原子性操作
            pipe = self.redis.pipeline()
            try:
                # 删除行程数据
                pipe.delete(trip_key)
                # 从用户行程列表中移除
                pipe.zrem(user_trips_list_key, trip_id)
                # 执行管道中的所有命令
                pipe.execute()
                
                logger.info(f"行程删除成功 - UserID: {user_id}, TripID: {trip_id}")
                return True
            except Exception as e:
                logger.error(f"Redis管道执行失败: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"行程删除失败: {str(e)}")
            return False

    def update_trip(self, user_id: str, trip_id: str, trip_data: Dict[str, Any], expected_version: Optional[int] = None) -> tuple[bool, Optional[str]]:
        """
        更新指定行程

        Args:
            user_id: 用户ID
            trip_id: 行程ID
            trip_data: 更新后的完整行程数据

        Returns:
            (是否更新成功, 错误类型)
        """
        try:
            trip_key = self._generate_trip_key(trip_id)
            user_trips_list_key = self._generate_user_trips_list_key(user_id)
            versions_key = self._generate_trip_versions_key(trip_id)

            if not self.redis.exists(trip_key):
                logger.warning(f"行程不存在 - TripID: {trip_id}")
                return False, "not_found"

            # 验证行程归属
            is_member = self.redis.zscore(user_trips_list_key, trip_id)
            if is_member is None:
                logger.warning(f"行程不属于当前用户 - UserID: {user_id}, TripID: {trip_id}")
                return False, "forbidden"

            # 保留原创建时间和ID
            old_trip = self.get_trip(trip_id) or {}
            current_version = int(old_trip.get("version", 1))

            # 乐观锁：版本冲突保护
            if expected_version is not None and expected_version != current_version:
                logger.warning(
                    f"行程版本冲突 - TripID: {trip_id}, expected={expected_version}, current={current_version}"
                )
                return False, "version_conflict"

            trip_data["id"] = trip_id
            trip_data["created_at"] = old_trip.get("created_at", datetime.datetime.now().isoformat())
            trip_data["updated_at"] = datetime.datetime.now().isoformat()
            trip_data["version"] = current_version + 1

            self.redis.set(
                trip_key,
                json.dumps(trip_data, ensure_ascii=False),
                ex=365 * 24 * 60 * 60
            )

            # 追加版本快照
            version_snapshot = {
                "version": int(trip_data["version"]),
                "snapshot_at": datetime.datetime.now().isoformat(),
                "data": trip_data
            }
            self.redis.lpush(versions_key, json.dumps(version_snapshot, ensure_ascii=False))
            self.redis.ltrim(versions_key, 0, 19)
            self.redis.expire(versions_key, 365 * 24 * 60 * 60)
            logger.info(f"行程更新成功 - UserID: {user_id}, TripID: {trip_id}")
            return True, None
        except Exception as e:
            logger.error(f"行程更新失败: {str(e)}")
            return False, "internal_error"

    def list_trip_versions(self, user_id: str, trip_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取行程版本历史（按新到旧）
        """
        try:
            user_trips_list_key = self._generate_user_trips_list_key(user_id)
            if self.redis.zscore(user_trips_list_key, trip_id) is None:
                return []

            versions_key = self._generate_trip_versions_key(trip_id)
            items = self.redis.lrange(versions_key, 0, max(limit - 1, 0))
            versions = []
            for item in items:
                try:
                    parsed = json.loads(item)
                    versions.append({
                        "version": parsed.get("version"),
                        "snapshot_at": parsed.get("snapshot_at"),
                        "trip_title": (parsed.get("data") or {}).get("trip_title", "")
                    })
                except Exception:
                    continue
            return versions
        except Exception as e:
            logger.error(f"获取行程版本历史失败: {str(e)}")
            return []

    def rollback_trip(self, user_id: str, trip_id: str, target_version: int) -> tuple[bool, Optional[str]]:
        """
        回滚行程到指定版本（生成新版本）
        """
        try:
            user_trips_list_key = self._generate_user_trips_list_key(user_id)
            if self.redis.zscore(user_trips_list_key, trip_id) is None:
                return False, "forbidden"

            versions_key = self._generate_trip_versions_key(trip_id)
            items = self.redis.lrange(versions_key, 0, 99)
            target_snapshot = None
            for item in items:
                parsed = json.loads(item)
                if int(parsed.get("version", -1)) == int(target_version):
                    target_snapshot = parsed
                    break

            if not target_snapshot:
                return False, "version_not_found"

            current_trip = self.get_trip(trip_id)
            if not current_trip:
                return False, "not_found"
            current_version = int(current_trip.get("version", 1))

            rollback_data = dict(target_snapshot.get("data", {}))
            rollback_data["id"] = trip_id
            rollback_data["created_at"] = current_trip.get("created_at", datetime.datetime.now().isoformat())
            rollback_data["updated_at"] = datetime.datetime.now().isoformat()
            rollback_data["version"] = current_version + 1
            rollback_data["rollback_from_version"] = target_version

            trip_key = self._generate_trip_key(trip_id)
            self.redis.set(trip_key, json.dumps(rollback_data, ensure_ascii=False), ex=365 * 24 * 60 * 60)

            new_snapshot = {
                "version": rollback_data["version"],
                "snapshot_at": datetime.datetime.now().isoformat(),
                "data": rollback_data
            }
            self.redis.lpush(versions_key, json.dumps(new_snapshot, ensure_ascii=False))
            self.redis.ltrim(versions_key, 0, 19)
            self.redis.expire(versions_key, 365 * 24 * 60 * 60)
            return True, None
        except Exception as e:
            logger.error(f"回滚行程失败: {str(e)}")
            return False, "internal_error"

    # ============ 行程任务相关方法 ============

    def create_trip_task(self, task_id: str, user_id: str, request_data: Dict[str, Any]) -> bool:
        try:
            key = self._generate_trip_task_key(task_id)
            now = datetime.datetime.now().isoformat()
            payload = {
                "task_id": task_id,
                "user_id": user_id,
                "status": "pending",
                "progress": "0",
                "message": "任务已创建，等待调度",
                "created_at": now,
                "updated_at": now,
                "started_at": "",
                "worker_id": "",
                "lease_expires_at": "",
                "request_data": json.dumps(request_data, ensure_ascii=False),
                "result_trip_id": "",
                "error": "",
                "city_support_level": "",
                "city_support_message": ""
            }
            self.redis.hset(key, mapping=payload)
            self.redis.expire(key, 24 * 60 * 60)
            return True
        except Exception as e:
            logger.error(f"创建行程任务失败: {str(e)}")
            return False

    def enqueue_trip_task(self, task_id: str) -> bool:
        try:
            self.redis.rpush(self._generate_trip_task_queue_key(), task_id)
            return True
        except Exception as e:
            logger.error(f"鍏ラ槦琛岀▼浠诲姟澶辫触: {str(e)}")
            return False

    def dequeue_trip_task(self, timeout_seconds: int = 5) -> Optional[str]:
        try:
            item = self.redis.blpop(self._generate_trip_task_queue_key(), timeout=timeout_seconds)
            if not item:
                return None
            _, task_id = item
            return task_id
        except Exception as e:
            logger.error(f"鍑洪槦琛岀▼浠诲姟澶辫触: {str(e)}")
            return None

    def claim_trip_task(self, task_id: str, worker_id: str, lease_seconds: int) -> Optional[Dict[str, Any]]:
        key = self._generate_trip_task_key(task_id)

        for _ in range(3):
            pipe = self.redis.pipeline()
            try:
                pipe.watch(key)
                task = pipe.hgetall(key)
                if not task:
                    return None

                status = task.get("status", "pending")
                lease_expires_at = task.get("lease_expires_at", "")
                lease_is_valid = False
                if lease_expires_at:
                    try:
                        lease_is_valid = datetime.datetime.fromisoformat(lease_expires_at) > datetime.datetime.now()
                    except ValueError:
                        lease_is_valid = False

                if status not in {"pending", "running"}:
                    return None
                if status == "running" and lease_is_valid:
                    return None

                now = datetime.datetime.now()
                started_at = task.get("started_at") or now.isoformat()
                lease_until = (now + datetime.timedelta(seconds=lease_seconds)).isoformat()

                pipe.multi()
                pipe.hset(
                    key,
                    mapping={
                        "status": "running",
                        "worker_id": worker_id,
                        "started_at": started_at,
                        "lease_expires_at": lease_until,
                        "updated_at": now.isoformat(),
                    },
                )
                pipe.expire(key, 24 * 60 * 60)
                pipe.execute()

                task.update(
                    {
                        "status": "running",
                        "worker_id": worker_id,
                        "started_at": started_at,
                        "lease_expires_at": lease_until,
                    }
                )
                return task
            except WatchError:
                continue
            except Exception as e:
                logger.error(f"璁ょ淮琛岀▼浠诲姟澶辫触: {str(e)}")
                return None
            finally:
                pipe.reset()
        return None

    def requeue_incomplete_trip_tasks(self) -> int:
        requeued = 0
        now = datetime.datetime.now()
        try:
            for key in self.redis.scan_iter(match="trip_task:*"):
                task = self.redis.hgetall(key)
                if not task:
                    continue

                status = task.get("status", "pending")
                if status not in {"pending", "running"}:
                    continue

                lease_expires_at = task.get("lease_expires_at", "")
                lease_expired = True
                if lease_expires_at:
                    try:
                        lease_expired = datetime.datetime.fromisoformat(lease_expires_at) <= now
                    except ValueError:
                        lease_expired = True

                if status == "running" and not lease_expired:
                    continue

                task_id = task.get("task_id")
                if not task_id:
                    continue

                self.update_trip_task(
                    task_id,
                    status="pending",
                    message="Task re-queued after worker recovery",
                    worker_id="",
                    lease_expires_at="",
                )
                self.enqueue_trip_task(task_id)
                requeued += 1
        except Exception as e:
            logger.error(f"閲嶆柊鍏ラ槦鏈畬鎴愪换鍔″け璐? {str(e)}")
        return requeued

    def update_trip_task(self, task_id: str, **fields) -> bool:
        try:
            key = self._generate_trip_task_key(task_id)
            if not self.redis.exists(key):
                return False
            if fields.get("status") in {"succeeded", "failed"}:
                fields.setdefault("worker_id", "")
                fields.setdefault("lease_expires_at", "")
            fields = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)) for k, v in fields.items()}
            fields["updated_at"] = datetime.datetime.now().isoformat()
            self.redis.hset(key, mapping=fields)
            self.redis.expire(key, 24 * 60 * 60)
            return True
        except Exception as e:
            logger.error(f"更新行程任务失败: {str(e)}")
            return False

    def get_trip_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            key = self._generate_trip_task_key(task_id)
            data = self.redis.hgetall(key)
            if not data:
                return None
            return data
        except Exception as e:
            logger.error(f"获取行程任务失败: {str(e)}")
            return None
    
    def update_trip(self, user_id: str, trip_id: str, trip_data: Dict[str, Any], expected_version: Optional[int] = None) -> tuple[bool, Optional[str]]:
        trip_key = self._generate_trip_key(trip_id)
        user_trips_list_key = self._generate_user_trips_list_key(user_id)
        versions_key = self._generate_trip_versions_key(trip_id)

        for _ in range(3):
            pipe = self.redis.pipeline()
            try:
                pipe.watch(trip_key, user_trips_list_key, versions_key)

                if not pipe.exists(trip_key):
                    return False, "not_found"
                if pipe.zscore(user_trips_list_key, trip_id) is None:
                    return False, "forbidden"

                old_trip_str = pipe.get(trip_key)
                old_trip = json.loads(old_trip_str) if old_trip_str else {}
                current_version = int(old_trip.get("version", 1))

                if expected_version is not None and expected_version != current_version:
                    return False, "version_conflict"

                now = datetime.datetime.now().isoformat()
                new_trip_data = dict(trip_data)
                new_trip_data["id"] = trip_id
                new_trip_data["created_at"] = old_trip.get("created_at", now)
                new_trip_data["updated_at"] = now
                new_trip_data["version"] = current_version + 1

                version_snapshot = {
                    "version": int(new_trip_data["version"]),
                    "snapshot_at": now,
                    "data": new_trip_data,
                }

                pipe.multi()
                pipe.set(trip_key, json.dumps(new_trip_data, ensure_ascii=False), ex=365 * 24 * 60 * 60)
                pipe.lpush(versions_key, json.dumps(version_snapshot, ensure_ascii=False))
                pipe.ltrim(versions_key, 0, 19)
                pipe.expire(versions_key, 365 * 24 * 60 * 60)
                pipe.execute()
                return True, None
            except WatchError:
                continue
            except Exception as e:
                logger.error(f"琛岀▼鏇存柊澶辫触: {str(e)}")
                return False, "internal_error"
            finally:
                pipe.reset()

        return False, "version_conflict"

    def rollback_trip(self, user_id: str, trip_id: str, target_version: int) -> tuple[bool, Optional[str]]:
        trip_key = self._generate_trip_key(trip_id)
        user_trips_list_key = self._generate_user_trips_list_key(user_id)
        versions_key = self._generate_trip_versions_key(trip_id)

        for _ in range(3):
            pipe = self.redis.pipeline()
            try:
                pipe.watch(trip_key, user_trips_list_key, versions_key)

                if pipe.zscore(user_trips_list_key, trip_id) is None:
                    return False, "forbidden"

                current_trip_str = pipe.get(trip_key)
                if not current_trip_str:
                    return False, "not_found"
                current_trip = json.loads(current_trip_str)
                current_version = int(current_trip.get("version", 1))

                items = pipe.lrange(versions_key, 0, 99)
                target_snapshot = None
                for item in items:
                    parsed = json.loads(item)
                    if int(parsed.get("version", -1)) == int(target_version):
                        target_snapshot = parsed
                        break

                if not target_snapshot:
                    return False, "version_not_found"

                now = datetime.datetime.now().isoformat()
                rollback_data = dict(target_snapshot.get("data", {}))
                rollback_data["id"] = trip_id
                rollback_data["created_at"] = current_trip.get("created_at", now)
                rollback_data["updated_at"] = now
                rollback_data["version"] = current_version + 1
                rollback_data["rollback_from_version"] = target_version

                new_snapshot = {
                    "version": rollback_data["version"],
                    "snapshot_at": now,
                    "data": rollback_data,
                }

                pipe.multi()
                pipe.set(trip_key, json.dumps(rollback_data, ensure_ascii=False), ex=365 * 24 * 60 * 60)
                pipe.lpush(versions_key, json.dumps(new_snapshot, ensure_ascii=False))
                pipe.ltrim(versions_key, 0, 19)
                pipe.expire(versions_key, 365 * 24 * 60 * 60)
                pipe.execute()
                return True, None
            except WatchError:
                continue
            except Exception as e:
                logger.error(f"鍥炴粴琛岀▼澶辫触: {str(e)}")
                return False, "internal_error"
            finally:
                pipe.reset()

        return False, "internal_error"

    def close(self):
        """关闭Redis连接"""
        if self._redis_client:
            try:
                self._redis_client.close()
                logger.info("Redis连接已关闭")
            except Exception as e:
                logger.error(f"关闭Redis连接失败: {str(e)}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# 创建全局Redis服务实例
redis_service = RedisService()
