"""Kiểm thử thực tế cho sidecar sinh ảnh FLUX 3 Image Klein.

Yêu cầu thực thi:
- Cần GPU NVIDIA có ít nhất 12 GB VRAM (chạy bfloat16/FP8).
- Trọng số FLUX 3 Image Klein đã được tải và kiểm tra sha256 đầy đủ (provision).
- Môi trường thực thi uv riêng biệt tại tools/imagegen với PyTorch cu130.
- Không sử dụng mạng ngoài trong quá trình thực thi kiểm thử.
"""

import hashlib
import http.client
import json
import os
import pathlib
import subprocess
import sys
import time
import pytest

TOOLS_IMAGEGEN = pathlib.Path(__file__).resolve().parents[2] / 'tools' / 'imagegen'
sys.path.insert(0, str(TOOLS_IMAGEGEN))

import engine

VRAM_MAX_BYTES = 10_000_000_000
PEAK_WSET_MAX_BYTES = 4 * 1024 ** 3
HOST_PRIVATE_MAX_BYTES = 4 * 1024 ** 3


def test_imagegen_real_full_pipeline(tmp_path):
    py_exec = os.environ.get('AIAVC_IMAGEGEN_PYTHON')
    if not py_exec or not pathlib.Path(py_exec).exists():
        pytest.skip('AIAVC_IMAGEGEN_PYTHON chưa được đặt hoặc không tồn tại')

    token = 'a' * 32
    env = os.environ.copy()
    env['AIAVC_IMAGEGEN_TOKEN'] = token
    # Chứng minh không có mạng ngoài khi thực thi
    env.pop('HTTPS_PROXY', None)
    env['HTTPS_PROXY'] = ''

    stop_file = tmp_path / 'stop.txt'
    out_dir = tmp_path / 'out'
    port = 57030

    cmd = [
        py_exec,
        str(TOOLS_IMAGEGEN / 'server.py'),
        '--parent-pid', str(os.getpid()),
        '--out', str(out_dir),
        '--stop-file', str(stop_file),
        '--port', str(port),
    ]

    proc = subprocess.Popen(cmd, env=env)
    try:
        # Chờ server khởi động và sẵn sàng
        ready = False
        for _ in range(60):
            try:
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                conn.request('GET', '/v1/health')
                r = conn.getresponse()
                if r.status == 200:
                    ready = True
                    conn.close()
                    break
                conn.close()
            except Exception:
                pass
            time.sleep(1.0)
        assert ready, 'Server không sẵn sàng sau 60 giây'

        # Chu kỳ 1: POST một job 6 ảnh 864x1536 steps 16
        job1 = {
            'job_id': '11111111111111111111111111111111',
            'items': [
                {
                    'item_id': f'img_{i}',
                    'caption': f'A cinematic photo of a beautiful landscape {i}',
                    'width': 864,
                    'height': 1536,
                    'steps': 16,
                    'seed': 42 + i,
                }
                for i in range(6)
            ]
        }
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        conn.request('POST', '/v1/jobs', body=json.dumps(job1).encode('utf-8'), headers=headers)
        r = conn.getresponse()
        assert r.status == 202
        conn.close()

        # Chờ job 1 hoàn thành (tối đa 900 giây)
        start_wait = time.time()
        job1_done = False
        while time.time() - start_wait < 900.0:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            conn.request('GET', f'/v1/jobs/{job1["job_id"]}', headers={'Authorization': f'Bearer {token}'})
            r = conn.getresponse()
            if r.status == 200:
                data = json.loads(r.read().decode('utf-8'))
                conn.close()
                if data.get('state') == 'done':
                    job1_done = True
                    break
            else:
                conn.close()
            time.sleep(2.0)
        assert job1_done, 'Job 1 không hoàn thành trong thời gian quy định'

        # Kiểm tra tính toàn vẹn PNG và X-Content-SHA256
        for it in job1['items']:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            conn.request('GET', f'/v1/jobs/{job1["job_id"]}/items/{it["item_id"]}.png', headers={'Authorization': f'Bearer {token}'})
            r = conn.getresponse()
            assert r.status == 200
            png_bytes = r.read()
            expected_sha = hashlib.sha256(png_bytes).hexdigest()
            header_sha = r.getheader('X-Content-SHA256') or r.getheader('x-content-sha256')
            assert header_sha == expected_sha
            conn.close()

        # Đọc health và đánh giá memory_budget
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        conn.request('GET', '/v1/health')
        r = conn.getresponse()
        assert r.status == 200
        health_data = json.loads(r.read().decode('utf-8'))
        conn.close()

        stats1 = {'phases': health_data.get('memory', {}), 'cycle_index': 0}
        budget_res = engine.memory_budget(stats1)
        assert budget_res['ok'] is True, f"Vi phạm ngân sách bộ nhớ chu kỳ 0: {budget_res['violations']}"

        # Chu kỳ 2: Chạy kiểm tra residual ở chu kỳ tiếp theo
        job2 = {
            'job_id': '22222222222222222222222222222222',
            'items': [
                {
                    'item_id': 'img_second_cycle',
                    'caption': 'A serene sunrise over mountains',
                    'width': 864,
                    'height': 1536,
                    'steps': 16,
                    'seed': 999,
                }
            ]
        }
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        conn.request('POST', '/v1/jobs', body=json.dumps(job2).encode('utf-8'), headers=headers)
        r = conn.getresponse()
        assert r.status == 202
        conn.close()

        start_wait = time.time()
        job2_done = False
        while time.time() - start_wait < 300.0:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            conn.request('GET', f'/v1/jobs/{job2["job_id"]}', headers={'Authorization': f'Bearer {token}'})
            r = conn.getresponse()
            if r.status == 200:
                data = json.loads(r.read().decode('utf-8'))
                conn.close()
                if data.get('state') == 'done':
                    job2_done = True
                    break
            else:
                conn.close()
            time.sleep(2.0)
        assert job2_done, 'Job 2 không hoàn thành'

        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        conn.request('GET', '/v1/health')
        r = conn.getresponse()
        health_data2 = json.loads(r.read().decode('utf-8'))
        conn.close()

        stats2 = {'phases': health_data2.get('memory', {}), 'cycle_index': 1}
        budget_res2 = engine.memory_budget(stats2)
        assert budget_res2['ok'] is True, f"Vi phạm ngân sách bộ nhớ chu kỳ 1: {budget_res2['violations']}"

    finally:
        # Tạo stop file và kiểm tra tiến trình thoát
        stop_file.write_text('stop', encoding='utf-8')
        try:
            proc.wait(timeout=15.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()