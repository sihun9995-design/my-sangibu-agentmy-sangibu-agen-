import streamlit as st
import pandas as pd
from openai import OpenAI
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# ⚙️ [인코딩 최적화] 유연한 바이트 계산 함수 (EUC-KR / UTF-8 선택 가능)
def calculate_bytes(text, encoding_type):
    if not text:
        return 0
    try:
        return len(str(text).encode(encoding_type))
    except Exception:
        return len(str(text).encode('utf-8')) # 폴백

# 바이트 수에 따른 신호등 문자열 반환 함수
def get_status_string(current_bytes, max_bytes):
    if current_bytes > max_bytes:
        return f"❌ 초과 ({current_bytes}B)"
    elif current_bytes >= (max_bytes - 150):
        return f"✅ 적정 ({current_bytes}B)"
    else:
        return f"⚠️ 부족 ({current_bytes}B)"

# [최적화 마스터 V3] ALL gpt-4o 고정 + Prompt Caching 적중 + max_tokens 방어벽
def generate_student_draft(client, system_prompt, student_name, raw_content, max_bytes, encoding_type, feedback_msg=None):
    try:
        if feedback_msg:
            user_prompt = f"대상 학생 이름: {student_name}\n원본 관찰 기록 및 소감 내용:\n{raw_content}\n\n[선생님의 추가 수정 피드백]:\n{feedback_msg}\n\n[필수]: 위 피드백을 반영하되, 학생 실명은 세특 본문에 절대 언급하지 말고 명사형 종결 어미로 작성하세요."
        else:
            user_prompt = f"대상 학생 이름: {student_name}\n제출된 보고서 및 관찰 메모 내용:\n{raw_content}\n\n[필수]: 위 학생의 이름을 세특 본문에 절대 언급하지 말고, 주어를 생략하여 작성하세요."

        # 1차 초안 생성 (gpt-4o 고정)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt}, 
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.6 if not feedback_msg else 0.5,
            max_tokens=800 # 비정상적 토큰 폭발 방지 방어벽
        )
        draft_text = response.choices[0].message.content.strip()
        current_bytes = calculate_bytes(draft_text, encoding_type)
        
        # 💡 [Prompt Caching 최적화] 시스템 프롬프트(Prefix)를 그대로 유지하여 캐싱 할인을 유지하며 gpt-4o로 정교한 압축 수행
        retry_count = 0
        while current_bytes > max_bytes and retry_count < 2:
            retry_user_prompt = f"""
            앞서 생성된 텍스트가 현재 목표치인 {max_bytes}바이트를 초과하여 {current_bytes}바이트로 계산되었습니다.
            지정된 모든 세특 작성 원칙(명사형 종결, 실명 배제, 컴플라이언스)을 철저히 유지하면서, 핵심 맥락과 전문 용어 손실 없이 내용을 조밀하게 축약하여 반드시 {max_bytes}바이트 이하로 재작성하십시오.
            
            [초과된 이전 텍스트]:
            {draft_text}
            """
            
            response_retry = client.chat.completions.create(
                model="gpt-4o", # 💡 gpt-4o로 품질 일관성 유지
                messages=[
                    {"role": "system", "content": system_prompt}, # 💡 동일한 시스템 지침으로 Cache Miss 차단
                    {"role": "user", "content": retry_user_prompt}
                ],
                temperature=0.4,
                max_tokens=700
            )
            draft_text = response_retry.choices[0].message.content.strip()
            current_bytes = calculate_bytes(draft_text, encoding_type)
            retry_count += 1
            
        return draft_text, get_status_string(current_bytes, max_bytes)
    except Exception as e:
        return f"오류 발생 ({str(e)})", "❌ 에러"

# 페이지 설정
st.set_page_config(
    page_title="생기부 올인원 에이전트 플랫폼",
    page_icon="📝",
    layout="wide"
)

# 세션 상태 초기화
if "generated_df" not in st.session_state:
    st.session_state.generated_df = None
if "selected_preset" not in st.session_state:
    st.session_state.selected_preset = "자연과학 계열"

# UI 커스텀 CSS (기존 스타일 아이덴티티 유지)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght=400;500;700;800&display=swap');
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans KR', sans-serif;
        background-color: #F4F9F4;
    }
    [data-testid="stSidebar"] {
        background-color: #E8F5E9 !important;
        border-right: 1px solid #C8E6C9;
    }
    .main-title-container { text-align: center; padding: 1.5rem 0; margin-bottom: 1.5rem; }
    .main-title { font-size: 2.3rem; font-weight: 800; color: #2E7D32; margin-bottom: 0.4rem; }
    .main-subtitle { font-size: 1.05rem; color: #558B2F; font-weight: 500; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: white !important;
        border: 1px solid #C8E6C9 !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
        padding: 1.8rem !important;
        margin-bottom: 1rem !important;
    }
    .card-title { font-size: 1.3rem; font-weight: 700; color: #1B5E20; margin-bottom: 1.2rem; border-bottom: 2px solid #A5D6A7; padding-bottom: 0.5rem; }
    .rule-item { background-color: #F9FBF9; padding: 0.6rem 0.8rem; border-radius: 8px; border: 1px solid #E8F5E9; margin-bottom: 0.6rem; font-size: 0.95rem; color: #374151; }
    .stButton>button {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%) !important;
        color: white !important; font-weight: 700 !important; font-size: 1.15rem !important;
        border-radius: 30px !important; padding: 0.75rem 3.5rem !important; border: none !important;
        box-shadow: 0 4px 10px rgba(27, 94, 32, 0.3) !important; transition: all 0.2s ease-in-out !important;
    }
    .stButton>button:hover { transform: translateY(-2px) !important; box-shadow: 0 6px 15px rgba(27, 94, 32, 0.4) !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="main-title-container">
        <div class="main-title">📑 생기부 올인원 검수 및 자동화 플랫폼</div>
        <div class="main-subtitle">엑셀 파일을 업로드하면 가이드라인에 맞춘 초안을 빌드하고 화면 내 즉시 편집을 지원합니다.</div>
    </div>
""", unsafe_allow_html=True)

# 사이드바 영역
with st.sidebar:
    st.markdown("### 🐰 시스템 설정 및 인증")
    st.markdown("---")
    openai_api_key = st.text_input("OpenAI API Key 입력", type="password", placeholder="sk-proj-...")
    
    st.markdown("---")
    st.markdown("### 📚 담당 계열 설정")
    subject_preset = st.selectbox("작성할 활동 계열 선택", ["자연과학 계열", "공학 계열", "인문/사회 계열", "진로 탐색 활동"])
    st.session_state.selected_preset = subject_preset
    
    st.markdown("---")
    st.markdown("### 🎯 나이스 바이트 기준 설정")
    encoding_choice = st.radio(
        "학교 나이스(NEIS) 시스템 환경",
        ["개정 4세대 표준 (UTF-8 / 자당 3B)", "일부 구형/특수 창 (EUC-KR / 자당 2B)"],
        index=0
    )
    encoding_type = "utf-8" if "UTF-8" in encoding_choice else "euc-kr"
    
    st.markdown("---")
    st.markdown("### 📊 글자 수 설정")
    max_bytes = st.slider("최대 허용 바이트 (나이스 한도: 1500)", min_value=1000, max_value=1450, value=1350, step=50)
    st.markdown("---")
    st.caption("🔒 본 시스템은 입력된 데이터를 수집하지 않는 안전한 휘발성 에이전트입니다.")

preset_guidelines = {
    "자연과학 계열": "과학적 호기심, 가설 설정 및 탐구 실험 과정, 객관적 데이터 분석 및 논리적 결론 도출 역량을 중심으로 서술하십시오.",
    "공학 계열": "공학적 문제해결력, 기술적 대안 설계 및 프로토타입 구상, 실용적 구현 가능성 및 테크놀로지 접목 능력을 중심으로 서술하십시오.",
    "인문/사회 계열": "사회 현상에 대한 비판적 사고력, 문헌 및 텍스트 분석 능력, 인문학적 통찰과 논리적 에세이 전개 능력을 중심으로 서술하십시오.",
    "진로 탐색 활동": "학생의 구체적인 진로 희망 및 전공 분야와의 유기적 연계성, 자기주도적인 학업 탐색 태도와 향후 발전 가능성을 중심으로 서술하십시오."
}

col1, col2 = st.columns([1, 1])

with col1:
    with st.container(border=True):
        st.markdown('<div class="card-title">🐰 1. 데이터 업로드</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("학생 데이터 엑셀 파일(.xlsx)을 선택하세요", type=["xlsx"])
        
        sample_df = pd.DataFrame({
            "학번": [10101, 10102],
            "이름": ["홍길동", "이순신"],
            "보고서내용": ["자율주행 자동차의 윤리적 딜레마 보고서를 제출함.", "효소 촉매 반응 실험을 주도하고 시각화함."]
        })
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            sample_df.to_excel(writer, index=False)
            
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(label="📥 엑셀 양식 샘플 다운로드", data=buffer.getvalue(), file_name="생기부_입력양식_샘플.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with col2:
    with st.container(border=True):
        st.markdown('<div class="card-title">🐰 2. 가이드라인 규칙</div>', unsafe_allow_html=True)
        st.markdown(f"""
            <div class="rule-item"><b>🎯 선택된 프리셋:</b> <span style='color:#2E7D32; font-weight:bold;'>{subject_preset}</span></div>
            <div class="rule-item"><b>🐰 문체 제한:</b> 모든 문장의 반드시 명사형 종결 어미(~함., ~임.)로 종결</div>
            <div class="rule-item"><b>🐰 실명 배제:</b> 문장 내부에서 학생의 실명을 절대 언급하지 않음</div>
            <div class="rule-item"><b>🐰 컴플라이언스:</b> 사교육 유발 요소, 교외 수상, 부모 직업, 대학명 차단</div>
            <div class="rule-item"><b>🐰 문항 극대화:</b> 설정된 바이트 제한 한도 내에서 최대한 풍부하게 서술</div>
        """, unsafe_allow_html=True)

if uploaded_file:
    try:
        df_origin = pd.read_excel(uploaded_file)
        columns_list = list(df_origin.columns)
        
        id_keywords = ['학번', '번호', '학생번호', 'id', 'no', '학적', 'num']
        name_keywords = ['이름', '성명', '학생명', '학생 이름', 'name']
        content_keywords = ['보고서내용', '내용', '보고서', '특기사항', '세특', '활동', '관찰', '메모', 'content', '기술', '기록']
        
        default_id_col = next((c for c in columns_list if any(k in str(c).lower() for k in id_keywords)), columns_list[0])
        default_name_col = next((c for c in columns_list if any(k in str(c).lower() for k in name_keywords)), columns_list[1] if len(columns_list) > 1 else columns_list[0])
        default_content_col = next((c for c in columns_list if any(k in str(c).lower() for k in content_keywords)), columns_list[2] if len(columns_list) > 2 else columns_list[0])
        
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<div class="card-title">🎯 엑셀 항목(열) 자동 지정 시스템</div>', unsafe_allow_html=True)
            sel_col1, sel_col2, sel_col3 = st.columns(3)
            with sel_col1: id_col = st.selectbox("📌 '학번'에 해당하는 열", columns_list, index=columns_list.index(default_id_col))
            with sel_col2: name_col = st.selectbox("📌 '이름'에 해당하는 열", columns_list, index=columns_list.index(default_name_col))
            with sel_col3: content_col = st.selectbox("📌 '보고서 내용'에 해당하는 열", columns_list, index=columns_list.index(default_content_col))

        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<div class="card-title">📊 업로드된 학생 데이터 미리보기</div>', unsafe_allow_html=True)
            st.dataframe(df_origin, use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        c_col1, c_col2, c_col3 = st.columns([1, 2, 1])
        with c_col2: start_button = st.button("⚙️ 생기부 초안 일괄 생성 시작 (SaaS형 하이브리드 병렬 최적화)", use_container_width=True)
            
        selected_guideline = preset_guidelines[subject_preset]
        master_system_prompt = f"""
        당신은 대한민국 고등학교의 대학입시 및 학생부종합전형(학종)을 완벽하게 숙지하고 있는 20년 경력의 베테랑 교사입니다.
        학생이 제출한 날것의 활동 내용을 바탕으로 학교생활기록부 '과목별 세부능력 및 특기사항(세특)' 초안을 작성하십시오.

        [선택 계열 맞춤 강조 지침]
        {selected_guideline}

        [엄격 준수 규정 및 가이드라인]
        1. 문체 제한: 모든 문장은 어떠한 예외도 없이 반드시 명사형 종결 어미인 '~함.', '~임.'으로 끝내야 합니다.
        2. 완벽한 실명 언급 배제: 제공되는 유저 입력 내 학생 이름을 절대로 세특 생성 본문에 노출하지 마십시오. 주어를 생략하거나 '위 학생은'으로 대체하십시오.
        3. 분량 극대화 및 바이트 관리: 설정된 목표 한도인 {max_bytes}바이트에 최대한 가깝게(최소 {max_bytes - 150}바이트 이상) 학생의 역량을 풍부하고 상세하게 서술하십시오.
        4. 법정 기재 금지사항 컴플라이언스: 사교육 유발 요소(교외 수상, 공인성적), 부모 직업 암시, 구체적인 대학명은 철저히 배제하고 삭제하십시오.
        5. 정석적 세특 서술 구조 체계: [주제 선정 동기 및 학술적 호기심] -> [이를 해결하기 위한 구체적인 주도적 탐구 과정 및 논리적 전개] -> [활동을 통해 배우고 느낀 점, 후속 탐구 의지]

        [올바른 기재 예시 참고 (Few-shot)]
        - 예시 1: 자율주행 자동차의 윤리적 딜레마를 주제로 트롤리 딜레마 상황에서 알고리즘의 판단 기준을 비판적으로 분석한 보고서를 제출함. 센서 데이터 인식 오류 가능성을 확률적으로 접근하여 제어 공학적 대안을 제시하는 등 학술적 깊이가 돋보임. 탐구 과정에서 기술의 사회적 책임감을 깨닫고 향후 공학도로서의 윤리적 가치관을 정립하는 계기가 됨.
        - 예시 2: 현대 사회의 양극화 현상에 관한 문헌을 조사하고 소득 격차가 교육 기회의 불평등으로 이어지는 메커니즘을 사회학적 관점에서 고찰함. 통계 자료를 바탕으로 복지 정책의 실효성을 다각도로 분석하여 논리적 에세이를 전개함. 사회 문제에 대한 깊은 통찰력과 비판적 사고력이 매우 우수함.
        """

        if start_button:
            if not openai_api_key:
                st.warning("🔑 왼쪽 사이드바에 OpenAI API Key를 먼저 입력해주세요.")
            else:
                client = OpenAI(api_key=openai_api_key)
                total_rows = len(df_origin)
                
                draft_list = [""] * total_rows
                status_list = [""] * total_rows
                
                progress_bar = st.progress(0)
                status_message = st.empty()
                status_message.info(f"⏳ 총 {total_rows}명의 세특 초안을 고속 인프라(gpt-4o)로 생성 중입니다...")

                with ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_idx = {}
                    for idx, row in df_origin.iterrows():
                        student_name = str(row[name_col])
                        raw_content = str(row[content_col])
                        
                        future = executor.submit(
                            generate_student_draft, 
                            client, master_system_prompt, student_name, raw_content, max_bytes, encoding_type
                        )
                        future_to_idx[future] = idx

                    completed_count = 0
                    for future in as_completed(future_to_idx):
                        idx = future_to_idx[future]
                        draft_text, status_str = future.result()
                        draft_list[idx] = draft_text
                        status_list[idx] = status_str
                        
                        completed_count += 1
                        progress_bar.progress(completed_count / total_rows)
                
                status_message.success("🎉 모든 학생의 캐싱 최적화 세특 초안 생성이 완료되었습니다!")
                
                working_df = df_origin[[id_col, name_col, content_col]].copy()
                working_df["생기부_초안"] = draft_list
                working_df["상태_확인"] = status_list
                st.session_state.generated_df = working_df

        # ----------------- 실시간 편집 및 개별 재생성 렌더링 구역 -----------------
        if st.session_state.generated_df is not None:
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 1. 결과 노출 및 화면 내 더블클릭 실시간 편집기
            with st.container(border=True):
                st.markdown('<div class="card-title">✨ 최종 생성 결과 검수실 (마우스 더블클릭으로 즉시 수정 가능)</div>', unsafe_allow_html=True)
                st.info("💡 아래 테이블의 '생기부_초안' 칸을 더블클릭하면 직접 수정할 수 있습니다. 수정한 내용이 개별 재생성 및 엑셀 다운로드에 실시간 반영됩니다.")
                
                edited_df = st.data_editor(
                    st.session_state.generated_df,
                    use_container_width=True,
                    disabled=[id_col, name_col, content_col, "상태_확인"],
                    height=350,
                    key="student_se_editor"
                )
                st.session_state.generated_df = edited_df

            # 2. 개별 학생 핀포인트 피드백 재작성 컨트롤러
            with st.container(border=True):
                st.markdown('<div class="card-title">🔄 핀포인트 개별 학생 맞춤형 재요청 비서</div>', unsafe_allow_html=True)
                st.write("문장 퀄리티가 아쉬운 특정 학생이 있다면 추가 지시를 통해 한 명만 다시 만들 수 있습니다. (기존 다른 학생의 수동 수정본은 안전하게 보존되며 캐싱 혜택을 받습니다)")
                
                student_options = st.session_state.generated_df[name_col].tolist()
                tgt_col1, tgt_col2 = st.columns([1, 2])
                with tgt_col1: target_student = st.selectbox("🎯 대상 학생 선택", student_options)
                with tgt_col2: feedback_msg = st.text_input("💡 AI에게 줄 추가 수정 지시사항", placeholder="예: 실험 실패를 극복하기 위해 노력한 탐구 태도를 더 구체적으로 보완해줘.")
                
                if st.button("🔄 선택한 학생 한 명만 재생성 실행"):
                    if not openai_api_key:
                        st.error("🔑 OpenAI API Key를 먼저 입력해주세요.")
                    elif not feedback_msg:
                        st.warning("💡 AI에게 전달할 수정 지시사항(피드백)을 입력해주세요.")
                    else:
                        client = OpenAI(api_key=openai_api_key)
                        with st.spinner(f"⏳ {target_student} 학생의 세특 초안을 최적화 필터로 보완 재구성하는 중..."):
                            
                            target_row = st.session_state.generated_df[st.session_state.generated_df[name_col] == target_student].iloc[0]
                            target_idx = st.session_state.generated_df[st.session_state.generated_df[name_col] == target_student].index[0]
                            
                            new_text, new_status = generate_student_draft(
                                client, master_system_prompt, target_student, target_row[content_col], max_bytes, encoding_type, feedback_msg=feedback_msg
                            )
                            st.session_state.generated_df.at[target_idx, "생기부_초안"] = new_text
                            st.session_state.generated_df.at[target_idx, "상태_확인"] = new_status
                            
                            st.success(f"🎉 {target_student} 학생의 초안이 성공적으로 수정되었습니다!")
                            st.rerun()

            # 마스터 엑셀 다운로드 빌드
            out_buffer = io.BytesIO()
            with pd.ExcelWriter(out_buffer, engine='openpyxl') as writer:
                st.session_state.generated_df.to_excel(writer, index=False, sheet_name='생기부_최종본')
                
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label="📥 최종 화면 교정본 반영 마스터 엑셀 다운로드",
                data=out_buffer.getvalue(),
                file_name="생기부_올인원마스터_최종결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
                    
    except Exception as e:
        st.error(f"파일 처리 중 오류 발생: {e}")
