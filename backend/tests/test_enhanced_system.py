"""
增强系统测试（对齐当前API）
覆盖：注册/登录、/me、guest会话、guest行程保存与回查
"""
from datetime import date, timedelta
from typing import Optional, Dict, Any
import requests

BASE_URL = "http://localhost:8000"


def _future_date(days_from_today: int) -> str:
    return (date.today() + timedelta(days=days_from_today)).isoformat()


def _check_server() -> bool:
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


def _register_or_login(username: str, password: str) -> Optional[str]:
    register_payload = {"username": username, "password": password}
    login_payload = {"username": username, "password": password}

    reg_resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json=register_payload, timeout=15)
    if reg_resp.status_code == 200:
        return reg_resp.json().get("access_token")

    login_resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_payload, timeout=15)
    if login_resp.status_code == 200:
        return login_resp.json().get("access_token")

    print("认证失败:", login_resp.status_code, login_resp.text)
    return None


def test_auth_system() -> Optional[str]:
    print("=== 测试认证系统（当前API）===")
    if not _check_server():
        print("服务器未运行，请先执行: python run.py")
        return None

    token = _register_or_login("testuser_v2", "testpassword123")
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}
    me_resp = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers, timeout=15)
    if me_resp.status_code == 200:
        me_data = me_resp.json()
        print("登录用户信息:", {"user_id": me_data.get("user_id"), "user_type": me_data.get("user_type")})
    else:
        print("/me 接口失败:", me_resp.status_code, me_resp.text)

    return token


def test_guest_session_and_trip_persistence() -> bool:
    print("\n=== 测试 guest 会话与行程持久化 ===")
    if not _check_server():
        print("服务器未运行，请先执行: python run.py")
        return False

    # 用Session维持cookie（guest_id）
    session = requests.Session()

    guest_resp = session.post(f"{BASE_URL}/api/v1/auth/guest", timeout=15)
    if guest_resp.status_code != 200:
        print("guest会话初始化失败:", guest_resp.status_code, guest_resp.text)
        return False

    guest_info = guest_resp.json()
    print("guest会话:", guest_info)

    trip_request = {
        "destination": "北京",
        "start_date": _future_date(7),
        "end_date": _future_date(9),
        "preferences": ["历史", "美食"],
        "hotel_preferences": ["舒适型"],
        "budget": "中等"
    }

    plan_resp = session.post(f"{BASE_URL}/api/v1/trips/plan", json=trip_request, timeout=240)
    if plan_resp.status_code != 200:
        print("guest行程创建失败（可能是外部依赖未配置）:", plan_resp.status_code, plan_resp.text[:200])
        return False

    trip = plan_resp.json()
    trip_id = trip.get("id")
    if not trip_id:
        print("返回数据缺少trip_id")
        return False
    print("guest行程创建成功:", {"trip_id": trip_id, "title": trip.get("trip_title")})

    list_resp = session.get(f"{BASE_URL}/api/v1/trips/list", timeout=30)
    if list_resp.status_code != 200:
        print("guest行程列表获取失败:", list_resp.status_code, list_resp.text)
        return False
    trip_ids = [t.get("id") for t in list_resp.json()]
    print("guest行程列表数量:", len(trip_ids))
    if trip_id not in trip_ids:
        print("行程不在列表中")
        return False

    detail_resp = session.get(f"{BASE_URL}/api/v1/trips/{trip_id}", timeout=30)
    if detail_resp.status_code != 200:
        print("guest行程详情获取失败:", detail_resp.status_code, detail_resp.text)
        return False
    print("guest行程详情获取成功")

    return True


def main():
    token = test_auth_system()
    print("\n认证测试结果:", "通过" if token else "失败")

    guest_ok = test_guest_session_and_trip_persistence()
    print("guest测试结果:", "通过" if guest_ok else "失败")


if __name__ == "__main__":
    main()
