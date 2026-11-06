import streamlit as st

def apply_custom_styles(theme, theme_name):
    """Apply shared styling for the selected Reader Insights theme."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
        :root {{
            --bg: {theme["bg"]};
            --sidebar: {theme["sidebar"]};
            --panel: {theme["panel"]};
            --ink: {theme["ink"]};
            --muted: {theme["muted"]};
            --primary: {theme["primary"]};
            --border: {theme["border"]};
        }}
        .stApp {{ background: var(--bg); color: var(--ink); font-family: 'DM Sans', sans-serif; }}
        [data-testid="stSidebar"] {{ background: var(--sidebar); border-right: 1px solid var(--border); }}
        [data-testid="stHeader"] {{ background: transparent; }}
        h1, h2, h3, h4 {{ color: var(--ink); font-family: 'Space Grotesk', sans-serif; }}
        .eyebrow {{ color: var(--primary); font-size: .72rem; font-weight: 700; letter-spacing: 2px; margin-bottom: .4rem; }}
        .subtitle {{ color: var(--muted); font-size: 1rem; line-height: 1.65; max-width: 850px; margin-bottom: 1.2rem; }}
        .section-label {{ font-size: .72rem; font-weight: 700; letter-spacing: 1.8px; text-transform: uppercase; margin: 1.1rem 0 .25rem; }}
        .panel, .metric-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 1.15rem 1.3rem; }}
        .metric-card {{ min-height: 125px; height: 100%; }}
        .metric-label {{ color: var(--muted); font-size: .78rem; font-weight: 600; letter-spacing: .5px; text-transform: uppercase; }}
        .metric-value {{ color: var(--ink); font-family: 'Space Grotesk', sans-serif; font-size: 1.9rem; font-weight: 700; margin: .35rem 0; }}
        .metric-note {{ color: var(--muted); font-size: .78rem; }}
        .book-title {{ color: var(--ink); font-weight: 700; }}
        div[data-testid="stDataFrame"], div[data-testid="stTable"] {{ border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }}
        .stButton button, .stDownloadButton button {{ border-radius: 10px; }}
        hr {{ border-color: var(--border); }}
        </style>
        """,
        unsafe_allow_html=True,
    )
