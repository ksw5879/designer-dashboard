import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ============================================
# 페이지 설정
# ============================================
st.set_page_config(
    page_title="디자이너 리소스 대시보드",
    page_icon="📊",
    layout="wide"
)

# ============================================
# Google Sheets 연동
# ============================================
def connect_to_gsheet(credentials_dict, sheet_url):
    """Google Sheets 데이터 로드"""
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    credentials = Credentials.from_service_account_info(
        credentials_dict, scopes=scope
    )
    client = gspread.authorize(credentials)
    
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.get_worksheet(0)
    
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    
    return df

# ============================================
# 데이터 전처리
# ============================================
def preprocess_data(df):
    """데이터 정제 및 전처리"""
    # 필수 컬럼 확인
    required_columns = ['날짜', '제작자', '브랜드명', '콘텐츠 유형', '콘텐츠 수']
    
    # 빈 행 제거 (날짜가 비어있거나 '날짜'가 반복되는 헤더 행)
    df = df[df['날짜'].notna()]
    df = df[df['날짜'] != '날짜']
    df = df[df['날짜'] != '']
    
    # 날짜 처리
    df['날짜'] = df['날짜'].astype(str).str.strip()
    # '2026. 1. 27' 형식을 '2026-01-27'로 변환
    df['날짜_변환'] = pd.to_datetime(df['날짜'].str.replace(' ', '').str.replace('.', '-'), errors='coerce')
    
    # 날짜 변환 실패한 행 제거
    df = df[df['날짜_변환'].notna()].copy()
    
    # 제작자가 비어있는 행 제거 (같은 제작자의 여러 브랜드 처리)
    df['제작자_채움'] = df['제작자'].replace('', None)
    df['제작자_채움'] = df['제작자_채움'].fillna(method='ffill')
    
    # 빈 제작자 행 제거
    df = df[df['제작자_채움'].notna()].copy()
    df = df[df['제작자_채움'] != ''].copy()
    
    # 콘텐츠 수를 숫자로 변환
    df['콘텐츠 수'] = pd.to_numeric(df['콘텐츠 수'], errors='coerce').fillna(0).astype(int)
    
    # 콘텐츠 유형이 비어있는 행 제거
    df = df[df['콘텐츠 유형'].notna()].copy()
    df = df[df['콘텐츠 유형'] != ''].copy()
    
    # 주차 계산
    df['주차'] = df['날짜_변환'].dt.strftime('%Y-W%U')
    df['주차_정렬용'] = df['날짜_변환'].dt.to_period('W')
    
    # 콘텐츠 유형 정리 (신규 포함 여부)
    df['신규여부'] = df['콘텐츠 유형'].str.contains('신규', case=False, na=False)
    
    # 콘텐츠 유형 간소화
    def simplify_content_type(content_type):
        if pd.isna(content_type) or content_type == '':
            return '기타'
        content_type = str(content_type).lower()
        if '신규' in content_type or '디벨롭' in content_type:
            return '신규/디벨롭'
        elif 'ai' in content_type:
            return 'AI'
        elif '리사이징' in content_type:
            return '리사이징'
        elif '베리' in content_type:
            return '베리'
        elif '지면확장' in content_type:
            return '지면확장'
        else:
            return '기타'
    
    df['콘텐츠유형_간소화'] = df['콘텐츠 유형'].apply(simplify_content_type)
    
    return df

# ============================================
# 주차별 팀 전체 통계
# ============================================
def calculate_weekly_team_stats(df):
    """주차별 팀 전체 제작량 계산"""
    weekly_total = df.groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
    weekly_total.columns = ['주차', '총제작량']
    
    weekly_new = df[df['신규여부'] == True].groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
    weekly_new.columns = ['주차', '신규제작량']
    
    weekly_stats = pd.merge(weekly_total, weekly_new, on='주차', how='left').fillna(0)
    weekly_stats['주차_표시'] = weekly_stats['주차'].astype(str)
    
    # 정렬
    weekly_stats = weekly_stats.sort_values('주차')
    
    return weekly_stats

# ============================================
# 사람별 상세 통계
# ============================================
def calculate_person_stats(df, selected_week=None):
    """사람별 상세 통계 계산"""
    if selected_week and selected_week != '전체':
        df_filtered = df[df['주차_정렬용'] == selected_week].copy()
    else:
        df_filtered = df.copy()
    
    person_stats = []
    
    for person in df_filtered['제작자_채움'].unique():
        person_df = df_filtered[df_filtered['제작자_채움'] == person]
        
        # 신규 제작량
        new_count = person_df[person_df['신규여부'] == True]['콘텐츠 수'].sum()
        
        # 담당 브랜드 수
        brand_count = person_df['브랜드명'].nunique()
        
        # 기타 제작량 상세 (신규 제외)
        other_df = person_df[person_df['신규여부'] == False]
        other_detail = other_df.groupby('콘텐츠유형_간소화')['콘텐츠 수'].sum().to_dict()
        
        # 총 기타 제작량
        other_total = sum(other_detail.values())
        
        person_stats.append({
            '이름': person,
            '신규제작량': int(new_count),
            '담당브랜드수': int(brand_count),
            '기타제작량': int(other_total),
            '기타상세': other_detail
        })
    
    # 신규 제작량 기준 정렬
    return sorted(person_stats, key=lambda x: x['신규제작량'], reverse=True)

# ============================================
# 샘플 데이터 로드
# ============================================
@st.cache_data
def load_sample_data():
    """업로드된 샘플 CSV 로드"""
    try:
        df = pd.read_csv('/mnt/user-data/uploads/테스트용1.csv')
        return df
    except:
        return None

# ============================================
# 메인 앱
# ============================================
def main():
    st.title("📊 디자이너 리소스 관리 대시보드")
    
    # ============================================
    # 사이드바: 설정
    # ============================================
    with st.sidebar:
        st.header("⚙️ 설정")
        
        # 데이터 소스 선택
        data_source = st.radio(
            "데이터 소스",
            ["샘플 데이터 사용", "Google Sheets 연결"]
        )
        
        if data_source == "Google Sheets 연결":
            st.markdown("---")
            sheet_url = st.text_input(
                "Google Sheets URL",
                placeholder="https://docs.google.com/spreadsheets/d/..."
            )
            
            uploaded_file = st.file_uploader(
                "Service Account JSON",
                type=['json'],
                help="Google Cloud Console에서 다운로드한 서비스 계정 키"
            )
            
            if sheet_url and uploaded_file:
                try:
                    import json
                    credentials_dict = json.load(uploaded_file)
                    df_raw = connect_to_gsheet(credentials_dict, sheet_url)
                    st.success("✅ Google Sheets 연결 완료!")
                except Exception as e:
                    st.error(f"❌ 연결 실패: {str(e)}")
                    df_raw = None
            else:
                df_raw = None
        else:
            # 샘플 데이터 로드
            df_raw = load_sample_data()
            if df_raw is not None:
                st.success("✅ 샘플 데이터 로드 완료!")
            else:
                st.warning("샘플 데이터를 찾을 수 없습니다.")
        
        st.markdown("---")
        st.markdown("""
        ### 📋 Google Sheets 형식
        필수 컬럼:
        - 날짜 (YYYY. M. D)
        - 제작자
        - 브랜드명
        - 콘텐츠 유형
        - 콘텐츠 수
        """)
    
    # ============================================
    # 데이터 처리
    # ============================================
    if df_raw is None or df_raw.empty:
        st.warning("⚠️ 데이터를 로드해주세요.")
        st.info("왼쪽 사이드바에서 '샘플 데이터 사용'을 선택하거나 Google Sheets를 연결하세요.")
        return
    
    try:
        df = preprocess_data(df_raw)
    except Exception as e:
        st.error(f"❌ 데이터 처리 중 오류 발생: {str(e)}")
        st.write("원본 데이터:")
        st.dataframe(df_raw.head())
        return
    
    if df.empty:
        st.warning("⚠️ 처리할 수 있는 데이터가 없습니다.")
        return
    
    # ============================================
    # 필터 영역
    # ============================================
    st.markdown("---")
    col_filter1, col_filter2, col_filter3 = st.columns([2, 1, 1])
    
    with col_filter1:
        available_weeks = sorted(df['주차_정렬용'].unique(), reverse=True)
        week_options = ['전체'] + [str(w) for w in available_weeks]
        selected_week = st.selectbox(
            "📅 주차 선택 (사람별 통계 필터)",
            options=week_options,
            index=0
        )
    
    with col_filter2:
        if st.button("🔄 새로고침", use_container_width=True):
            st.rerun()
    
    with col_filter3:
        show_raw_data = st.checkbox("데이터 보기", value=False)
    
    # ============================================
    # 상단: 주차별 팀 전체 제작량 그래프
    # ============================================
    st.markdown("---")
    st.markdown("## 📈 주차별 팀 전체 제작량")
    
    weekly_stats = calculate_weekly_team_stats(df)
    
    if not weekly_stats.empty:
        fig = go.Figure()
        
        # 총 제작량
        fig.add_trace(go.Scatter(
            x=weekly_stats['주차_표시'],
            y=weekly_stats['총제작량'],
            mode='lines+markers+text',
            name='총 제작량',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=10),
            text=weekly_stats['총제작량'].astype(int),
            textposition='top center',
            textfont=dict(size=12, color='#1f77b4')
        ))
        
        # 신규 제작량
        fig.add_trace(go.Scatter(
            x=weekly_stats['주차_표시'],
            y=weekly_stats['신규제작량'],
            mode='lines+markers+text',
            name='신규 제작량',
            line=dict(color='#ff7f0e', width=3),
            marker=dict(size=10),
            text=weekly_stats['신규제작량'].astype(int),
            textposition='bottom center',
            textfont=dict(size=12, color='#ff7f0e')
        ))
        
        fig.update_layout(
            height=450,
            hovermode='x unified',
            xaxis_title="주차",
            yaxis_title="제작량 (개)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            font=dict(size=13)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 통계 요약
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_all = int(weekly_stats['총제작량'].sum())
            st.metric("전체 기간 총 제작량", f"{total_all:,}개")
        
        with col2:
            total_new = int(weekly_stats['신규제작량'].sum())
            st.metric("전체 기간 신규 제작량", f"{total_new:,}개")
        
        with col3:
            latest_total = int(weekly_stats.iloc[-1]['총제작량'])
            st.metric("최근 주차 총 제작량", f"{latest_total}개")
        
        with col4:
            latest_new = int(weekly_stats.iloc[-1]['신규제작량'])
            st.metric("최근 주차 신규 제작량", f"{latest_new}개")
    
    # ============================================
    # 하단: 사람별 카드
    # ============================================
    st.markdown("---")
    st.markdown("## 👥 사람별 제작 현황")
    
    # 주차 필터 적용
    if selected_week == '전체':
        person_stats = calculate_person_stats(df, selected_week=None)
        st.markdown("### 📊 전체 기간")
    else:
        selected_week_period = pd.Period(selected_week, freq='W')
        person_stats = calculate_person_stats(df, selected_week=selected_week_period)
        st.markdown(f"### 📊 {selected_week}")
    
    if not person_stats:
        st.info("해당 기간에 데이터가 없습니다.")
        return
    
    # 3열 그리드로 카드 배치
    cols_per_row = 3
    for i in range(0, len(person_stats), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j in range(cols_per_row):
            if i + j < len(person_stats):
                person = person_stats[i + j]
                
                with cols[j]:
                    # 카드 헤더
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 20px;
                        border-radius: 10px;
                        color: white;
                        text-align: center;
                        margin-bottom: 10px;
                    ">
                        <h2 style="margin: 0; color: white;">{person['이름']}</h2>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 신규 제작량 (크게)
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                        padding: 30px;
                        border-radius: 10px;
                        text-align: center;
                        margin-bottom: 10px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    ">
                        <h1 style="margin: 0; color: white; font-size: 4em; font-weight: bold;">{person['신규제작량']}</h1>
                        <p style="margin: 10px 0 0 0; color: white; font-size: 1.3em; font-weight: 600;">신규 제작</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 담당 브랜드 수
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                        padding: 20px;
                        border-radius: 10px;
                        text-align: center;
                        margin-bottom: 10px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    ">
                        <h2 style="margin: 0; color: white; font-size: 2.5em;">{person['담당브랜드수']}</h2>
                        <p style="margin: 5px 0 0 0; color: white; font-size: 1.1em;">담당 브랜드</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 기타 제작량
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
                        padding: 20px;
                        border-radius: 10px;
                        margin-bottom: 10px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    ">
                        <h3 style="margin: 0 0 15px 0; color: #2c3e50; font-size: 1.3em;">기타 제작: <strong>{person['기타제작량']}개</strong></h3>
                    """, unsafe_allow_html=True)
                    
                    # 기타 상세
                    if person['기타상세']:
                        detail_html = "<ul style='margin: 0; padding-left: 20px; color: #34495e;'>"
                        for content_type, count in sorted(person['기타상세'].items(), key=lambda x: x[1], reverse=True):
                            detail_html += f"<li style='margin: 5px 0; font-size: 1.1em;'><strong>{content_type}</strong>: {int(count)}개</li>"
                        detail_html += "</ul>"
                        
                        st.markdown(f"{detail_html}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
    
    # ============================================
    # 원본 데이터 보기
    # ============================================
    if show_raw_data:
        st.markdown("---")
        st.markdown("## 📋 원본 데이터")
        st.dataframe(
            df[['날짜', '제작자_채움', '브랜드명', '콘텐츠 유형', '콘텐츠 수', '주차']].rename(columns={'제작자_채움': '제작자'}),
            use_container_width=True
        )

if __name__ == "__main__":
    main()
