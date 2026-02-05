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

# 디자이너 분류 (3팀 전용)
TEAM_3_IMAGE_DESIGNERS = ["박유정", "권지연", "안서현", "도혜진", "김성웅"]
TEAM_3_VIDEO_DESIGNERS = ["은누리", "박시은", "이재호", "이현성"]

# 나중에 다른 팀 추가 시 여기 추가
TEAM_DESIGNERS = {
    "3팀": {
        "image": TEAM_3_IMAGE_DESIGNERS,
        "video": TEAM_3_VIDEO_DESIGNERS
    },
    # "1팀": {"image": [...], "video": [...]},  # 나중에 추가
}

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
    
    # 팀 선택 (사이드바)
    st.sidebar.title("⚙️ 설정")
    selected_team = st.sidebar.selectbox(
        "팀 선택",
        options=["1팀", "2팀", "3팀", "4팀", "5팀", "6팀"],
        index=2  # 기본: 3팀
    )
    
    sheet = client.open_by_url(sheet_url)
    
    # 선택한 팀의 시트 읽기
    try:
        worksheet = sheet.worksheet(selected_team)
    except:
        st.error(f"❌ '{selected_team}' 시트를 찾을 수 없습니다. 첫 번째 시트를 사용합니다.")
        worksheet = sheet.get_worksheet(0)
    
    # 모든 데이터 가져오기
    all_data = worksheet.get_all_values()
    
    # 1행을 헤더로 사용
    headers = all_data[0]
    data_rows = all_data[1:]
    
    # DataFrame 생성
    df = pd.DataFrame(data_rows, columns=headers)
    
    # 빈 컬럼명 제거
    df = df.loc[:, df.columns != '']
    
    # 병합 셀 처리: 날짜와 제작자 빈칸 채우기
    df['날짜'] = df['날짜'].replace('', None)
    df['날짜'] = df['날짜'].fillna(method='ffill')
    
    df['제작자'] = df['제작자'].replace('', None)
    df['제작자'] = df['제작자'].fillna(method='ffill')
    
    # 데이터 전처리
    # 1. 날짜가 비어있지 않은 행만 (ffill 이후)
    df = df[df['날짜'].notna()]
    df = df[df['날짜'].astype(str).str.strip() != '']
    
    # 2. 날짜 형식 변환 시도 (실패하면 제외)
    df['날짜_변환'] = pd.to_datetime(
        df['날짜'].astype(str).str.replace(' ', '').str.replace('.', '-'), 
        errors='coerce'
    )
    
    # 3. 날짜 변환 성공한 행만 (유효한 날짜 형식만)
    df = df[df['날짜_변환'].notna()].copy()
    
    st.write(f"✅ 유효한 데이터 {len(df)}개 인식")
    
    # 선택된 팀의 디자이너 가져오기
    if selected_team in TEAM_DESIGNERS:
        IMAGE_DESIGNERS = TEAM_DESIGNERS[selected_team]["image"]
        VIDEO_DESIGNERS = TEAM_DESIGNERS[selected_team]["video"]
    else:
        # 팀 정보 없으면 데이터에서 자동 감지
        st.warning(f"⚠️ {selected_team} 디자이너 정보가 없습니다. 전체 제작자를 표시합니다.")
        all_designers = df['제작자'].unique().tolist()
        IMAGE_DESIGNERS = all_designers
        VIDEO_DESIGNERS = []
    
    # 제작자는 이미 ffill로 채워졌으니 그냥 사용
    df['제작자_채움'] = df['제작자']
    
    # 콘텐츠 수 처리
    df['콘텐츠 수'] = pd.to_numeric(df['콘텐츠 수'], errors='coerce').fillna(0).astype(int)
    
    # 콘텐츠 유형 처리
    df = df[df['콘텐츠 유형'].notna()].copy()
    df = df[df['콘텐츠 유형'].astype(str).str.strip() != ''].copy()
    
    df['주차'] = df['날짜_변환'].dt.strftime('%Y-W%U')
    df['주차_정렬용'] = df['날짜_변환'].dt.to_period('W')
    df['월'] = df['날짜_변환'].dt.to_period('M')
    
    df['신규여부'] = df['콘텐츠 유형'].str.contains('신규', case=False, na=False) | df['콘텐츠 유형'].str.contains('ai', case=False, na=False)
    
    # 콘텐츠 유형 간소화
    def simplify_content_type(content_type):
        if pd.isna(content_type) or content_type == '':
            return '기타'
        content_type = str(content_type).lower()
        if '신규' in content_type or '디벨롭' in content_type or 'ai' in content_type:
            return '신규/디벨롭'
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
    
    # 이미지/영상 디자이너 데이터 분리
    df_image = df[df['제작자_채움'].isin(IMAGE_DESIGNERS)].copy()
    df_video = df[df['제작자_채움'].isin(VIDEO_DESIGNERS)].copy()
    
    # 필터 섹션
    st.markdown("<h3 style='font-size: 24px;'>🔍 기간 선택</h3>", unsafe_allow_html=True)
    
    # 현재 연도/월 가져오기
    current_date = df['날짜_변환'].max()
    current_year = current_date.year
    current_month = current_date.month
    
    # 사용 가능한 연도/월 목록
    available_years = sorted(df['날짜_변환'].dt.year.unique())
    available_months = list(range(1, 13))
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        selected_year = st.selectbox(
            "📅 연도",
            options=available_years,
            index=available_years.index(current_year) if current_year in available_years else 0
        )
    with col_f2:
        selected_month = st.selectbox(
            "📅 월",
            options=available_months,
            format_func=lambda x: f"{x}월",
            index=current_month - 1
        )
    
    st.markdown("---")
    
    # 그래프 1: 월별 제작량
    st.markdown(f"<h2 style='text-align: center; font-size: 32px;'>{selected_year-2000}년 {selected_month}월</h2>", unsafe_allow_html=True)
    
    # 이미지 디자이너 데이터
    monthly_image = df_image.groupby('월')['콘텐츠 수'].sum().reset_index()
    monthly_image.columns = ['월', '총제작량']
    monthly_image['월_표시'] = monthly_image['월'].astype(str)
    monthly_image = monthly_image.sort_values('월')
    
    monthly_image_new = df_image[df_image['신규여부'] == True].groupby('월')['콘텐츠 수'].sum().reset_index()
    monthly_image_new.columns = ['월', '신규제작량']
    
    monthly_image_stats = pd.merge(monthly_image, monthly_image_new, on='월', how='left').fillna(0)
    
    # 영상 디자이너 데이터
    monthly_video = df_video.groupby('월')['콘텐츠 수'].sum().reset_index()
    monthly_video.columns = ['월', '총제작량']
    monthly_video['월_표시'] = monthly_video['월'].astype(str)
    monthly_video = monthly_video.sort_values('월')
    
    monthly_video_new = df_video[df_video['신규여부'] == True].groupby('월')['콘텐츠 수'].sum().reset_index()
    monthly_video_new.columns = ['월', '신규제작량']
    
    monthly_video_stats = pd.merge(monthly_video, monthly_video_new, on='월', how='left').fillna(0)
    
    # 합쳐진 그래프
    fig_monthly = go.Figure()
    
    # 이미지 디자이너
    fig_monthly.add_trace(go.Scatter(
        x=monthly_image_stats['월_표시'],
        y=monthly_image_stats['총제작량'],
        mode='lines+markers',
        name='🎨 이미지 총제작량',
        line=dict(color='#4A90E2', width=3),
        marker=dict(size=10)
    ))
    fig_monthly.add_trace(go.Scatter(
        x=monthly_image_stats['월_표시'],
        y=monthly_image_stats['신규제작량'],
        mode='lines+markers',
        name='🎨 이미지 신규',
        line=dict(color='#E67E22', width=3),
        marker=dict(size=10)
    ))
    
    # 영상 디자이너
    fig_monthly.add_trace(go.Scatter(
        x=monthly_video_stats['월_표시'],
        y=monthly_video_stats['총제작량'],
        mode='lines+markers',
        name='🎬 영상 총제작량',
        line=dict(color='#4A90E2', width=3, dash='dash'),
        marker=dict(size=10, symbol='square')
    ))
    fig_monthly.add_trace(go.Scatter(
        x=monthly_video_stats['월_표시'],
        y=monthly_video_stats['신규제작량'],
        mode='lines+markers',
        name='🎬 영상 신규',
        line=dict(color='#E67E22', width=3, dash='dash'),
        marker=dict(size=10, symbol='square')
    ))
    
    fig_monthly.update_layout(
        height=450,
        xaxis_title="월",
        yaxis_title="제작량 (개)",
        yaxis=dict(rangemode='tozero'),
        hovermode='x unified',
        font=dict(size=16),
        xaxis=dict(title_font=dict(size=18)),
        yaxis=dict(title_font=dict(size=18)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14))
    )
    st.plotly_chart(fig_monthly, use_container_width=True)
    
    st.markdown("---")
    
    # 그래프 2: 주차별 제작량
    available_weeks = sorted(df['주차_정렬용'].unique(), reverse=True)
    current_week = available_weeks[0] if len(available_weeks) > 0 else None
    
    # 현재 주차 계산
    if current_week:
        week_num = current_week.start_time.isocalendar()[1]
        week_month = current_week.start_time.month
        st.markdown(f"<h2 style='text-align: center; font-size: 32px;'>{week_month}월 {week_num}주차</h2>", unsafe_allow_html=True)
    else:
        st.markdown("<h2 style='text-align: center; font-size: 32px;'>주차별 제작량</h2>", unsafe_allow_html=True)
    
    recent_8_weeks = available_weeks[:min(8, len(available_weeks))]
    
    # 이미지 디자이너 데이터
    week_image = df_image[df_image['주차_정렬용'].isin(recent_8_weeks)]
    
    weekly_image = week_image.groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
    weekly_image.columns = ['주차', '총제작량']
    weekly_image['주차_표시'] = weekly_image['주차'].astype(str).str[-2:] + '주차'
    weekly_image = weekly_image.sort_values('주차')
    
    weekly_image_new = week_image[week_image['신규여부'] == True].groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
    weekly_image_new.columns = ['주차', '신규제작량']
    
    weekly_image_stats = pd.merge(weekly_image, weekly_image_new, on='주차', how='left').fillna(0)
    
    # 영상 디자이너 데이터
    week_video = df_video[df_video['주차_정렬용'].isin(recent_8_weeks)]
    
    weekly_video = week_video.groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
    weekly_video.columns = ['주차', '총제작량']
    weekly_video['주차_표시'] = weekly_video['주차'].astype(str).str[-2:] + '주차'
    weekly_video = weekly_video.sort_values('주차')
    
    weekly_video_new = week_video[week_video['신규여부'] == True].groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
    weekly_video_new.columns = ['주차', '신규제작량']
    
    weekly_video_stats = pd.merge(weekly_video, weekly_video_new, on='주차', how='left').fillna(0)
    
    # 합쳐진 그래프
    fig_weekly = go.Figure()
    
    # 이미지 디자이너
    fig_weekly.add_trace(go.Scatter(
        x=weekly_image_stats['주차_표시'],
        y=weekly_image_stats['총제작량'],
        mode='lines+markers',
        name='🎨 이미지 총제작량',
        line=dict(color='#4A90E2', width=3),
        marker=dict(size=10)
    ))
    fig_weekly.add_trace(go.Scatter(
        x=weekly_image_stats['주차_표시'],
        y=weekly_image_stats['신규제작량'],
        mode='lines+markers',
        name='🎨 이미지 신규',
        line=dict(color='#E67E22', width=3),
        marker=dict(size=10)
    ))
    
    # 영상 디자이너
    fig_weekly.add_trace(go.Scatter(
        x=weekly_video_stats['주차_표시'],
        y=weekly_video_stats['총제작량'],
        mode='lines+markers',
        name='🎬 영상 총제작량',
        line=dict(color='#4A90E2', width=3, dash='dash'),
        marker=dict(size=10, symbol='square')
    ))
    fig_weekly.add_trace(go.Scatter(
        x=weekly_video_stats['주차_표시'],
        y=weekly_video_stats['신규제작량'],
        mode='lines+markers',
        name='🎬 영상 신규',
        line=dict(color='#E67E22', width=3, dash='dash'),
        marker=dict(size=10, symbol='square')
    ))
    
    fig_weekly.update_layout(
        height=450,
        xaxis_title="주차",
        yaxis_title="제작량 (개)",
        yaxis=dict(rangemode='tozero'),
        hovermode='x unified',
        font=dict(size=16),
        xaxis=dict(title_font=dict(size=18)),
        yaxis=dict(title_font=dict(size=18)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14))
    )
    st.plotly_chart(fig_weekly, use_container_width=True)
    
    st.markdown("---")
    
    # 주차 선택 (개인 카드용)
    week_options = ['전체'] + [str(w) for w in available_weeks]
    selected_week = st.selectbox("📅 주차 선택 (개인 상세)", options=week_options, index=1)
    
    # ============================================
    # 사람별 카드 + 개인 그래프
    # ============================================
    st.markdown("---")
    st.markdown("## 👥 사람별 제작 현황")
    
    # 필터링
    if selected_week != '전체':
        selected_week_period = pd.Period(selected_week, freq='W')
        df_filtered = df[df['주차_정렬용'] == selected_week_period]
        
        # 전주 데이터도 가져오기
        all_weeks = sorted(df['주차_정렬용'].unique(), reverse=True)
        current_week_idx = all_weeks.index(selected_week_period) if selected_week_period in all_weeks else -1
        
        if current_week_idx >= 0 and current_week_idx < len(all_weeks) - 1:
            prev_week_period = all_weeks[current_week_idx + 1]
            df_prev_week = df[df['주차_정렬용'] == prev_week_period]
        else:
            df_prev_week = pd.DataFrame()  # 전주 데이터 없음
    else:
        df_filtered = df
        df_prev_week = pd.DataFrame()
    
    # 사람별 통계 계산
    def calculate_person_stats(person_name):
        person_df = df_filtered[df_filtered['제작자_채움'] == person_name]
        
        # 유형별 집계
        type_counts = person_df.groupby('콘텐츠유형_간소화')['콘텐츠 수'].sum().to_dict()
        
        # AI 개수 별도 계산 (원본 데이터에서)
        ai_count = person_df[person_df['콘텐츠 유형'].str.contains('ai', case=False, na=False)]['콘텐츠 수'].sum()
        
        # 브랜드 목록
        brands = person_df['브랜드명'].unique().tolist()
        
        # 총 제작량
        total = person_df['콘텐츠 수'].sum()
        
        return {
            '이름': person_name,
            '총제작량': int(total),
            '신규': int(type_counts.get('신규/디벨롭', 0)),  # AI 포함됨
            '베리': int(type_counts.get('베리', 0)),
            '리사이징': int(type_counts.get('리사이징', 0)),
            '지면확장': int(type_counts.get('지면확장', 0)),
            'AI': int(ai_count),  # 별도 표시
            '브랜드수': len(brands),
            '브랜드목록': ", ".join(brands) if brands else "-"
        }
    
    # 날짜 정보 표시 함수
    def render_date_info(person_current, person_prev):
        if len(person_current) > 0:
            current_dates = sorted(person_current[person_current['날짜_변환'].dt.dayofweek < 5]['날짜_변환'].unique())
            current_dates_str = " / ".join([d.strftime('%m/%d') for d in current_dates])
        else:
            current_dates_str = "-"
        
        if len(person_prev) > 0:
            prev_dates = sorted(person_prev[person_prev['날짜_변환'].dt.dayofweek < 5]['날짜_변환'].unique())
            prev_dates_str = " / ".join([d.strftime('%m/%d') for d in prev_dates])
        else:
            prev_dates_str = "-"
        
        st.markdown(f"""
        <div style="
            background: #F8F9FA;
            padding: 12px;
            border-radius: 8px;
            font-size: 0.85em;
            color: #555;
            margin-top: -10px;
        ">
            <div style="margin-bottom: 5px;">
                <strong style="color: #E67E22;">📅 전주:</strong> {prev_dates_str}
            </div>
            <div>
                <strong style="color: #4A90E2;">📅 금주:</strong> {current_dates_str}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # 개인 그래프 생성 함수
    def create_person_graph(person_name, current_week_data, prev_week_data):
        # 기본 요일 템플릿 생성 (월~금)
        weekdays_template = pd.DataFrame({
            '요일': [0, 1, 2, 3, 4],
            '요일_표시': ['월', '화', '수', '목', '금']
        })
        
        # 이번주 일별 데이터 (평일만)
        current_week_data = current_week_data[current_week_data['날짜_변환'].dt.dayofweek < 5]
        
        if len(current_week_data) > 0:
            current_daily = current_week_data.groupby('날짜_변환')['콘텐츠 수'].sum().reset_index()
            current_daily.columns = ['날짜', '총제작량']
            current_daily['요일'] = current_daily['날짜'].dt.dayofweek
            current_daily['날짜_표시'] = current_daily['날짜'].dt.strftime('%m/%d')
            
            current_new = current_week_data[current_week_data['신규여부'] == True].groupby('날짜_변환')['콘텐츠 수'].sum().reset_index()
            current_new.columns = ['날짜', '신규제작량']
            current_new['요일'] = pd.to_datetime(current_new['날짜']).dt.dayofweek
            
            current_stats = pd.merge(current_daily, current_new[['요일', '신규제작량']], on='요일', how='left').fillna(0)
            
            # 템플릿과 병합하여 빈 요일 채우기
            current_stats = pd.merge(weekdays_template, current_stats[['요일', '총제작량', '신규제작량', '날짜_표시']], on='요일', how='left').fillna(0)
        else:
            current_stats = weekdays_template.copy()
            current_stats['총제작량'] = 0
            current_stats['신규제작량'] = 0
            current_stats['날짜_표시'] = '-'
        
        # 전주 일별 데이터 (평일만)
        if len(prev_week_data) > 0:
            prev_week_data = prev_week_data[prev_week_data['날짜_변환'].dt.dayofweek < 5]
            
            prev_daily = prev_week_data.groupby('날짜_변환')['콘텐츠 수'].sum().reset_index()
            prev_daily.columns = ['날짜', '총제작량']
            prev_daily['요일'] = prev_daily['날짜'].dt.dayofweek
            prev_daily['날짜_표시'] = prev_daily['날짜'].dt.strftime('%m/%d')
            
            prev_new = prev_week_data[prev_week_data['신규여부'] == True].groupby('날짜_변환')['콘텐츠 수'].sum().reset_index()
            prev_new.columns = ['날짜', '신규제작량']
            prev_new['요일'] = pd.to_datetime(prev_new['날짜']).dt.dayofweek
            
            prev_stats = pd.merge(prev_daily, prev_new[['요일', '신규제작량']], on='요일', how='left').fillna(0)
            
            # 템플릿과 병합하여 빈 요일 채우기
            prev_stats = pd.merge(weekdays_template, prev_stats[['요일', '총제작량', '신규제작량', '날짜_표시']], on='요일', how='left').fillna(0)
        else:
            prev_stats = pd.DataFrame()
        
        # 그래프 생성
        fig = go.Figure()
        
        # 전주 데이터 (40% 투명, 점선)
        if len(prev_stats) > 0:
            fig.add_trace(go.Scatter(
                x=prev_stats['요일_표시'],
                y=prev_stats['총제작량'],
                mode='lines+markers',
                name='전주 총제작량',
                line=dict(color='#4A90E2', width=2, dash='dot'),
                marker=dict(size=6),
                opacity=0.4,
                text=prev_stats['날짜_표시'],
                hovertemplate='<b>전주 총제작량</b><br>%{x}<br>%{text}<br>%{y}개<extra></extra>'
            ))
            
            fig.add_trace(go.Scatter(
                x=prev_stats['요일_표시'],
                y=prev_stats['신규제작량'],
                mode='lines+markers',
                name='전주 신규',
                line=dict(color='#E67E22', width=2, dash='dot'),
                marker=dict(size=6),
                opacity=0.4,
                text=prev_stats['날짜_표시'],
                hovertemplate='<b>전주 신규</b><br>%{x}<br>%{text}<br>%{y}개<extra></extra>'
            ))
        
        # 이번주 데이터 (진하게, 실선)
        fig.add_trace(go.Scatter(
            x=current_stats['요일_표시'],
            y=current_stats['총제작량'],
            mode='lines+markers',
            name='이번주 총제작량',
            line=dict(color='#4A90E2', width=3),
            marker=dict(size=8),
            text=current_stats['날짜_표시'],
            hovertemplate='<b>이번주 총제작량</b><br>%{x}<br>%{text}<br>%{y}개<extra></extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=current_stats['요일_표시'],
            y=current_stats['신규제작량'],
            mode='lines+markers',
            name='이번주 신규',
            line=dict(color='#E67E22', width=3),
            marker=dict(size=8),
            text=current_stats['날짜_표시'],
            hovertemplate='<b>이번주 신규</b><br>%{x}<br>%{text}<br>%{y}개<extra></extra>'
        ))
        
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title="요일",
            yaxis_title="제작량",
            yaxis=dict(rangemode='tozero'),  # y축 0부터 시작
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10)
            )
        )
        
        return fig
    
    # 카드 렌더링 함수
    def render_person_card(person):
        st.markdown(f"""
        <div style="
            border: 3px solid #FFE8F0;
            border-radius: 15px;
            overflow: hidden;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        ">
            <div style="background: #FFE8F0; padding: 15px; text-align: center;">
                <h3 style="margin: 0; color: #2C3E50; font-weight: 600;">{person['이름']}</h3>
            </div>
            <div style="background: #F5F7F9; padding: 20px 15px; display: grid; grid-template-columns: 1fr 1fr; gap: 15px; text-align: center;">
                <div>
                    <div style="font-size: 0.85em; color: #888; margin-bottom: 5px;">신규/디벨롭</div>
                    <div style="font-size: 2.5em; font-weight: bold; color: #2C3E50; line-height: 1;">{person['신규']}</div>
                </div>
                <div>
                    <div style="font-size: 0.85em; color: #888; margin-bottom: 5px;">총 제작량</div>
                    <div style="font-size: 2.5em; font-weight: bold; color: #2C3E50; line-height: 1;">{person['총제작량']}</div>
                </div>
            </div>
            <div style="padding: 15px; background: #FAFBFC; display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                <div style="background: white; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #E1E8ED;">
                    <div style="font-size: 1.5em; font-weight: bold; color: #5DADE2;">{person['베리']}</div>
                    <div style="font-size: 0.8em; color: #95A5A6;">베리</div>
                </div>
                <div style="background: white; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #E1E8ED;">
                    <div style="font-size: 1.5em; font-weight: bold; color: #5DADE2;">{person['리사이징']}</div>
                    <div style="font-size: 0.8em; color: #95A5A6;">리사이징</div>
                </div>
                <div style="background: white; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #E1E8ED;">
                    <div style="font-size: 1.5em; font-weight: bold; color: #5DADE2;">{person['지면확장']}</div>
                    <div style="font-size: 0.8em; color: #95A5A6;">지면확장</div>
                </div>
                <div style="background: white; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #E1E8ED;">
                    <div style="font-size: 1.5em; font-weight: bold; color: #5DADE2;">{person['AI']}</div>
                    <div style="font-size: 0.8em; color: #95A5A6;">AI</div>
                </div>
            </div>
            <div style="background: linear-gradient(135deg, #D4F1F4 0%, #FFE8F5 100%); padding: 15px; text-align: center;">
                <div style="margin-bottom: 8px;">
                    <span style="font-size: 2em; font-weight: bold; color: #2C3E50;">{person['브랜드수']}</span>
                    <span style="font-size: 0.9em; color: #5A6C7D; margin-left: 8px;">담당 브랜드</span>
                </div>
                <div style="font-size: 0.8em; color: #7B8A97; line-height: 1.4;">{person['브랜드목록']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # 이미지 디자이너
    st.markdown("### 🎨 이미지 디자이너")
    
    if selected_week == '전체':
        st.info("특정 주차를 선택하면 개인별 상세 데이터가 표시됩니다.")
    else:
        image_stats = []
        for designer in IMAGE_DESIGNERS:
            if designer in df_filtered['제작자_채움'].values:
                image_stats.append(calculate_person_stats(designer))
        
        image_stats = sorted(image_stats, key=lambda x: x['신규'], reverse=True)
        
        for person in image_stats:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                render_person_card(person)
            
            with col2:
                # 개인 데이터 필터링
                person_current = df_filtered[df_filtered['제작자_채움'] == person['이름']]
                person_prev = df_prev_week[df_prev_week['제작자_채움'] == person['이름']] if len(df_prev_week) > 0 else pd.DataFrame()
                
                # 그래프 생성
                fig = create_person_graph(person['이름'], person_current, person_prev)
                st.plotly_chart(fig, use_container_width=True)
                
                # 날짜 정보 표시
                render_date_info(person_current, person_prev)
            
            st.markdown("---")
    
    # 영상 디자이너
    st.markdown("### 🎬 영상 디자이너")
    
    if selected_week == '전체':
        st.info("특정 주차를 선택하면 개인별 상세 데이터가 표시됩니다.")
    else:
        video_stats = []
        for designer in VIDEO_DESIGNERS:
            if designer in df_filtered['제작자_채움'].values:
                video_stats.append(calculate_person_stats(designer))
        
        video_stats = sorted(video_stats, key=lambda x: x['신규'], reverse=True)
        
        for person in video_stats:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                render_person_card(person)
            
            with col2:
                # 개인 데이터 필터링
                person_current = df_filtered[df_filtered['제작자_채움'] == person['이름']]
                person_prev = df_prev_week[df_prev_week['제작자_채움'] == person['이름']] if len(df_prev_week) > 0 else pd.DataFrame()
                
                # 그래프 생성
                fig = create_person_graph(person['이름'], person_current, person_prev)
                st.plotly_chart(fig, use_container_width=True)
                
                # 날짜 정보 표시
                render_date_info(person_current, person_prev)
            
            st.markdown("---")

except Exception as e:
    st.error("❌ 데이터를 불러올 수 없습니다.")
    st.error(f"오류: {str(e)}")
    
    # 디버그 정보
    import traceback
    st.code(traceback.format_exc())
    
    st.info("관리자에게 문의하세요.")
