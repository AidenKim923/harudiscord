import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from datetime import datetime, timedelta
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='|', intents=intents)

# 데이터베이스 연결 및 테이블 생성
conn = sqlite3.connect('attendance.db')
c = conn.cursor()

# 출석 테이블 생성 (guild_id 추가)
c.execute('''CREATE TABLE IF NOT EXISTS attendance (
    guild_id INTEGER,
    user_id INTEGER,
    date TEXT,
    year INTEGER,
    week INTEGER,
    cumulative INTEGER,
    last_attendance TEXT,
    PRIMARY KEY (guild_id, user_id, date)
)''')
conn.commit()

# 주간 및 하루에 한 번만 출석 체크 (DB 기반, guild_id 추가)
def check_attendance_db(guild_id, user_id):
    now = datetime.now()
    year, week_num, _ = now.isocalendar()
    today = now.strftime('%Y-%m-%d')  # 오늘 날짜

    # 오늘 출석했는지 확인
    c.execute('SELECT * FROM attendance WHERE guild_id=? AND user_id=? AND date=?', (guild_id, user_id, today))
    result = c.fetchone()

    if result is None:
        # 오늘 처음 출석하는 경우
        c.execute('INSERT INTO attendance (guild_id, user_id, date, year, week, cumulative, last_attendance) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                    (guild_id, user_id, today, year, week_num, 1, now.strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
    else:
        # 이미 출석한 경우
        return {'already_checked_in': True, 'last_attendance': result[6]}
    
    # 누적 출석 조회
    c.execute('SELECT SUM(cumulative) FROM attendance WHERE guild_id=? AND user_id=?', (guild_id, user_id))
    cumulative = c.fetchone()[0]

    # 마지막 출석 시간 반환
    return {'weekly': week_num, 'cumulative': cumulative, 'last_attendance': now.strftime('%Y-%m-%d %H:%M:%S')}

# 출석체크 명령어
@bot.tree.command(name="출석", description="오늘의 출석을 체크합니다.")
async def 출석(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    user_id = interaction.user.id
    attendance = check_attendance_db(guild_id, user_id)

    if 'already_checked_in' in attendance:
        await interaction.response.send_message(f"{interaction.user.mention} 이미 오늘 출석했습니다. 마지막 출석 시간: {attendance['last_attendance']}")
    else:
        await interaction.response.send_message(f"{interaction.user.mention} 출석 완료!\n"
                                                f"누적 출석: {attendance['cumulative']}회\n"
                                                f"마지막 출석 시간: {attendance['last_attendance']}")

# 사용자 이름과 태그를 가져오는 함수
async def get_member_name_and_tag(guild, user_id):
    try:
        member = await guild.fetch_member(user_id)
        return f"{member.display_name}({member.name}#{member.discriminator})"
    except discord.errors.NotFound:
        return f"알 수 없는 사용자(ID: {user_id})"

# 주간 출석 확인 명령어 (guild_id 추가)
@bot.tree.command(name="주간출석", description="이번 주 전체 사용자의 출석 현황을 확인합니다.")
async def 주간출석(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    now = datetime.now()
    year, week_num, _ = now.isocalendar()

    c.execute('''
        SELECT user_id, 
        COUNT(*) as count, 
        MAX(date) as last_attendance_date
        FROM attendance 
        WHERE guild_id=? AND year=? AND week=? 
        GROUP BY user_id 
        ORDER BY count DESC, last_attendance_date DESC
    ''', (guild_id, year, week_num))
    weekly_attendance = c.fetchall()

    embed = discord.Embed(title="이번 주 출석 현황", color=discord.Color.blue())
    
    for rank, (user_id, count, last_attendance_date) in enumerate(weekly_attendance, 1):
        user_name = await get_member_name_and_tag(interaction.guild, user_id)
        
        if rank == 1:
            rank_emoji = "🥇"
        elif rank == 2:
            rank_emoji = "🥈"
        elif rank == 3:
            rank_emoji = "🥉"
        else:
            rank_emoji = f"{rank}등"
        
        embed.add_field(
            name=f"{rank_emoji} {user_name}",
            value=f"{count}회 출석\n마지막 출석: {last_attendance_date}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# 전체 출석 랭킹 확인 명령어 
@bot.tree.command(name="출석랭킹", description="전체 사용자의 누적 출석 랭킹을 확인합니다.")
async def 출석랭킹(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    c.execute('''
        SELECT user_id, 
        SUM(cumulative) as total, 
        MAX(date(last_attendance)) as last_attendance_date
        FROM attendance 
        WHERE guild_id=?
        GROUP BY user_id 
        ORDER BY total DESC
    ''', (guild_id,))
    rankings = c.fetchall()

    embed = discord.Embed(title="전체 출석 랭킹", color=discord.Color.gold())
    for rank, (user_id, total, last_attendance_date) in enumerate(rankings, 1):
        user_name = await get_member_name_and_tag(interaction.guild, user_id)
        
        if rank == 1:
            rank_emoji = "🥇"
        elif rank == 2:
            rank_emoji = "🥈"
        elif rank == 3:
            rank_emoji = "🥉"
        else:
            rank_emoji = f"{rank}등"
        
        embed.add_field(
            name=f"{rank_emoji} {user_name}", 
            value=f"총 출석: {total}회\n마지막 출석: {last_attendance_date}", 
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# 마지막 출석 확인 명령어
@bot.tree.command(name="마지막출석", description="본인의 마지막 출석 시간을 확인합니다.")
async def 마지막출석(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    user_id = interaction.user.id

    c.execute('SELECT last_attendance FROM attendance WHERE guild_id=? AND user_id=? ORDER BY date DESC LIMIT 1', (guild_id, user_id))
    result = c.fetchone()

    embed = discord.Embed(title="마지막 출석 정보", color=discord.Color.green())
    if result:
        embed.add_field(name=interaction.user.name, value=f"마지막 출석 시간: {result[0]}", inline=False)
    else:
        embed.add_field(name=interaction.user.name, value="아직 출석 기록이 없습니다.", inline=False)

    await interaction.response.send_message(embed=embed)

# 출석 미달 확인 명령어 
@bot.tree.command(name="출석미달", description="지난주 출석 3회 미만인 유저를 확인합니다.")
async def 출석미달(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    today = datetime.now()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)

    last_monday_str = last_monday.strftime('%Y-%m-%d')
    last_sunday_str = last_sunday.strftime('%Y-%m-%d')

    c.execute('''SELECT a.user_id, COUNT(*) as attendances, MAX(a.last_attendance) as last_attendance
                FROM attendance a
                WHERE a.guild_id=? AND a.date BETWEEN ? AND ?
                GROUP BY a.user_id
                HAVING attendances < 3''', (guild_id, last_monday_str, last_sunday_str))
    users_below_threshold = c.fetchall()

    embed = discord.Embed(title="지난주 출석 미달 유저", description=f"{last_monday_str} ~ {last_sunday_str}", color=discord.Color.red())
    
    if not users_below_threshold:
        embed.add_field(name="알림", value="지난주에 출석 3회 미만인 유저가 없습니다.", inline=False)
    else:
        for user_id, attendances, last_attendance in users_below_threshold:
            try:
                user = await bot.fetch_user(user_id)
                user_name = user.name
            except discord.errors.NotFound:
                user_name = f"알 수 없는 사용자 (ID: {user_id})"
            embed.add_field(name=user_name, value=f"{attendances}회 출석, 마지막 출석: {last_attendance}", inline=False)

    await interaction.response.send_message(embed=embed)

# 명령어 목록을 출력하는 embed 명령어
@bot.tree.command(name="명령어", description="봇의 명령어 목록을 확인합니다.")
async def 명령어(interaction: discord.Interaction):
    embed = discord.Embed(
        title="봇 명령어 목록",
        description="아래는 이 봇의 명령어 목록입니다.",
        color=discord.Color.blue()
    )

    # 출석 관련 명령어 추가
    embed.add_field(
        name="**출석 관련 명령어**",
        value=(
            "`/출석` - 오늘 출석을 합니다. 하루에 한 번만 가능.\n"
            "`/주간출석` - 이번 주에 몇 번 출석했는지 전체 사용자의 출석 횟수를 확인합니다.\n"
            "`/출석랭킹` - 모든 사용자의 누적 출석 랭킹을 보여줍니다.\n"
            "`/마지막출석` - 본인의 마지막 출석 시간을 확인합니다."
        ),
        inline=False
    )

    # 기타 명령어 추가
    embed.add_field(
        name="**기타 명령어**",
        value="`/명령어` - 봇의 명령어 목록을 확인합니다.",
        inline=False
    )

    # Embed 메시지를 보냅니다.
    await interaction.response.send_message(embed=embed)

# 봇 종료 시 데이터베이스 연결 닫기
@bot.event
async def on_shutdown():
    conn.close()

@bot.event
async def on_ready():
    print(f'봇이 로그인되었습니다: {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"동기화된 명령어 수: {len(synced)}")
    except Exception as e:
        print(f"명령어 동기화 중 오류 발생: {e}")
    
    # 봇의 상태 메시지 설정
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="출석 체크"))
    
    # 봇 설명 추가
    bot_description = "봇 설명 체크"
    if not bot.description:
        bot.description = bot_description

# 봇 실행
bot.run(os.getenv('DISCORD_BOT_TOKEN'))