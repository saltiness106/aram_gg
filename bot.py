import os
import discord
import requests
from datetime import datetime, timedelta

# 🔑 민감정보
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# 🔗 API 엔드포인트
ACCOUNT_API_URL = "https://asia.api.riotgames.com"
MATCH_API_URL = "https://asia.api.riotgames.com"

# 🔧 Discord 봇 설정
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f'✅ 로그인 완료! 봇 이름: {client.user}')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!금칼'):
        try:
            # 1. 입력 파싱: "!금칼 게임명#태그"
            command = message.content.split(' ', 1)
            if len(command) < 2:
                await message.channel.send("사용법: `!금칼 게임명#태그`")
                return

            parts = command[1].split('#', 1)
            if len(parts) < 2:
                await message.channel.send("올바른 형식으로 입력해주세요: `!금칼 게임명#태그`")
                return

            gameName, tagLine = parts[0], parts[1]

            # 2. 계정 정보 조회 → PUUID 가져오기
            headers = {"X-Riot-Token": RIOT_API_KEY}
            account_url = f"{ACCOUNT_API_URL}/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}"
            response = requests.get(account_url, headers=headers)
            response.raise_for_status()

            account_data = response.json()
            puuid = account_data.get('puuid')

            if not puuid:
                await message.channel.send(f"소환사 `{gameName}#{tagLine}`를 찾을 수 없습니다.")
                return

            # 3. PUUID로 최근 20개 칼바람(큐 ID 450) 경기 ID 목록 가져오기
            matches_url = f"{MATCH_API_URL}/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=450&start=0&count=20"
            matches_response = requests.get(matches_url, headers=headers)
            matches_response.raise_for_status()
            match_ids = matches_response.json()

            if not match_ids:
                await message.channel.send(f"`{gameName}#{tagLine}`님의 최근 칼바람 기록이 없습니다.")
                return

            # 4. 오전 6시 기준 오늘 승패 집계
            kst_now = datetime.now()
            today_6am_kst = kst_now.replace(hour=6, minute=0, second=0, microsecond=0)
            if kst_now.hour < 6:
                today_6am_kst -= timedelta(days=1)

            today_wins = today_losses = 0

            for match_id in match_ids:
                match_url = f"{MATCH_API_URL}/lol/match/v5/matches/{match_id}"
                match_response = requests.get(match_url, headers=headers)
                match_response.raise_for_status()
                match_data = match_response.json()

                game_creation_ts = match_data['info']['gameCreation'] // 1000
                game_creation_dt = datetime.fromtimestamp(game_creation_ts)

                # 금일 경기가 아니면 루프 중단 (최신 경기부터 가져오므로)
                if game_creation_dt < today_6am_kst:
                    break

                is_win = False
                for participant in match_data['info']['participants']:
                    if participant['puuid'] == puuid:
                        is_win = participant['win']
                        break
                
                if is_win:
                    today_wins += 1
                else:
                    today_losses += 1

            # 5. 결과 계산
            today_total = today_wins + today_losses
            today_winrate = (today_wins / today_total * 100) if today_total > 0 else 0

            # 6. 메시지 전송
            message_text = (
                f"금일 칼바람 **{today_wins}승 {today_losses}패** ({today_winrate:.1f}%)\n"
                "* 오전 6시 기준으로 갱신됨"
            )
            await message.channel.send(message_text)

        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 404:
                await message.channel.send(f"소환사 `{gameName}#{tagLine}`를 찾을 수 없습니다.")
            elif err.response.status_code == 403:
                await message.channel.send("🚫 라이엇 API 키가 만료되었거나 잘못되었습니다. 새 키를 발급받아주세요.")
            elif err.response.status_code == 401:
                await message.channel.send("🚫 API 인증 오류: 키가 비어있거나 잘못되었습니다.")
            else:
                await message.channel.send(f"데이터를 가져오는 중 오류가 발생했습니다: {err}")
        except Exception as e:
            await message.channel.send(f"⚠️ 오류가 발생했습니다: {e}")

# 🔥 봇 실행
client.run(DISCORD_BOT_TOKEN)