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

# 디자이너 분류
try:
    IMAGE_DESIGNERS = st.secrets.get("image_designers", ["박유정", "권지연", "안서현", "도혜진", "김성웅"])
    VIDEO_DESIGNERS = st.secrets.get("video_designers", ["은누리", "박시은", "이재호", "이현성"])
except:
    IMAGE_DESIGNERS = ["박유정", "권지연", "안서현", "도혜진", "김성웅"]
    VIDEO_DESIGNERS = ["은누리", "박시은", "이재호", "이현성"]

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
    df['월'] = df['날짜_변환'].dt.to_period('M')
    
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
    
    # ============================================
    # 그래프 섹션
    # ============================================
    st.markdown("---")
    
    # 주차 선택
    available_weeks = sorted(df['주차_정렬용'].unique(), reverse=True)
    week_options = ['전체'] + [str(w) for w in available_weeks]
    selected_week = st.selectbox("📅 주차 선택", options=week_options, index=0)
    
    # 그래프 1: 주차별 그래프 (월단위) - 위
    st.markdown("### 📊 주차별 제작량 (월단위)")
    
    available_months = sorted(df['월'].unique(), reverse=True)
    if len(available_months) > 0:
        recent_month = available_months[0]
        month_df = df[df['월'] == recent_month]
        
        weekly_total = month_df.groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
        weekly_total.columns = ['주차', '총제작량']
        
        weekly_new = month_df[month_df['신규여부'] == True].groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
        weekly_new.columns = ['주차', '신규제작량']
        
        weekly_stats = pd.merge(weekly_total, weekly_new, on='주차', how='left').fillna(0)
        weekly_stats['주차_표시'] = weekly_stats['주차'].astype(str).str[-2:] + '주차'
        weekly_stats = weekly_stats.sort_values('주차')
        
        fig_weekly = go.Figure()
        
        # 선 그래프만
        fig_weekly.add_trace(go.Scatter(
            x=weekly_stats['주차_표시'],
            y=weekly_stats['총제작량'],
            mode='lines+markers',
            name='총 제작량',
            line=dict(color='#4A90E2', width=3),
            marker=dict(size=10)
        ))
        
        fig_weekly.add_trace(go.Scatter(
            x=weekly_stats['주차_표시'],
            y=weekly_stats['신규제작량'],
            mode='lines+markers',
            name='신규 제작량',
            line=dict(color='#E67E22', width=3),
            marker=dict(size=10)
        ))
        
        fig_weekly.update_layout(
            height=400,
            xaxis_title="주차",
            yaxis_title="제작량 (개)",
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_weekly, use_container_width=True)
    
    st.markdown("---")
    
    # 그래프 2: 일별 그래프 (주차별) - 아래
    st.markdown("### 📅 일별 제작량 (주차별)")
    
    if selected_week == '전체':
        st.info("특정 주차를 선택하면 일별 그래프가 표시됩니다.")
    else:
        selected_week_period = pd.Period(selected_week, freq='W')
        week_df = df[df['주차_정렬용'] == selected_week_period]
        
        daily_total = week_df.groupby('날짜_변환')['콘텐츠 수'].sum().reset_index()
        daily_total.columns = ['날짜', '총제작량']
        daily_total['날짜_표시'] = daily_total['날짜'].dt.strftime('%m/%d')
        
        daily_new = week_df[week_df['신규여부'] == True].groupby('날짜_변환')['콘텐츠 수'].sum().reset_index()
        daily_new.columns = ['날짜', '신규제작량']
        
        daily_stats = pd.merge(daily_total, daily_new, on='날짜', how='left').fillna(0)
        daily_stats = daily_stats.sort_values('날짜')
        
        fig_daily = go.Figure()
        
        # 선 그래프만
        fig_daily.add_trace(go.Scatter(
            x=daily_stats['날짜_표시'],
            y=daily_stats['총제작량'],
            mode='lines+markers',
            name='총 제작량',
            line=dict(color='#4A90E2', width=3),
            marker=dict(size=10)
        ))
        
        fig_daily.add_trace(go.Scatter(
            x=daily_stats['날짜_표시'],
            y=daily_stats['신규제작량'],
            mode='lines+markers',
            name='신규 제작량',
            line=dict(color='#E67E22', width=3),
            marker=dict(size=10)
        ))
        
        fig_daily.update_layout(
            height=400,
            xaxis_title="날짜",
            yaxis_title="제작량 (개)",
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_daily, use_container_width=True)
    
    # ============================================
    # 사람별 카드
    # ============================================
    st.markdown("---")
    st.markdown("## 👥 사람별 제작 현황")
    
    # 필터링
    if selected_week != '전체':
        selected_week_period = pd.Period(selected_week, freq='W')
        df_filtered = df[df['주차_정렬용'] == selected_week_period]
    else:
        df_filtered = df
    
    # 사람별 통계 계산
    def calculate_person_stats(person_name):
        person_df = df_filtered[df_filtered['제작자_채움'] == person_name]
        
        # 유형별 집계
        type_counts = person_df.groupby('콘텐츠유형_간소화')['콘텐츠 수'].sum().to_dict()
        
        # 브랜드 목록
        brands = person_df['브랜드명'].unique().tolist()
        
        # 총 제작량
        total = person_df['콘텐츠 수'].sum()
        
        return {
            '이름': person_name,
            '총제작량': int(total),
            '신규': int(type_counts.get('신규/디벨롭', 0)),
            '베리': int(type_counts.get('베리', 0)),
            '리사이징': int(type_counts.get('리사이징', 0)),
            '지면확장': int(type_counts.get('지면확장', 0)),
            'AI': int(type_counts.get('AI', 0)),
            '브랜드수': len(brands),
            '브랜드목록': brands
        }
    
    # 이미지 디자이너
    st.markdown("### 🎨 이미지 디자이너")
    image_stats = []
    for designer in IMAGE_DESIGNERS:
        if designer in df_filtered['제작자_채움'].values:
            image_stats.append(calculate_person_stats(designer))
    
    image_stats = sorted(image_stats, key=lambda x: x['신규'], reverse=True)
    
    cols = st.columns(3)
    for i, person in enumerate(image_stats):
        with cols[i % 3]:
            # 헤더
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #4A90E2 0%, #357ABD 100%);
                padding: 15px;
                border-radius: 10px 10px 0 0;
                color: white;
                text-align: center;
            ">
                <h3 style="margin: 0; color: white;">{person['이름']}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # 신규/디벨롭 + 총제작량
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #E67E22 0%, #D35400 100%);
                padding: 30px 20px;
                text-align: center;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <h1 style="margin: 0; color: white; font-size: 3.5em; font-weight: bold;">{person['신규']}</h1>
                <p style="margin: 10px 0 0 0; color: white; font-size: 1.3em; font-weight: 600;">신규/디벨롭</p>
                <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.9); font-size: 1em;">총 {person['총제작량']}개 제작</p>
            </div>
            """, unsafe_allow_html=True)
            
            # 기타 유형들
            st.markdown(f"""
            <div style="
                background: #f8f9fa;
                padding: 20px;
                border-left: 5px solid #6c757d;
            ">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                    <div style="background: white; padding: 10px; border-radius: 5px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #4A90E2;">{person['베리']}</div>
                        <div style="font-size: 0.9em; color: #6c757d;">베리</div>
                    </div>
                    <div style="background: white; padding: 10px; border-radius: 5px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #4A90E2;">{person['리사이징']}</div>
                        <div style="font-size: 0.9em; color: #6c757d;">리사이징</div>
                    </div>
                    <div style="background: white; padding: 10px; border-radius: 5px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #4A90E2;">{person['지면확장']}</div>
                        <div style="font-size: 0.9em; color: #6c757d;">지면확장</div>
                    </div>
                    <div style="background: white; padding: 10px; border-radius: 5px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #4A90E2;">{person['AI']}</div>
                        <div style="font-size: 0.9em; color: #6c757d;">AI</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 담당 브랜드
            brands_text = ", ".join(person['브랜드목록'])
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
                padding: 20px;
                border-radius: 0 0 10px 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="text-align: center; margin-bottom: 10px;">
                    <span style="font-size: 2.5em; font-weight: bold; color: #2c3e50;">{person['브랜드수']}</span>
                    <span style="font-size: 1.2em; color: #34495e; margin-left: 10px;">담당 브랜드</span>
                </div>
                <div style="font-size: 0.9em; color: #555; text-align: center; line-height: 1.6;">
                    {brands_text}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
    
    # 영상 디자이너
    st.markdown("---")
    st.markdown("### 🎬 영상 디자이너")
    video_stats = []
    for designer in VIDEO_DESIGNERS:
        if designer in df_filtered['제작자_채움'].values:
            video_stats.append(calculate_person_stats(designer))
    
    video_stats = sorted(video_stats, key=lambda x: x['신규'], reverse=True)
    
    cols = st.columns(3)
    for i, person in enumerate(video_stats):
        with cols[i % 3]:
            # 헤더
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #4A90E2 0%, #357ABD 100%);
                padding: 15px;
                border-radius: 10px 10px 0 0;
                color: white;
                text-align: center;
            ">
                <h3 style="margin: 0; color: white;">{person['이름']}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # 신규/디벨롭 + 총제작량
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #E67E22 0%, #D35400 100%);
                padding: 30px 20px;
                text-align: center;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <h1 style="margin: 0; color: white; font-size: 3.5em; font-weight: bold;">{person['신규']}</h1>
                <p style="margin: 10px 0 0 0; color: white; font-size: 1.3em; font-weight: 600;">신규/디벨롭</p>
                <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.9); font-size: 1em;">총 {person['총제작량']}개 제작</p>
            </div>
            """, unsafe_allow_html=True)
            
            # 기타 유형들
            st.markdown(f"""
            <div style="
                background: #f8f9fa;
                padding: 20px;
                border-left: 5px solid #6c757d;
            ">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                    <div style="background: white; padding: 10px; border-radius: 5px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #4A90E2;">{person['베리']}</div>
                        <div style="font-size: 0.9em; color: #6c757d;">베리</div>
                    </div>
                    <div style="background: white; padding: 10px; border-radius: 5px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #4A90E2;">{person['리사이징']}</div>
                        <div style="font-size: 0.9em; color: #6c757d;">리사이징</div>
                    </div>
                    <div style="background: white; padding: 10px; border-radius: 5px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #4A90E2;">{person['지면확장']}</div>
                        <div style="font-size: 0.9em; color: #6c757d;">지면확장</div>
                    </div>
                    <div style="background: white; padding: 10px; border-radius: 5px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #4A90E2;">{person['AI']}</div>
                        <div style="font-size: 0.9em; color: #6c757d;">AI</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 담당 브랜드
            brands_text = ", ".join(person['브랜드목록'])
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
                padding: 20px;
                border-radius: 0 0 10px 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="text-align: center; margin-bottom: 10px;">
                    <span style="font-size: 2.5em; font-weight: bold; color: #2c3e50;">{person['브랜드수']}</span>
                    <span style="font-size: 1.2em; color: #34495e; margin-left: 10px;">담당 브랜드</span>
                </div>
                <div style="font-size: 0.9em; color: #555; text-align: center; line-height: 1.6;">
                    {brands_text}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)

except Exception as e:
    st.error("❌ 데이터를 불러올 수 없습니다.")
    st.error(f"오류: {str(e)}")
    st.info("관리자에게 문의하세요.")
