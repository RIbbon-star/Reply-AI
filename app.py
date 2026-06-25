import streamlit as st
from supabase import create_client, Client
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# [설정] 웹 페이지 제목 및 안내문
st.set_page_config(page_title="카페 리뷰 답글 AI", page_icon="☕", layout="centered")
st.title("☕ 우리집 카페 리뷰 답글 AI")
st.write("클라우드 데이터베이스(Supabase)와 연동되어 데이터가 평생 안전하게 보존되며, 단골 관리 패널이 제공됩니다.")

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
# 🔌 [DB 연동] 수파베이스 클라우드 창고에 무선 연결
# ------------------------------------------------------------------
@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(supabase_url, supabase_key)

supabase: Client = get_supabase_client()


# ------------------------------------------------------------------
# 🛠️ [사이드바] 관리자 전용 삭제 데이터 조작 패널
# ------------------------------------------------------------------
st.sidebar.header("⚙️ 단골 명부 데이터 관리")

# 먼저 최신 DB 목록을 실시간으로 가져옵니다.
response_sidebar = supabase.table("chat_history").select("id", "name").execute()
sidebar_records = response_sidebar.data

if sidebar_records:
    # 🌟 [요청사항 1] 손님 닉네임들과 '🚨 전체 삭제' 항목을 하나의 리스트로 통합
    unique_names = list(set([row["name"] for row in sidebar_records]))
    delete_options = unique_names + ["🚨 전체 데이터 삭제"]
    
    selected_target = st.sidebar.selectbox("삭제 대상을 선택하세요:", delete_options)
    
    # 🌟 [요청사항 2] 흔히 쓰는 "정말 삭제하시겠습니까?" 전환형 확인창 구현
    # 버튼 클릭 여부를 기억하기 위해 세션 상태(session_state) 활용
    if f"delete_clicked_{selected_target}" not in st.session_state:
        st.session_state[f"delete_clicked_{selected_target}"] = False

    # 아직 삭제 버튼을 누르기 전 상태
    if not st.session_state[f"delete_clicked_{selected_target}"]:
        if st.sidebar.button("❌ 선택 대상 삭제하기"):
            st.session_state[f"delete_clicked_{selected_target}"] = True
            st.rerun() # 화면을 확인창 상태로 새로고침
            
    # 첫 번째 삭제 버튼을 누른 후 -> 창이 바뀐 듯한 대화상자 노출
    else:
        st.sidebar.warning(f"❓ 정말로 **[{selected_target}]** 항목을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
        col_yes, col_no = st.sidebar.columns(2)
        
        # "네, 삭제합니다" 클릭 시 진짜 삭제 진행
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
                st.sidebar.success("성공적으로 영구 삭제되었습니다!")
                st.rerun()
                
        # "아니오" 클릭 시 삭제 취소하고 원래 상태로 복귀
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
        st.warning("손님의 닉네임을 입력해주세요.")
    elif not review_input:
        st.warning("리뷰를 입력해주세요.")
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=openai_api_key, temperature=0.7)
        
        response_db = supabase.table("chat_history").select("name", "review", "reply").execute()
        db_records = response_db.data
        
        history_text = ""
        for i, record in enumerate(db_records):
            history_text += f"\n[과거 대화 {i+1}]\n손님 닉네임: {record['name']}\n손님 리뷰: {record['review']}\n사장님 답글: {record['reply']}\n"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 친절하고 센스 있는 카페 사장님입니다. 
            손님이 남긴 리뷰에 대해 감동적이고 재방문을 유도하는 답글을 작성해주세요.
            
            [핵심 지시사항]
            당신은 과거에 손님들과 나눈 대화 기록을 기억하고 있습니다.
            현재 리뷰를 남긴 손님의 닉네임은 '{current_customer}' 입니다.
            
            만약 과거 대화 기록 중에서 이 손님('{current_customer}')의 닉네임과 일치하는 내역이 있다면,
            이 손님은 우리 가게를 다시 찾은 '재방문 단골'입니다. 
            "앗, {current_customer}님! 또 뵙네요!", "지난번 리뷰도 정말 감사했는데 이렇게 또 감동을 주시네요" 처럼 
            반가움을 듬뿍 표현하고 과거에 대화했던 맥락을 은연중에 언급하세요.
            
            [과거 대화 기록]
            {history}
            
            [작성 규칙]
            1. 손님이 칭찬한 부분에 대해 진심으로 감사 인사를 전하세요.
            2. 손님이 아쉬워한 부분이 있다면 유연하게 공감하고 개선하겠다는 의지를 보이세요.
            3. 지정된 말투 스타일을 완벽하게 반영하세요.
            
            지정된 말투 스타일: {tone}"""),
            ("human", "현재 손님 닉네임: {current_customer}\n현재 손님 리뷰: {review}")
        ])
        
        chain = prompt | llm
        
        with st.spinner("클라우드 데이터베이스를 조회하며 최적의 답글을 고민하는 중..."):
            response_ai = chain.invoke({
                "history": history_text,
                "tone": tone_option,
                "current_customer": customer_name,
                "review": review_input
            })
            
            supabase.table("chat_history").insert({
                "name": customer_name,
                "review": review_input,
                "reply": response_ai.content
            }).execute()
            
            st.success("🎉 AI 사장님의 추천 답글이 완성되었습니다!")
            st.subheader("📋 추천 답글 내용")
            st.write(response_ai.content)


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