import os
import sys
import hmac
import hashlib
import aiohttp
import asyncio
import google.generativeai as genai
import logging
import base64
import json
from collections import Counter

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 환경 변수 로드 (GitHub Actions Secrets & Context에서 가져옴) ---
GITHUB_API_TOKEN = os.environ.get('GITHUB_API_TOKEN')
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# --- 기존 코드의 핵심 함수들 (거의 그대로 사용) ---
# is_resource_file, detect_file_type, is_unity_related 등 모든 헬퍼 함수를 여기에 포함합니다.
# (사용자 제공 코드의 모든 함수를 여기에 붙여넣으세요)

def is_resource_file(filename):
    """파일이 리소스 파일인지 확인"""
    resource_extensions = {
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.ico', '.svg',
        '.mp3', '.wav', '.ogg', '.m4a', '.aac', '.wma', '.flac', '.aiff', '.mid', '.midi',
        '.unity3d', '.bank', '.fsb', '.vag', '.xma', '.xwb',
        '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm',
        '.unity', '.prefab', '.asset', '.mat', '.anim', '.controller', '.mask', '.meta',
        '.fbx', '.obj', '.blend', '.tga', '.psd', '.ai', '.pdf',
        '.zip', '.rar', '.7z', '.tar', '.gz',
        '.exe', '.dll', '.so', '.dylib', '.bin'
    }
    resource_dirs = {
        'Assets/Resources', 'Assets/StreamingAssets', 'Assets/Textures', 'Assets/Models',
        'Assets/Animations', 'Assets/Audio', 'Assets/Scenes', 'Assets/Prefabs',
        'Assets/Materials', 'Assets/Sprites', 'Library', 'Temp', 'Logs'
    }
    ext = os.path.splitext(filename)[1].lower()
    if ext in resource_extensions:
        return True
    for dir_path in resource_dirs:
        if filename.startswith(dir_path):
            return True
    return False

async def get_code_diff(diff_url):
    """GitHub API로 diff 내용 가져오기"""
    if not GITHUB_API_TOKEN:
        logger.error("Cannot fetch diff without GITHUB_API_TOKEN.")
        return None
    headers = {
        'Accept': 'application/vnd.github.v3.diff',
        'Authorization': f'token {GITHUB_API_TOKEN}'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(diff_url, headers=headers) as resp:
                resp.raise_for_status()
                diff_text = await resp.text()
                # (diff 압축 및 정리 로직은 제공된 코드와 동일하게 유지)
                # ...
                return diff_text # 간결함을 위해 원본 diff를 반환, 실제로는 정리된 diff를 반환해야 함
    except Exception as e:
        logger.error(f"Error fetching diff: {e}")
        return None

async def get_repo_info(owner_repo, changed_files=None):
    """GitHub API를 통해 저장소 정보 가져오기"""
    # (제공된 코드의 get_repo_info 함수 로직과 동일하게 유지)
    # ...
    return {"name": "example-repo", "description": "An example repository"} # 예시 반환

async def get_ai_code_review(diff_text, file_type=None, is_unity_project=False, repo_info=None):
    """Gemini AI를 이용해 리뷰 생성"""
    # (제공된 코드의 get_ai_code_review 함수 로직과 동일하게 유지)
    # ...
    return {"summary": "This is a summary.", "full_review": "This is the full review."} # 예시 반환

async def send_to_discord(data):
    """Discord에 메시지 전송"""
    # (제공된 코드의 send_to_discord 함수 로직과 동일하게 유지)
    # ...
    logger.info(f"Sending to Discord: {data['embeds'][0]['title']}")

def split_review_into_messages(review_text, max_length=1900):
    """리뷰 텍스트를 여러 메시지로 분할"""
    # (제공된 코드의 split_review_into_messages 함수 로직과 동일하게 유지)
    # ...
    return [review_text] # 예시 반환

# --- 메인 실행 로직 ---
async def main():
    """GitHub Actions에서 직접 실행될 메인 함수"""
    logger.info("Starting AI Code Review Bot from GitHub Actions...")

    # 1. GitHub Actions 환경 변수에서 이벤트 정보 가져오기
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    if not event_path:
        logger.error("GITHUB_EVENT_PATH not found.")
        return

    with open(event_path, 'r') as f:
        payload = json.load(f)

    # 2. PR 정보 추출
    pr = payload.get('pull_request')
    if not pr:
        logger.info("Not a pull_request event. Exiting.")
        return

    owner_repo = payload['repository']['full_name']
    diff_url = pr['diff_url']
    title = pr['title']
    target_url = pr['html_url']
    author = pr['user']['login']

    # 3. 변경된 파일 목록 추출 및 분석 (기존 로직 활용)
    # 이 부분은 GitHub API를 호출하여 파일 목록을 가져와야 합니다.
    # 여기서는 간단하게 예시로 처리합니다.
    changed_files = ["src/main.js", "src/utils.cs"]
    is_unity_project = any('unity' in file or '.cs' in file for file in changed_files)
    file_type = "csharp" # 예시

    # 4. diff 가져오기
    diff_text = await get_code_diff(diff_url)
    if not diff_text:
        logger.error("Could not fetch diff. Exiting.")
        return

    # 5. 저장소 정보 가져오기
    repo_info = await get_repo_info(owner_repo, changed_files)

    # 6. AI 리뷰 생성
    review_result = await get_ai_code_review(diff_text, file_type, is_unity_project, repo_info)

    # 7. Discord 메시지 구성 및 전송 (기존 로직 활용)
    project_icon = "🎮 Unity " if is_unity_project else ""
    base_embed = {
        'title': f"{project_icon}코드 리뷰: {title}",
        'url': target_url,
        'color': 7506394,
        'footer': {'text': f"작성자: {author}"}
    }
    
    # ... (메시지 분할 및 전송 로직) ...
    review_messages = split_review_into_messages(review_result['full_review'])
    for i, message_text in enumerate(review_messages, 1):
        review_embed = base_embed.copy()
        review_embed['title'] = f"{project_icon}코드 리뷰 ({i}/{len(review_messages)}): {title}"
        review_embed['description'] = message_text
        await send_to_discord({
            'username': 'Unity 코드 리뷰 AI',
            'embeds': [review_embed]
        })

    logger.info("Code review process completed successfully.")


if __name__ == '__main__':
    # 비동기 메인 함수 실행
    asyncio.run(main())
