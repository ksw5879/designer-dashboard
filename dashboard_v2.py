import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# 페이지 설정
st.set_page_config(
    page_title="디자이너 리소스 대시보드",
    page_icon="📊",
    layout="wide"
)

st.title("📊 디자이너 리소스 관리 대시보드")

# Secrets에서 자동으로 읽기
try:
    sheet_url = st.secrets["SHEET_URL"]
    credentials_dict = dict(st.secrets["gcp_service_account"])
    
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
    st.error("❌ 데이터를 불러올 수 없습니다.")
    st.error(f"오류: {str(e)}")
    st.info("관리자에게 문의하세요.")
