"""
测试异步任务与行程版本能力
"""
from datetime import date, timedelta
import time
import requests

BASE_URL = "http://localhost:8000"


def future_date(days_from_today: int) -> str:
    return (date.today() + timedelta(days=days_from_today)).isoformat()


def get_token(username: str, password: str) -> str:
    reg = requests.post(f"{BASE_URL}/api/v1/auth/register", json={"username": username, "password": password}, timeout=10)
    if reg.status_code == 200:
        return reg.json()["access_token"]
    login = requests.post(f"{BASE_URL}/api/v1/auth/login", json={"username": username, "password": password}, timeout=10)
    if login.status_code == 200:
        return login.json()["access_token"]
    raise RuntimeError(f"认证失败: {login.status_code} {login.text}")


def test_async_and_version():
    print("=== 异步任务与版本测试 ===")
    health = requests.get(f"{BASE_URL}/health", timeout=5)
    if health.status_code != 200:
        print("服务器未启动")
        return

    token = get_token("test_task_user", "testpassword123")
    headers = {"Authorization": f"Bearer {token}"}

    req = {
        "destination": "北京",
        "start_date": future_date(7),
        "end_date": future_date(9),
        "preferences": ["历史", "美食"],
        "hotel_preferences": ["舒适型"],
        "budget": "中等"
    }

    task = requests.post(f"{BASE_URL}/api/v1/trips/plan-async", json=req, headers=headers, timeout=30)
    print("创建任务:", task.status_code, task.text)
    if task.status_code != 200:
        return
    task_id = task.json()["task_id"]

    trip_id = None
    for _ in range(120):
        status = requests.get(f"{BASE_URL}/api/v1/trips/tasks/{task_id}", headers=headers, timeout=10)
        if status.status_code != 200:
            print("查询任务失败:", status.status_code, status.text)
            return
        data = status.json()
        print("任务状态:", data.get("status"), "progress=", data.get("progress"))
        if data.get("status") == "succeeded":
            trip_id = data.get("result_trip_id")
            break
        if data.get("status") == "failed":
            print("任务失败:", data.get("error"))
            return
        time.sleep(1.5)

    if not trip_id:
        print("任务超时未完成")
        return

    detail = requests.get(f"{BASE_URL}/api/v1/trips/{trip_id}", headers=headers, timeout=15)
    if detail.status_code != 200:
        print("获取详情失败:", detail.status_code, detail.text)
        return
    trip = detail.json()
    print("初始版本:", trip.get("version"))

    # 保存新版本
    old_version = int(trip.get("version", 1))
    trip["trip_title"] = f"{trip.get('trip_title', '')}-v2"
    upd = requests.put(
        f"{BASE_URL}/api/v1/trips/{trip_id}",
        json=trip,
        headers={**headers, "If-Match-Version": str(old_version)},
        timeout=20
    )
    print("更新结果:", upd.status_code)
    if upd.status_code != 200:
        print("更新失败:", upd.text)
        return
    new_trip = upd.json()
    print("更新后版本:", new_trip.get("version"))

    # 构造冲突（用旧版本再提交）
    conflict = requests.put(
        f"{BASE_URL}/api/v1/trips/{trip_id}",
        json=trip,
        headers={**headers, "If-Match-Version": str(old_version)},
        timeout=20
    )
    print("冲突结果（预期409）:", conflict.status_code, conflict.text[:120])

    versions = requests.get(f"{BASE_URL}/api/v1/trips/{trip_id}/versions", headers=headers, timeout=10)
    print("版本历史:", versions.status_code, versions.text[:200])


if __name__ == "__main__":
    test_async_and_version()
