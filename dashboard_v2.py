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
        if '신규' in content_type or '디벨롭' in content_type or 'ai' in content_type or '상세페이지' in content_type or '상세' in content_type:
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
    
    monthly_image_new = df_image[df_image['신규여부'] == True].groupby('월')['콘텐츠 수'].sum().reset_index()
    monthly_image_new.columns = ['월', '신규제작량']
    
    monthly_image_stats = pd.merge(monthly_image, monthly_image_new, on='월', how='left').fillna(0)
    
    # 영상 디자이너 데이터
    monthly_video = df_video.groupby('월')['콘텐츠 수'].sum().reset_index()
    monthly_video.columns = ['월', '총제작량']
    
    monthly_video_new = df_video[df_video['신규여부'] == True].groupby('월')['콘텐츠 수'].sum().reset_index()
    monthly_video_new.columns = ['월', '신규제작량']
    
    monthly_video_stats = pd.merge(monthly_video, monthly_video_new, on='월', how='left').fillna(0)
    
    # 최소 5개월 표시를 위해 빈 월 추가
    # 선택된 월을 기준으로 이전 4개월 + 선택 월 = 5개월 표시
    selected_period = pd.Period(f"{selected_year}-{selected_month:02d}", freq='M')
    
    # 선택 월 기준 이전 4개월 생성
    months_to_show = []
    for i in range(4, -1, -1):  # 4, 3, 2, 1, 0
        month_back = selected_month - i
        year_adjusted = selected_year
        
        if month_back <= 0:
            month_back += 12
            year_adjusted -= 1
        
        months_to_show.append(pd.Period(f"{year_adjusted}-{month_back:02d}", freq='M'))
    
    # 빈 데이터프레임 생성
    full_months_df = pd.DataFrame({'월': months_to_show})
    
    # 안전하게 병합 - 이미지
    monthly_image_full = pd.merge(full_months_df, monthly_image_stats, on='월', how='left')
    monthly_image_full['총제작량'] = monthly_image_full['총제작량'].fillna(0)
    monthly_image_full['신규제작량'] = monthly_image_full['신규제작량'].fillna(0)
    monthly_image_full['월_표시'] = monthly_image_full['월'].apply(lambda x: f"{x.year}년 {x.month}월")
    monthly_image_full = monthly_image_full.sort_values('월')
    
    # 안전하게 병합 - 영상
    monthly_video_full = pd.merge(full_months_df, monthly_video_stats, on='월', how='left')
    monthly_video_full['총제작량'] = monthly_video_full['총제작량'].fillna(0)
    monthly_video_full['신규제작량'] = monthly_video_full['신규제작량'].fillna(0)
    monthly_video_full['월_표시'] = monthly_video_full['월'].apply(lambda x: f"{x.year}년 {x.month}월")
    monthly_video_full = monthly_video_full.sort_values('월')
    
    # 2열로 그래프 배치
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("<h3 style='font-size: 20px; text-align: center;'>🎨 이미지 디자이너</h3>", unsafe_allow_html=True)
        
        fig_monthly_image = go.Figure()
        fig_monthly_image.add_trace(go.Scatter(
            x=monthly_image_full['월_표시'],
            y=monthly_image_full['총제작량'],
            mode='lines+markers',
            name='총 제작량',
            line=dict(color='#4A90E2', width=3),
            marker=dict(size=10)
        ))
        fig_monthly_image.add_trace(go.Scatter(
            x=monthly_image_full['월_표시'],
            y=monthly_image_full['신규제작량'],
            mode='lines+markers',
            name='신규 제작량',
            line=dict(color='#E67E22', width=3),
            marker=dict(size=10)
        ))
        fig_monthly_image.update_layout(
            height=400,
            xaxis_title="월",
            yaxis_title="제작량 (개)",
            hovermode='x unified',
            font=dict(size=16),
            xaxis=dict(title_font=dict(size=18)),
            yaxis=dict(rangemode='tozero', title_font=dict(size=18)),
            legend=dict(font=dict(size=14))
        )
        st.plotly_chart(fig_monthly_image, use_container_width=True)
    
    with col2:
        st.markdown("<h3 style='font-size: 20px; text-align: center;'>🎬 영상 디자이너</h3>", unsafe_allow_html=True)
        
        fig_monthly_video = go.Figure()
        fig_monthly_video.add_trace(go.Scatter(
            x=monthly_video_full['월_표시'],
            y=monthly_video_full['총제작량'],
            mode='lines+markers',
            name='총 제작량',
            line=dict(color='#4A90E2', width=3),
            marker=dict(size=10)
        ))
        fig_monthly_video.add_trace(go.Scatter(
            x=monthly_video_full['월_표시'],
            y=monthly_video_full['신규제작량'],
            mode='lines+markers',
            name='신규 제작량',
            line=dict(color='#E67E22', width=3),
            marker=dict(size=10)
        ))
        fig_monthly_video.update_layout(
            height=400,
            xaxis_title="월",
            yaxis_title="제작량 (개)",
            hovermode='x unified',
            font=dict(size=16),
            xaxis=dict(title_font=dict(size=18)),
            yaxis=dict(rangemode='tozero', title_font=dict(size=18)),
            legend=dict(font=dict(size=14))
        )
        st.plotly_chart(fig_monthly_video, use_container_width=True)
    
    st.markdown("---")
    

    # 그래프 2: 주차별 제작량 (선택된 월 기준)
    # 선택된 월의 주차만 필터링
    df_month_filtered = df[(df['날짜_변환'].dt.year == selected_year) & (df['날짜_변환'].dt.month == selected_month)]
    df_image_month = df_image[(df_image['날짜_변환'].dt.year == selected_year) & (df_image['날짜_변환'].dt.month == selected_month)]
    df_video_month = df_video[(df_video['날짜_변환'].dt.year == selected_year) & (df_video['날짜_변환'].dt.month == selected_month)]
    
    # 해당 월의 주차 목록
    month_weeks = sorted(df_month_filtered['주차_정렬용'].unique())
    
    # 최소 5주차 표시 (데이터 없어도 표시)
    max_weeks = max(5, len(month_weeks)) if len(month_weeks) > 0 else 5
    
    # 빈 주차를 위한 전체 주차 레이블
    all_week_labels = [f"{i}주차" for i in range(1, max_weeks + 1)]
    
    # 해당 월의 몇 주차인지 계산 (1주차, 2주차, 3주차...)
    week_labels = {}
    for idx in range(1, max_weeks + 1):
        if idx <= len(month_weeks):
            week_labels[month_weeks[idx-1]] = f"{idx}주차"
    
    # 타이틀
    current_week_idx = len(month_weeks) if len(month_weeks) > 0 else 0
    st.markdown(f"<h2 style='text-align: center; font-size: 32px;'>{selected_month}월 {current_week_idx}주차</h2>", unsafe_allow_html=True)
    
    # 이미지 디자이너 주차별 집계
    weekly_image = df_image_month.groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
    weekly_image.columns = ['주차', '총제작량']
    
    weekly_image_new = df_image_month[df_image_month['신규여부'] == True].groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
    weekly_image_new.columns = ['주차', '신규제작량']
    
    weekly_image_stats = pd.merge(weekly_image, weekly_image_new, on='주차', how='left').fillna(0)
    
    # 빈 주차 추가
    full_weeks_image = pd.DataFrame({'주차_표시': all_week_labels})
    weekly_image_stats['주차_표시'] = weekly_image_stats['주차'].map(week_labels)
    weekly_image_stats = pd.merge(full_weeks_image, weekly_image_stats[['주차_표시', '총제작량', '신규제작량']], on='주차_표시', how='left').fillna(0)
    
    # 영상 디자이너 주차별 집계
    weekly_video = df_video_month.groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
    weekly_video.columns = ['주차', '총제작량']
    
    weekly_video_new = df_video_month[df_video_month['신규여부'] == True].groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
    weekly_video_new.columns = ['주차', '신규제작량']
    
    weekly_video_stats = pd.merge(weekly_video, weekly_video_new, on='주차', how='left').fillna(0)
    
    # 빈 주차 추가
    full_weeks_video = pd.DataFrame({'주차_표시': all_week_labels})
    weekly_video_stats['주차_표시'] = weekly_video_stats['주차'].map(week_labels)
    weekly_video_stats = pd.merge(full_weeks_video, weekly_video_stats[['주차_표시', '총제작량', '신규제작량']], on='주차_표시', how='left').fillna(0)
    
    # 2열로 그래프 배치
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("<h3 style='font-size: 20px; text-align: center;'>🎨 이미지 디자이너</h3>", unsafe_allow_html=True)
        
        fig_weekly_image = go.Figure()
        fig_weekly_image.add_trace(go.Scatter(
            x=weekly_image_stats['주차_표시'],
            y=weekly_image_stats['총제작량'],
            mode='lines+markers',
            name='총 제작량',
            line=dict(color='#4A90E2', width=3),
            marker=dict(size=10)
        ))
        fig_weekly_image.add_trace(go.Scatter(
            x=weekly_image_stats['주차_표시'],
            y=weekly_image_stats['신규제작량'],
            mode='lines+markers',
            name='신규 제작량',
            line=dict(color='#E67E22', width=3),
            marker=dict(size=10)
        ))
        fig_weekly_image.update_layout(
            height=400,
            xaxis_title="주차",
            yaxis_title="제작량 (개)",
            hovermode='x unified',
            font=dict(size=16),
            xaxis=dict(title_font=dict(size=18)),
            yaxis=dict(rangemode='tozero', title_font=dict(size=18)),
            legend=dict(font=dict(size=14))
        )
        st.plotly_chart(fig_weekly_image, use_container_width=True, key='weekly_image_chart')
    
    with col2:
        st.markdown("<h3 style='font-size: 20px; text-align: center;'>🎬 영상 디자이너</h3>", unsafe_allow_html=True)
        
        fig_weekly_video = go.Figure()
        fig_weekly_video.add_trace(go.Scatter(
            x=weekly_video_stats['주차_표시'],
            y=weekly_video_stats['총제작량'],
            mode='lines+markers',
            name='총 제작량',
            line=dict(color='#4A90E2', width=3),
            marker=dict(size=10)
        ))
        fig_weekly_video.add_trace(go.Scatter(
            x=weekly_video_stats['주차_표시'],
            y=weekly_video_stats['신규제작량'],
            mode='lines+markers',
            name='신규 제작량',
            line=dict(color='#E67E22', width=3),
            marker=dict(size=10)
        ))
        fig_weekly_video.update_layout(
            height=400,
            xaxis_title="주차",
            yaxis_title="제작량 (개)",
            hovermode='x unified',
            font=dict(size=16),
            xaxis=dict(title_font=dict(size=18)),
            yaxis=dict(rangemode='tozero', title_font=dict(size=18)),
            legend=dict(font=dict(size=14))
        )
        st.plotly_chart(fig_weekly_video, use_container_width=True, key='weekly_video_chart')
    
    st.markdown("---")
    
    # 월 선택 (개인 카드용)
    available_months_for_detail = sorted(df['월'].unique(), reverse=True)
    month_options_dict = {f"{m.year}년 {m.month}월": m for m in available_months_for_detail}
    month_options_display = ['전체'] + list(month_options_dict.keys())
    
    # 기본값: 최신 월
    selected_month_display = st.selectbox(
        "📅 월 선택 (개인 상세)",
        options=month_options_display,
        index=1
    )
    
    # 선택된 Period 가져오기
    if selected_month_display == '전체':
        selected_month_for_detail = '전체'
    else:
        selected_month_for_detail = month_options_dict[selected_month_display]
    
    # ============================================
    # 사람별 카드 + 개인 그래프
    # ============================================
    st.markdown("---")
    st.markdown("## 👥 사람별 제작 현황")
    
    # 필터링
    if selected_month_for_detail != '전체':
        selected_month_period = pd.Period(selected_month_for_detail, freq='M')
        df_filtered = df[df['월'] == selected_month_period]
        
        # 선택 월의 년도 전체 데이터
        selected_year = selected_month_period.year
        df_year = df[df['날짜_변환'].dt.year == selected_year]
    else:
        df_filtered = df
        df_year = df
    
    # 사람별 통계 계산
    def calculate_person_stats(person_name):
        person_df = df_filtered[df_filtered['제작자_채움'] == person_name]
        
        # 유형별 집계
        type_counts = person_df.groupby('콘텐츠유형_간소화')['콘텐츠 수'].sum().to_dict()
        
        # AI 개수 별도 계산 (원본 데이터에서)
        ai_count = person_df[person_df['콘텐츠 유형'].str.contains('ai', case=False, na=False)]['콘텐츠 수'].sum()
        
        # 상세페이지/배너 개수 별도 계산
        detail_banner_count = person_df[person_df['콘텐츠 유형'].str.contains('상세페이지|상세', case=False, na=False, regex=True)]['콘텐츠 수'].sum()
        
        # 브랜드 목록 (선택된 월에 진행한 브랜드만)
        # 컬럼명이 '브랜드', '브랜드명' 등 다양할 수 있으므로 확인
        brand_column = None
        for col in ['브랜드', '브랜드명', 'Brand', 'brand']:
            if col in person_df.columns:
                brand_column = col
                break
        
        if brand_column:
            brands = person_df[brand_column].dropna().unique().tolist()
            brands = [b for b in brands if str(b).strip() != '']
        else:
            brands = []
        
        # 총 제작량
        total = person_df['콘텐츠 수'].sum()
        
        return {
            '이름': person_name,
            '총제작량': int(total),
            '신규': int(type_counts.get('신규/디벨롭', 0)),  # AI, 상세페이지/배너 포함됨
            '베리': int(type_counts.get('베리', 0)),
            '리사이징': int(type_counts.get('리사이징', 0)),
            '지면확장': int(type_counts.get('지면확장', 0)),
            'AI': int(ai_count),  # 별도 표시
            '상세페이지/배너': int(detail_banner_count),  # 별도 표시
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
    
    # 개인 그래프 생성 함수 (선택 월 기준 5개월)
    def create_person_graph(person_name, person_year_data, selected_month_period):
        # 선택 월 기준 이전 4개월 포함 (총 5개월)
        selected_month_idx = selected_month_period.month
        selected_year = selected_month_period.year
        
        # 5개월 범위 생성 (선택 월 포함 이전 4개월)
        months_range = []
        for i in range(4, -1, -1):  # 4, 3, 2, 1, 0
            month_back = selected_month_idx - i
            if month_back > 0:
                months_range.append(pd.Period(f"{selected_year}-{month_back:02d}", freq='M'))
            else:
                # 작년으로 넘어감
                months_range.append(pd.Period(f"{selected_year-1}-{12+month_back:02d}", freq='M'))
        
        # 해당 인물의 월별 데이터
        person_monthly = person_year_data.groupby('월')['콘텐츠 수'].sum().reset_index()
        person_monthly.columns = ['월', '총제작량']
        
        person_monthly_new = person_year_data[person_year_data['신규여부'] == True].groupby('월')['콘텐츠 수'].sum().reset_index()
        person_monthly_new.columns = ['월', '신규제작량']
        
        person_stats = pd.merge(person_monthly, person_monthly_new, on='월', how='left').fillna(0)
        
        # 5개월 템플릿 생성
        full_months_df = pd.DataFrame({'월': months_range})
        person_stats_full = pd.merge(full_months_df, person_stats, on='월', how='left').fillna(0)
        person_stats_full['월_표시'] = person_stats_full['월'].apply(lambda x: f"{x.year}년 {x.month}월")
        person_stats_full = person_stats_full.sort_values('월')
        
        # 그래프 생성
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=person_stats_full['월_표시'],
            y=person_stats_full['총제작량'],
            mode='lines+markers',
            name='총 제작량',
            line=dict(color='#4A90E2', width=2),
            marker=dict(size=8)
        ))
        
        fig.add_trace(go.Scatter(
            x=person_stats_full['월_표시'],
            y=person_stats_full['신규제작량'],
            mode='lines+markers',
            name='신규 제작량',
            line=dict(color='#E67E22', width=2),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            height=300,
            xaxis_title="월",
            yaxis_title="제작량 (개)",
            hovermode='x unified',
            font=dict(size=12),
            yaxis=dict(rangemode='tozero'),
            margin=dict(l=40, r=40, t=40, b=40)
        )
        
        # 선택 년도 전체 데이터 (표용)
        year_stats = person_year_data.groupby('월')['콘텐츠 수'].sum().reset_index()
        year_stats.columns = ['월', '총제작량']
        
        year_stats_new = person_year_data[person_year_data['신규여부'] == True].groupby('월')['콘텐츠 수'].sum().reset_index()
        year_stats_new.columns = ['월', '신규제작량']
        
        year_stats = pd.merge(year_stats, year_stats_new, on='월', how='left').fillna(0)
        year_stats = year_stats.sort_values('월')
        
        return fig, year_stats
    
    
    def render_person_card(person, month_text):
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
                <div style="font-size: 0.9em; color: #7F8C8D; margin-top: 5px;">{month_text}</div>
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
            <div style="padding: 15px; background: #FAFBFC; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
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
                <div style="background: white; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #E1E8ED; grid-column: span 2;">
                    <div style="font-size: 1.5em; font-weight: bold; color: #5DADE2;">{person['상세페이지/배너']}</div>
                    <div style="font-size: 0.8em; color: #95A5A6;">상세페이지/배너</div>
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
    
    if selected_month_for_detail == '전체':
        st.info("특정 월을 선택하면 개인별 상세 데이터가 표시됩니다.")
    else:
        # 선택 월 텍스트 (26년 2월)
        month_text = f"{selected_month_period.year-2000}년 {selected_month_period.month}월"
        
        image_stats = []
        for designer in IMAGE_DESIGNERS:
            if designer in df_filtered['제작자_채움'].values:
                image_stats.append(calculate_person_stats(designer))
        
        image_stats = sorted(image_stats, key=lambda x: x['신규'], reverse=True)
        
        for person in image_stats:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                render_person_card(person, month_text)
            
            with col2:
                # 개인 12개월 데이터
                person_year = df_year[df_year['제작자_채움'] == person['이름']]
                
                # 그래프 생성
                fig, person_year_stats = create_person_graph(person['이름'], person_year, selected_month_period)
                st.plotly_chart(fig, use_container_width=True, key=f"image_{person['이름']}_graph")
                
                # 년도 데이터 표 (가로 레이아웃)
                st.markdown("**📊 월별 제작량**")
                
                # 1~12월 전체 템플릿 생성
                selected_year = selected_month_period.year
                all_months_in_year = [pd.Period(f"{selected_year}-{m:02d}", freq='M') for m in range(1, 13)]
                
                # 데이터가 있는 월만 추출
                year_stats_dict = {}
                for _, row in person_year_stats.iterrows():
                    month = row['월']
                    year_stats_dict[month] = {
                        '총제작량': int(row['총제작량']),
                        '신규제작량': int(row['신규제작량'])
                    }
                
                # 가로 테이블 생성 (1~12월)
                table_data = {
                    '': ['총 제작량', '신규 제작량']
                }
                
                for month_period in all_months_in_year:
                    month_label = f"{month_period.month}월"
                    if month_period in year_stats_dict:
                        table_data[month_label] = [
                            year_stats_dict[month_period]['총제작량'],
                            year_stats_dict[month_period]['신규제작량']
                        ]
                    else:
                        table_data[month_label] = [0, 0]
                
                table_df = pd.DataFrame(table_data)
                st.dataframe(table_df, use_container_width=True, hide_index=True)
                
                # 브랜드별 월별 제작량 추가
                st.markdown("**📊 브랜드별 제작량**")
                
                # 선택된 월에 작업한 브랜드 목록 가져오기
                person_month_data = df_filtered[df_filtered['제작자_채움'] == person['이름']]
                
                # 브랜드 컬럼 찾기
                brand_column = None
                for col in ['브랜드', '브랜드명', 'Brand', 'brand']:
                    if col in person_month_data.columns:
                        brand_column = col
                        break
                
                if brand_column and len(person_month_data) > 0:
                    # 선택된 월에 작업한 브랜드 목록
                    brands_in_month = person_month_data[brand_column].dropna().unique().tolist()
                    brands_in_month = [b for b in brands_in_month if str(b).strip() != '']
                    
                    if len(brands_in_month) > 0:
                        # 각 브랜드별 월별 제작량 계산
                        brand_table_data = {'': []}
                        
                        # 브랜드명을 첫 번째 컬럼에 추가
                        for brand in brands_in_month:
                            brand_table_data[''].append(brand)
                        
                        # 각 월별로 브랜드 제작량 계산
                        for month_period in all_months_in_year:
                            month_label = f"{month_period.month}월"
                            brand_table_data[month_label] = []
                            
                            # 해당 월 데이터 필터링
                            month_data = person_year[person_year['월'] == month_period]
                            
                            for brand in brands_in_month:
                                brand_count = month_data[month_data[brand_column] == brand]['콘텐츠 수'].sum()
                                brand_table_data[month_label].append(int(brand_count))
                        
                        brand_df = pd.DataFrame(brand_table_data)
                        st.dataframe(brand_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("선택한 월에 작업한 브랜드가 없습니다.")
                else:
                    st.info("브랜드 정보가 없습니다.")
            
            st.markdown("---")
    
    # 영상 디자이너
    st.markdown("### 🎬 영상 디자이너")
    
    if selected_month_for_detail == '전체':
        st.info("특정 월을 선택하면 개인별 상세 데이터가 표시됩니다.")
    else:
        # 선택 월 텍스트 (26년 2월)
        month_text = f"{selected_month_period.year-2000}년 {selected_month_period.month}월"
        
        video_stats = []
        for designer in VIDEO_DESIGNERS:
            if designer in df_filtered['제작자_채움'].values:
                video_stats.append(calculate_person_stats(designer))
        
        video_stats = sorted(video_stats, key=lambda x: x['신규'], reverse=True)
        
        for person in video_stats:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                render_person_card(person, month_text)
            
            with col2:
                # 개인 12개월 데이터
                person_year = df_year[df_year['제작자_채움'] == person['이름']]
                
                # 그래프 생성
                fig, person_year_stats = create_person_graph(person['이름'], person_year, selected_month_period)
                st.plotly_chart(fig, use_container_width=True, key=f"video_{person['이름']}_graph")
                
                # 년도 데이터 표 (가로 레이아웃)
                st.markdown("**📊 월별 제작량**")
                
                # 1~12월 전체 템플릿 생성
                selected_year = selected_month_period.year
                all_months_in_year = [pd.Period(f"{selected_year}-{m:02d}", freq='M') for m in range(1, 13)]
                
                # 데이터가 있는 월만 추출
                year_stats_dict = {}
                for _, row in person_year_stats.iterrows():
                    month = row['월']
                    year_stats_dict[month] = {
                        '총제작량': int(row['총제작량']),
                        '신규제작량': int(row['신규제작량'])
                    }
                
                # 가로 테이블 생성 (1~12월)
                table_data = {
                    '': ['총 제작량', '신규 제작량']
                }
                
                for month_period in all_months_in_year:
                    month_label = f"{month_period.month}월"
                    if month_period in year_stats_dict:
                        table_data[month_label] = [
                            year_stats_dict[month_period]['총제작량'],
                            year_stats_dict[month_period]['신규제작량']
                        ]
                    else:
                        table_data[month_label] = [0, 0]
                
                table_df = pd.DataFrame(table_data)
                st.dataframe(table_df, use_container_width=True, hide_index=True)
                
                # 브랜드별 월별 제작량 추가
                st.markdown("**📊 브랜드별 제작량**")
                
                # 선택된 월에 작업한 브랜드 목록 가져오기
                person_month_data = df_filtered[df_filtered['제작자_채움'] == person['이름']]
                
                # 브랜드 컬럼 찾기
                brand_column = None
                for col in ['브랜드', '브랜드명', 'Brand', 'brand']:
                    if col in person_month_data.columns:
                        brand_column = col
                        break
                
                if brand_column and len(person_month_data) > 0:
                    # 선택된 월에 작업한 브랜드 목록
                    brands_in_month = person_month_data[brand_column].dropna().unique().tolist()
                    brands_in_month = [b for b in brands_in_month if str(b).strip() != '']
                    
                    if len(brands_in_month) > 0:
                        # 각 브랜드별 월별 제작량 계산
                        brand_table_data = {'': []}
                        
                        # 브랜드명을 첫 번째 컬럼에 추가
                        for brand in brands_in_month:
                            brand_table_data[''].append(brand)
                        
                        # 각 월별로 브랜드 제작량 계산
                        for month_period in all_months_in_year:
                            month_label = f"{month_period.month}월"
                            brand_table_data[month_label] = []
                            
                            # 해당 월 데이터 필터링
                            month_data = person_year[person_year['월'] == month_period]
                            
                            for brand in brands_in_month:
                                brand_count = month_data[month_data[brand_column] == brand]['콘텐츠 수'].sum()
                                brand_table_data[month_label].append(int(brand_count))
                        
                        brand_df = pd.DataFrame(brand_table_data)
                        st.dataframe(brand_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("선택한 월에 작업한 브랜드가 없습니다.")
                else:
                    st.info("브랜드 정보가 없습니다.")
            
            st.markdown("---")

except Exception as e:
    st.error("❌ 데이터를 불러올 수 없습니다.")
    st.error(f"오류: {str(e)}")
    
    # 디버그 정보
    import traceback
    st.code(traceback.format_exc())
    
    st.info("관리자에게 문의하세요.")
