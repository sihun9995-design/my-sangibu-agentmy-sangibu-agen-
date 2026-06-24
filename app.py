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

# [최적화 마스터 V6] 순수 텍스트 단일 병합 + 선택한 모델 동적 반영 + Prompt Caching 적중
def generate_student_draft(client, system_prompt, student_name, raw_content, max_bytes, encoding_type, model_name, feedback_msg=None):
    try:
        if feedback_msg:
            user_prompt = f"대상 학생 이름: {student_name}\n원래 관찰 기록 및 소감 내용:\n{raw_content}\n\n[선생님의 추가 수정 피드백]:\n{feedback_msg}\n\n[필수]: 위 피드백을 반영하되, 학생 실명은 세특 본문에 절대 언급하지 말고 명사형 종결 어미로 작성하세요."
        else:
            user_prompt = f"대상 학생 이름: {student_name}\n제출된 보고서 및 관찰 메모 내용:\n{raw_content}\n\n[필수]: 위 학생의 이름을 세특 본문에 절대 언급하지 말고, 주어를 생략하여 작성하세요."

        # 1차 초안 생성
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt}, 
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.6 if not feedback_msg else 0.5,
            max_tokens=800
        )
        draft_text = response.choices[0].message.content.strip()
        current_bytes = calculate_bytes(draft_text, encoding_type)
        
        retry_count = 0
        while current_bytes > max_bytes and retry_count < 2:
            retry_user_prompt = f"""
            앞서 생성된 텍스트가 현재 목표치인 {max_bytes}바이트를 초과하여 {current_bytes}바이트로 계산되었습니다.
            지정된 모든 세특 작성 원칙(명사형 종결, 실명 배제, 컴플라이언스)을 철저히 유지하면서, 핵심 맥락과 전문 용어 손실 없이 내용을 조밀하게 축약하여 반드시 {max_bytes}바이트 이하로 재작성하십시오.
            
            [초과된 이전 텍스트]:
            {draft_text}
            """
            
            response_retry = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt}, 
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
    page_title="생기부 올인원 검수 및 자동화 플랫폼",
    page_icon="📝",
    layout="wide"
)

# 세션 상태 초기화
if "generated_df" not in st.session_state:
    st.session_state.generated_df = None
if "selected_preset" not in st.session_state:
    st.session_state.selected_preset = "자연과학 계열"

# UI 커스텀 CSS (구글/제미나이 룩앤필 유지)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans KR', sans-serif;
        background-color: #F8F9FA !important;
        color: #202124;
    }
    
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E0E0E0 !important;
    }
    
    .main-title-container {
        text-align: left;
        padding: 1.2rem 2rem;
        background-color: #FFFFFF;
        border-bottom: 1px solid #E0E0E0;
        margin-bottom: 2rem;
        border-radius: 8px;
    }
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        color: #1A73E8;
        margin-bottom: 0.3rem;
    }
    .main-subtitle {
        font-size: 0.95rem;
        color: #5F6368;
        font-weight: 400;
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border: 1px solid #DADCE0 !important;
        border-radius: 8px !important;
        box-shadow: none !important;
        padding: 1.5rem !important;
        margin-bottom: 1rem !important;
    }
    
    .card-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #202124;
        margin-bottom: 1rem;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid #F1F3F4;
    }
    
    .rule-item {
        background-color: #F8F9FA;
        padding: 0.5rem 0.8rem;
        border-radius: 6px;
        border: 1px solid #F1F3F4;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
        color: #3C4043;
    }
    
    .stButton>button {
        background-color: #1A73E8 !important;
        color: #FFFFFF !important;
        font-weight: 500 !important;
        font-size: 0.95rem !important;
        border-radius: 24px !important;
        padding: 0.5rem 2rem !important;
        border: none !important;
        box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3) !important;
        transition: background-color 0.2s, box-shadow 0.2s;
    }
    .stButton>button:hover {
        background-color: #1557B1 !important;
        box-shadow: 0 1px 3px 1px rgba(60,64,67,0.15) !important;
    }
    
    div[data-testid="stDownloadButton"]>button {
        background-color: #FFFFFF !important;
        color: #1A73E8 !important;
        border: 1px solid #DADCE0 !important;
        border-radius: 24px !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        box-shadow: none !important;
    }
    div[data-testid="stDownloadButton"]>button:hover {
        background-color: #F8F9FA !important;
        border-color: #1A73E8 !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="main-title-container">
        <div class="main-title">생기부 올인원 검수 및 자동화 플랫폼</div>
        <div class="main-subtitle">엑셀 파일을 업로드하여 가이드라인에 맞춘 초안을 기술하고 내측 실시간 교정 및 마이크로 편집을 지원합니다.</div>
    </div>
""", unsafe_allow_html=True)

# 사이드바 영역
with st.sidebar:
    st.markdown("### ⚙️ 시스템 설정 및 인증")
    openai_api_key = st.text_input("OpenAI API Key 입력", type="password", placeholder="sk-proj-...")
    
    st.markdown("---")
    st.markdown("### 🤖 AI 모델 선택")
    model_choice = st.selectbox(
        "엔진 모델 지정",
        ["🔥 GPT-4o (마스터 고품질 모드)", "⚡ GPT-4o-mini (초가성비 고속 모드)"],
        index=0
    )
    model_name = "gpt-4o-mini" if "mini" in model_choice.lower() else "gpt-4o"
    
    st.markdown("---")
    st.markdown("### 👥 담당 관리")
    subject_preset = st.selectbox("활동 분석 계열 설정", ["자연과학 계열", "공학 계열", "인문/사회 계열", "진로 탐색 활동"])
    st.session_state.selected_preset = subject_preset
    
    st.markdown("---")
    st.markdown("### 📝 서비스 기준")
    encoding_choice = st.radio(
        "나이스(NEIS) 바이트 규격",
        ["개정 4세대 표준 (UTF-8 / 3B)", "구형 및 일부 특수창 (EUC-KR / 2B)"],
        index=0
    )
    encoding_type = "utf-8" if "UTF-8" in encoding_choice else "euc-kr"
    
    st.markdown("---")
    st.markdown("### 📊 분량 한계 설정")
    max_bytes = st.slider("최대 허용 바이트 (한도: 1500)", min_value=1000, max_value=1450, value=1350, step=50)

# 프리셋 지침
preset_guidelines = {
    "자연과학 계열": "과학적 호기심, 가설 설정 및 탐구 실험 과정, 객관적 데이터 분석 및 논리적 결론 도출 역량을 중심으로 서술하십시오.",
    "공학 계열": "공학적 문제해결력, 기술적 대안 설계 및 프로토타입 구상, 실용적 구현 가능성 및 테크놀로지 접목 능력을 중심으로 서술하십시오.",
    "인문/사회 계열": "사회 현상에 대한 비판적 사고력, 문헌 및 텍스트 분석 능력, 인문학적 통찰과 논리적 에세이 전개 능력을 중심으로 서술하십시오.",
    "진로 탐색 활동": "학생의 구체적인 진로 희망 및 전공 분야와의 유기적 연계성, 자기주도적인 학업 탐색 태도와 향후 발전 가능성을 중심으로 서술하십시오."
}

col1, col2 = st.columns([1, 1])

with col1:
    with st.container(border=True):
        st.markdown('<div class="card-title">1. 데이터 업로드 및 처리</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("학생 데이터 파일(.xlsx)을 드래그하거나 클릭하여 업로드하세요", type=["xlsx"])
        
        sample_df = pd.DataFrame({
            "학번": [10101, 10102],
            "이름": ["홍길동", "이순신"],
            "보고서내용": ["자율주행 자동차 보고서 제출함.", "효소 촉매 반응 실험을 주도함."],
            "발표및참여도": ["딜레마 제안 발표 역량이 우수함.", "시각화 데이터를 급우들에게 논리적으로 설명함."]
        })
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            sample_df.to_excel(writer, index=False)
            
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(label="📥 엑셀 입력양식 샘플 다운로드", data=buffer.getvalue(), file_name="생기부_입력양식_샘플.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with col2:
    with st.container(border=True):
        st.markdown('<div class="card-title">2. 가이드라인 적용 기준</div>', unsafe_allow_html=True)
        st.markdown(f"""
            <div class="rule-item"><b>지정 엔지니어링:</b> {model_name.upper()}</div>
            <div class="rule-item"><b>매핑 타겟 그룹:</b> {subject_preset}</div>
            <div class="rule-item"><b>문체 준수:</b> 전체 명사형 종결 어미 마감 처리 강제</div>
            <div class="rule-item"><b>개인정보 배제:</b> 본문 영역 내 학생 실명 완벽 제어 및 삭제</div>
            <div class="rule-item"><b>컴플라이언스 필터:</b> 사교육 유발 요소, 대학명 전면 차단</div>
        """, unsafe_allow_html=True)

if uploaded_file:
    try:
        df_origin = pd.read_excel(uploaded_file)
        columns_list = list(df_origin.columns)
        
        id_keywords = ['학번', '번호', '학생번호', 'id', 'no', '학적', 'num']
        name_keywords = ['이름', '성명', '학생명', '학생 이름', 'name']
        content_keywords = ['보고서내용', '내용', '보고서', '특기사항', '세특', '활동', '관찰', '메모', 'content', '기술', '기록', '발표', '참여', '평가']
        
        default_id_col = next((c for c in columns_list if any(k in str(c).lower() for k in id_keywords)), columns_list[0])
        default_name_col = next((c for c in columns_list if any(k in str(c).lower() for k in name_keywords)), columns_list[1] if len(columns_list) > 1 else columns_list[0])
        
        default_content_cols = [c for c in columns_list if any(k in str(c).lower() for k in content_keywords)]
        if not default_content_cols and len(columns_list) > 2:
            default_content_cols = [columns_list[2]]
        
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<div class="card-title">🎯 매핑 인덱스 매칭 구조 자동화</div>', unsafe_allow_html=True)
            sel_col1, sel_col2, sel_col3 = st.columns(3)
            with sel_col1: id_col = st.selectbox("📌 학번 인덱스 열", columns_list, index=columns_list.index(default_id_col))
            with sel_col2: name_col = st.selectbox("📌 성명 인덱스 열", columns_list, index=columns_list.index(default_name_col))
            with sel_col3: 
                content_cols = st.multiselect("📌 특기사항 소스 데이터 열 (복수 선택 가능)", columns_list, default=default_content_cols)

        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<div class="card-title">📊 소스 데이터 타임라인 미리보기</div>', unsafe_allow_html=True)
            st.dataframe(df_origin, use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        c_col1, c_col2, c_col3 = st.columns([1, 2, 1])
        with c_col2: start_button = st.button("자동화 프로세스 시작", use_container_width=True)
            
        selected_guideline = preset_guidelines[subject_preset]
        master_system_prompt = f"""
        당신은 대한민국 고등학교의 대학입시 및 학생부종합전형(학종)을 완벽하게 숙지하고 있는 20년 경력의 베테랑 교사입니다.
        제공되는 활동 소스 내용들을 하나의 유기적이고 완벽한 학교생활기록부 '과목별 세부능력 및 특기사항(세특)' 초안으로 직조하십시오.
        [선택 계열 맞춤 강조 지침] {selected_guideline}
        [엄격 준수 규정 및 가이드라인]
        1. 문체 제한: 모든 문장은 어떠한 예외도 없이 반드시 명사형 종결 어미인 '~함.', '~임.'으로 끝내야 합니다.
        2. 완벽한 실명 언급 배제: 제공되는 유저 입력 내 학생 이름을 절대로 세특 생성 본문에 노출하지 마십시오.
        3. 분량 극대화 및 바이트 관리: 설정된 목표 한도인 {max_bytes}바이트에 최대한 가깝게(최소 {max_bytes - 150}바이트 이상) 서술하십시오.
        4. 법정 기재 금지사항 컴플라이언스: 사교육 유발 요소, 부모 직업 암시, 구체적인 대학명은 철저히 배제하고 삭제하십시오.
        5. 정석적 세특 서술 구조 체계: [주제 선정 동기] -> [구체적인 주도적 탐구 과정] -> [활동을 통해 배우고 느낀 점]
        """

        if start_button:
            if not openai_api_key:
                st.warning("🔑 왼쪽 사이드바에 OpenAI API Key를 먼저 입력해주세요.")
            elif not content_cols:
                st.error("⚠️ 소스 데이터 열을 최소 한 개 이상 선택해주세요.")
            else:
                client = OpenAI(api_key=openai_api_key)
                total_rows = len(df_origin)
                
                draft_list = [""] * total_rows
                status_list = [""] * total_rows
                
                progress_bar = st.progress(0)
                status_message = st.empty()
                status_message.info(f"⏳ 총 {total_rows}명의 데이터 세트를 {model_name.upper()} 핵심 코어로 병렬 변환 처리 중...")

                with ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_idx = {}
                    for idx, row in df_origin.iterrows():
                        student_name = str(row[name_col])
                        
                        # 🛠️ [최적화 변경 부분] 말머리표 다 떼어내고, 빈칸이 아닌 내용만 순수하게 공백 단위로 엮어 하나의 텍스트로 합칩니다.
                        raw_content = " ".join([str(row[col]).strip() for col in content_cols if pd.notna(row[col])])
                        
                        future = executor.submit(
                            generate_student_draft, 
                            client, master_system_prompt, student_name, raw_content, max_bytes, encoding_type, model_name
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
                
                status_message.success(f"🎉 동적 파이프라인 처리가 완료되었습니다. (사용한 모델: {model_name.upper()})")
                
                working_df = df_origin[[id_col, name_col] + content_cols].copy()
                working_df["생기부_초안"] = draft_list
                working_df["상태_확인"] = status_list
                st.session_state.generated_df = working_df

        # ----------------- 실시간 편집 및 개별 재생성 렌더링 구역 -----------------
        if st.session_state.generated_df is not None:
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 1. 결과 노출 및 화면 내 더블클릭 실시간 편집기
            with st.container(border=True):
                st.markdown('<div class="card-title">✨ 최종 생성 결과 검수실 (셀 더블클릭 시 데이터 즉시 수정)</div>', unsafe_allow_html=True)
                st.info("💡 세특 결과 셀을 더블클릭하여 최종 텍스트 보완이 가능하며, 편집 내역은 다운로드 마스터 파일에 동기화 보존됩니다.")
                
                edited_df = st.data_editor(
                    st.session_state.generated_df,
                    use_container_width=True,
                    disabled=[id_col, name_col, "상태_확인"] + content_cols,
                    height=350,
                    key="student_se_editor"
                )
                st.session_state.generated_df = edited_df

            # 2. 개별 학생 핀포인트 피드백 재작성 컨트롤러
            with st.container(border=True):
                st.markdown('<div class="card-title">🔄 핀포인트 마이크로 교정 및 단일 갱신 컨트롤러</div>', unsafe_allow_html=True)
                st.write("단일 수정이 필요한 개별 대상을 지정하고 심화 지시 피드백을 전달하여 핀포인트 갱신을 수행합니다.")
                
                student_options = st.session_state.generated_df[name_col].tolist()
                tgt_col1, tgt_col2 = st.columns([1, 2])
                with tgt_col1: target_student = st.selectbox("🎯 대상 타겟 선택", student_options)
                with tgt_col2: feedback_msg = st.text_input("💡 핀포인트 전용 마이크로 수정 피드백 지시사항", placeholder="예: 발표와 보고서 내용을 더 촘촘하게 엮어줘.")
                
                if st.button("선택 대상을 타겟으로 재가동"):
                    if not openai_api_key:
                        st.error("🔑 OpenAI API Key를 먼저 입력해주세요.")
                    elif not feedback_msg:
                        st.warning("💡 수정 피드백 메시지를 입력하십시오.")
                    else:
                        client = OpenAI(api_key=openai_api_key)
                        with st.spinner(f"⏳ {target_student} 학생의 데이터를 백엔드 가이드라인 엔진으로 갱신하는 중..."):
                            
                            target_row = st.session_state.generated_df[st.session_state.generated_df[name_col] == target_student].iloc[0]
                            target_idx = st.session_state.generated_df[st.session_state.generated_df[name_col] == target_student].index[0]
                            
                            # 🛠️ [최적화 변경 부분] 핀포인트 단일 재생성 시에도 동일하게 순수 공백 단위로 텍스트를 하나로 합침
                            raw_content = " ".join([str(target_row[col]).strip() for col in content_cols if pd.notna(target_row[col])])
                            
                            new_text, new_status = generate_student_draft(
                                client, master_system_prompt, target_student, raw_content, max_bytes, encoding_type, model_name, feedback_msg=feedback_msg
                            )
                            st.session_state.generated_df.at[target_idx, "생기부_초안"] = new_text
                            st.session_state.generated_df.at[target_idx, "상태_확인"] = new_status
                            
                            st.success(f"🎉 {target_student} 학생의 결과물이 최적화 필터링되어 보완 완료되었습니다.")
                            st.rerun()

            # 마스터 엑셀 다운로드 빌드
            out_buffer = io.BytesIO()
            with pd.ExcelWriter(out_buffer, engine='openpyxl') as writer:
                st.session_state.generated_df.to_excel(writer, index=False, sheet_name='생기부_최종본')
                
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label="📥 최종 화면 교정본 반영 마스터 엑셀 다운로드",
                data=out_buffer.getvalue(),
                file_name=f"생기부_올인원마스터_{model_name}_최종결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
                    
    except Exception as e:
        st.error(f"파일 처리 중 오류 발생: {e}")
