import os
import sys
import aiohttp
import asyncio
import google.generativeai as genai
import logging
import base64
import json
from collections import Counter
from datetime import datetime

# ----------------------------------------------------------------------
# 설정 (Configuration)
# ----------------------------------------------------------------------

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 환경 변수 로드
GH_API_TOKEN = os.environ.get('GH_API_TOKEN')
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Gemini AI 설정
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("Gemini API configured successfully.")
    except Exception as e:
        logger.error(f"Failed to configure Gemini API: {e}")
        model = None
else:
    logger.error("GEMINI_API_KEY is not set. AI review will not be available.")
    model = None

# ----------------------------------------------------------------------
# 헬퍼 함수 (Helper Functions)
# ----------------------------------------------------------------------

def is_resource_file(filename):
    """파일이 코드 리뷰에서 제외할 리소스 파일인지 확인"""
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

def detect_file_type(file_path):
    """파일 경로에서 확장자를 추출하여 파일 타입 반환"""
    extensions = {
        '.py': 'python', '.js': 'javascript', '.html': 'html', '.css': 'css',
        '.ts': 'typescript', '.jsx': 'react', '.tsx': 'react', '.java': 'java',
        '.c': 'c', '.cpp': 'cpp', '.cs': 'csharp', '.go': 'go', '.rs': 'rust',
        '.rb': 'ruby', '.php': 'php', '.sql': 'sql', '.shader': 'unity-shader',
        '.anim': 'unity-animation', '.prefab': 'unity-prefab', '.mat': 'unity-material',
        '.asset': 'unity-asset', '.unity': 'unity-scene'
    }
    ext = os.path.splitext(file_path)[1].lower()
    return extensions.get(ext)

def is_unity_related(file_path):
    """파일이 Unity 프로젝트와 관련되어 있는지 확인"""
    unity_related_patterns = [
        'Assets/', '.cs', '.shader', '.anim', '.prefab', '.mat', '.unity',
        'ProjectSettings/', 'Packages/', 'Assembly-CSharp', 'ScriptableObject'
    ]
    return any(pattern in file_path for pattern in unity_related_patterns)

async def test_api_token_access(owner_repo):
    """API 토큰이 레포지토리에 접근 가능한지 테스트하는 진단 함수"""
    logger.info(f"Testing API token access for repository: {owner_repo}")
    if not GH_API_TOKEN:
        logger.error("CRITICAL: GH_API_TOKEN is not set.")
        return False

    test_url = f"https://api.github.com/repos/{owner_repo}"
    headers = {'Accept': 'application/vnd.github.v3+json', 'Authorization': f'token {GH_API_TOKEN}'}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(test_url, headers=headers) as resp:
                if resp.status == 200:
                    logger.info("✅ API token has valid access to the repository.")
                    return True
                else:
                    error_info = await resp.json()
                    logger.error(f"❌ API token access test failed! Status: {resp.status}")
                    logger.error(f"Error Message: {error_info.get('message', 'No message')}")
                    logger.error("Please check if the token has 'repo' scope and is authorized for SSO if it's an organization repository.")
                    return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during API access test: {e}")
        return False

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
                diff_text = await resp.text()
                
                # 리소스 파일 제외 및 diff 정리
                filtered_diff_lines = []
                current_file_is_resource = False
                for line in diff_text.split('\n'):
                    if line.startswith('diff --git'):
                        # a/path/to/file b/path/to/file 에서 파일 경로 추출
                        try:
                            file_path = line.split(' b/')[-1]
                            current_file_is_resource = is_resource_file(file_path)
                        except IndexError:
                            current_file_is_resource = False
                    
                    if not current_file_is_resource:
                        filtered_diff_lines.append(line)

                return '\n'.join(filtered_diff_lines)
    except aiohttp.ClientResponseError as e:
        logger.error(f"Error fetching diff: {e.status}, message='{e.message}', url='{diff_url}'")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching diff: {e}")
        return None

async def get_ai_code_review(diff_text):
    """Gemini AI를 이용해 리뷰 생성"""
    if not model:
        return "Gemini 모델이 초기화되지 않았습니다. API 키를 확인해주세요."
    if not diff_text:
        return "코드 변경 사항이 없어 리뷰를 생성할 수 없습니다."
    
    prompt = f"""
As an expert code reviewer, please analyze the following code changes (`git diff` format).
Provide your feedback in Korean, using markdown for clarity. Structure your review with these sections:

1.  **📝 변경사항 요약 (Summary):** Briefly describe the main purpose of these changes.
2.  **✅ 좋은 점 (Pros):** Point out well-implemented parts or good practices.
3.  **🤔 개선 제안 (Suggestions):** Suggest improvements for readability, performance, or potential issues.
4.  **❓ 질문 (Questions):** Ask questions if the intent of the code is unclear.

---

**Code Changes:**
```diff
{diff_text}
```
"""
    try:
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating code review from Gemini: {e}")
        return f"코드 리뷰 생성 중 오류가 발생했습니다: {str(e)}"

async def send_to_discord(data):
    """Discord에 메시지 전송"""
    if not DISCORD_WEBHOOK_URL:
        logger.error("DISCORD_WEBHOOK_URL is not set. Cannot send message.")
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DISCORD_WEBHOOK_URL, json=data) as resp:
                if resp.status >= 300:
                    logger.error(f"Discord API returned error {resp.status}: {await resp.text()}")
                else:
                    logger.info(f"Successfully sent message to Discord (status: {resp.status}).")
    except Exception as e:
        logger.error(f"Error sending to Discord: {e}")

def split_review_into_messages(review_text, max_length=1900):
    """리뷰 텍스트를 Discord 메시지 최대 길이에 맞게 분할"""
    messages = []
    while len(review_text) > max_length:
        split_pos = review_text.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = max_length
        messages.append(review_text[:split_pos])
        review_text = review_text[split_pos:].lstrip()
    messages.append(review_text)
    return messages

# ----------------------------------------------------------------------
# 메인 실행 로직 (Main Execution Logic)
# ----------------------------------------------------------------------

async def main():
    logger.info("Starting AI Code Review Bot from GitHub Actions...")

    event_path = os.environ.get('GITHUB_EVENT_PATH')
    event_name = os.environ.get('GITHUB_EVENT_NAME')

    if not event_path:
        logger.error("GITHUB_EVENT_PATH not found.")
        sys.exit(1)

    with open(event_path, 'r') as f:
        payload = json.load(f)

    # 이벤트 유형에 따라 정보 추출
    if event_name == 'push':
        logger.info("Processing 'push' event...")
        if payload.get('deleted', False):
            logger.info("Ignoring 'deleted' push event (branch was deleted).")
            return

        owner_repo = payload['repository']['full_name']
        base_commit = payload.get('before')
        head_commit = payload.get('after')

        if not base_commit or base_commit.startswith('0000000'):
            logger.info("New branch push or first push detected. No base to compare. Exiting.")
            return

        diff_url = f"https://api.github.com/repos/{owner_repo}/compare/{base_commit}...{head_commit}"
        
        head_commit_info = payload.get('head_commit')
        if not head_commit_info:
            logger.info("No head_commit details found in push payload.")
            return
            
        title = head_commit_info['message'].split('\n')[0]
        target_url = head_commit_info['url']
        author = head_commit_info['author']['name']

    else:
        logger.warning(f"Unsupported event type: {event_name}. Exiting.")
        return

    # API 토큰 접근 권한 테스트
    if not await test_api_token_access(owner_repo):
        logger.error("Exiting due to failed API token access test.")
        return

    # diff 가져오기 (URL에 .diff 확장자 추가)
    logger.info(f"Fetching diff from: {diff_url}")
    diff_text = await get_code_diff(f"{diff_url}")
    if not diff_text or not diff_text.strip():
        logger.info("No code changes found to review. Exiting.")
        return

    # AI 리뷰 생성
    review_text = await get_ai_code_review(diff_text)

    # Discord 메시지 구성 및 전송
    base_embed = {
        'title': f"🤖 코드 리뷰: {title}",
        'url': target_url,
        'color': 0x7289DA, # Discord 색상
        'footer': {'text': f"작성자: {author} | 레포지토리: {owner_repo}"},
        'timestamp': datetime.utcnow().isoformat()
    }

    review_messages = split_review_into_messages(review_text)
    for i, message_part in enumerate(review_messages, 1):
        embed = base_embed.copy()
        if len(review_messages) > 1:
            embed['title'] += f" ({i}/{len(review_messages)})"
        embed['description'] = message_part
        
        await send_to_discord({'username': 'AI 코드 리뷰 봇', 'embeds': [embed]})

    logger.info("Code review process completed successfully.")

if __name__ == '__main__':
    asyncio.run(main())
