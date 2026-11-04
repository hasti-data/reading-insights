import html
import re
import pandas as pd
import plotly.express as px
import streamlit as st
# ==================================================
# PAGE CONFIGURATION
# ==================================================
st.set_page_config(
    page_title="Reader Insights",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)
# ==================================================
# THEMES
# ==================================================
THEMES = {
    "☁️ Daydream": {
        "bg": "#F4F8FA",
        "sidebar": "#E7F0F3",
        "panel": "#FFFFFF",
        "ink": "#263746",
        "muted": "#718493",
        "primary": "#79B9D2",
        "secondary": "#91BFAE",
        "accent": "#D6B6D9",
        "gold": "#E4C77B",
        "border": "#DCE7EB",
        "grid": "#EAF0F3",
        "button_text": "#183746",
    },
    "🌙 Midnight Bunny": {
        "bg": "#111A2B",
        "sidebar": "#17243A",
        "panel": "#1B2940",
        "ink": "#F0F5FA",
        "muted": "#A6B8CC",
        "primary": "#83CFF0",
        "secondary": "#8FE0C2",
        "accent": "#D6A8F0",
        "gold": "#F1D37A",
        "border": "#30425A",
        "grid": "#293A50",
        "button_text": "#102134",
    },
}
# ==================================================
# HELPER FUNCTIONS
# ==================================================
def safe_text(value):
    return html.escape(str(value))
def section_label(label, color):
    st.markdown(
        f'<div class="section-label" style="color:{color}">'
        f'{safe_text(label)}</div>',
        unsafe_allow_html=True,
    )
def metric_card(label, value, note, C):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{safe_text(label)}</div>
            <div class="metric-value">{safe_text(value)}</div>
            <div class="metric-note">{safe_text(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
def style_chart(fig, C, height=340):
    fig.update_layout(
        height=height,
        paper_bgcolor=C["panel"],
        plot_bgcolor=C["panel"],
        font=dict(
            family="DM Sans, sans-serif",
            color=C["ink"],
            size=12,
        ),
        margin=dict(l=15, r=25, t=45, b=15),
        title_font=dict(
            family="Space Grotesk, sans-serif",
            size=17,
            color=C["ink"],
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(color=C["ink"]),
        ),
        hoverlabel=dict(
            bgcolor=C["panel"],
            font_color=C["ink"],
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor=C["border"],
        tickfont=dict(color=C["muted"]),
        title_font=dict(color=C["ink"]),
    )
    fig.update_yaxes(
        gridcolor=C["grid"],
        zeroline=False,
        tickfont=dict(color=C["muted"]),
        title_font=dict(color=C["ink"]),
    )
    return fig
def filled_mask(series):
    """True for non-empty values, including non-string columns."""
    return (
        series.notna()
        & series.astype("string").str.strip().ne("").fillna(False)
    )
def get_column(df, column, default=None):
    """Return a column or a default Series with the same index."""
    if column in df.columns:
        return df[column]
    return pd.Series(default, index=df.index)
def normalize_reading_export(data):
    """Convert Goodreads and StoryGraph exports to shared column names."""
    data = data.copy()
    columns = set(data.columns)
    if "Exclusive Shelf" in columns or "My Rating" in columns:
        source = "Goodreads"
        aliases = {
            "Author": "Authors",
            "Exclusive Shelf": "Read Status",
            "My Rating": "Star Rating",
            "Date Read": "Last Date Read",
            "Binding": "Format",
            "Bookshelves": "Tags",
            "My Review": "Review",
        }
    elif "Read Status" in columns or "Star Rating" in columns or "Authors" in columns:
        source = "StoryGraph"
        aliases = {}
    else:
        source = "Unknown"
        aliases = {}
    # Keep original export fields, adding the shared dashboard fields only
    # when they are not already present.
    for original, canonical in aliases.items():
        if canonical not in data.columns and original in data.columns:
            data[canonical] = data[original]
    if "Read Status" in data.columns:
        status = data["Read Status"].astype("string").str.strip().str.lower()
        status_map = {
            "currently reading": "currently-reading",
            "currently-reading": "currently-reading",
            "to read": "to-read",
            "to-read": "to-read",
            "read": "read",
        }
        data["Read Status"] = status.map(status_map).fillna(data["Read Status"])
    if source == "Goodreads" and "Star Rating" in data.columns:
        # Goodreads uses 0 to mean that a book has not been rated.
        rating = pd.to_numeric(data["Star Rating"], errors="coerce")
        data["Star Rating"] = rating.mask(rating.eq(0), pd.NA)
    return data, source
def parse_reading_dates(values):
    """Parse full dates and year-only values from reading exports safely."""
    text = values.astype("string").str.strip()
    text = text.mask(text.eq(""), pd.NA)
    # Some StoryGraph exports contain only a year (for example, 2021).
    year_only = text.str.fullmatch(r"\d{4}", na=False)
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    if year_only.any():
        parsed.loc[year_only] = pd.to_datetime(
            text.loc[year_only] + "-01-01",
            format="%Y-%m-%d",
            errors="coerce",
        )
    remaining = text.notna() & ~year_only
    if remaining.any():
        try:
            parsed.loc[remaining] = pd.to_datetime(
                text.loc[remaining],
                format="mixed",
                errors="coerce",
            )
        except (TypeError, ValueError):
            parsed.loc[remaining] = pd.to_datetime(
                text.loc[remaining],
                errors="coerce",
            )
    return parsed
def split_categories(value):
    """

    Split multi-value fields such as Moods and Tags.

    Supports comma, semicolon, pipe and line-break separators.

    """
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"[,;|\n]+", text)
    cleaned = []
    seen = set()
    for part in parts:
        part = part.strip()
        key = part.casefold()
        if part and key not in seen:
            cleaned.append(part)
            seen.add(key)
    return cleaned
def make_monthly_data(data):
    """Count records with Last Date Read by calendar month."""
    dated = data.dropna(subset=["_last_read_date"]).copy()
    if dated.empty:
        return pd.DataFrame(columns=["Month", "Books"])
    dated["Month"] = (
        dated["_last_read_date"].dt.to_period("M").dt.to_timestamp()
    )
    return (
        dated.groupby("Month")
        .size()
        .reset_index(name="Books")
        .sort_values("Month")
    )
def make_yearly_data(data):
    """Count records with Last Date Read by calendar year."""
    dated = data.dropna(subset=["_last_read_date"]).copy()
    if dated.empty:
        return pd.DataFrame(columns=["Year", "Books"])
    dated["Year"] = dated["_last_read_date"].dt.year
    return (
        dated.groupby("Year")
        .size()
        .reset_index(name="Books")
        .sort_values("Year")
    )
def category_rating_data(data, column, split_multi=False):
    """

    Calculate mean rating and sample count for each category.

    Multi-value fields can be exploded into individual categories.

    """
    if column not in data.columns:
        return pd.DataFrame(
            columns=["Category", "Average Rating", "Rated Books"]
        )
    subset = data[[column, "_rating"]].copy()
    subset = subset[subset["_rating"].notna()]
    subset = subset[filled_mask(subset[column])]
    if subset.empty:
        return pd.DataFrame(
            columns=["Category", "Average Rating", "Rated Books"]
        )
    subset["Category"] = (
        subset[column].astype(str).str.strip()
    )
    if split_multi:
        subset["Category"] = subset[column].apply(split_categories)
        subset = subset.explode("Category")
        subset = subset[
            subset["Category"].notna()
            & subset["Category"].astype(str).str.strip().ne("")
        ]
    if subset.empty:
        return pd.DataFrame(
            columns=["Category", "Average Rating", "Rated Books"]
        )
    # A book should count only once within each category.
    subset = subset.drop_duplicates(
        subset=["Category", "_rating"],
        keep="first",
    ) if False else subset
    return (
        subset.groupby("Category")["_rating"]
        .agg(["mean", "count"])
        .reset_index()
        .rename(
            columns={
                "mean": "Average Rating",
                "count": "Rated Books",
            }
        )
        .sort_values("Average Rating", ascending=True)
    )
# ==================================================
# SIDEBAR
# ==================================================
with st.sidebar:
    st.markdown(
        """

        <div style="font-size:1.8rem;font-weight:800;letter-spacing:-1px;">

            reader<span style="color:#83CFF0;">.</span>

        </div>

        <div style="font-size:0.78rem;letter-spacing:1px;opacity:0.8;">

            YOUR PERSONAL READING UNIVERSE

        </div>

        """,
        unsafe_allow_html=True,
    )
    st.divider()
    theme_name = st.radio(
        "YOUR ATMOSPHERE",
        list(THEMES.keys()),
    )
    C = THEMES[theme_name]
    st.divider()
    page = st.radio(
        "EXPLORE",
        [
            "Overview",
            "Reading DNA",
            "Reading Timeline",
            "Taste Analysis",
            "My Library",
        ],
    )
    st.divider()
    st.markdown("**YOUR DATA**")
    uploaded_file = st.file_uploader(
        "Import your reading export",
        type=["csv"],
        help="Upload your reading-history CSV.",
    )
    st.caption("Charts are calculated from your supplied data.")
# ==================================================
# CUSTOM DESIGN
# ==================================================
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    :root {{
        color-scheme: {"dark" if theme_name == "🌙 Midnight Bunny" else "light"};
    }}
    .stApp {{
        background: {C["bg"]};
        color: {C["ink"]};
        font-family: 'DM Sans', sans-serif;
    }}
    .block-container {{
        max-width: 1480px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }}
    .stApp h1, .stApp h2, .stApp h3,
    .stApp h4, .stApp h5, .stApp h6 {{
        color: {C["ink"]} !important;
        font-family: 'Space Grotesk', sans-serif !important;
    }}
    .stApp h1 {{
        font-size: 2.8rem !important;
        font-weight: 700 !important;
        letter-spacing: -1.5px;
    }}
    .stApp p, .stApp li, .stApp label,
    .stApp [data-testid="stMarkdownContainer"] {{
        color: {C["ink"]};
    }}
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stCaptionContainer"] p {{
        color: {C["muted"]} !important;
    }}
    [data-testid="stSidebar"] {{
        background: {C["sidebar"]};
        border-right: 1px solid {C["border"]};
    }}
    [data-testid="stSidebar"] * {{
        color: {C["ink"]};
    }}
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
        color: {C["muted"]} !important;
    }}
    [data-testid="stSidebar"] [role="radiogroup"] label {{
        border-radius: 10px;
        padding: 5px 8px;
    }}
    .stApp input, .stApp textarea {{
        color: {C["ink"]} !important;
        background: {C["panel"]} !important;
        -webkit-text-fill-color: {C["ink"]} !important;
        caret-color: {C["primary"]};
    }}
    .stApp input::placeholder,
    .stApp textarea::placeholder {{
        color: {C["muted"]} !important;
        -webkit-text-fill-color: {C["muted"]} !important;
        opacity: 1;
    }}
    .stApp [data-baseweb="select"] > div {{
        background: {C["panel"]} !important;
        border-color: {C["border"]} !important;
    }}
    .stApp [data-baseweb="select"] span,
    .stApp [data-baseweb="select"] div {{
        color: {C["ink"]} !important;
    }}
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [role="listbox"] {{
        background: {C["panel"]} !important;
    }}
    [role="option"] {{
        background: {C["panel"]} !important;
        color: {C["ink"]} !important;
    }}
    [role="option"]:hover {{
        background: {C["border"]} !important;
    }}
    [data-testid="stFileUploader"] section {{
        background: {C["panel"]} !important;
        border: 1px dashed {C["primary"]} !important;
        border-radius: 14px;
    }}
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploader"] section * {{
        color: {C["ink"]} !important;
    }}
    [data-testid="stFileUploader"] button {{
        background: {C["primary"]} !important;
        border-color: {C["primary"]} !important;
        color: {C["button_text"]} !important;
    }}
    [data-testid="stMetric"] {{
        background: {C["panel"]};
        border: 1px solid {C["border"]};
        border-radius: 16px;
        padding: 1rem 1.1rem;
    }}
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] * {{
        color: {C["muted"]} !important;
    }}
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * {{
        color: {C["ink"]} !important;
    }}
    .stApp .stButton > button,
    .stApp .stDownloadButton > button {{
        background: {C["primary"]};
        color: {C["button_text"]} !important;
        border: 1px solid {C["primary"]};
        border-radius: 10px;
        font-weight: 700;
    }}
    .stApp .stButton > button *,
    .stApp .stDownloadButton > button * {{
        color: {C["button_text"]} !important;
    }}
    [data-testid="stDataFrame"] {{
        border: 1px solid {C["border"]};
        border-radius: 12px;
        overflow: hidden;
    }}
    .eyebrow {{
        color: {C["primary"]};
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 2.5px;
        text-transform: uppercase;
        margin-bottom: 0.6rem;
    }}
    .subtitle {{
        color: {C["muted"]} !important;
        font-size: 0.96rem;
        margin-top: -0.5rem;
        margin-bottom: 1.5rem;
        line-height: 1.7;
    }}
    .section-label {{
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-top: 0.5rem;
        margin-bottom: 0.4rem;
    }}
    .panel {{
        background: {C["panel"]};
        border: 1px solid {C["border"]};
        border-radius: 16px;
        padding: 1.2rem;
    }}
    .metric-card {{
        background: {C["panel"]};
        border: 1px solid {C["border"]};
        border-radius: 16px;
        padding: 1.2rem;
        min-height: 125px;
    }}
    .metric-label {{
        color: {C["muted"]} !important;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 1.2px;
        text-transform: uppercase;
    }}
    .metric-value {{
        color: {C["ink"]} !important;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2rem;
        font-weight: 700;
        margin-top: 0.5rem;
        line-height: 1.3;
        overflow-wrap: anywhere;
    }}
    .metric-note {{
        color: {C["muted"]} !important;
        font-size: 0.78rem;
        margin-top: 0.35rem;
    }}
    .book-title {{
        color: {C["ink"]} !important;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1rem;
        font-weight: 700;
    }}
    hr {{
        border-color: {C["border"]};
    }}
    footer {{
        visibility: hidden;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)
# ==================================================
# HEADER
# ==================================================
st.markdown(
    '<div class="eyebrow">YOUR PERSONAL READING PROJECT ✦</div>',
    unsafe_allow_html=True,
)
st.title("Reader Insights")
st.markdown(
    """

    <div class="subtitle">

        A little universe of the books you read, the stories you keep,

        and the patterns that make your reading life yours.

    </div>

    """,
    unsafe_allow_html=True,
)
# ==================================================
# LOAD DATA
# ==================================================
df = None
if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        st.error(f"Could not read this CSV file: {exc}")
        st.stop()
# ==================================================
# EMPTY STATE AND VALIDATION
# ==================================================
if df is None:
    st.markdown(
        f"""
        <div class="panel">
            <h3 style="color:{C["ink"]};">
                Your reading universe starts here ✦
            </h3>
            <p style="color:{C["muted"]};">
                Upload your reading-history CSV using the sidebar.
            </p>
            <p style="color:{C["ink"]};">
                Explore your collection, discover reading patterns,
                and search your book records.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()
if df.empty:
    st.warning("This CSV contains no book records.")
    st.stop()
if "Title" not in df.columns:
    st.error(
        "This file does not contain a 'Title' column. "
        "Please upload your reading-history CSV export."
    )
    st.stop()
# ==================================================
# DATA PREPARATION
# ==================================================
df, detected_source = normalize_reading_export(df)
st.caption(f"Detected reading platform: {detected_source}")
# Normalize blank text cells to missing values.
for col in df.select_dtypes(include=["object", "string"]).columns:
    df[col] = df[col].replace(r"^\s*$", pd.NA, regex=True)
status = (
    get_column(df, "Read Status", "Unknown")
    .fillna("Unknown")
    .astype(str)
    .str.strip()
)
normalized_status = status.str.lower()
read_mask = normalized_status.eq("read")
df["_rating"] = pd.to_numeric(
    get_column(df, "Star Rating"),
    errors="coerce",
)
df["_last_read_date"] = parse_reading_dates(
    get_column(df, "Last Date Read")
)
df["_date_added"] = parse_reading_dates(
    get_column(df, "Date Added")
)
total_books = len(df)
books_read = int(read_mask.sum())
to_read = int(normalized_status.eq("to-read").sum())
currently_reading = int(
    normalized_status.eq("currently-reading").sum()
)
ratings = df["_rating"].dropna()
average_rating = ratings.mean() if not ratings.empty else None
dated_books = df["_last_read_date"].notna().sum()
# ==================================================
# OVERVIEW
# ==================================================
if page == "Overview":
    section_label("YOUR COLLECTION", C["primary"])
    st.subheader("The big picture")
    cols = st.columns(4)
    with cols[0]:
        metric_card(
            "Total books",
            f"{total_books:,}",
            "Books in your export",
            C,
        )
    with cols[1]:
        metric_card(
            "Books read",
            f"{books_read:,}",
            "Marked as read",
            C,
        )
    with cols[2]:
        metric_card(
            "On your TBR",
            f"{to_read:,}",
            "Waiting to be read",
            C,
        )
    with cols[3]:
        rating_text = (
            f"{average_rating:.2f} / 5"
            if average_rating is not None
            else "—"
        )
        metric_card(
            "Average rating",
            rating_text,
            f"{len(ratings)} rated books",
            C,
        )
    st.markdown("")
    left, right = st.columns([1, 1.35], gap="large")
    with left:
        section_label("READING STATUS", C["primary"])
        st.subheader("Where things stand")
        counts = (
            status.value_counts()
            .rename_axis("Status")
            .reset_index(name="Books")
        )
        fig = px.pie(
            counts,
            names="Status",
            values="Books",
            hole=0.67,
            color_discrete_sequence=[
                C["primary"],
                C["secondary"],
                C["accent"],
                C["gold"],
                C["muted"],
            ],
        )
        fig.update_traces(
            textposition="inside",
            textinfo="percent",
            marker=dict(line=dict(color=C["panel"], width=3)),
        )
        fig.add_annotation(
            text=(
                f"<b>{total_books}</b>"
                "<br><span style='font-size:11px'>books</span>"
            ),
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=21, color=C["ink"]),
        )
        st.plotly_chart(
            style_chart(fig, C, 350),
            use_container_width=True,
        )
    with right:
        section_label("COLLECTION GROWTH", C["primary"])
        st.subheader("When books joined your shelves")
        dates = df["_date_added"].dropna()
        if not dates.empty:
            yearly = (
                dates.dt.year.value_counts()
                .sort_index()
                .rename_axis("Year")
                .reset_index(name="Books")
            )
            fig = px.bar(
                yearly,
                x="Year",
                y="Books",
                text="Books",
                color_discrete_sequence=[C["secondary"]],
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(showlegend=False)
            st.plotly_chart(
                style_chart(fig, C, 350),
                use_container_width=True,
            )
        else:
            st.info("No valid Date Added values were found.")
    st.divider()
    section_label("RECENTLY ADDED", C["primary"])
    st.subheader("New arrivals")
    recent = (
        df.dropna(subset=["_date_added"])
        .sort_values("_date_added", ascending=False)
        .head(5)
    )
    if recent.empty:
        st.info("There are no valid addition dates in this export.")
    else:
        for _, row in recent.iterrows():
            title = safe_text(row.get("Title", "Untitled"))
            author = safe_text(row.get("Authors", "Unknown author"))
            date = row["_date_added"].strftime("%b %d, %Y")
            st.markdown(
                f"""
                <div class="panel" style="margin-bottom:9px;
                     display:flex;justify-content:space-between;
                     align-items:center;gap:12px;">
                    <div>
                        <div class="book-title">{title}</div>
                        <div style="color:{C["muted"]};font-size:0.85rem;">
                            {author}
                        </div>
                    </div>
                    <div style="color:{C["primary"]};white-space:nowrap;
                                font-size:0.82rem;">
                        {date}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
# ==================================================
# READING DNA
# ==================================================
elif page == "Reading DNA":
    section_label("YOUR READING DNA", C["primary"])
    st.subheader("The shape of your taste")
    st.markdown(
        """

        <div class="subtitle">

            Patterns from your ratings, authors, formats, and the information

            recorded in your reading history.

        </div>

        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns(2, gap="large")
    # Rating profile
    with left:
        section_label("RATING PROFILE", C["primary"])
        st.subheader("How you rate books")
        if ratings.empty:
            st.info("There are no numeric ratings in this dataset.")
        else:
            rating_counts = (
                ratings.value_counts()
                .sort_index()
                .rename_axis("Rating")
                .reset_index(name="Books")
            )
            fig = px.bar(
                rating_counts,
                x="Rating",
                y="Books",
                text="Books",
                color_discrete_sequence=[C["primary"]],
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(showlegend=False)
            st.plotly_chart(
                style_chart(fig, C, 350),
                use_container_width=True,
            )
            st.caption(
                f"You rated {len(ratings)} books. "
                f"Your average is {ratings.mean():.2f} out of 5."
            )
    # Authors
    with right:
        section_label("FAMILIAR NAMES", C["secondary"])
        st.subheader("Authors in your collection")
        authors = get_column(df, "Authors")
        authors = authors.dropna().astype(str).str.strip()
        authors = authors[authors.ne("")]
        if authors.empty:
            st.info("No author names were recorded.")
        else:
            top_authors = (
                authors.value_counts()
                .head(10)
                .rename_axis("Author")
                .reset_index(name="Books")
            )
            fig = px.bar(
                top_authors.sort_values("Books"),
                x="Books",
                y="Author",
                orientation="h",
                text="Books",
                color_discrete_sequence=[C["secondary"]],
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                showlegend=False,
                yaxis_title=None,
            )
            st.plotly_chart(
                style_chart(fig, C, 390),
                use_container_width=True,
            )
    st.divider()
    # Formats
    section_label("FORMAT PREFERENCES", C["gold"])
    st.subheader("Print, digital, or audio?")
    formats = (
        get_column(df, "Format", "Unknown")
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace("", "Unknown")
        .value_counts()
        .rename_axis("Format")
        .reset_index(name="Books")
    )
    if not formats.empty:
        fig = px.bar(
            formats,
            x="Format",
            y="Books",
            text="Books",
            color_discrete_sequence=[C["gold"]],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False)
        st.plotly_chart(
            style_chart(fig, C, 300),
            use_container_width=True,
        )
    st.divider()
    # Data coverage
    section_label("DATA COVERAGE", C["accent"])
    st.subheader("What your export tells us")
    useful_columns = [
        c for c in [
            "Star Rating",
            "Review",
            "Moods",
            "Pace",
            "Tags",
            "Character- or Plot-Driven?",
            "Strong Character Development?",
            "Loveable Characters?",
            "Diverse Characters?",
            "Flawed Characters?",
        ]
        if c in df.columns
    ]
    if useful_columns:
        coverage = pd.DataFrame({
            "Field": useful_columns,
            "Books with data": [
                int(filled_mask(df[c]).sum())
                for c in useful_columns
            ],
        })
        coverage["Coverage (%)"] = (
            coverage["Books with data"] / len(df) * 100
        ).round(1)
        coverage = coverage.sort_values("Coverage (%)")
        fig = px.bar(
            coverage,
            x="Coverage (%)",
            y="Field",
            orientation="h",
            text="Coverage (%)",
            color_discrete_sequence=[C["accent"]],
            range_x=[0, 110],
        )
        fig.update_traces(
            texttemplate="%{text:.1f}%",
            textposition="outside",
            cliponaxis=False,
        )
        fig.update_layout(
            showlegend=False,
            yaxis_title=None,
        )
        st.plotly_chart(
            style_chart(fig, C, 390),
            use_container_width=True,
        )
        st.caption(
            "Empty fields are treated as missing data, not as evidence "
            "of a reading preference."
        )
    else:
        st.info("No data-coverage fields were found.")
# ==================================================
# READING TIMELINE
# ==================================================
elif page == "Reading Timeline":
    section_label("YOUR READING TIMELINE", C["primary"])
    st.subheader("When did your reading happen?")
    st.markdown(
        """

        <div class="subtitle">

            Explore the dates recorded in Last Date Read to see how your

            reading history is distributed across months and years.

        </div>

        """,
        unsafe_allow_html=True,
    )
    dated = df.dropna(subset=["_last_read_date"]).copy()
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card(
            "Books with dates",
            f"{len(dated):,}",
            "Records with a valid Last Date Read",
            C,
        )
    with c2:
        metric_card(
            "Books without dates",
            f"{total_books - len(dated):,}",
            "Not included in the timeline",
            C,
        )
    with c3:
        coverage_pct = (
            len(dated) / total_books * 100 if total_books else 0
        )
        metric_card(
            "Date coverage",
            f"{coverage_pct:.1f}%",
            "Share of all book records",
            C,
        )
    st.divider()
    if dated.empty:
        st.warning(
            "No valid Last Date Read values were found. "
            "Check that your CSV contains a Last Date Read column "
            "with recognizable dates."
        )
    else:
        view = st.radio(
            "Timeline interval",
            ["Monthly", "Yearly"],
            horizontal=True,
        )
        if view == "Monthly":
            timeline = make_monthly_data(dated)
            fig = px.bar(
                timeline,
                x="Month",
                y="Books",
                text="Books",
                color_discrete_sequence=[C["primary"]],
                labels={
                    "Month": "Last read month",
                    "Books": "Book records",
                },
                hover_data={"Month": "|%B %Y"},
            )
            fig.update_traces(
                textposition="outside",
                marker_line_width=0,
            )
            fig.update_xaxes(
                tickformat="%b\n%Y",
                dtick="M1",
            )
            fig.update_layout(
                showlegend=False,
                xaxis_title="Month",
                yaxis_title="Book records",
            )
            st.plotly_chart(
                style_chart(fig, C, 420),
                use_container_width=True,
            )
        else:
            timeline = make_yearly_data(dated)
            fig = px.bar(
                timeline,
                x="Year",
                y="Books",
                text="Books",
                color_discrete_sequence=[C["secondary"]],
                labels={
                    "Year": "Last read year",
                    "Books": "Book records",
                },
            )
            fig.update_traces(
                textposition="outside",
                marker_line_width=0,
            )
            fig.update_layout(
                showlegend=False,
                xaxis_title="Year",
                yaxis_title="Book records",
            )
            st.plotly_chart(
                style_chart(fig, C, 380),
                use_container_width=True,
            )
        # Monthly/yearly data table
        st.divider()
        section_label("TIMELINE DATA", C["primary"])
        st.subheader("Explore the counts")
        if view == "Monthly":
            display_timeline = timeline.copy()
            display_timeline["Month"] = (
                display_timeline["Month"].dt.strftime("%B %Y")
            )
        else:
            display_timeline = timeline.copy()
        st.dataframe(
            display_timeline,
            use_container_width=True,
            hide_index=True,
        )
        csv_timeline = timeline.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Export timeline data as CSV",
            data=csv_timeline,
            file_name="reader_insights_timeline.csv",
            mime="text/csv",
        )
        st.info(
            "Important: this chart counts book records by their last "
            "recorded reading date. It does not count every reading "
            "session or every reread. Missing dates are excluded."
        )
# ==================================================
# TASTE ANALYSIS
# ==================================================
elif page == "Taste Analysis":
    section_label("TASTE ANALYSIS", C["accent"])
    st.subheader("What patterns appear in your ratings?")
    st.markdown(
        """

        <div class="subtitle">

            Compare your recorded ratings with moods, pacing, and

            character-versus-plot preferences. These are associations

            in your dataset, not proof of cause and effect.

        </div>

        """,
        unsafe_allow_html=True,
    )
    rated_df = df[df["_rating"].notna()].copy()
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card(
            "Rated books",
            f"{len(rated_df):,}",
            "Records with numeric ratings",
            C,
        )
    with c2:
        metric_card(
            "Unrated books",
            f"{total_books - len(rated_df):,}",
            "Not used in rating comparisons",
            C,
        )
    with c3:
        rating_coverage = (
            len(rated_df) / total_books * 100 if total_books else 0
        )
        metric_card(
            "Rating coverage",
            f"{rating_coverage:.1f}%",
            "Share of all book records",
            C,
        )
    st.divider()
    if rated_df.empty:
        st.warning(
            "No numeric ratings were found. Taste Analysis needs "
            "Star Rating values to compare categories."
        )
    else:
        st.markdown(
            "**Choose a characteristic to investigate**"
        )
        available_fields = []
        for col in [
            "Moods",
            "Pace",
            "Character- or Plot-Driven?",
            "Tags",
        ]:
            if col in df.columns and filled_mask(df[col]).any():
                available_fields.append(col)
        if not available_fields:
            st.warning(
                "No populated Moods, Pace, Character- or Plot-Driven?, "
                "or Tags columns were found."
            )
        else:
            selected_field = st.selectbox(
                "Compare ratings by",
                available_fields,
                format_func=lambda x: {
                    "Moods": "Mood",
                    "Pace": "Pacing",
                    "Character- or Plot-Driven?": (
                        "Character-driven vs. plot-driven"
                    ),
                    "Tags": "Tags",
                }.get(x, x),
            )
            split_multi = selected_field in ["Moods", "Tags"]
            analysis = category_rating_data(
                df,
                selected_field,
                split_multi=split_multi,
            )
            if analysis.empty:
                st.info(
                    "There are no rated books with usable values "
                    "for this characteristic."
                )
            else:
                # Small groups are still displayed, but clearly flagged.
                analysis["Sample size"] = analysis["Rated Books"].apply(
                    lambda n: (
                        "Small sample" if n < 5 else "5+ books"
                    )
                )
                analysis["Average Rating"] = analysis[
                    "Average Rating"
                ].round(2)
                fig = px.bar(
                    analysis.sort_values("Average Rating"),
                    x="Average Rating",
                    y="Category",
                    orientation="h",
                    text="Average Rating",
                    color_discrete_sequence=[C["primary"]],
                    range_x=[0, 5.8],
                    hover_data=["Rated Books", "Sample size"],
                    labels={
                        "Average Rating": "Average rating / 5",
                        "Category": "Category",
                        "Rated Books": "Rated books",
                    },
                )
                fig.update_traces(
                    texttemplate="%{text:.2f}",
                    textposition="outside",
                    cliponaxis=False,
                )
                fig.update_layout(
                    showlegend=False,
                    xaxis_title="Average rating (out of 5)",
                    yaxis_title=None,
                )
                st.plotly_chart(
                    style_chart(fig, C, max(340, 42 * len(analysis))),
                    use_container_width=True,
                )
                st.caption(
                    "Each bar shows the average rating for books with "
                    "that category. For Moods and Tags, a book can belong "
                    "to more than one category."
                )
                st.divider()
                section_label("CATEGORY BREAKDOWN", C["secondary"])
                st.subheader("How much data supports each result?")
                display_analysis = analysis[
                    [
                        "Category",
                        "Average Rating",
                        "Rated Books",
                        "Sample size",
                    ]
                ].sort_values(
                    "Average Rating",
                    ascending=False,
                )
                st.dataframe(
                    display_analysis,
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(
                    "Groups with fewer than five rated books are marked "
                    "as small samples. Treat their averages as tentative, "
                    "because a few ratings can change them substantially."
                )
                csv_analysis = analysis.to_csv(
                    index=False
                ).encode("utf-8-sig")
                st.download_button(
                    "Export this analysis as CSV",
                    data=csv_analysis,
                    file_name="reader_insights_taste_analysis.csv",
                    mime="text/csv",
                )
    st.divider()
    st.markdown("#### How to interpret these results")
    st.markdown(
        """

        - A higher average rating means the books in that category

          received higher ratings in this dataset.

        - It does not establish that the category caused the rating.

        - Missing ratings and missing category values are excluded

          from the corresponding comparison.

        - A small number of rated books makes the average less stable.

        """
    )
# ==================================================
# MY LIBRARY
# ==================================================
elif page == "My Library":
    section_label("YOUR BOOKSHELF", C["primary"])
    st.subheader("The whole collection")
    st.markdown(
        """

        <div class="subtitle">

            Search, filter, and explore your book records.

        </div>

        """,
        unsafe_allow_html=True,
    )
    search = st.text_input(
        "Search by title or author",
        placeholder="Try a book title or an author name...",
    )
    filtered = df.copy()
    if search.strip():
        title_match = filtered["Title"].astype(str).str.contains(
            search,
            case=False,
            na=False,
            regex=False,
        )
        authors = get_column(filtered, "Authors")
        author_match = authors.astype(str).str.contains(
            search,
            case=False,
            na=False,
            regex=False,
        )
        filtered = filtered[title_match | author_match]
    filter_cols = st.columns(2)
    with filter_cols[0]:
        if "Read Status" in df.columns:
            status_options = ["All"] + sorted(
                status.unique().tolist()
            )
        else:
            status_options = ["All"]
        chosen_status = st.selectbox(
            "Reading status",
            status_options,
        )
    with filter_cols[1]:
        if "Format" in df.columns:
            format_values = (
                df["Format"]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .replace("", "Unknown")
                .unique()
                .tolist()
            )
            format_options = ["All"] + sorted(format_values)
        else:
            format_options = ["All"]
        chosen_format = st.selectbox(
            "Book format",
            format_options,
        )
    if chosen_status != "All" and "Read Status" in filtered.columns:
        filtered = filtered[
            filtered["Read Status"]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
            .eq(chosen_status)
        ]
    if chosen_format != "All" and "Format" in filtered.columns:
        filtered = filtered[
            filtered["Format"]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
            .replace("", "Unknown")
            .eq(chosen_format)
        ]
    st.caption(f"Showing {len(filtered)} of {len(df)} books")
    preferred_columns = [
        "Title",
        "Authors",
        "Read Status",
        "Star Rating",
        "Format",
        "Date Added",
        "Last Date Read",
        "Tags",
        "Review",
    ]
    visible_columns = [
        col for col in preferred_columns
        if col in filtered.columns
    ]
    st.dataframe(
        filtered[visible_columns],
        use_container_width=True,
        hide_index=True,
        height=500,
    )
    csv_bytes = filtered.to_csv(
        index=False
    ).encode("utf-8-sig")
    st.download_button(
        "Export filtered books as CSV",
        data=csv_bytes,
        file_name="reader_insights_filtered.csv",
        mime="text/csv",
    )
# ==================================================
# FOOTER
# ==================================================
st.divider()
st.markdown(
    f"""
    <div style="text-align:center;color:{C["muted"]};
                font-size:0.72rem;letter-spacing:1.5px;">
        READER INSIGHTS &nbsp; ✦ &nbsp; YOUR PERSONAL READING UNIVERSE
    </div>
    """,
    unsafe_allow_html=True,
)
