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
    page_title="생기부 자동화 에이전트",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 디자인 개선을 위한 커스텀 CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.4rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 2rem;
    }
    .card {
        background-color: #F8FAFC;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border: 1px solid #E2E8F0;
        margin-bottom: 1.5rem;
    }
    .stButton>button {
        background-color: #1E3A8A;
        color: white;
        font-weight: 600;
        border-radius: 0.375rem;
        padding: 0.5rem 2rem;
    }
    .stButton>button:hover {
        background-color: #1D4ED8;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# 헤더 영역
st.markdown('<div class="main-header">📝 생기부 일괄 작성 및 자동 분류 에이전트</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">선생님의 야근을 줄여드리기 위해 엑셀 파일을 업로드하면 AI가 나이스(NEIS) 기준에 맞춰 생기부 초안을 일괄 생성합니다.</div>', unsafe_allow_html=True)

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 시스템 설정 및 인증")
    st.markdown("---")
    openai_api_key = st.text_input("OpenAI API Key 입력", type="password", help="OpenAI 플랫폼에서 발급받은 sk- 체인의 비밀키를 입력하세요.")
    
    st.markdown("### 📊 글자 수 설정")
    max_bytes = st.slider(
        "최대 허용 바이트 (나이스 한도: 1500바이트)",
        min_value=1000,
        max_value=1450,
        value=1350,
        step=50,
        help="안정적인 기입을 위해 1,350바이트(공백 포함 한글 약 450자) 내외를 권장합니다."
    )
    
    st.markdown("---")
    st.markdown("💡 **보안 안내:** 업로드된 엑셀 데이터와 API 키는 외부 서버나 데이터베이스에 저장되지 않고 브라우저 종료 시 완전히 휘발됩니다.")

# 메인 기능 영역
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown('<div class="card"><h3>1. 데이터 업로드</h3>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("학생 데이터 엑셀 파일 (.xlsx)을 선택하세요", type=["xlsx"])
    
    # 샘플 엑셀 다운로드 기능 기능 제공
    sample_data = {
        "학번": [10101, 10102],
        "이름": ["홍길동", "이순신"],
        "보고서내용": [
            "자율주행 자동차의 윤리적 딜레마(트롤리 문제)에 대해 탐구하고 보고서를 제출함. 센서 인지 오류 가능성을 코딩 관점에서 분석함.",
            "효소의 활성화 에너지와 온도 간의 관계를 측정하는 실험을 주도함. 데이터 분석 과정에서 오차 원인을 그래프로 시각화하여 설명함."
        ]
    }
    sample_df = pd.DataFrame(sample_data)
    
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
    st.markdown('<div class="card"><h3>2. 실행 및 가이드라인 확인</h3>', unsafe_allow_html=True)
    st.markdown("""
    * **필수 포함 컬럼:** `학번`, `이름`, `보고서내용`
    * **자동 컴플라이언스:** 사교육 유발 요소, 교외 수상, 부모 직업, 대학명 자동 필터링
    * **문체 강제:** 모든 문장을 `~함.`, `~임.` 형태로 종결
    """)
    st.markdown('</div>', unsafe_allow_html=True)

# 파일 업로드 및 API 키 검증 후 프로세스 진행
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        required_columns = ["학번", "이름", "보고서내용"]
        
        # 컬럼 검증
        if not all(col in df.columns for col in required_columns):
            st.error(f"⚠️ 엑셀 파일에 필수 컬럼이 부족합니다. 다음 컬럼이 명확히 포함되어 있는지 확인해주세요: {required_columns}")
        else:
            st.markdown("### 📋 업로드된 학생 데이터 미리보기")
            st.dataframe(df.head(), use_container_width=True)
            
            # 구동 버튼
            if st.button("🚀 생기부 초안 일괄 생성 시작"):
                if not openai_api_key:
                    st.warning("🔑 왼쪽 사이드바에 OpenAI API Key를 먼저 입력해주세요.")
                else:
                    client = OpenAI(api_key=openai_api_key)
                    
                    draft_list = []
                    byte_list = []
                    
                    # 프로그레스 바 및 상태 메시지 창
                    progress_bar = st.progress(0)
                    status_message = st.empty()
                    
                    total_rows = len(df)
                    
                    for idx, row in df.iterrows():
                        student_name = row["이름"]
                        raw_content = row["보고서내용"]
                        
                        status_message.info(f"⏳ [{idx+1}/{total_rows}] {student_name} 학생의 생기부 문장 생성 및 교정 중...")
                        
                        # 프롬프트 설계
                        system_prompt = f"""
                        당신은 대한민국 고등학교의 대학입시 및 학생부종합전형을 완벽하게 숙지하고 있는 베테랑 교사입니다.
                        학생이 제출한 날것의 '보고서내용'을 바탕으로, 학교생활기록부 '과목별 세부능력 및 특기사항(세특)'에 기입할 완성도 높은 초안을 작성하십시오.

                        [엄격 준수 규칙]
                        1. 문체: 모든 문장은 예외 없이 반드시 명사형 종결 어미인 '~함.', '~임.'으로 끝내야 합니다. (~했음, ~하였음 등은 금지하며 오직 ~함., ~임. 구조만 허용)
                        2. 컴플라이언스: 사교육 유발 요소(소논문, 교외 수상 기록, 공인어학시험, 사설 학원 연계 활동), 부모의 사회경제적 지위 암시 단어, 구체적인 대학명 및 교육청 외의 기관명은 철저히 배제하고 삭제하십시오.
                        3. 서술 구조: 주제 선정 동기 -> 구체적인 탐구 과정 및 논리적 전개 -> 배우고 느낀 점 및 학생의 인지적 성장이 유기적이고 밀도 있게 연결되도록 작성하십시오.
                        4. 분량 제한: 공백을 포함한 전체 텍스트의 결과물이 {max_bytes}바이트를 절대로 초과하지 않도록 컴팩트하게 요약하십시오.
                        """
                        
                        user_prompt = f"학생 이름: {student_name}\n제출된 보고서 및 관찰 메모 내용:\n{raw_content}"
                        
                        try:
                            # 1차 초안 생성
                            response = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt}
                                ],
                                temperature=0.5
                            )
                            draft_text = response.choices[0].message.content.strip()
                            current_bytes = calculate_bytes(draft_text)
                            
                            # 바이트 제한 초과 시 자체 재교정 Loop (Fallback)
                            retry_count = 0
                            while current_bytes > max_bytes and retry_count < 2:
                                response_retry = client.chat.completions.create(
                                    model="gpt-4o",
                                    messages=[
                                        {"role": "system", "content": system_prompt},
                                        {"role": "user", "content": f"앞서 작성된 내용이 {max_bytes}바이트를 초과하여 나이스 시스템에 입력할 수 없습니다. 핵심 맥락만 조밀하게 압축하여 더 짧은 명사형 종결 어미 문장으로 재작성하세요.\n\n기존 초안:\n{draft_text}"}
                                    ],
                                    temperature=0.3
                                )
                                draft_text = response_retry.choices[0].message.content.strip()
                                current_bytes = calculate_bytes(draft_text)
                                retry_count += 1
                            
                            draft_list.append(draft_text)
                            byte_list.append(current_bytes)
                            
                        except Exception as e:
                            draft_list.append(f"오류 발생 ({str(e)})")
                            byte_list.append(0)
                        
                        # 프로그레스 바 갱신
                        progress_bar.progress((idx + 1) / total_rows)
                    
                    status_message.success("🎉 모든 학생의 생기부 초안 생성이 완벽하게 완료되었습니다!")
                    
                    # 결과 데이터프레임 구축
                    df["생기부_초안"] = draft_list
                    df["사용_바이트"] = byte_list
                    
                    # 화면에 최종 결과 테이블 표출
                    st.markdown("### ✨ 자동 생성 결과 (미리보기)")
                    st.dataframe(df[["학번", "이름", "생기부_초안", "사용_바이트"]], use_container_width=True)
                    
                    # 엑셀 다운로드 다운로드 스트림 생성
                    out_buffer = io.BytesIO()
                    with pd.ExcelWriter(out_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='생기부_초안_결과')
                    
                    st.download_button(
                        label="📥 변환된 최종 엑셀 파일 다운로드",
                        data=out_buffer.getvalue(),
                        file_name="생기부_일괄작성_완료.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
    except Exception as e:
        st.error(f"파일을 읽는 중 에러가 발생했습니다: {e}")
