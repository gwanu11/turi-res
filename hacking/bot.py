import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

# --- 설정 ---
CLIENT_ID = '내_클라이언트_ID'
CLIENT_SECRET = '내_클라이언트_시크릿'
REDIRECT_URI = 'http://localhost:5000/callback'
WEBHOOK_URL = '디스코드_웹훅_URL'
API_ENDPOINT = 'https://discord.com/api/v10'

# 임시 저장소 (프로그램 재시작 시 초기화됨, 영구 저장을 원하면 파일을 써야 함)
user_list = []

# HTML 템플릿 (관리자 페이지)
ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>연동 유저 목록</title>
    <style>
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #5865F2; color: white; }
        tr:nth-child(even) { background-color: #f2 f2 f2; }
    </style>
</head>
<body>
    <h2>🚀 연동된 유저 리스트 (총 {{ count }}명)</h2>
    <table>
        <tr>
            <th>유저명</th>
            <th>ID</th>
            <th>이메일</th>
            <th>서버 수</th>
            <th>연결 계정</th>
        </tr>
        {% for user in users %}
        <tr>
            <td>{{ user.username }}</td>
            <td>{{ user.id }}</td>
            <td>{{ user.email }}</td>
            <td>{{ user.guilds }}개</td>
            <td>{{ user.connections }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route('/callback')
def callback():
    code = request.args.get('code')
    
    # 1. 토큰 발급
    data = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI}
    token_res = requests.post(f'{API_ENDPOINT}/oauth2/token', data=data).json()
    access_token = token_res.get('access_token')

    # 2. 정보 수집
    headers = {'Authorization': f'Bearer {access_token}'}
    u = requests.get(f'{API_ENDPOINT}/users/@me', headers=headers).json()
    g = requests.get(f'{API_ENDPOINT}/users/@me/guilds', headers=headers).json()
    c = requests.get(f'{API_ENDPOINT}/users/@me/connections', headers=headers).json()
    
    conn_names = ", ".join([conn['type'] for conn in c])
    
    # 데이터 정리
    user_data = {
        "username": u['username'],
        "id": u['id'],
        "email": u.get('email', 'N/A'),
        "guilds": len(g),
        "connections": conn_names
    }
    
    # 중복 체크 후 리스트 저장
    if not any(item['id'] == u['id'] for item in user_list):
        user_list.append(user_data)
        
        # 3. 웹훅 전송
        requests.post(WEBHOOK_URL, json={
            "content": f"🔔 **신규 연동:** {u['username']} (서버 {len(g)}개)"
        })

    return "✅ 연동 완료! 목록에 추가되었습니다."

@app.route('/admin')
def admin():
    # 관리자 페이지 표시
    return render_template_string(ADMIN_HTML, users=user_list, count=len(user_list))

if __name__ == '__main__':
    app.run(port=5000, debug=True)