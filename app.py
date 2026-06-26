import streamlit as st
from supabase import create_client, Client
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import datetime

# [설정] 웹 페이지 제목 및 안내문
st.set_page_config(page_title="카페 리뷰 답글 AI", page_icon="☕", layout="centered")

# 2. 알림창 함수 정의
def st_latte_box(text: str):
    st.markdown(
        f"""
        <div style="
            background-color: #F5EBE6; 
            color: #5C4033; 
            padding: 15px; 
            border-radius: 8px; 
            border-left: 5px solid #D2B48C;
            margin-bottom: 15px;
            font-size: 15px;
            font-weight: 500;
        ">
            ☕ {text}
        </div>
        """, 
        unsafe_allow_html=True
    )

# 3. 🔐 [UX 개선] 비밀번호 입력창을 제어할 빈 컨테이너박스 생성
auth_container = st.empty()

# 컨테이너 상자 안에 비밀번호 입력창을 집어넣습니다.
password_input = auth_container.text_input("🔑 관리자 인증 비밀번호를 입력하세요:", type="password")

if password_input != st.secrets["APP_PASSWORD"]:
    st_latte_box("올바른 비밀번호를 입력하시면 AI 사장님 비서 기능이 활성화됩니다.")
    st.stop()  # 🛑 틀리면 여기서 대기
else:
    # 🎉 비밀번호가 맞으면? 입력창이 있던 상자 내용물을 싹 비워버립니다!
    auth_container.empty()
    # 만약 완전히 빈 공간이 어색하다면 아래 주석(#)을 풀고 성공 메시지를 띄워도 됩니다.
    # auth_container.success("🔓 인증되었습니다. 메인 화면을 편집하세요!")
# 4. 🎨 [비밀번호 통과자만 진입] 메인 화면 종합 CSS 테마 도색
st.markdown(
    """
    <style>
    .stApp { background-color: #FDFBF7 !important; }
    section[data-testid="stSidebar"] { background-color: #F5EBE6 !important; border-right: 1px solid #D2B48C !important; }
    section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 { color: #5C4033 !important; }
    div[data-baseweb="input"], div[data-baseweb="textarea"] { background-color: #FFFFFF !important; border: 1px solid #D2B48C !important; border-radius: 6px !important; }
    div.stButton > button { background-color: #8B5A2B !important; color: #FFFFFF !important; border: none !important; border-radius: 6px !important; font-weight: bold !important; transition: background-color 0.2s ease !important; }
    div.stButton > button:hover { background-color: #5C4033 !important; color: #FFFFFF !important; }
    label[data-testid="stWidgetLabel"] p { color: #5C4033 !important; font-weight: 600 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("☕ 카페 리뷰 답글 AI")
st.write("리뷰를 입력해주세요!")

# ------------------------------------------------------------------
# 🎨 [디자인 가미] 감성적인 카페라떼 알림 박스 함수
# ------------------------------------------------------------------
def st_latte_box(text: str):
    st.markdown(
        f"""
        <div style="
            background-color: #F5EBE6; 
            color: #5C4033; 
            padding: 15px; 
            border-radius: 8px; 
            border-left: 5px solid #D2B48C;
            margin-bottom: 15px;
            font-size: 15px;
            font-weight: 500;
        ">
            ☕ {text}
        </div>
        """, 
        unsafe_allow_html=True
    )

# ------------------------------------------------------------------
# 🔑 [보안 적용] 금고에서 OpenAI 키 및 Supabase 주소/열쇠 안전하게 가져오기
# ------------------------------------------------------------------
try:
    openai_api_key = st.secrets["OPENAI_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
except KeyError as e:
    st.error(f".streamlit/secrets.toml 파일에 {e} 설정이 누락되었습니다!")
    st.stop()

# ------------------------------------------------------------------
# 🔌 [DB 연동 & 캐싱] 수파베이스 클라우드 창고에 무선 연결 및 조회 최적화
# ------------------------------------------------------------------
@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(supabase_url, supabase_key)

supabase: Client = get_supabase_client()

@st.cache_data(ttl=600)  
def load_past_history_by_name(name: str):
    response = supabase.table("chat_history").select("name", "review", "reply").eq("name", name).execute()
    return response.data

@st.cache_data(ttl=60)
def load_sidebar_records():
    response = supabase.table("chat_history").select("id", "name", "review").order("id", desc=True).limit(500).execute()
    return response.data

@st.cache_data(ttl=60)
def load_all_view_records():
    response = supabase.table("chat_history").select("name", "review", "reply").order("id", desc=True).limit(500).execute()
    return response.data

# ------------------------------------------------------------------
# 🛠️ [사이드바] 관리자 전용 데이터 조작 패널 (안전을 위해 구석에 격리 보관)
# ------------------------------------------------------------------
st.sidebar.header("⚙️ 단골 명부 데이터 관리")

sidebar_records = load_sidebar_records()

if sidebar_records:
    unique_names = list(set([row["name"] for row in sidebar_records]))
    selected_name = st.sidebar.selectbox("1. 대상을 선택하세요:", unique_names)
    
    customer_specific_records = [row for row in sidebar_records if row["name"] == selected_name]
    
    detail_options = []
    id_mapping = {} 
    
    for idx, row in enumerate(customer_specific_records):
        short_review = row["review"][:15] + "..." if len(row["review"]) > 15 else row["review"]
        option_text = f"📄 [{idx+1}번째 기록] {short_review}"
        detail_options.append(option_text)
        id_mapping[option_text] = row["id"]
        
    detail_options.append(f"🚨 【{selected_name}】 손님 전체 기록 삭제")
    selected_detail = st.sidebar.selectbox("2. 어떤 기록을 삭제할까요?:", detail_options)
    
    session_key = f"del_{selected_name}_{selected_detail}"
    if session_key not in st.session_state:
        st.session_state[session_key] = False

    if not st.session_state[session_key]:
        if st.sidebar.button("❌ 선택 내역 삭제하기", key=f"btn_del_{session_key}"):
            st.session_state[session_key] = True
            st.rerun() 
            
    else:
        st.sidebar.warning("❓ 정말로 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
        col_yes, col_no = st.sidebar.columns(2)
        
        with col_yes:
            if st.sidebar.button("⭕ 네, 지웁니다", key="yes_execute_btn"):
                if "🚨" in selected_detail:
                    with st.spinner(f"【{selected_name}】 모든 기록 삭제 중..."):
                        target_ids = [row["id"] for row in customer_specific_records]
                        supabase.table("chat_history").delete().in_("id", target_ids).execute()
                else:
                    target_id = id_mapping[selected_detail]
                    with st.spinner("선택하신 방문 기록 한 개 삭제 중..."):
                        supabase.table("chat_history").delete().eq("id", target_id).execute()
                
                st.session_state[session_key] = False
                st.cache_data.clear() 
                st.sidebar.success("성공적으로 영구 삭제되었습니다!")
                st.rerun()
                
        with col_no:
            if st.sidebar.button("❌ 아니오", key="no_cancel_btn"):
                st.session_state[session_key] = False
                st.rerun()
else:
    st.sidebar.info("저장된 단골 명부가 없어 삭제 메뉴가 비활성화되었습니다.")


# ------------------------------------------------------------------
# ✍️ 메인 화면: 닉네임(선택), 리뷰 입력 및 옵션 선택
# ------------------------------------------------------------------
raw_customer_name = st.text_input(
    "👤 손님 닉네임 (입력하지 않으면 '익명 손님'으로 처리됩니다):",
    placeholder="예: 배민_아메리카노조아 (비워두셔도 됩니다)",
)
customer_name = raw_customer_name.strip() if raw_customer_name else ""

review_input = st.text_area(
    "📝 손님이 남긴 리뷰를 복사해서 붙여넣으세요:",
    placeholder="여기에 배민이나 네이버 리뷰를 붙여넣으세요.",
    height=150
)

tone_option = st.radio(
    "📢 어떤 말투로 답글을 작성할까요?",
    ("친절하고 따뜻하게 (기본)", "이모지 가득! 위트 있고 유머러스하게", "정중하고 진중하게 (불만족 리뷰 대응용)")
)


# ------------------------------------------------------------------
# ✨ AI 답글 생성 및 실시간 DB 클라우드 저장 로직
# ------------------------------------------------------------------
if st.button("✨ AI 답글 생성하기", key="ai_reply_button_1"):
    if not review_input:
        st_latte_box("리뷰 내용을 입력해주세요.")
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=openai_api_key, temperature=0.7)
        
        is_anonymous = False
        if not customer_name:
            is_anonymous = True
            now_str = datetime.datetime.now().strftime("%m%d_%H%M")
            db_save_name = f"익명_{now_str}"
            current_customer_records = []
        else:
            db_save_name = customer_name
            current_customer_records = load_past_history_by_name(customer_name)
        
        if current_customer_records and not is_anonymous:
            is_regular_customer = "예 (이전에 방문한 적이 있는 진짜 재방문 단골손님입니다!)"
            history_text = ""
            for i, record in enumerate(current_customer_records):
                history_text += f"\n[과거 대화 {i+1}]\n손님 리뷰: {record['review']}\n사장님 답글: {record['reply']}\n"
        else:
            is_regular_customer = "아니오 (이번이 첫 방문인 손님입니다. 아는 척하지 마세요)"
            history_text = "과거 방문 기록 없음"
        
        # 🌟 [요청사항 4번 반영] 프롬프트에 글자 수 제한 규칙을 강력하게 각인시킵니다.
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 친절하고 센스 있는 카페 사장님입니다. 
            손님이 남긴 리뷰에 대해 감동적이고 재방문을 유도하는 답글을 작성해주세요.
            
            [단골 여부 판독 결과]
            현재 리뷰를 남긴 손님은 진짜 재방문 단골인가요?: {is_regular}
            
            [핵심 지시사항]
            1. 위 판독 결과가 '예'라고 되어 있을 때만 반갑게 아는 척을 하세요.
            2. 배달앱 등록 규격에 맞춰, 공백 포함 반드시 **300자 내외로 너무 길지 않고 컴팩트하게** 작성하세요. (가장 중요)
            
            [참고용 이 손님의 과거 기록]
            {history}
            
            지정된 말투 스타일: {tone}"""),
            ("human", "현재 손님 리뷰: {review}")
        ])
        
        chain = prompt | llm
        
        with st.spinner("불필요한 토큰 낭비를 줄이고 안전하게 최적의 답글을 고민하는 중..."):
            response_ai = chain.invoke({
                "history": history_text,
                "tone": tone_option,
                "is_regular": is_regular_customer,
                "review": review_input
            })
            
            supabase.table("chat_history").insert({
                "name": db_save_name,
                "review": review_input,
                "reply": response_ai.content
            }).execute()
            
            st.cache_data.clear() 
            
            st.success("🎉 AI 사장님의 추천 답글이 완성되었습니다!")
            st.subheader("📋 추천 답글 내용")
            
            # 결과물 렌더링
            st.markdown(f"<div style='color: #4A3B32; font-size: 16px; line-height: 1.6; white-space: pre-wrap;'>{response_ai.content}</div>", unsafe_allow_html=True)
            
            # 🌟 [요청사항 4번 반영] 글자 수 카운터 배치
            char_count = len(response_ai.content)
            st.caption(f"📝 현재 답글 글자 수: **{char_count}자** (공백 포함) / 배민·네이버 플레이스 등록 최적")
            
            # 🌟 [사용자 경험 극대화] 클릭/터치 시 부드럽게 사라지는 커스텀 라떼 토스트 팝업
            st.components.v1.html(
                f"""
                <div id="toast" style="
                    position: fixed;
                    top: 20px;
                    left: 50%;
                    transform: translateX(-50%) translateY(-20px);
                    background-color: #4A3B32;
                    color: #FDFBF7;
                    padding: 12px 24px;
                    border-radius: 30px;
                    font-size: 14px;
                    font-weight: bold;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    z-index: 9999;
                    opacity: 0;
                    transition: all 0.3s ease;
                    pointer-events: none; /* 평소엔 터치 방해 금지 */
                    cursor: pointer;
                ">
                    📋 답글이 복사되었습니다! 배민에 바로 붙여넣으세요.
                </div>

                <button onclick="copyAndShowToast()" style="
                    background-color: #D2B48C;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: bold;
                    border-radius: 5px;
                    cursor: pointer;
                    width: 100%;
                    margin-top: 10px;
                ">📋 클릭 한 번으로 답글 바로 복사하기</button>

                <script>
                const toast = document.getElementById('toast');

                function copyAndShowToast() {{
                    const text = `{response_ai.content}`;
                    navigator.clipboard.writeText(text).then(function() {{
                        // 토스트 알림 켜기
                        toast.style.opacity = "1";
                        toast.style.transform = "translateX(-50%) translateY(0px)";
                        toast.style.pointerEvents = "auto"; /* 클릭 가능하게 전환 */

                        // ⚠️ 2.5초 뒤에 자동으로 안 없어지더라도 사용자가 터치하면 바로 사라지도록 이벤트 추가
                        window.addEventListener('click', closeToast);
                        window.addEventListener('touchstart', closeToast);
                    }}, function(err) {{
                        console.error('복사 실패: ', err);
                    }});
                }}

                function closeToast() {{
                    toast.style.opacity = "0";
                    toast.style.transform = "translateX(-50%) translateY(-20px)";
                    toast.style.pointerEvents = "none";
                    
                    // 이벤트 리스너 제거 (메모리 관리)
                    window.removeEventListener('click', closeToast);
                    window.removeEventListener('touchstart', closeToast);
                }}
                </script>
                """,
                height=70
                # 이 구역 하단에 iframe 여백이 생기지 않도록 가볍게 감싸줍니다.
            )

# ------------------------------------------------------------------
# 🗂️ 최하단: 클라우드 DB에서 실시간 분류해오는 '폴더형' 단골 명부
# ------------------------------------------------------------------
current_db_records = load_all_view_records()

if current_db_records:
    st.write("---")
    st.subheader("🗂️ 클라우드 DB에 저장된 단골 명부 (닉네임별 분류)")
    
    # 🌟 [요청사항 3번 반영] 수백 명의 단골 중 엄마가 원하는 사람을 0.1초 만에 찾는 실시간 검색창
    search_query = st.text_input("🔍 찾고 싶은 단골 손님의 닉네임을 입력하세요 (실시간 필터링):", placeholder="검색할 이름을 적으세요...").strip()
    
    grouped_history = {}
    for record in current_db_records:
        name = record["name"]
        display_name = "익명 손님" if name.startswith("익명_") else name
        
        # 🌟 검색어가 입력되었다면, 해당 검색어가 포함된 손님만 묶음 그룹에 추가 (대소문자 무시)
        if search_query and search_query.lower() not in display_name.lower():
            continue
            
        if display_name not in grouped_history:
            grouped_history[display_name] = []
        grouped_history[display_name].append({"review": record["review"], "reply": record["reply"]})
        
    if grouped_history:
        for name, records in grouped_history.items():
            with st.expander(f"👤 【{name}】손님 (총 {len(records)}개의 기록 보존됨)"):
                for j, record in enumerate(records):
                    st.markdown(f"**📌 {j+1}번째 방문 기록**")
                    st.caption(f"**손님 리뷰:** {record['review']}")
                    st.info(f"**☕ 사장님 대답:** {record['reply']}")
                    if j < len(records) - 1:
                        st.write("---")
    else:
        st.info("검색 결과와 일치하는 단골 손님이 없습니다.")