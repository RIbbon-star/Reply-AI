import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def fetch_reviews():  # 👈 [핵심] 스트림릿에서 갖다 쓸 수 있게 함수로 포장!
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 서버용 헤드리스 옵션
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    unanswered_reviews = []
    
    try:
        # 1. 우리 가게 네이버 플레이스 리뷰 페이지로 곧장 이동!
        driver.get("https://m.place.naver.com/restaurant/1950512318/review/visitor") 
        time.sleep(3) # 페이지가 완전히 로딩될 때까지 3초 넉넉하게 대기
        
        # 2. [검색창 코드 삭제됨] 이미 들어왔으므로 바로 리뷰 카드들을 통째로 긁어옵니다.
        # 네이버 플레이스의 리뷰 1개 덩어리 클래스명은 보통 'E02A2' 또는 'P92vA' 등인데, 
        # 가장 확실한 건 리뷰 텍스트가 담긴 태그들을 긁어오는 것입니다.
        # (※ 2026년 현재 기준 플레이스 리뷰 텍스트 영역의 일반적인 태그 구조를 타겟팅합니다)
        all_reviews = driver.find_elements(By.CLASS_NAME, "pui__GStJHB") # 👈 네이버 플레이스 리뷰 박스 단위 (수정 가능)
        
        for review in all_reviews:
            # 3. 🔍 이 리뷰 박스 안에 '사장님 답글' 구역이 있는지 검사합니다.
            # 네이버는 사장님 답글 영역에 주로 'reply'나 특정 클래스명을 부여합니다.
            # 여기서는 'review_reply' 혹은 사장님 아이콘 태그가 있는지 체크하는 원리입니다.
            boss_reply = review.find_elements(By.CLASS_NAME, "v698A") # 👈 사장님 답글 구역 클래스명 예시
            
            # 4. 사장님 답글 구역의 개수가 0개다? = 사장님이 아직 답글을 안 달았다!
            if len(boss_reply) == 0:
                # 손님이 쓴 진짜 리뷰 글자만 쏙 추출합니다.
                review_text = review.text
                
                # 가끔 빈 텍스트가 긁히는 것을 방지하기 위한 안전장치
                if review_text.strip(): 
                    unanswered_reviews.append({
                        "text": review_text,
                        "date": "최신"
                    })
            
    except Exception as e:
        print("크롤링 중 에러 발생:", e)
    finally:
        driver.quit()  # 무조건 브라우저 닫기!
        
    return unanswered_reviews  # 👈 [핵심] 긁어온 장바구니를 밖으로 던져줍니다!