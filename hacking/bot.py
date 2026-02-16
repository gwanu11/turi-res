import os
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

# --- Render 환경 변수 로드 ---
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
REDIRECT_URI = os.environ.get('REDIRECT_URI')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
API_ENDPOINT = 'https://discord.com/api/v10'

# 임시 데이터 저장소 (서버 재시작 시 초기화됨)
user_list = []

# 관리자 페이지 HTML 디자인
ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>관리자 대시보드</title>
    <meta charset="utf-8">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #36393f; color: #dcddde; padding: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background-color: #2f3136; }
        th, td { border: 1px solid #202225; padding: 12px; text-align: left; }
        th { background-color: #5865F2; color: white; }
        tr:hover { background-color: #32353b; }
        h2 { color: #fff; }
        .count-box { display: inline-block; background: #43b581; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.9em; }
    </style>
</head>
<body>
    <h2>🚀 실시간 연동 유저 목록 <span class="count-box">총 {{ count }}명</span></h2>
    <table>
        <tr>
            <th>유저명(ID)</th>
            <th>이메일</th>
            <th>서버 수</th>
            <th>연결된 계정</th>
        </tr>
        {% for user in users %}
        <tr>
            <td>{{ user.username }}<br><small style="color: #72767d;">{{ user.id }}</small></td>
            <td>{{ user.email }}</td>
            <td>{{ user.guilds }}개</td>
            <td>{{ user.connections }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route('/')
def home():
    return "서버가 정상 작동 중입니다. 연동 URL을 사용하세요."

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "오류: 인증 코드가 없습니다.", 400
    
    try:
        # 1. Access Token 교환
        data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        token_res = requests.post(f'{API_ENDPOINT}/oauth2/token', data=data, headers=headers).json()
        access_token = token_res.get('access_token')

        if not access_token:
            return f"인증 실패: {token_res.get('error_description', '토큰을 받지 못했습니다.')}", 400

        # 2. 유저 데이터 수집
        auth_header = {'Authorization': f'Bearer {access_token}'}
        u = requests.get(f'{API_ENDPOINT}/users/@me', headers=auth_header).json()
        g = requests.get(f'{API_ENDPOINT}/users/@me/guilds', headers=auth_header).json()
        c = requests.get(f'{API_ENDPOINT}/users/@me/connections', headers=auth_header).json()
        
        # 3. 데이터 정리 및 저장
        conn_names = ", ".join([conn['type'] for conn in c]) if c else "없음"
        user_data = {
            "username": u.get('username'),
            "id": u.get('id'),
            "email": u.get('email', 'N/A'),
            "guilds": len(g),
            "connections": conn_names
        }
        
        # 중복 체크 후 리스트 추가
        if not any(item['id'] == u['id'] for item in user_list):
            user_list.append(user_data)
            
            # 4. 디스코드 웹훅 알림 전송
            webhook_payload = {
                "embeds": [{
                    "title": "🔔 신규 유저 연동 완료",
                    "color": 5814783,
                    "fields": [
                        {"name": "유저", "value": f"{u['username']} ({u['id']})", "inline": True},
                        {"name": "이메일", "value": u.get('email', 'N/A'), "inline": True},
                        {"name": "서버 수", "value": f"{len(g)}개", "inline": True},
                        {"name": "연결 계정", "value": conn_names, "inline": False}
                    ]
                }]
            }
            requests.post(WEBHOOK_URL, json=webhook_payload)

        return "<h1>✅ 연동 성공!</h1><p>이제 이 창을 닫으셔도 됩니다.</p>"

    except Exception as e:
        return f"서버 오류 발생: {str(e)}", 500

@app.route('/admin')
def admin():
    # 저장된 유저 목록 확인 페이지
    return render_template_string(ADMIN_HTML, users=user_list, count=len(user_list))

if __name__ == '__main__':
    # Render는 PORT 환경 변수를 사용함
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
