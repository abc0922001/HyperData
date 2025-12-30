#!/usr/bin/env python3
"""
效能測試腳本 - 比較優化前後的執行時間
使用方式: python benchmark.py
"""

import subprocess
import time
import sys
from pathlib import Path

def measure_execution(script_path, runs=5):
    """測量腳本執行時間"""
    times = []
    
    for i in range(runs):
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            check=False
        )
        elapsed = time.perf_counter() - start
        
        if result.returncode == 0:
            times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.3f}s")
        else:
            print(f"  Run {i+1}: FAILED")
            print(result.stderr)
    
    return times

def calculate_stats(times):
    """計算統計數據"""
    if not times:
        return None
    
    times_sorted = sorted(times)
    return {
        'min': min(times),
        'max': max(times),
        'median': times_sorted[len(times)//2],
        'mean': sum(times) / len(times)
    }

def main():
    print("="*60)
    print("HyperOS Tracker 效能測試")
    print("="*60)
    
    # 檢查檔案是否存在
    original = Path("generate_tw_original.py")
    optimized = Path("generate_tw_optimized.py")
    
    if not original.exists():
        print(f"❌ 找不到原始腳本: {original}")
        print("請將原始腳本命名為 generate_tw_original.py")
        return
    
    if not optimized.exists():
        print(f"❌ 找不到優化腳本: {optimized}")
        print("請將優化腳本命名為 generate_tw_optimized.py")
        return
    
    print("\n📊 測試原始版本...")
    original_times = measure_execution(original, runs=5)
    original_stats = calculate_stats(original_times)
    
    print("\n📊 測試優化版本...")
    optimized_times = measure_execution(optimized, runs=5)
    optimized_stats = calculate_stats(optimized_times)
    
    # 結果比較
    print("\n" + "="*60)
    print("測試結果")
    print("="*60)
    
    if original_stats and optimized_stats:
        print(f"\n原始版本:")
        print(f"  最小值: {original_stats['min']:.3f}s")
        print(f"  中位數: {original_stats['median']:.3f}s")
        print(f"  平均值: {original_stats['mean']:.3f}s")
        print(f"  最大值: {original_stats['max']:.3f}s")
        
        print(f"\n優化版本:")
        print(f"  最小值: {optimized_stats['min']:.3f}s")
        print(f"  中位數: {optimized_stats['median']:.3f}s")
        print(f"  平均值: {optimized_stats['mean']:.3f}s")
        print(f"  最大值: {optimized_stats['max']:.3f}s")
        
        improvement = (1 - optimized_stats['median'] / original_stats['median']) * 100
        speedup = original_stats['median'] / optimized_stats['median']
        
        print(f"\n{'='*60}")
        print(f"效能提升: {improvement:+.1f}%")
        print(f"加速倍數: {speedup:.2f}x")
        print(f"{'='*60}")
        
        if improvement > 0:
            print(f"\n✅ 優化成功! 節省 {original_stats['median'] - optimized_stats['median']:.3f}s")
        else:
            print(f"\n⚠️  優化效果不明顯或負面")
    
    # 記憶體使用比較 (需要 psutil)
    try:
        import psutil
        print("\n💾 記憶體使用分析 (需手動檢查):")
        print("   使用 'mprof run script.py' 進行詳細分析")
    except ImportError:
        pass

if __name__ == "__main__":
    main()
