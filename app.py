import streamlit as st
import pandas as pd
from openai import OpenAI
import io

# 나이스 기준 바이트 계산 함수
def calculate_bytes(text):
    if not text:
        return 0
    return len(str(text).encode('utf-8'))

# 페이지 설정
st.set_page_config(
    page_title="생기부 일괄 작성 에이전트",
    page_icon="📝",
    layout="wide"
)

# 🎨 이미지의 그린/토끼 컨셉을 반영한 커스텀 CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans KR', sans-serif;
        background-color: #F4F9F4;
    }
    
    /* 사이드바 그린 테마 */
    [data-testid="stSidebar"] {
        background-color: #E8F5E9 !important;
        border-right: 1px solid #C8E6C9;
    }
    
    /* 메인 헤더 영역 */
    .main-title-container {
        text-align: center;
        padding: 1.5rem 0;
        margin-bottom: 1.5rem;
    }
    .main-title {
        font-size: 2.3rem;
        font-weight: 800;
        color: #2E7D32;
        margin-bottom: 0.4rem;
    }
    .main-subtitle {
        font-size: 1.05rem;
        color: #558B2F;
        font-weight: 500;
    }
    
    /* 화이트 카드 컴포넌트 */
    .green-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #C8E6C9;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        margin-bottom: 1rem;
        min-height: 280px;
    }
    
    .green-card-wide {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #C8E6C9;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        margin-bottom: 1.5rem;
    }
    
    .card-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #1B5E20;
        margin-bottom: 1rem;
        border-bottom: 2px solid #A5D6A7;
        padding-bottom: 0.5rem;
    }
    
    /* 가이드라인 리스트 아이템 스타일 */
    .rule-item {
        background-color: #F9FBF9;
        padding: 0.6rem 0.8rem;
        border-radius: 8px;
        border: 1px solid #E8F5E9;
        margin-bottom: 0.5rem;
        font-size: 0.95rem;
        color: #374151;
    }
    
    /* 하단 중앙 정렬 대형 버튼 스타일 */
    .center-btn-container {
        display: flex;
        justify-content: center;
        margin-top: 1.5rem;
        margin-bottom: 2rem;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%) !important;
        color: white !important;
        font-weight: 700 !important;
        font-size: 1.15rem !important;
        border-radius: 30px !important;
        padding: 0.75rem 3.5rem !important;
        border: none !important;
        box-shadow: 0 4px 10px rgba(27, 94, 32, 0.3) !important;
        transition: all 0.2s ease-in-out !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 15px rgba(27, 94, 32, 0.4) !important;
    }
    </style>
""", unsafe_allow_html=True)

# 🎇 중앙 타이틀 배너
st.markdown("""
    <div class="main-title-container">
        <div class="main-title">📑 생기부 일괄 작성 및 자동 분류 에이전트</div>
        <div class="main-subtitle">선생님의 야근을 덜어드리기 위해 엑셀 파일을 업로드하면 OpenAI GPT-4o 엔진이 가이드라인에 맞춘 초안을 생성합니다.</div>
    </div>
""", unsafe_allow_html=True)

# ⚙️ 사이드바 영역
with st.sidebar:
    st.markdown("### 🐰 시스템 설정 및 인증")
    st.markdown("---")
    openai_api_key = st.text_input("OpenAI API Key 입력", type="password", placeholder="sk-proj-...")
    
    st.markdown("### 📊 글자 수 설정")
    max_bytes = st.slider(
        "최대 허용 바이트 (나이스 한도: 1500)",
        min_value=1000, max_value=1450, value=1350, step=50
    )
    st.markdown("---")
    st.caption("🔒 본 시스템은 입력된 데이터를 수집하지 않는 안전한 휘발성 에이전트입니다.")

# 🧩 메인 레이아웃 (상단 2분할 구조)
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown('<div class="green-card"><div class="card-title">🐰 1. 데이터 업로드</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("학생 데이터 엑셀 파일(.xlsx)을 선택하세요", type=["xlsx"])
    
    # 샘플 파일 다운로드
    sample_df = pd.DataFrame({
        "학번": [10101, 10102],
        "이름": ["홍길동", "이순신"],
        "보고서내용": ["자율주행 자동차의 윤리적 딜레마 보고서를 제출함.", "효소 촉매 반응 실험을 주도하고 시각화함."]
    })
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        sample_df.to_excel(writer, index=False)
        
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        label="📥 엑셀 양식 샘플 다운로드",
        data=buffer.getvalue(),
        file_name="생기부_입력양식_샘플.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="green-card"><div class="card-title">🐰 2. 가이드라인 규칙</div>', unsafe_allow_html=True)
    st.markdown("""
        <div class="rule-item"><b>🐰 문체 제안:</b> 모든 문장의 반드시 명사형 종결 어미(~함., ~임.)로 종결</div>
        <div class="rule-item"><b>🐰 실명 배제:</b> 문장 내부에서 학생의 실명을 절대 언급하지 않음</div>
        <div class="rule-item"><b>🐰 컴플라이언스:</b> 사교육 유발 요소, 교외 수상, 부모 직업, 대학명 차단</div>
        <div class="rule-item"><b>🐰 문항 극대화:</b> 설정된 바이트 제한 한도 내에서 최대한 조밀하고 풍부하게 서술</div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# 📊 하단 와이드 미리보기 및 로직 구동 영역
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        required_columns = ["학번", "이름", "보고서내용"]
        
        if not all(col in df.columns for col in required_columns):
            st.error(f"⚠️ 엑셀 파일에 필수 컬럼({required_columns})이 부족합니다.")
        else:
            st.markdown('<div class="green-card-wide"><div class="card-title">📊 업로드된 학생 데이터 미리보기</div>', unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # 레이아웃을 이용한 하단 정중앙 버튼 배치
            c_col1, c_col2, c_col3 = st.columns([1, 2, 1])
            with c_col2:
                start_button = st.button("⚙️ 생기부 초안 일괄 생성 시작", use_container_width=True)
                
            if start_button:
                if not openai_api_key:
                    st.warning("🔑 왼쪽 사이드바에 OpenAI API Key를 먼저 입력해주세요.")
                else:
                    client = OpenAI(api_key=openai_api_key)
                    
                    draft_list = []
                    byte_list = []
                    
                    progress_bar = st.progress(0)
                    status_message = st.empty()
                    total_rows = len(df)
                    
                    for idx, row in df.iterrows():
                        student_name = row["이름"]
                        raw_content = row["보고서내용"]
                        
                        status_message.info(f"⏳ [{idx+1}/{total_rows}] {student_name} 학생 생기부 생성 중...")
                        
                        system_prompt = f"""
                        당신은 대한민국 고등학교의 대학입시 및 학생부종합전형을 완벽하게 숙지하고 있는 베테랑 교사입니다.
                        학생이 제출한 날것의 '보고서내용'을 바탕으로, 학교생활기록부 '과목별 세부능력 및 특기사항(세특)'에 기입할 완성도 높은 초안을 작성하십시오.

                        [엄격 준수 규칙]
                        1. 문체: 모든 문장은 예외 없이 반드시 명사형 종결 어미인 '~함.', '~임.'으로 끝내야 합니다. (~했음, ~하였음 등은 금지하며 오직 ~함., ~임. 구조만 허용)
                        2. 실명 언급 금지: 생성되는 텍스트 내부에서 학생의 이름(예: '{student_name}', '{student_name} 학생은')을 절대로 언급하지 마십시오. 주어가 필요한 경우 '위 학생은', '본인은' 등으로 대체하거나 아예 생략하십시오.
                        3. 분량 및 바이트 극대화: 서술 내용을 축약하지 말고, 설정된 최대 제한 분량인 {max_bytes}바이트에 최대한 가깝도록(최소 {max_bytes - 150}바이트 이상, 목표치의 90% 이상 수준) 탐구 과정과 학업적 성장을 매우 구체적이고 풍부하게 풀어써서 분량을 꽉 채우십시오.
                        4. 컴플라이언스: 사교육 유발 요소(소논문, 교외 수상 기록, 공인어학시험, 사설 학원 연계 활동), 부모의 사회경제적 지위 암시 단어, 구체적인 대학명 및 교육청 외의 기관명은 철저히 배제하고 삭제하십시오.
                        5. 서술 구조: 주제 선정 동기 -> 구체적인 탐구 과정 및 논리적 전개 -> 배우고 느낀 점 및 학생의 인지적 성장이 유기적이고 밀도 있게 연결되도록 작성하십시오.
                        """
                        
                        user_prompt = f"제출된 보고서 및 관찰 메모 내용:\n{raw_content}"
                        
                        try:
                            response = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt}
                                ],
                                temperature=0.6
                            )
                            draft_text = response.choices[0].message.content.strip()
                            current_bytes = calculate_bytes(draft_text)
                            
                            retry_count = 0
                            while current_bytes > max_bytes and retry_count < 2:
                                response_retry = client.chat.completions.create(
                                    model="gpt-4o",
                                    messages=[
                                        {"role": "system", "content": system_prompt},
                                        {"role": "user", "content": f"앞서 작성된 내용이 {max_bytes}바이트를 초과했습니다. 문맥을 조밀하게 압축해서 다시 써주세요.\n\n이전 내용:\n{draft_text}"}
                                    ],
                                    temperature=0.4
                                )
                                draft_text = response_retry.choices[0].message.content.strip()
                                current_bytes = calculate_bytes(draft_text)
                                retry_count += 1
                                
                            draft_list.append(draft_text)
                            byte_list.append(current_bytes)
                            
                        except Exception as e:
                            draft_list.append(f"오류 발생 ({str(e)})")
                            byte_list.append(0)
                            
                        progress_bar.progress((idx + 1) / total_rows)
                        
                    status_message.success("🎉 모든 학생의 생기부 초안 생성이 완료되었습니다!")
                    
                    df["생기부_초안"] = draft_list
                    df["사용_바이트"] = byte_list
                    
                    st.markdown('<div class="green-card-wide"><div class="card-title">✨ 자동 생성 결과 (미리보기)</div>', unsafe_allow_html=True)
                    st.dataframe(df[["학번", "이름", "생기부_초안", "사용_바이트"]], use_container_width=True)
                    
                    out_buffer = io.BytesIO()
                    with pd.ExcelWriter(out_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='생기부_결과')
                        
                    st.download_button(
                        label="📥 변환된 최종 엑셀 파일 다운로드",
                        data=out_buffer.getvalue(),
                        file_name="생기부_그린버전_완료.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                    
    except Exception as e:
        st.error(f"파일 에러: {e}")
