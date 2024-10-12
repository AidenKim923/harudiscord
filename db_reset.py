import sqlite3
import os

def reset_database():
    # 데이터베이스 파일 경로
    db_path = 'attendance.db'

    try:
        # 데이터베이스 연결
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # 기존 테이블 삭제
        c.execute("DROP TABLE IF EXISTS attendance")

        # 새로운 구조로 테이블 재생성
        c.execute('''CREATE TABLE attendance (
            guild_id INTEGER,
            user_id INTEGER,
            date TEXT,
            year INTEGER,
            week INTEGER,
            cumulative INTEGER,
            last_attendance TEXT,
            PRIMARY KEY (guild_id, user_id, date)
        )''')

        # 변경사항 저장
        conn.commit()

        print("데이터베이스가 성공적으로 초기화되었습니다.")

    except sqlite3.Error as e:
        print(f"데이터베이스 오류 발생: {e}")

    finally:
        # 데이터베이스 연결 종료
        if conn:
            conn.close()

if __name__ == "__main__":
    # 사용자 확인
    confirmation = input("정말로 데이터베이스를 초기화하시겠습니까? 이 작업은 모든 데이터를 삭제하고 테이블을 재생성합니다. 계속하려면 '확인'을 입력해주세요: ")

    if confirmation.lower() == '확인':
        reset_database()
    else:
        print("데이터베이스 초기화가 취소되었습니다.")
