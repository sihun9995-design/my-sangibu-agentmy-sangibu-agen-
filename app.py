import streamlit as st
import pandas as pd
from openai import OpenAI
import io

# 나이스 기준 바이트 계산 함수 (UTF-8 기준: 한글 3바이트, 영문/숫자/공백 1바이트)
def calculate_bytes(text):
    if not text:
        return 0
    return len(str(text).encode('utf-8'))

# 페이지 설정
st.set_page_config(
    page_title="생기부 자동화 에이전트 (ChatGPT)",
    page_icon="📝",
    layout="wide"
)

# 디자인 개선을 위한 커스텀 CSS
st.markdown("""
    <style>
    .main-header { font-size: 2.4rem; font-weight: 800; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.1rem; color: #4B5563; margin-bottom: 2rem; }
    .card { background-color: #F8FAFC; padding: 1.5rem; border-radius: 0.5rem; border: 1px solid #E2E8F0; margin-bottom: 1.5rem; }
    .stButton>button { background-color: #1E3A8A; color: white; font-weight: 600; border-radius: 0.375rem; padding: 0.5rem 2rem; }
    .stButton>button:hover { background-color: #1D4ED8; color: white; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">📝 생기부 일괄 작성 및 자동 분류 에이전트</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">선생님의 야근을 줄여드리기 위해 엑셀 파일을 업로드하면 OpenAI GPT-4o 엔진이 나이스(NEIS) 기준에 맞춰 초안을 생성합니다.</div>', unsafe_allow_html=True)

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 시스템 설정 및 인증")
    st.markdown("---")
    openai_api_key = st.text_input("OpenAI API Key 입력", type="password", help="발급받으신 sk-... 형태의 키를 입력하세요.")
    
    st.markdown("### 📊 글자 수 설정")
    max_bytes = st.slider(
        "최대 허용 바이트 (나이스 한도: 1500바이트)",
        min_value=1000, max_value=1450, value=1350, step=50,
        help="안정적인 기입을 위해 1,350바이트(공백 포함 한글 약 450자) 내외를 권장합니다."
    )

# 메인 기능 영역
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown('<div class="card"><h3>1. 데이터 업로드</h3>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("학생 데이터 엑셀 파일 (.xlsx)을 선택하세요", type=["xlsx"])
    
    # 예시 샘플 데이터 제공
    sample_df = pd.DataFrame({
        "학번": [10101, 10102],
        "이름": ["홍길동", "이순신"],
        "보고서내용": [
            "자율주행 자동차의 윤리적 딜레마에 대해 탐구하고 보고서를 제출함. 센서 인지 오류 가능성을 분석함.",
            "효소의 활성화 에너지와 온도 간의 관계를 측정하는 실험을 주도하고 그래프로 시각화하여 설명함."
        ]
    })
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        sample_df.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 엑셀 양식 샘플 다운로드",
        data=buffer.getvalue(),
        file_name="생기부_입력양식_샘플.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="card"><h3>2. 가이드라인 규칙</h3>', unsafe_allow_html=True)
    st.markdown("""
    * **문체 제한:** 모든 문장을 반드시 `~함.`, `~임.` 형태로 종결
    * **실명 배제:** 문장 내부에서 학생의 실명을 절대 언급하지 않음
    * **컴플라이언스:** 사교육 유발 요소, 교외 수상, 부모 직업, 구체적 대학명 자동 차단
    * **분량 극대화:** 설정한 목표 바이트 수에 최대한 꽉 차게 풍부한 내용 서술
    """)
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        required_columns = ["학번", "이름", "보고서내용"]
        
        if not all(col in df.columns for col in required_columns):
            st.error(f"⚠️ 엑셀 파일에 필수 컬럼({required_columns})이 부족합니다.")
        else:
            st.markdown("### 📋 업로드된 학생 데이터 미리보기")
            st.dataframe(df.head(), use_container_width=True)
            
            if st.button("🚀 생기부 초안 일괄 생성 시작"):
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
                        
                        status_message.info(f"⏳ [{idx+1}/{total_rows}] {student_name} 학생의 생기부 문장 생성 중...")
                        
                        system_prompt = f"""
                        당신은 대한민국 고등학교의 대학입시 및 학생부종합전형을 완벽하게 숙지하고 있는 베테랑 교사입니다.
                        학생이 제출한 날것의 '보고서내용'을 바탕으로, 학교생활기록부 '과목별 세부능력 및 특기사항(세특)'에 기입할 완성도 높은 초안을 작성하십시오.

                        [엄격 준수 규칙]
                        1. 문체: 모든 문장은 예외 없이 반드시 명사형 종결 어미인 '~함.', '~임.'으로 끝내야 합니다. (~했음, ~하였음 등은 금지하며 오직 ~함., ~임. 구조만 허용)
                        2. 실명 언급 금지: 생성되는 텍스트 내부에서 학생의 이름(예: '{student_name}', '{student_name} 학생은')을 절대로 언급하지 마십시오. 나이스 시스템 특성상 주어 없이 바로 구체적인 탐구 내용이나 동기부터 서술을 시작해야 합니다. 주어가 필요한 경우 '위 학생은', '본인은' 등으로 대체하거나 아예 생략하십시오.
                        3. 분량 및 바이트 극대화: 서술 내용을 축약하지 말고, 설정된 최대 제한 분량인 {max_bytes}바이트에 최대한 가깝도록(최소 {max_bytes - 150}바이트 이상, 목표치의 90% 이상 수준) 탐구 과정과 학업적 성장을 매우 구체적이고 풍부하게 풀어써서 분량을 꽉 채우십시오.
                        4. 컴플라이언스: 사교육 유발 요소(소논문, 교외 수상 기록, 공인어학시험, 사설 학원 연계 활동), 부모의 사회경제적 지위 암시 단어, 구체적인 대학명 및 교육청 외의 기관명은 철저히 배제하고 삭제하십시오.
                        5. 서술 구조: 주제 선정 동기 -> 구체적인 탐구 과정 및 논리적 전개 -> 배우고 느낀 점 및 학생의 인지적 성장이 유기적이고 밀도 있게 연결되도록 작성하십시오.
                        """
                        
                        user_prompt = f"제출된 보고서 및 관찰 메모 내용:\n{raw_content}"
                        
                        try:
                            # 1차 문장 생성
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
                            
                            # 바이트 제한 초과 시에만 조밀하게 압축 재시도 Loop
                            retry_count = 0
                            while current_bytes > max_bytes and retry_count < 2:
                                response_retry = client.chat.completions.create(
                                    model="gpt-4o",
                                    messages=[
                                        {"role": "system", "content": system_prompt},
                                        {"role": "user", "content": f"앞서 작성된 내용이 {max_bytes}바이트를 초과했습니다. 핵심 맥락과 풍부함은 유지하되 문장 구조를 조금 더 조밀하게 압축해서 다시 써주세요.\n\n이전 내용:\n{draft_text}"}
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
                    
                    st.markdown("### ✨ 자동 생성 결과 (미리보기)")
                    st.dataframe(df[["학번", "이름", "생기부_초안", "사용_바이트"]], use_container_width=True)
                    
                    out_buffer = io.BytesIO()
                    with pd.ExcelWriter(out_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='생기부_결과')
                        
                    st.download_button(
                        label="📥 변환된 최종 엑셀 파일 다운로드",
                        data=out_buffer.getvalue(),
                        file_name="생기부_ChatGPT_변환완료.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
    except Exception as e:
        st.error(f"파일 에러: {e}")
