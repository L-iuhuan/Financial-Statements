"""更新模块验证脚本: 演示 compare_versions 表格 + 模拟 check_for_update 流程。

用法: python scripts/verify_update.py
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fsa.core.version import APP_VERSION
from fsa.updater.updater import UpdateError, Updater, compare_versions


def demo_compare_versions() -> None:
    """演示版本比较函数。"""
    print("=" * 60)
    print("版本比较函数 (compare_versions) 演示")
    print("=" * 60)

    test_cases: list[tuple[str, str]] = [
        ("0.1.0", "0.1.0"),
        ("0.1.0", "0.2.0"),
        ("0.2.0", "0.1.0"),
        ("v0.1.0", "0.1.0"),
        ("0.1.0", "v0.2.0"),
        ("0.1", "0.1.0"),
        ("0.1.0.1", "0.1.0"),
        ("1.0.0", "0.9.9"),
        ("0.10.0", "0.2.0"),
        (APP_VERSION, "0.2.0"),
    ]

    result_map = {-1: "当前 < 最新 (需要更新)", 0: "版本相同", 1: "当前 > 最新 (当前更新)"}

    print(f"{'当前版本':<16} {'最新版本':<16} {'结果':<30}")
    print("-" * 62)
    for cur, lat in test_cases:
        cmp = compare_versions(cur, lat)
        print(f"{cur:<16} {lat:<16} {result_map[cmp]:<30}")

    print()


def demo_check_for_update() -> None:
    """演示模拟的 check_for_update 流程。"""
    print("=" * 60)
    print("更新检查模拟 (check_for_update) 演示")
    print("=" * 60)

    # 场景 1: 有新版本
    print("\n--- 场景 1: 发现新版本 ---")
    manifest = json.dumps({
        "version": "0.2.0",
        "download_url": "http://intranet/fsa/fsa_0.2.0_setup.exe",
        "release_notes": "修复了若干勾稽规则问题，新增间接法现金流量表支持。",
    }).encode("utf-8")

    mock_response = MagicMock()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.read.return_value = manifest

    with patch("urllib.request.urlopen", return_value=mock_response):
        updater = Updater(
            manifest_url="http://intranet/fsa/version.json",
            current_version=APP_VERSION,
        )
        info = updater.check_for_update()
        print(f"  当前版本: {info.current_version}")
        print(f"  最新版本: {info.latest_version}")
        print(f"  是否有更新: {'是' if info.has_update else '否'}")
        print(f"  下载地址: {info.download_url}")
        print(f"  更新说明: {info.release_notes}")

    # 场景 2: 已是最新
    print("\n--- 场景 2: 已是最新版本 ---")
    manifest2 = json.dumps({
        "version": APP_VERSION,
        "download_url": "",
        "release_notes": "",
    }).encode("utf-8")

    mock_response2 = MagicMock()
    mock_response2.__enter__ = MagicMock(return_value=mock_response2)
    mock_response2.__exit__ = MagicMock(return_value=False)
    mock_response2.read.return_value = manifest2

    with patch("urllib.request.urlopen", return_value=mock_response2):
        updater2 = Updater(
            manifest_url="http://intranet/fsa/version.json",
            current_version=APP_VERSION,
        )
        info2 = updater2.check_for_update()
        print(f"  当前版本: {info2.current_version}")
        print(f"  最新版本: {info2.latest_version}")
        print(f"  是否有更新: {'是' if info2.has_update else '否'}")
        if not info2.has_update:
            print("  状态: 已是最新版本")

    # 场景 3: 网络错误
    print("\n--- 场景 3: 网络错误 (模拟) ---")
    with patch("urllib.request.urlopen", side_effect=OSError("网络不可达")):
        updater3 = Updater(
            manifest_url="http://intranet/fsa/version.json",
            current_version=APP_VERSION,
        )
        try:
            updater3.check_for_update()
        except UpdateError as e:
            print(f"  错误信息: {e}")

    print()


if __name__ == "__main__":
    demo_compare_versions()
    demo_check_for_update()
    print("=" * 60)
    print("验证完成")
    print("=" * 60)
