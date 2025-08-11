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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 환경 변수 로드 ---
GH_API_TOKEN = os.environ.get('GH_API_TOKEN')
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# --- 헬퍼 함수들 ---
# (이전에 작성하신 is_resource_file, get_repo_info, get_ai_code_review 등 모든 헬퍼 함수를 여기에 포함시켜주세요.)

async def get_code_diff(diff_url):
    """GitHub API로 diff 내용 가져오기"""
    if not GH_API_TOKEN:
        logger.error("GH_API_TOKEN is not set. Cannot fetch diff.")
        return None
    headers = {'Accept': 'application/vnd.github.v3.diff', 'Authorization': f'token {GH_API_TOKEN}'}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(diff_url, headers=headers) as resp:
                resp.raise_for_status()
                return await resp.text()
    except aiohttp.ClientResponseError as e:
        logger.error(f"Error fetching diff: {e.status}, message='{e.message}', url='{diff_url}'")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching diff: {e}")
        return None

# ... (다른 모든 헬퍼 함수들) ...

# --- 메인 실행 로직 (수정됨) ---
async def main():
    """GitHub Actions에서 직접 실행될 메인 함수"""
    logger.info("Starting AI Code Review Bot from GitHub Actions...")

    event_path = os.environ.get('GITHUB_EVENT_PATH')
    event_name = os.environ.get('GITHUB_EVENT_NAME')

    if not event_path:
        logger.error("GITHUB_EVENT_PATH not found.")
        sys.exit(1)

    with open(event_path, 'r') as f:
        payload = json.load(f)

    # 이벤트 유형에 따라 정보 추출
    if event_name == 'pull_request':
        # (PR 로직은 기존과 동일)
        # ...
        pass
    elif event_name == 'push':
        logger.info("Processing 'push' event...")
        if payload.get('deleted', False):
            logger.info("Ignoring 'deleted' push event (branch was deleted).")
            return

        owner_repo = payload['repository']['full_name']
        base_commit = payload.get('before')
        head_commit = payload.get('after')

        # 'before' 커밋이 000... 이면 새 브랜치 푸시이므로 비교 대상이 없음
        if not base_commit or base_commit.startswith('0000000'):
            logger.info("New branch push or first push detected. No base to compare against. Exiting.")
            return

        if not head_commit:
            logger.info("No 'after' commit found in push payload. Exiting.")
            return

        # diff URL을 수동으로 더 안정적으로 구성
        diff_url = f"https://api.github.com/repos/{owner_repo}/compare/{base_commit}...{head_commit}.diff"
        
        head_commit_info = payload.get('head_commit')
        if not head_commit_info:
            logger.info("No head_commit details found in push payload.")
            return
            
        title = head_commit_info['message'].split('\n')[0]
        target_url = head_commit_info['url']
        author = head_commit_info['author']['name']
        changed_files = head_commit_info.get('added', []) + head_commit_info.get('modified', [])

    else:
        logger.warning(f"Unsupported event type: {event_name}. Exiting.")
        return

    # diff 가져오기
    logger.info(f"Fetching diff from: {diff_url}")
    diff_text = await get_code_diff(diff_url)
    if not diff_text or not diff_text.strip():
        logger.info("No code changes found to review. Exiting.")
        return

    # (이하 프로젝트 분석, 리뷰 생성, 디스코드 전송 로직은 기존과 동일)
    # ...
    
    logger.info("Code review process completed successfully.")


if __name__ == '__main__':
    # 이 파일 안에 모든 헬퍼 함수가 정의되어 있어야 합니다.
    asyncio.run(main())
