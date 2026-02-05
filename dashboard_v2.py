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
    
    # 콘텐츠 유형 간소화 (상세페이지/배너 추가)
    def simplify_content_type(content_type):
        if pd.isna(content_type) or content_type == '':
            return '기타'
        content_type = str(content_type).lower()
        if '상세페이지' in content_type or '상세' in content_type:
            return '상세페이지/배너'
        elif '신규' in content_type or '디벨롭' in content_type or 'ai' in content_type:
            return '신규/디벨롭'
        elif '리사이징' in content_type:
            return '리사이징'
        elif '베리' in content_type or '배너' in content_type:
            return '배너'
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
    all_months = pd.period_range(start=df['날짜_변환'].min(), end=df['날짜_변환'].max(), freq='M')
    # 최근 5개월 포함하도록
    if len(all_months) < 5:
        start_month = df['날짜_변환'].max() - pd.DateOffset(months=4)
        all_months = pd.period_range(start=start_month, end=df['날짜_변환'].max(), freq='M')
    
    # 빈 데이터프레임 생성
    full_months_df = pd.DataFrame({'월': list(all_months)})
    
    # 이미지 데이터 병합
    monthly_image_stats_full = pd.merge(full_months_df, monthly_image_stats, on='월', how='left').fillna(0)
    monthly_image_stats_full = monthly_image_stats_full.sort_values('월')
    
    # 영상 데이터 병합
    monthly_video_stats_full = pd.merge(full_months_df, monthly_video_stats, on='월', how='left').fillna(0)
    monthly_video_stats_full = monthly_video_stats_full.sort_values('월')
    
    # X축 레이블 (26년 1월 형식)
    monthly_image_stats_full['월_표시'] = monthly_image_stats_full['월'].apply(
        lambda x: f"{x.year-2000}년 {x.month}월"
    )
    monthly_video_stats_full['월_표시'] = monthly_video_stats_full['월'].apply(
        lambda x: f"{x.year-2000}년 {x.month}월"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🎨 이미지 디자이너 월별 제작량")
        
        fig_image = go.Figure()
        fig_image.add_trace(go.Bar(
            x=monthly_image_stats_full['월_표시'],
            y=monthly_image_stats_full['총제작량'],
            name='총 제작량',
            marker_color='#5DADE2',
            text=monthly_image_stats_full['총제작량'].apply(lambda x: f"{int(x)}"),
            textposition='outside',
            textfont=dict(size=12, color='#2C3E50')
        ))
        
        fig_image.add_trace(go.Bar(
            x=monthly_image_stats_full['월_표시'],
            y=monthly_image_stats_full['신규제작량'],
            name='신규 제작량',
            marker_color='#F39C12',
            text=monthly_image_stats_full['신규제작량'].apply(lambda x: f"{int(x)}"),
            textposition='outside',
            textfont=dict(size=12, color='#2C3E50')
        ))
        
        fig_image.update_layout(
            barmode='group',
            height=400,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(title="", tickangle=0),
            yaxis=dict(title="제작량", rangemode='tozero'),
            margin=dict(l=40, r=40, t=60, b=40)
        )
        
        st.plotly_chart(fig_image, use_container_width=True)
    
    with col2:
        st.markdown("#### 🎬 영상 디자이너 월별 제작량")
        
        fig_video = go.Figure()
        fig_video.add_trace(go.Bar(
            x=monthly_video_stats_full['월_표시'],
            y=monthly_video_stats_full['총제작량'],
            name='총 제작량',
            marker_color='#5DADE2',
            text=monthly_video_stats_full['총제작량'].apply(lambda x: f"{int(x)}"),
            textposition='outside',
            textfont=dict(size=12, color='#2C3E50')
        ))
        
        fig_video.add_trace(go.Bar(
            x=monthly_video_stats_full['월_표시'],
            y=monthly_video_stats_full['신규제작량'],
            name='신규 제작량',
            marker_color='#F39C12',
            text=monthly_video_stats_full['신규제작량'].apply(lambda x: f"{int(x)}"),
            textposition='outside',
            textfont=dict(size=12, color='#2C3E50')
        ))
        
        fig_video.update_layout(
            barmode='group',
            height=400,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(title="", tickangle=0),
            yaxis=dict(title="제작량", rangemode='tozero'),
            margin=dict(l=40, r=40, t=60, b=40)
        )
        
        st.plotly_chart(fig_video, use_container_width=True)
    
    st.markdown("---")
    
    # 그래프 2: 콘텐츠 유형별 제작량
    st.markdown("### 📊 콘텐츠 유형별 제작량")
    
    # 선택된 연월의 데이터만 필터링
    selected_period = pd.Period(f"{selected_year}-{selected_month:02d}", freq='M')
    df_selected_month = df[df['월'] == selected_period].copy()
    
    # 이미지 디자이너 콘텐츠 유형별
    df_image_month = df_selected_month[df_selected_month['제작자_채움'].isin(IMAGE_DESIGNERS)]
    content_type_image = df_image_month.groupby('콘텐츠유형_간소화')['콘텐츠 수'].sum().reset_index()
    content_type_image.columns = ['콘텐츠유형', '개수']
    
    # 영상 디자이너 콘텐츠 유형별
    df_video_month = df_selected_month[df_selected_month['제작자_채움'].isin(VIDEO_DESIGNERS)]
    content_type_video = df_video_month.groupby('콘텐츠유형_간소화')['콘텐츠 수'].sum().reset_index()
    content_type_video.columns = ['콘텐츠유형', '개수']
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🎨 이미지 디자이너")
        
        fig_content_image = go.Figure()
        fig_content_image.add_trace(go.Bar(
            x=content_type_image['콘텐츠유형'],
            y=content_type_image['개수'],
            marker_color='#5DADE2',
            text=content_type_image['개수'].apply(lambda x: f"{int(x)}"),
            textposition='outside',
            textfont=dict(size=12)
        ))
        
        fig_content_image.update_layout(
            height=400,
            showlegend=False,
            xaxis=dict(title="콘텐츠 유형"),
            yaxis=dict(title="제작량", rangemode='tozero'),
            margin=dict(l=40, r=40, t=40, b=40)
        )
        
        st.plotly_chart(fig_content_image, use_container_width=True)
    
    with col2:
        st.markdown("#### 🎬 영상 디자이너")
        
        fig_content_video = go.Figure()
        fig_content_video.add_trace(go.Bar(
            x=content_type_video['콘텐츠유형'],
            y=content_type_video['개수'],
            marker_color='#5DADE2',
            text=content_type_video['개수'].apply(lambda x: f"{int(x)}"),
            textposition='outside',
            textfont=dict(size=12)
        ))
        
        fig_content_video.update_layout(
            height=400,
            showlegend=False,
            xaxis=dict(title="콘텐츠 유형"),
            yaxis=dict(title="제작량", rangemode='tozero'),
            margin=dict(l=40, r=40, t=40, b=40)
        )
        
        st.plotly_chart(fig_content_video, use_container_width=True)
    
    st.markdown("---")
    
    # 개인별 상세 통계
    st.markdown("### 👤 개인별 상세 통계")
    
    # 월 선택 필터
    available_months_list = sorted(df['월'].unique())
    month_options = ['전체'] + [f"{m.year}년 {m.month}월" for m in available_months_list]
    
    selected_month_for_detail = st.selectbox(
        "📅 상세 통계 조회 월 선택",
        options=month_options,
        index=0
    )
    
    # 선택된 월에 해당하는 데이터 필터링
    if selected_month_for_detail == '전체':
        df_filtered = df.copy()
        df_year = df.copy()
    else:
        # "2026년 2월" → Period 객체로 변환
        year = int(selected_month_for_detail.split('년')[0])
        month = int(selected_month_for_detail.split('년')[1].replace('월', '').strip())
        selected_month_period = pd.Period(f"{year}-{month:02d}", freq='M')
        
        df_filtered = df[df['월'] == selected_month_period].copy()
        
        # 해당 연도 전체 데이터 (12개월 그래프용)
        df_year = df[df['날짜_변환'].dt.year == selected_month_period.year].copy()
    
    # 개인별 통계 계산 함수 (상세페이지/배너 추가)
    def calculate_person_stats(person_name):
        person_data = df_filtered[df_filtered['제작자_채움'] == person_name]
        
        # 신규/디벨롭 (신규여부=True인 것)
        new_count = person_data[person_data['신규여부'] == True]['콘텐츠 수'].sum()
        
        # 총 제작량
        total_count = person_data['콘텐츠 수'].sum()
        
        # 콘텐츠 유형별 (상세페이지/배너 추가)
        banner_count = person_data[person_data['콘텐츠유형_간소화'] == '배너']['콘텐츠 수'].sum()
        resizing_count = person_data[person_data['콘텐츠유형_간소화'] == '리사이징']['콘텐츠 수'].sum()
        monthly_count = person_data[person_data['콘텐츠유형_간소화'] == '지면확장']['콘텐츠 수'].sum()
        ai_count = person_data[person_data['콘텐츠 유형'].str.contains('AI', case=False, na=False)]['콘텐츠 수'].sum()
        detail_banner_count = person_data[person_data['콘텐츠유형_간소화'] == '상세페이지/배너']['콘텐츠 수'].sum()
        
        # 브랜드 (해당 월에 작업한 브랜드만)
        if '브랜드' in person_data.columns:
            brands = person_data['브랜드'].dropna().unique()
            brands = [b for b in brands if str(b).strip() != '']
            brand_count = len(brands)
            brand_list = ', '.join(brands[:5]) + (f' 외 {len(brands)-5}개' if len(brands) > 5 else '')
        else:
            brand_count = 0
            brand_list = '-'
        
        return {
            '이름': person_name,
            '신규': int(new_count),
            '총제작량': int(total_count),
            '배너': int(banner_count),
            '리사이징': int(resizing_count),
            '지면확장': int(monthly_count),
            'AI': int(ai_count),
            '상세페이지/배너': int(detail_banner_count),
            '브랜드수': brand_count,
            '브랜드목록': brand_list
        }
    
    # 개인별 그래프 생성 함수 (12개월 추이)
    def create_person_graph(person_name, person_year_data, selected_month_period):
        # 월별 집계
        person_monthly = person_year_data.groupby('월')['콘텐츠 수'].sum().reset_index()
        person_monthly.columns = ['월', '총제작량']
        
        person_monthly_new = person_year_data[person_year_data['신규여부'] == True].groupby('월')['콘텐츠 수'].sum().reset_index()
        person_monthly_new.columns = ['월', '신규제작량']
        
        person_monthly_stats = pd.merge(person_monthly, person_monthly_new, on='월', how='left').fillna(0)
        
        # 1~12월 전체 생성
        selected_year = selected_month_period.year
        all_months_in_year = [pd.Period(f"{selected_year}-{m:02d}", freq='M') for m in range(1, 13)]
        full_months_df = pd.DataFrame({'월': all_months_in_year})
        
        person_monthly_stats_full = pd.merge(full_months_df, person_monthly_stats, on='월', how='left').fillna(0)
        person_monthly_stats_full = person_monthly_stats_full.sort_values('월')
        
        # X축 레이블
        person_monthly_stats_full['월_표시'] = person_monthly_stats_full['월'].apply(
            lambda x: f"{x.month}월"
        )
        
        # 그래프 생성
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=person_monthly_stats_full['월_표시'],
            y=person_monthly_stats_full['총제작량'],
            mode='lines+markers+text',
            name='총 제작량',
            line=dict(color='#5DADE2', width=3),
            marker=dict(size=8),
            text=person_monthly_stats_full['총제작량'].apply(lambda x: f"{int(x)}"),
            textposition='top center',
            textfont=dict(size=10)
        ))
        
        fig.add_trace(go.Scatter(
            x=person_monthly_stats_full['월_표시'],
            y=person_monthly_stats_full['신규제작량'],
            mode='lines+markers+text',
            name='신규 제작량',
            line=dict(color='#F39C12', width=3),
            marker=dict(size=8),
            text=person_monthly_stats_full['신규제작량'].apply(lambda x: f"{int(x)}"),
            textposition='top center',
            textfont=dict(size=10)
        ))
        
        fig.update_layout(
            height=300,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(title=""),
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
                    <div style="font-size: 1.5em; font-weight: bold; color: #5DADE2;">{person['배너']}</div>
                    <div style="font-size: 0.8em; color: #95A5A6;">배너</div>
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
                st.plotly_chart(fig, use_container_width=True)
                
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
                st.plotly_chart(fig, use_container_width=True)
                
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
            
            st.markdown("---")

except Exception as e:
    st.error("❌ 데이터를 불러올 수 없습니다.")
    st.error(f"오류: {str(e)}")
    
    # 디버그 정보
    import traceback
    st.code(traceback.format_exc())
    
    st.info("관리자에게 문의하세요.")
