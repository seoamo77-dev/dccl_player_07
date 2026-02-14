import subprocess
import threading
import os
import sys
import time
import requests
import xml.etree.ElementTree as ET

# [설정] 스트림 상태 및 타이머 관리
stream_names = {1: "OFF", 2: "OFF", 3: "OFF", 4: "OFF", 5: "OFF"}
streams = {1: None, 2: None, 3: None, 4: None, 5: None}
refresh_timers = {1: None, 2: None, 3: None, 4: None, 5: None}

# 서버 접속 정보
AUTH = ('pi', 'dccl')
STAT_URL = "http://dccl02.duckdns.org/stat"
base_url = "rtmp://dccl02.duckdns.org/stream/"

# 레이아웃 설정
width, height = 800, 450
gap = 20
RESTART_INTERVAL = 60000 # 10분

positions = {
    1: (gap, gap),
    2: (width + gap * 3, gap),
    3: (gap, height + gap * 5),
    4: (width + gap * 3, height + gap * 5)
}

def get_server_status():
    """서버에서 현재 입출력 중인 스트림 정보를 가져옴"""
    status_msg = []
    try:
        response = requests.get(STAT_URL, auth=AUTH, timeout=1)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for s in root.findall(".//stream"):
                name = s.find("name").text
                bin = int(s.find("bw_in").text) // 1024  # kbps 변환
                bout = int(s.find("bw_out").text) // 1024
                status_msg.append(f"[{name}] In: {bin}k / Out: {bout}k")
    except:
        return ["서버 연결 불가 (ID/PW 또는 주소 확인)"]
    
    return status_msg if status_msg else ["현재 송출 중인 카메라 없음"]

def clear_screen():
    """화면 지우기 및 대시보드 + 서버 상태 출력"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("="*65)
    print(" [ RTMP 통합 관제 - 실시간 모니터링 모드 ] ".center(65))
    print("="*65)
    print(f"  CH1: {stream_names[1]:<15} |  CH2: {stream_names[2]:<15}")
    print(f"  CH3: {stream_names[3]:<15} |  CH4: {stream_names[4]:<15}")
    print(f"  CH5(MIC): {stream_names[5]:<15}")
    print("-" * 65)
    
    # 서버 실시간 상태 출력 구역
    print(" [ 실시간 서버 신호 상태 ]")
    server_info = get_server_status()
    for info in server_info:
        print(f" > {info}")
    
    print("-" * 65)
    print(" [명령어] 채널번호 이름 (예: 1 cam01) / 채널번호 off / exit")
    print("-" * 65)
    print(" 명령 입력 >> ", end="", flush=True)

def start_stream(ch, name, is_auto_refresh=False):
    if refresh_timers[ch]:
        refresh_timers[ch].cancel()

    stop_stream(ch, quiet=True)

    if is_auto_refresh:
        time.sleep(3.0) 

    stream_names[ch] = name
    clear_screen()
    
    x, y = positions.get(ch, (gap, gap))

    if ch == 5: # 마이크
        command = [
            "ffmpeg", "-f", "dshow", "-i", "audio=usb마이크(USB Audio Device)",
            "-ac", "1", "-ar", "44100", "-fflags", "nobuffer", "-flags", "low_delay",
            "-f", "flv", base_url + name
        ]
    else: # 카메라
        command = [
            "ffplay", "-x", str(width), "-y", str(height),
            "-fflags", "nobuffer", "-flags", "low_delay",
            "-framedrop", "-strict", "experimental",
            "-left", str(x), "-top", str(y),
            "-window_title", f"CH{ch}: {name}",
            base_url + name
        ]

    try:
        p = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5) 
        if p.poll() is None:
            streams[ch] = p
            clear_screen()
    except:
        pass

    if ch != 5:
        t = threading.Timer(RESTART_INTERVAL, start_stream, args=(ch, name, True))
        t.daemon = True
        t.start()
        refresh_timers[ch] = t

def stop_stream(ch, quiet=False):
    if refresh_timers[ch]:
        refresh_timers[ch].cancel()
        refresh_timers[ch] = None

    if ch in streams and streams[ch] and streams[ch].poll() is None:
        streams[ch].terminate()
        try: streams[ch].wait(timeout=1.0)
        except: streams[ch].kill()
        
        streams[ch] = None
        stream_names[ch] = "OFF"
        if not quiet: clear_screen()

def main_menu():
    # 5초마다 화면의 서버 정보만 갱신해주는 스레드 (입력 방해 안 함)
    def auto_refresh_ui():
        while True:
            time.sleep(5)
            # 입력 중이 아닐 때만 화면 갱신 (선택 사항, 여기서는 그냥 갱신)
            # clear_screen() 

    threading.Thread(target=auto_refresh_ui, daemon=True).start()

    while True:
        clear_screen()
        try:
            user_input = sys.stdin.readline().strip().split()
            if not user_input: continue
            
            if user_input[0].lower() == "exit":
                for i in range(1, 6): stop_stream(i, quiet=True)
                break
            
            if len(user_input) < 2: continue

            target_ch = int(user_input[0])
            action = user_input[1].lower()

            if action == "off":
                stop_stream(target_ch)
            else:
                threading.Thread(target=start_stream, args=(target_ch, user_input[1]), daemon=True).start()
                time.sleep(0.5)
        except:
            pass

if __name__ == "__main__":
    main_menu()