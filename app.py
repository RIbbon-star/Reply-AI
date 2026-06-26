import streamlit as st
from supabase import create_client, Client
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# [설정] 웹 페이지 제목 및 안내문
st.set_page_config(page_title="카페 리뷰 답글 AI", page_icon="☕", layout="centered")
st.title("☕ 우리집 카페 리뷰 답글 AI")
st.write("리뷰를 입력해주세요!")

# ------------------------------------------------------------------
# 🎨 [디자인 가미] 감성적인 카페라떼 알림 박스 함수
# ------------------------------------------------------------------
def st_latte_box(text: str):
    """쨍한 에러 메시지 대신 포근한 라떼색 배경으로 안내하는 커스텀 박스"""
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

# 🌟 [최적화 1] 10분간 메모리에 킵해두고 현재 손님의 데이터만 '조준 사격'해서 가져오는 효자 함수
@st.cache_data(ttl=600)  
def load_past_history_by_name(name: str):
    # 🌟 [토큰 절약 핵심] .eq("name", name)을 붙여 불필요한 전체 데이터를 긁어오지 않고 토큰을 최소화합니다!
    response = supabase.table("chat_history").select("name", "review", "reply").eq("name", name).execute()
    return response.data

# ------------------------------------------------------------------
# 🛠️ [사이드바] 관리자 전용 삭제 데이터 조작 패널
# ------------------------------------------------------------------
st.sidebar.header("⚙️ 단골 명부 데이터 관리")

response_sidebar = supabase.table("chat_history").select("id", "name").execute()
sidebar_records = response_sidebar.data

if sidebar_records:
    unique_names = list(set([row["name"] for row in sidebar_records]))
    delete_options = unique_names + ["🚨 전체 데이터 삭제"]
    
    selected_target = st.sidebar.selectbox("삭제 대상을 선택하세요:", delete_options)
    
    if f"delete_clicked_{selected_target}" not in st.session_state:
        st.session_state[f"delete_clicked_{selected_target}"] = False

    if not st.session_state[f"delete_clicked_{selected_target}"]:
        if st.sidebar.button("❌ 선택 대상 삭제하기"):
            st.session_state[f"delete_clicked_{selected_target}"] = True
            st.rerun() 
            
    else:
        st.sidebar.warning(f"❓ 정말로 **[{selected_target}]** 항목을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
        col_yes, col_no = st.sidebar.columns(2)
        
        with col_yes:
            if st.sidebar.button("⭕ 네, 삭제합니다", key="btn_yes"):
                if selected_target == "🚨 전체 데이터 삭제":
                    with st.spinner("클라우드 창고 통째로 비우는 중..."):
                        id_list = [row["id"] for row in sidebar_records]
                        supabase.table("chat_history").delete().in_("id", id_list).execute()
                else:
                    with st.spinner(f"[{selected_target}] 손님 기록 지우는 중..."):
                        supabase.table("chat_history").delete().eq("name", selected_target).execute()
                
                st.session_state[f"delete_clicked_{selected_target}"] = False
                
                # 🌟 데이터가 실제로 삭제되었으므로 캐시 메모리를 깨끗하게 비워줍니다.
                st.cache_data.clear()
                
                st.sidebar.success("성공적으로 영구 삭제되었습니다!")
                st.rerun()
                
        with col_no:
            if st.sidebar.button("❌ 아니오", key="btn_no"):
                st.session_state[f"delete_clicked_{selected_target}"] = False
                st.rerun()
else:
    st.sidebar.info("저장된 단골 명부가 없어 삭제 메뉴가 비활성화되었습니다.")


# ------------------------------------------------------------------
# ✍️ 메인 화면: 닉네임, 리뷰 입력 및 옵션 선택
# ------------------------------------------------------------------
customer_name = st.text_input(
    "👤 손님 닉네임 (아이디) 입력:",
    placeholder="예: 배민_아메리카노조아, 네이버_초코맘",
).strip()

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
    if not customer_name:
        # 🎨 쨍한 빨간 경고창 대신 우리가 만든 예쁜 라떼 박스 적용!
        st_latte_box("손님의 닉네임을 입력해주세요.")
    elif not review_input:
        st_latte_box("리뷰를 입력해주세요.")
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=openai_api_key, temperature=0.7)
        
        # 🌟 [최적화 2] 전체 조회가 아닌, 현재 손님의 과거 기록만 캐시 함수로 캐치!
        current_customer_records = load_past_history_by_name(customer_name)
        
        # 🌟 [오판 방지 3] 파이썬이 정확하게 완벽 일치 여부를 검사하므로 
        # "하나둘셋넷" 손님이 왔을 때 "하나"로 착각하는 일은 원천 차단됩니다.
        if current_customer_records:
            is_regular_customer = "예 (이전에 방문한 적이 있는 진짜 재방문 단골손님입니다!)"
            history_text = ""
            for i, record in enumerate(current_customer_records):
                history_text += f"\n[과거 대화 {i+1}]\n손님 리뷰: {record['review']}\n사장님 답글: {record['reply']}\n"
        else:
            is_regular_customer = "아니오 (이번이 첫 방문인 손님입니다. 아는 척하지 마세요)"
            history_text = "과거 방문 기록 없음"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 친절하고 센스 있는 카페 사장님입니다. 
            손님이 남긴 리뷰에 대해 감동적이고 재방문을 유도하는 답글을 작성해주세요.
            
            [단골 여부 판독 결과]
            현재 리뷰를 남긴 손님('{current_customer}')이 진짜 재방문 단골인가요?: {is_regular}
            
            [핵심 지시사항]
            위 [단골 여부 판독 결과]가 '예'라고 되어 있을 때만 반갑게 아는 척을 하세요.
            만약 '아니오'라고 되어 있다면, 과거 대화 기록에 비슷한 글자(예: '하나'와 '하나둘셋넷')가 있더라도 
            절대 아는 척을 하지 말고, 처음 온 손님 대하듯 정중하고 친절하게 답글을 쓰셔야 합니다.
            
            [참고용 이 손님의 과거 기록]
            {history}
            
            [작성 규칙]
            1. 손님이 칭찬한 부분에 대해 진심으로 감사 인사를 전하세요.
            2. 손님이 아쉬워한 부분이 있다면 유연하게 공감하고 개선하겠다는 의지를 보이세요.
            3. 지정된 말투 스타일을 완벽하게 반영하세요.
            
            지정된 말투 스타일: {tone}"""),
            ("human", "현재 손님 닉네임: {current_customer}\n현재 손님 리뷰: {review}")
        ])
        
        chain = prompt | llm
        
        with st.spinner("불필요한 토큰 낭비를 줄이고 안전하게 최적의 답글을 고민하는 중..."):
            response_ai = chain.invoke({
                "history": history_text,
                "tone": tone_option,
                "current_customer": customer_name,
                "review": review_input,
                "is_regular": is_regular_customer
            })
            
            supabase.table("chat_history").insert({
                "name": customer_name,
                "review": review_input,
                "reply": response_ai.content
            }).execute()
            
            # 🌟 새 데이터가 등록되었으니 다음 방문을 위해 캐시 메모리를 한 번 비워줍니다.
            st.cache_data.clear()
            
            st.success("🎉 AI 사장님의 추천 답글이 완성되었습니다!")
            st.subheader("📋 추천 답글 내용")
            
            # 🎨 결과 텍스트가 배경에 자연스럽게 스며들도록 갈색 톤다운 가미
            st.markdown(f"<div style='color: #4A3B32; font-size: 16px; line-height: 1.6; white-space: pre-wrap;'>{response_ai.content}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------
# 🗂️ 최하단: 클라우드 DB에서 실시간 분류해오는 '폴더형' 단골 명부
# ------------------------------------------------------------------
response_view = supabase.table("chat_history").select("name", "review", "reply").execute()
current_db_records = response_view.data

if current_db_records:
    st.write("---")
    st.subheader("🗂️ 클라우드 DB에 저장된 단골 명부 (닉네임별 분류)")
    
    grouped_history = {}
    for record in current_db_records:
        name = record["name"]
        if name not in grouped_history:
            grouped_history[name] = []
        grouped_history[name].append({"review": record["review"], "reply": record["reply"]})
        
    for name, records in grouped_history.items():
        with st.expander(f"👤 【{name}】 단골 손님 (총 {len(records)}개의 기록 보존됨)"):
            for j, record in enumerate(records):
                st.markdown(f"**📌 {j+1}번째 방문 기록**")
                st.caption(f"**손님 리뷰:** {record['review']}")
                st.info(f"**☕ 사장님 대답:** {record['reply']}")
                if j < len(records) - 1:
                    st.write("---")