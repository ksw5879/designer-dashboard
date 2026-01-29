import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# 페이지 설정
st.set_page_config(
    page_title="디자이너 리소스 대시보드",
    page_icon="📊",
    layout="wide"
)

st.title("📊 디자이너 리소스 관리 대시보드")

# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")
    
    st.info("Google Sheets를 연결하면 실제 데이터를 볼 수 있습니다!")
    
    sheet_url = st.text_input(
        "Google Sheets URL",
        placeholder="https://docs.google.com/spreadsheets/d/..."
    )
    
    uploaded_file = st.file_uploader(
        "Service Account JSON",
        type=['json']
    )
    
    st.markdown("---")
    st.markdown("""
    ### 📋 필요한 컬럼
    - 날짜 (YYYY. M. D)
    - 제작자
    - 브랜드명
    - 콘텐츠 유형
    - 콘텐츠 수
    """)

# 메인 화면
if not sheet_url or not uploaded_file:
    st.info("👈 왼쪽 사이드바에서 Google Sheets를 연결해주세요!")
    
    st.markdown("---")
    st.markdown("## 📖 사용 방법")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 1️⃣ Google Cloud 설정
        1. Google Cloud Console 접속
        2. Google Sheets API + Drive API 활성화
        3. 서비스 계정 만들기
        4. JSON 키 다운로드
        """)
    
    with col2:
        st.markdown("""
        ### 2️⃣ Google Sheets 공유
        1. JSON 파일에서 client_email 복사
        2. Google Sheets 공유
        3. 편집자 권한 부여
        """)
    
    st.markdown("---")
    st.markdown("### 📊 대시보드 기능")
    st.markdown("""
    - **상단 그래프**: 주차별 총 제작량 + 신규 제작량 추이
    - **사람별 카드**: 신규 제작량, 담당 브랜드 수, 기타 제작 상세
    - **필터**: 주차별 선택 가능
    """)
    
else:
    try:
        import json
        
        # JSON 로드
        credentials_dict = json.load(uploaded_file)
        
        # Google Sheets 연결
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
        
        st.success("✅ Google Sheets 연결 완료!")
        
        # 데이터 전처리
        df = df[df['날짜'].notna()]
        df = df[df['날짜'] != '날짜']
        df = df[df['날짜'] != '']
        
        df['날짜_변환'] = pd.to_datetime(
            df['날짜'].astype(str).str.replace(' ', '').str.replace('.', '-'), 
            errors='coerce'
        )
        
        df = df[df['날짜_변환'].notna()].copy()
        
        df['제작자_채움'] = df['제작자'].replace('', None)
        df['제작자_채움'] = df['제작자_채움'].fillna(method='ffill')
        
        df = df[df['제작자_채움'].notna()].copy()
        df = df[df['제작자_채움'] != ''].copy()
        
        df['콘텐츠 수'] = pd.to_numeric(df['콘텐츠 수'], errors='coerce').fillna(0).astype(int)
        
        df = df[df['콘텐츠 유형'].notna()].copy()
        df = df[df['콘텐츠 유형'] != ''].copy()
        
        df['주차'] = df['날짜_변환'].dt.strftime('%Y-W%U')
        df['주차_정렬용'] = df['날짜_변환'].dt.to_period('W')
        
        df['신규여부'] = df['콘텐츠 유형'].str.contains('신규', case=False, na=False)
        
        # 주차별 통계
        st.markdown("---")
        st.markdown("## 📈 주차별 팀 전체 제작량")
        
        weekly_total = df.groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
        weekly_total.columns = ['주차', '총제작량']
        
        weekly_new = df[df['신규여부'] == True].groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
        weekly_new.columns = ['주차', '신규제작량']
        
        weekly_stats = pd.merge(weekly_total, weekly_new, on='주차', how='left').fillna(0)
        weekly_stats['주차_표시'] = weekly_stats['주차'].astype(str)
        weekly_stats = weekly_stats.sort_values('주차')
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=weekly_stats['주차_표시'],
            y=weekly_stats['총제작량'],
            mode='lines+markers',
            name='총 제작량',
            line=dict(color='#1f77b4', width=3)
        ))
        
        fig.add_trace(go.Scatter(
            x=weekly_stats['주차_표시'],
            y=weekly_stats['신규제작량'],
            mode='lines+markers',
            name='신규 제작량',
            line=dict(color='#ff7f0e', width=3)
        ))
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # 통계
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("전체 총 제작량", f"{int(weekly_stats['총제작량'].sum()):,}개")
        with col2:
            st.metric("전체 신규 제작량", f"{int(weekly_stats['신규제작량'].sum()):,}개")
        with col3:
            st.metric("최근 주차 총 제작량", f"{int(weekly_stats.iloc[-1]['총제작량'])}개")
        with col4:
            st.metric("최근 주차 신규 제작량", f"{int(weekly_stats.iloc[-1]['신규제작량'])}개")
        
        # 사람별 통계
        st.markdown("---")
        st.markdown("## 👥 사람별 제작 현황")
        
        selected_week = st.selectbox(
            "주차 선택",
            ['전체'] + [str(w) for w in sorted(df['주차_정렬용'].unique(), reverse=True)]
        )
        
        if selected_week != '전체':
            df_filtered = df[df['주차_정렬용'] == pd.Period(selected_week, freq='W')]
        else:
            df_filtered = df
        
        person_stats = []
        
        for person in df_filtered['제작자_채움'].unique():
            person_df = df_filtered[df_filtered['제작자_채움'] == person]
            new_count = person_df[person_df['신규여부'] == True]['콘텐츠 수'].sum()
            brand_count = person_df['브랜드명'].nunique()
            
            person_stats.append({
                '이름': person,
                '신규제작량': int(new_count),
                '담당브랜드수': int(brand_count)
            })
        
        person_stats = sorted(person_stats, key=lambda x: x['신규제작량'], reverse=True)
        
        # 카드 표시
        cols = st.columns(3)
        for i, person in enumerate(person_stats):
            with cols[i % 3]:
                st.markdown(f"### {person['이름']}")
                st.metric("신규 제작", f"{person['신규제작량']}개")
                st.metric("담당 브랜드", f"{person['담당브랜드수']}개")
                st.markdown("---")
        
    except Exception as e:
        st.error(f"❌ 연결 실패: {str(e)}")
        st.info("Google Sheets URL과 JSON 파일을 확인해주세요.")
