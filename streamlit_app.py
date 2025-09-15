import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from dateutil import parser

st.set_page_config(page_title="YouTube Mini Analytics", page_icon="📈", layout="wide")
st.title("📈 YouTube Mini Analytics — CSV Starter")
st.caption("초보자용: CSV만 업로드하면 핵심 지표를 자동 요약합니다. API 연결은 다음 단계에서 추가 예정")

with st.sidebar:
    st.header("모드")
    mode = st.radio("분석 모드", ["CSV 업로드 (권장)", "API(준비중)"])
    st.markdown("---")
    st.subheader("정렬 기준")
    sort_key = st.selectbox("TOP 리스트 정렬", ["views","watch_time","avg_view_duration","impressions","ctr","subs"], index=0)
    top_k = st.slider("상위 N개", 5, 50, 10)

def detect_col(df, candidates):
    cols = list(df.columns)
    lower_map = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand in df.columns: return cand
        lc = cand.lower()
        if lc in lower_map: return lower_map[lc]
        for c in cols:
            if lc in c.lower(): return c
    return None

def coerce_numeric(s):
    if s is None: return None
    return pd.to_numeric(s, errors='coerce')

@st.cache_data
def load_csv(uploaded_file):
    return pd.read_csv(uploaded_file)

if mode.startswith("CSV"):
    st.subheader("1) CSV 업로드")
    csv = st.file_uploader("YouTube Studio에서 내보낸 CSV 파일을 업로드하세요 (여러 개 가능)", type=["csv"], accept_multiple_files=True)
    map_file = st.file_uploader("(선택) 영상 길이/타입 매핑 CSV 업로드 — 'Video title, duration_sec, type' 컬럼", type=["csv"], accept_multiple_files=False)

    if csv:
        dfs = []
        for f in csv:
            try:
                df = load_csv(f); df["__source_file__"] = f.name; dfs.append(df)
            except Exception as e:
                st.warning(f"파일 `{f.name}` 읽기 실패: {e}")
        if not dfs: st.stop()
        raw = pd.concat(dfs, ignore_index=True)

        title_col = detect_col(raw, ["Video title","제목","동영상","Video","Title"]) or "Video title"
        date_col  = detect_col(raw, ["Date","날짜","일자"])
        views_col = detect_col(raw, ["Views","조회수"])
        wt_col    = detect_col(raw, ["Watch time (hours)","시청 시간(시간)","Watch time","시청 시간"])
        avd_col   = detect_col(raw, ["Average view duration","평균 시청 시간","Avg view duration"])
        impr_col  = detect_col(raw, ["Impressions","노출수"])
        ctr_col   = detect_col(raw, ["Impressions click-through rate","노출 대비 클릭률","CTR"])
        subs_col  = detect_col(raw, ["Subscribers","구독자","Subscribers gained","구독자 증가"])

        work = raw.copy()
        for c in [views_col, wt_col, avd_col, impr_col, ctr_col, subs_col]:
            if c and c in work.columns:
                work[c] = coerce_numeric(work[c].astype(str).str.replace('%','', regex=False).str.replace(',',''))
        if date_col and date_col in work.columns:
            def parse_date(x):
                try: return parser.parse(str(x)).date()
                except Exception: return pd.NaT
            work["__date__"] = work[date_col].apply(parse_date)

        work = work.rename(columns={title_col: "Video title"})
        if map_file is not None:
            m = load_csv(map_file)
            cols_needed = [c for c in ["Video title","duration_sec","type"] if c in m.columns]
            work = work.merge(m[cols_needed], on="Video title", how="left")

        if "type" not in work.columns:
            if "duration_sec" in work.columns:
                work["type"] = np.where(work["duration_sec"].astype(float) <= 60, "Shorts", "Longform")
            else:
                work["type"] = np.where(work["Video title"].str.contains("#shorts", case=False, na=False), "Shorts", "Unknown")

        st.markdown("---"); st.subheader("2) 핵심 KPI 요약")
        def safe_sum(col): return work[col].sum() if col in work else np.nan
        def safe_mean(col): return work[col].mean() if col in work else np.nan
        total_views, total_wt, avg_ctr, subs_sum = safe_sum(views_col), safe_sum(wt_col), safe_mean(ctr_col), safe_sum(subs_col)
        k1,k2,k3,k4 = st.columns(4)
        k1.metric("총 조회수", f"{int(total_views):,}" if pd.notna(total_views) else "-")
        k2.metric("총 시청시간(시간)", f"{total_wt:,.1f}" if pd.notna(total_wt) else "-")
        k3.metric("평균 CTR(%)", f"{avg_ctr:,.2f}" if pd.notna(avg_ctr) else "-")
        k4.metric("구독자 증감", f"{int(subs_sum):,}" if pd.notna(subs_sum) else "-")

        st.subheader("3) 롱폼 vs 숏츠 비교")
        if "type" in work:
            rename_map = {}
            if views_col: rename_map[views_col] = 'views'
            if wt_col: rename_map[wt_col] = 'watch_time'
            if avd_col: rename_map[avd_col] = 'avg_view_duration'
            if impr_col: rename_map[impr_col] = 'impressions'
            if ctr_col: rename_map[ctr_col] = 'ctr'
            if subs_col: rename_map[subs_col] = 'subs'
            w2 = work.rename(columns=rename_map)
            g = w2.groupby('type').agg({
                'views':'sum' if 'views' in w2 else 'first',
                'watch_time':'sum' if 'watch_time' in w2 else 'first',
                'avg_view_duration':'mean' if 'avg_view_duration' in w2 else 'first',
                'impressions':'sum' if 'impressions' in w2 else 'first',
                'ctr':'mean' if 'ctr' in w2 else 'first',
                'subs':'sum' if 'subs' in w2 else 'first',
            })
            st.dataframe(g, use_container_width=True)

            if "__date__" in w2 and 'views' in w2:
                daily = w2.dropna(subset=["__date__"]).groupby(["__date__","type"]).agg({'views':'sum'}).reset_index()
                fig, ax = plt.subplots()
                for t, sub in daily.groupby('type'):
                    ax.plot(sub['__date__'], sub['views'], label=t)
                ax.set_title('일자별 조회수 추이 (타입별)')
                ax.set_xlabel('날짜'); ax.set_ylabel('조회수'); ax.legend()
                st.pyplot(fig)

        st.markdown("---"); st.subheader("4) 상위 영상 분석")
        if "Video title" in work:
            grp = work.groupby("Video title").agg({
                views_col: 'sum' if views_col in work else 'first',
                wt_col: 'sum' if wt_col in work else 'first',
                avd_col: 'mean' if avd_col in work else 'first',
                impr_col: 'sum' if impr_col in work else 'first',
                ctr_col: 'mean' if ctr_col in work else 'first',
                subs_col: 'sum' if subs_col in work else 'first',
                'type': 'first' if 'type' in work else 'first'
            }).reset_index()

            rename_map = {}
            if views_col: rename_map[views_col] = 'views'
            if wt_col: rename_map[wt_col] = 'watch_time'
            if avd_col: rename_map[avd_col] = 'avg_view_duration'
            if impr_col: rename_map[impr_col] = 'impressions'
            if ctr_col: rename_map[ctr_col] = 'ctr'
            if subs_col: rename_map[subs_col] = 'subs'
            grp = grp.rename(columns=rename_map)

            sort_key_use = sort_key if sort_key in grp.columns else 'views'
            grp = grp.sort_values(sort_key_use, ascending=False).head(top_k)
            st.dataframe(grp, use_container_width=True)
        else:
            st.info("영상 제목 컬럼을 찾지 못했습니다. CSV 내보내기 옵션을 확인해 주세요.")

        st.markdown("---"); st.subheader("5) 간단 인사이트 제안")
        tips = []
        if 'ctr' in locals().get('grp', pd.DataFrame()).columns:
            high_ctr = grp.nlargest(3, 'ctr') if 'ctr' in grp else pd.DataFrame()
            if not high_ctr.empty:
                tips.append("CTR 상위 영상의 제목/썸네일 공통 패턴을 다음 업로드에 반영해 보세요.")
        if 'avg_view_duration' in locals().get('grp', pd.DataFrame()).columns:
            tips.append("평균 시청시간이 높은 영상의 오프닝 길이와 전환 타이밍을 벤치마킹하세요.")
        if 'impressions' in locals().get('grp', pd.DataFrame()).columns and 'ctr' in locals().get('grp', pd.DataFrame()).columns:
            tips.append("노출수는 높지만 CTR이 낮은 영상은 썸네일/제목 A/B 테스트 대상입니다.")
        if 'type' in locals().get('grp', pd.DataFrame()).columns:
            tips.append("Shorts와 Longform 각각 TOP5의 공통 키워드를 비교해 보세요.")
        if not tips:
            tips.append("데이터 열 이름을 더 풍부하게 포함한 CSV를 업로드하면 인사이트가 늘어납니다.")
        for t in tips:
            st.write("• ", t)
else:
    st.info("API 모드는 준비 중입니다. CSV 모드로 먼저 시작해 보세요. (YouTube Analytics API 연동은 차후 업데이트)")
