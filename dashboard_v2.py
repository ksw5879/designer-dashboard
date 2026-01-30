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
    
    # 그래프 1: 주차별 그래프 (최근 5주) - 위
    st.markdown("### 📊 주차별 제작량 (최근 5주)")
    
    # 최근 5주 데이터 (주차 선택과 무관)
    available_weeks_all = sorted(df['주차_정렬용'].unique(), reverse=True)
    if len(available_weeks_all) > 0:
        recent_5_weeks = available_weeks_all[:min(5, len(available_weeks_all))]  # 최근 5주 (또는 가능한 만큼)
        month_df = df[df['주차_정렬용'].isin(recent_5_weeks)]
        
        weekly_total = month_df.groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
        weekly_total.columns = ['주차', '총제작량']
        
        weekly_new = month_df[month_df['신규여부'] == True].groupby('주차_정렬용')['콘텐츠 수'].sum().reset_index()
        weekly_new.columns = ['주차', '신규제작량']
        
        weekly_stats = pd.merge(weekly_total, weekly_new, on='주차', how='left').fillna(0)
        
        # 주차별 날짜 범위 계산
        def format_week_label(week_period):
            # 주차의 시작일과 종료일 계산
            start_date = week_period.start_time
            end_date = week_period.end_time
            
            # 해당 주차의 실제 데이터가 있는 날짜 범위
            week_data = df[df['주차_정렬용'] == week_period]
            if len(week_data) > 0:
                actual_start = week_data['날짜_변환'].min()
                actual_end = week_data['날짜_변환'].max()
                
                # "26년 1월 5주차 (1/26~2/1)" 형식
                year = actual_start.strftime('%y')
                month = actual_start.strftime('%m').lstrip('0')
                start_day = actual_start.strftime('%m/%d').lstrip('0').replace('/0', '/')
                end_day = actual_end.strftime('%m/%d').lstrip('0').replace('/0', '/')
                
                # 주차 번호 계산
                week_num = actual_start.isocalendar()[1]
                
                return f"{year}년 {month}월 {week_num}주차<br>({start_day}~{end_day})"
            return str(week_period)
        
        weekly_stats['주차_표시'] = weekly_stats['주차'].apply(format_week_label)
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
        
        # 평일만 필터링 (월~금)
        week_df = week_df[week_df['날짜_변환'].dt.dayofweek < 5]
        
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
    st.info("관리자에게 문의하세요.")
