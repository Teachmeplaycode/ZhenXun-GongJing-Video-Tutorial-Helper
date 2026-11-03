"""Real local services + Unicode video paths, without model/API downloads or paid calls.

Run with backend/.venv Python after installing the frontend. Restores local settings.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import httpx


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def closed(port):
    with socket.socket() as sock:
        return sock.connect_ex(('127.0.0.1', port)) != 0


def main():
    api, web = free_port(), free_port()
    while api == web:
        web = free_port()
    config = ROOT / 'backend/.env.local'
    saved = config.read_bytes() if config.exists() else None
    saved_mode = config.stat().st_mode if config.exists() else None
    process = None
    with tempfile.TemporaryDirectory(prefix='帧寻 本地验收 ') as tmp:
        tmp = Path(tmp)
        env = {**os.environ, 'API_PORT': str(api), 'WEB_PORT': str(web),
               'GONGJING_DATA_DIR': str(tmp / '中文 数据目录'), 'PYTHONUTF8': '1',
               'LLM_PROVIDER': 'deepseek', 'LLM_API_KEY': '', 'DEEPSEEK_API_KEY': '',
               'LLM_KEY_FILE': '', 'LLM_MODEL': 'deepseek-flash',
               'LLM_BASE_URL': 'http://127.0.0.1:9', 'SCREENTEXT': 'off', 'DECISION': 'off'}
        client = httpx.Client(base_url=f'http://127.0.0.1:{web}', trust_env=False, timeout=15)
        try:
            if os.name == 'nt':
                check = subprocess.run([os.environ.get('COMSPEC', 'cmd.exe'), '/c', str(ROOT / 'start.cmd'), '--check'], env=env, timeout=60)
                assert check.returncode == 0, 'start.cmd --check failed in Unicode checkout path'
            with (tmp / 'services.txt').open('w', encoding='utf-8') as log:
                options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {}
                process = subprocess.Popen([sys.executable, str(ROOT / 'start.py'), '--skip-install', '--no-browser'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, **options)
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    assert process.poll() is None, 'launcher exited before becoming ready'
                    try:
                        health = client.get('/api/health')
                        if health.status_code == 200 and health.json().get('ok') and '<html' in client.get('/').text.lower():
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.3)
                else:
                    raise AssertionError('real local services did not become ready')
                assert health.json()['model'] is None, 'missing key must still allow opening settings'
                print('PASS real backend + frontend readiness without API key', flush=True)
                settings = client.get('/api/settings')
                settings.raise_for_status()
                assert settings.json()['readonly'] is False
                response = client.put('/api/settings', json={'values': {'LLM_API_KEY': 'acceptance-placeholder-only'}})
                response.raise_for_status()
                assert 'acceptance-placeholder-only' not in response.text
                assert response.json()['values']['LLM_API_KEY']['local_configured']
                response = client.put('/api/settings', json={'clear': ['LLM_API_KEY']})
                response.raise_for_status()
                print('PASS settings through real Vite proxy, credential never echoed', flush=True)
                movie = tmp / '中文 测试视频.mp4'
                subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=4', '-t', '2', '-an', '-c:v', 'mpeg4', str(movie)], check=True, timeout=20)
                with movie.open('rb') as stream:
                    response = client.post('/api/videos', files={'file': (movie.name, stream, 'video/mp4')}, data={'sampling': json.dumps({'frames': 8, 'shots': False, 'ocr_fps': 0})})
                response.raise_for_status()
                job = response.json()
                job_id = job.get('job_id') or job.get('id')
                assert job_id, 'upload did not return an ID'
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    pictures = list((tmp / '中文 数据目录' / 'jobs' / job_id).rglob('*.jpg'))
                    if pictures:
                        from modules.cv_compat import imread
                        assert imread(pictures[0]) is not None
                        break
                    time.sleep(.3)
                else:
                    raise AssertionError('ffmpeg never produced a readable frame in the Unicode data directory')
                print('PASS actual video upload, ffmpeg extraction and image read in Chinese + space path', flush=True)
                if os.name == 'nt':
                    # TerminateProcess simulates an abrupt launcher close: its Job Object must release descendants.
                    process.terminate()
                else:
                    process.send_signal(signal.SIGTERM)
                process.wait(timeout=20)
                if os.name != 'nt':
                    assert process.returncode == 0
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline and not (closed(api) and closed(web)):
                    time.sleep(.2)
                assert closed(api) and closed(web), 'launcher left an owned service running'
                print('PASS owned backend/frontend process trees removed on launcher exit', flush=True)
                if os.name != 'nt':
                    restarted = subprocess.run([sys.executable, str(ROOT / 'start.py'), '--check'], env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
                    assert restarted.returncode == 0, restarted.stdout
                    print('PASS immediate restart check after stopping services', flush=True)
        except BaseException:
            service_log = tmp / 'services.txt'
            if service_log.exists():
                print(service_log.read_text(encoding='utf-8', errors='replace'))
            raise
        finally:
            client.close()
            if process and process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    process.send_signal(signal.SIGTERM)
                process.wait(timeout=20)
            if saved is None:
                config.unlink(missing_ok=True)
            else:
                config.write_bytes(saved)
                config.chmod(saved_mode)
        with socket.socket() as listener:
            occupied = free_port()
            listener.bind(('127.0.0.1', occupied))
            listener.listen()
            env['API_PORT'] = str(occupied)
            result = subprocess.run([sys.executable, str(ROOT / 'start.py'), '--check'], env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
            assert result.returncode == 1 and str(occupied) in result.stdout
            assert not closed(occupied), 'occupied service must not be stopped'
        env['API_PORT'] = 'invalid'
        result = subprocess.run([sys.executable, str(ROOT / 'start.py'), '--check'], env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
        assert result.returncode == 1 and 'Traceback' not in result.stderr
        print('PASS occupied/invalid ports fail without stopping unrelated services', flush=True)


if __name__ == '__main__':
    main()
