#!/usr/bin/env python3
"""Smoke-тесты эндпоинтов MagikBook API."""

import asyncio
import json
import sys
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"


def test_endpoint(method: str, path: str, expected_status: int = 200, description: str = ""):
    """Тестирование одного эндпоинта."""
    url = f"{BASE_URL}{path}" if not path.startswith("http") else path
    try:
        if method == "GET":
            response = urlopen(url, timeout=10)
            status = response.getcode()
            body = response.read().decode('utf-8')
        else:
            req = Request(url, method=method)
            response = urlopen(req, timeout=10)
            status = response.getcode()
            body = response.read().decode('utf-8')

        success = status == expected_status
        icon = "✅" if success else "❌"
        print(f"{icon} {method} {path} -> {status} (expected {expected_status})")
        if not success:
            print(f"   Response: {body[:200]}")
        return success, body
    except HTTPError as e:
        status = e.code
        success = status == expected_status
        icon = "✅" if success else "❌"
        print(f"{icon} {method} {path} -> {status} (expected {expected_status})")
        if not success:
            print(f"   Error: {e.reason}")
        return success, str(e)
    except URLError as e:
        print(f"❌ {method} {path} -> CONNECTION ERROR: {e.reason}")
        return False, str(e)
    except Exception as e:
        print(f"❌ {method} {path} -> EXCEPTION: {e}")
        return False, str(e)


from urllib.request import Request


def run_tests():
    """Запуск всех тестов."""
    print("=" * 60)
    print("SMOKE-ТЕСТЫ MAGIKBOOK API")
    print("=" * 60)

    results = []

    # 1. Health check
    print("\n[1] HEALTH CHECK:")
    success, body = test_endpoint("GET", "/health", 200)
    results.append(("health", success))
    if success:
        print(f"   Response: {body}")

    # 2. Homepage
    print("\n[2] HOMEPAGE API:")
    success, body = test_endpoint("GET", "/api/prompts/homepage", 200)
    results.append(("homepage", success))
    if success:
        try:
            data = json.loads(body)
            trending_text = len(data.get("trending_text", []))
            trending_media = len(data.get("trending_media", []))
            daily = "yes" if data.get("daily_prompt") else "no"
            print(f"   trending_text: {trending_text}, trending_media: {trending_media}, daily: {daily}")
        except:
            pass

    # 3. Feed
    print("\n[3] FEED API:")
    success, body = test_endpoint("GET", "/api/prompts/feed?page=1&page_size=5", 200)
    results.append(("feed", success))
    if success:
        try:
            data = json.loads(body)
            prompts = len(data.get("prompts", []))
            total = data.get("total_count", 0)
            print(f"   prompts: {prompts}, total_count: {total}")
        except:
            pass

    # 4. Feed с фильтрами
    print("\n[4] FEED API WITH FILTERS:")
    success, _ = test_endpoint("GET", "/api/prompts/feed?media_type=image&filter=trending", 200)
    results.append(("feed_filtered", success))

    # 5. Specific prompt (если есть данные)
    print("\n[5] SPECIFIC PROMPT:")
    if success:
        try:
            # Получим первый промпт из фида
            data = json.loads(body)
            prompts = data.get("prompts", [])
            if prompts:
                prompt_id = prompts[0]["id"]
                success, _ = test_endpoint("GET", f"/api/prompts/{prompt_id}", 200)
                results.append(("prompt_detail", success))
                print(f"   Tested prompt_id: {prompt_id[:8]}...")
            else:
                print("   ⚠️ No prompts to test")
                results.append(("prompt_detail", False))
        except:
            print("   ⚠️ Could not extract prompt_id")
            results.append(("prompt_detail", False))

    # 6. Battle pair
    print("\n[6] BATTLE API:")
    success, body = test_endpoint("GET", "/api/battle/pair", 200)
    results.append(("battle_pair", success))
    if success:
        try:
            data = json.loads(body)
            prompts = data.get("prompts", [])
            print(f"   Got {len(prompts)} prompts for battle")
        except:
            pass

    # 7. Generate (только проверка доступности)
    print("\n[7] GENERATE API (POST check):")
    success, _ = test_endpoint("POST", "/api/generate", 422)  # 422 без body
    results.append(("generate_post", success))

    # 8. Auth endpoints (без auth - должны возвращать 401/403)
    print("\n[8] AUTH API (unauthorized check):")
    success, _ = test_endpoint("GET", "/api/auth/me", 401)
    results.append(("auth_me_unauthorized", success))

    # Frontend proxy routes
    print("\n[9] FRONTEND PROXY ROUTES:")
    success, _ = test_endpoint("GET", f"{FRONTEND_URL}/api/prompts/homepage", 200)
    results.append(("frontend_homepage_proxy", success))

    success, _ = test_endpoint("GET", f"{FRONTEND_URL}/api/feed?page=1", 200)
    results.append(("frontend_feed_proxy", success))

    # Summary
    print("\n" + "=" * 60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"\nПройдено: {passed}/{total}")

    if passed == total:
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        return 0
    else:
        print("\n❌ ЕСТЬ ОШИБКИ:")
        for name, success in results:
            if not success:
                print(f"   - {name}")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
