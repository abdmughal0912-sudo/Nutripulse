import base64
from pathlib import Path

import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --np-bg:#040806; --np-card:#0b1512; --np-card2:#101d19;
          --np-line:rgba(224,246,237,.13); --np-line-gold:rgba(216,179,91,.26);
          --np-text:#f8fbf9; --np-muted:#91a7a0; --np-lime:#bff56d;
          --np-cyan:#55e4d2; --np-violet:#b49aff; --np-orange:#ffb86b;
          --np-gold:#d8b35b; --np-champagne:#f3dfad; --np-danger:#ff6476;
        }
        html,body,[class*="css"] { font-family:Inter,"Segoe UI",sans-serif; }
        .stApp { background:
          radial-gradient(circle at 82% -10%,rgba(85,228,210,.13),transparent 30%),
          radial-gradient(circle at 15% 22%,rgba(216,179,91,.07),transparent 28%),
          radial-gradient(circle at 85% 88%,rgba(180,154,255,.06),transparent 24%),
          linear-gradient(145deg,#030705 0%,#06100d 45%,#040806 100%);
          color:var(--np-text); }
        .stApp:before { content:""; position:fixed; inset:0; pointer-events:none; opacity:.18;
          background-image:linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px);
          background-size:42px 42px; mask-image:linear-gradient(to bottom,black,transparent 78%); }
        [data-testid="stSidebar"] { background:linear-gradient(180deg,rgba(5,15,12,.99),rgba(4,9,7,.99));
          border-right:1px solid var(--np-line-gold); box-shadow:24px 0 70px rgba(0,0,0,.22); }
        [data-testid="stSidebar"] * { color:#dce9e5; }
        [data-testid="stSidebarNav"] { padding-top:0; }
        [data-testid="stSidebar"] [role="radiogroup"] label { padding:.28rem .45rem; border-radius:12px;
          transition:background .2s ease,transform .2s ease; }
        [data-testid="stSidebar"] [role="radiogroup"] label:hover { background:rgba(85,228,210,.055); transform:translateX(2px); }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background:linear-gradient(90deg,rgba(191,245,109,.14),rgba(85,228,210,.05));
          border:1px solid rgba(191,245,109,.13); box-shadow:inset 3px 0 0 var(--np-lime); }
        .block-container { max-width:1580px; padding:1.35rem 2.35rem 4rem; }
        h1,h2,h3 { letter-spacing:-.035em; }
        h1 { font-size:clamp(2.2rem,5vw,4.3rem)!important; line-height:1.02!important; }
        p, label, .stCaption { color:var(--np-muted); }
        div[data-testid="stMetric"], .np-card {
          background:linear-gradient(145deg,rgba(20,36,31,.88),rgba(7,17,14,.92));
          border:1px solid var(--np-line); border-radius:20px; padding:1rem 1.1rem;
          box-shadow:0 22px 70px rgba(0,0,0,.19),inset 0 1px 0 rgba(255,255,255,.035);
          backdrop-filter:blur(18px); transition:transform .22s ease,border-color .22s ease,box-shadow .22s ease;
        }
        div[data-testid="stMetric"]:hover { transform:translateY(-2px); border-color:var(--np-line-gold); box-shadow:0 28px 80px rgba(0,0,0,.28); }
        div[data-testid="stMetric"] label { color:var(--np-muted); text-transform:uppercase; letter-spacing:.08em; font-size:.7rem; }
        div[data-testid="stMetricValue"] { color:var(--np-text); font-size:1.75rem; text-shadow:0 0 24px rgba(85,228,210,.08); }
        .np-brand { display:flex; gap:.75rem; align-items:center; padding:.25rem .2rem 1.35rem; }
        .np-logo { width:42px; height:42px; border-radius:13px; display:grid; place-items:center;
          background:linear-gradient(135deg,var(--np-lime),var(--np-gold)); color:#07100f; font-weight:900;
          box-shadow:0 0 38px rgba(191,245,109,.18),inset 0 1px 0 rgba(255,255,255,.5); position:relative; }
        .np-logo:after { content:""; position:absolute; inset:-5px; border-radius:17px; border:1px solid rgba(216,179,91,.25); }
        .np-brand strong { display:block; font-size:1.05rem; letter-spacing:-.02em; color:white; }
        .np-brand small { color:var(--np-gold); text-transform:uppercase; letter-spacing:.16em; font-size:.57rem; }
        .np-eyebrow,.np-section-kicker { color:var(--np-gold); text-transform:uppercase; letter-spacing:.2em; font-weight:800; font-size:.62rem; margin-bottom:.65rem; }
        .np-hero { padding:2rem 1.8rem 2.1rem; margin:.75rem 0 1.4rem; position:relative; overflow:hidden;
          border:1px solid var(--np-line); border-radius:28px;
          background:linear-gradient(125deg,rgba(16,32,27,.88),rgba(7,16,13,.72));
          box-shadow:0 30px 90px rgba(0,0,0,.23),inset 0 1px 0 rgba(255,255,255,.035); backdrop-filter:blur(16px); }
        .np-hero:after { content:""; position:absolute; width:320px; height:320px; border-radius:50%; right:-120px; top:-170px;
          background:radial-gradient(circle,rgba(85,228,210,.16),transparent 68%); pointer-events:none; }
        .np-hero h1 { margin:.1rem 0 .9rem; }
        .np-hero h1 em { background:linear-gradient(90deg,var(--np-lime),var(--np-champagne)); background-clip:text; -webkit-background-clip:text;
          color:transparent; font-style:normal; font-weight:500; }
        .np-hero p { max-width:760px; line-height:1.75; }
        .np-hero.visual { min-height:390px; display:flex; flex-direction:column; justify-content:center;
          background-position:center; background-size:cover; border-color:rgba(243,223,173,.24);
          box-shadow:0 38px 120px rgba(0,0,0,.38),inset 0 1px 0 rgba(255,255,255,.06); }
        .np-hero.visual:after { width:520px; height:520px; right:-80px; top:-210px;
          background:radial-gradient(circle,rgba(216,179,91,.14),transparent 66%); }
        .np-hero.visual h1,.np-hero.visual p,.np-hero.visual .np-eyebrow,.np-hero.visual .np-badge { position:relative; z-index:1; }
        .np-hero.visual h1 { max-width:680px; text-shadow:0 4px 45px rgba(0,0,0,.95); }
        .np-hero.visual p { max-width:650px; color:#c8d7d1; text-shadow:0 3px 22px rgba(0,0,0,.95); }
        .np-badge { display:inline-flex; align-items:center; gap:.45rem; padding:.38rem .65rem;
          border-radius:999px; border:1px solid rgba(185,240,106,.19); color:var(--np-lime);
          background:linear-gradient(90deg,rgba(191,245,109,.08),rgba(216,179,91,.04)); font-size:.68rem; font-weight:700; }
        .np-dot { width:7px; height:7px; border-radius:50%; background:var(--np-lime); display:inline-block; box-shadow:0 0 12px var(--np-lime); }
        .np-panel { border:1px solid var(--np-line); border-radius:22px; padding:1.25rem;
          background:linear-gradient(145deg,rgba(18,35,31,.86),rgba(7,18,15,.9)); margin-bottom:1rem;
          box-shadow:0 24px 70px rgba(0,0,0,.17),inset 0 1px 0 rgba(255,255,255,.03); backdrop-filter:blur(18px); }
        .np-panel h3 { margin:.1rem 0 .25rem; }
        .np-panel p { font-size:.82rem; line-height:1.6; }
        .np-alert { display:flex; gap:.8rem; padding:.9rem 1rem; border-radius:14px;
          background:rgba(92,224,208,.06); border:1px solid rgba(92,224,208,.16); margin:.8rem 0; }
        .np-alert strong { color:#dcebe7; }
        .np-alert.warning { background:rgba(255,184,107,.07); border-color:rgba(255,184,107,.18); }
        .np-alert.danger { background:rgba(255,95,108,.07); border-color:rgba(255,95,108,.22); }
        .np-meal { display:grid; grid-template-columns:70px 1fr auto; gap:1rem; align-items:center;
          padding:.85rem 0; border-bottom:1px solid var(--np-line); }
        .np-meal:last-child { border-bottom:0; }
        .np-meal time { color:var(--np-cyan); font-size:.74rem; }
        .np-meal strong { color:white; display:block; }
        .np-meal small { color:var(--np-muted); }
        .np-meal b { color:var(--np-lime); }
        .np-food-card { min-height:210px; border:1px solid var(--np-line); border-radius:16px; padding:1rem;
          background:linear-gradient(145deg,rgba(17,34,31,.90),rgba(10,23,21,.92)); }
        .np-food-card .type { color:var(--np-cyan); font-size:.62rem; letter-spacing:.09em; text-transform:uppercase; }
        .np-food-card h4 { height:48px; overflow:hidden; margin:.65rem 0 .4rem; color:white; }
        .np-food-card .kcal { color:var(--np-lime); font-size:1.45rem; font-weight:800; }
        .np-food-card .macros { color:var(--np-muted); font-size:.7rem; line-height:1.65; }
        .np-classification { border:1px solid color-mix(in srgb,var(--result-color) 35%,transparent);
          border-left:5px solid var(--result-color); border-radius:16px; padding:1rem 1.1rem;
          margin:.8rem 0 1rem; background:linear-gradient(135deg,rgba(18,35,31,.98),rgba(9,22,19,.95)); }
        .np-classification span { color:var(--result-color); font-size:.62rem; font-weight:800; letter-spacing:.16em; }
        .np-classification h3 { margin:.35rem 0 .3rem; color:white; }
        .np-classification p { margin:0; line-height:1.55; }
        .np-vision-result { position:relative; overflow:hidden; padding:1.25rem 1.35rem; margin:.35rem 0 1rem;
          border:1px solid rgba(216,179,91,.24); border-radius:22px;
          background:linear-gradient(135deg,rgba(18,39,33,.96),rgba(7,18,15,.98));
          box-shadow:0 28px 80px rgba(0,0,0,.25),inset 0 1px 0 rgba(255,255,255,.04); }
        .np-vision-result:after { content:""; position:absolute; width:160px; height:160px; right:-70px; top:-80px;
          border-radius:50%; background:var(--np-gold); opacity:.08; filter:blur(50px); }
        .np-vision-result h2 { margin:.1rem 0 .35rem; color:white; }
        .np-vision-result p { margin:0; }
        .np-vision-result p strong { color:var(--np-champagne); }
        .np-verdict { display:inline-flex; align-items:center; gap:.55rem; margin-top:.85rem; padding:.45rem .65rem;
          border:1px solid rgba(191,245,109,.18); border-radius:999px; color:#dce9e4; font-size:.7rem;
          background:linear-gradient(90deg,rgba(191,245,109,.08),rgba(216,179,91,.05)); }
        .np-verdict span { color:#07100f; background:linear-gradient(105deg,var(--np-lime),var(--np-gold));
          border-radius:999px; padding:.22rem .48rem; font-weight:900; text-transform:uppercase; letter-spacing:.08em; font-size:.56rem; }
        .np-empty-vision { min-height:420px; display:flex; flex-direction:column; align-items:center; justify-content:center;
          text-align:center; padding:2rem; border:1px dashed rgba(216,179,91,.22); border-radius:24px;
          background:radial-gradient(circle at 50% 40%,rgba(85,228,210,.06),transparent 38%),rgba(8,20,16,.58); }
        .np-empty-vision>span { width:58px; height:58px; display:grid; place-items:center; margin-bottom:1rem; border-radius:19px;
          color:var(--np-gold); font-size:1.6rem; border:1px solid rgba(216,179,91,.25); box-shadow:0 0 45px rgba(216,179,91,.08); }
        .np-empty-vision h3 { color:#eef8f4; margin:.2rem 0 .5rem; }
        .np-empty-vision p { max-width:540px; line-height:1.65; }
        .np-source-card { border:1px solid var(--np-line); border-left:3px solid var(--np-cyan);
          border-radius:14px; padding:.85rem 1rem; margin:.65rem 0; background:rgba(13,29,26,.82); }
        .np-source-card span { color:var(--np-cyan); font-size:.58rem; font-weight:800; letter-spacing:.16em; }
        .np-source-card p { margin:.45rem 0 0; line-height:1.62; color:#c8d8d3; }
        div[data-testid="stImage"] img { border-radius:20px; border:1px solid var(--np-line);
          box-shadow:0 30px 85px rgba(0,0,0,.32),0 0 0 1px rgba(216,179,91,.04); }
        .np-footer { color:#60756f; font-size:.68rem; text-align:center; padding:2rem 0 0; }
        .stButton>button, .stDownloadButton>button {
          border-radius:13px; border:1px solid var(--np-line); background:linear-gradient(145deg,rgba(255,255,255,.055),rgba(255,255,255,.025));
          color:#e9f4f0; min-height:2.65rem; font-weight:700; box-shadow:0 10px 30px rgba(0,0,0,.12); transition:all .2s ease;
        }
        .stButton>button:hover, .stDownloadButton>button:hover { border-color:var(--np-line-gold); color:white; transform:translateY(-1px); box-shadow:0 16px 35px rgba(0,0,0,.2); }
        .stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"] {
          background:linear-gradient(105deg,var(--np-lime),#d7ee82 55%,var(--np-gold)); color:#07100f; border-color:rgba(216,179,91,.55);
          box-shadow:0 14px 35px rgba(191,245,109,.12);
        }
        .stButton>button[kind="primary"] *, .stDownloadButton>button[kind="primary"] * { color:#07100f!important; }
        .stTextInput input,.stNumberInput input,.stTextArea textarea,
        div[data-baseweb="select"]>div { background:rgba(8,20,16,.9)!important; border-color:var(--np-line)!important; color:white!important; border-radius:12px!important; }
        .stTextInput input:focus,.stNumberInput input:focus,.stTextArea textarea:focus { border-color:rgba(85,228,210,.45)!important; box-shadow:0 0 0 1px rgba(85,228,210,.12)!important; }
        div[data-testid="stFileUploader"] { border-radius:16px; border:1px dashed rgba(185,240,106,.25); padding:.8rem; background:rgba(185,240,106,.025); }
        .stTabs [data-baseweb="tab-list"] { gap:.4rem; }
        .stTabs [data-baseweb="tab"] { border-radius:12px; border:1px solid var(--np-line); padding:.5rem .8rem; background:rgba(255,255,255,.02); }
        .stTabs [aria-selected="true"] { background:linear-gradient(90deg,rgba(191,245,109,.11),rgba(216,179,91,.06)); color:var(--np-lime); border-color:var(--np-line-gold); }
        .np-command-bar { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.75rem 1rem; margin:.1rem 0 .3rem;
          border:1px solid var(--np-line); border-radius:16px; background:rgba(8,18,15,.72); backdrop-filter:blur(18px); box-shadow:0 16px 50px rgba(0,0,0,.13); }
        .np-command-bar>div:first-child { display:flex; align-items:center; gap:.55rem; }
        .np-command-bar b { color:#f6fbf8; font-size:.78rem; letter-spacing:.02em; }
        .np-command-bar small { color:var(--np-gold); font-size:.62rem; border-left:1px solid var(--np-line); padding-left:.55rem; }
        .np-command-orb { width:8px; height:8px; border-radius:50%; background:var(--np-cyan); box-shadow:0 0 16px var(--np-cyan); animation:np-pulse 2.4s infinite; }
        .np-command-status { display:flex; align-items:center; gap:.4rem; }
        .np-command-status span { padding:.28rem .55rem; border:1px solid var(--np-line); border-radius:999px; color:var(--np-muted); font-size:.58rem; text-transform:uppercase; letter-spacing:.08em; }
        .np-sidebar-alert { display:flex; gap:.65rem; align-items:center; margin:.2rem 0 .85rem; padding:.72rem .78rem; border-radius:14px;
          border:1px solid rgba(85,228,210,.15); background:rgba(85,228,210,.045); }
        .np-sidebar-alert>span { color:var(--np-cyan); text-shadow:0 0 14px var(--np-cyan); }
        .np-sidebar-alert strong { color:#eaf5f1; display:block; font-size:.74rem; }
        .np-sidebar-alert small { color:var(--np-muted)!important; font-size:.59rem; line-height:1.35; display:block; }
        .np-sidebar-alert.critical { border-color:rgba(255,100,118,.28); background:rgba(255,100,118,.07); }
        .np-sidebar-alert.critical>span { color:var(--np-danger); text-shadow:0 0 14px var(--np-danger); }
        .np-alert-card { --alert-color:var(--np-cyan); position:relative; overflow:hidden; margin:.75rem 0; padding:1.05rem 1.15rem;
          border:1px solid color-mix(in srgb,var(--alert-color) 26%,transparent); border-left:4px solid var(--alert-color); border-radius:18px;
          background:linear-gradient(120deg,color-mix(in srgb,var(--alert-color) 7%,rgba(10,23,19,.96)),rgba(7,17,14,.94));
          box-shadow:0 20px 60px rgba(0,0,0,.16),inset 0 1px 0 rgba(255,255,255,.025); }
        .np-alert-card:after { content:""; position:absolute; width:120px; height:120px; right:-55px; top:-60px; border-radius:50%; background:var(--alert-color); filter:blur(60px); opacity:.10; }
        .np-alert-card.critical { --alert-color:var(--np-danger); }
        .np-alert-card.high { --alert-color:var(--np-orange); }
        .np-alert-card.medium { --alert-color:var(--np-gold); }
        .np-alert-card.info { --alert-color:var(--np-cyan); }
        .np-alert-card-top { display:flex; justify-content:space-between; align-items:center; }
        .np-severity { color:var(--alert-color); font-size:.6rem; font-weight:900; text-transform:uppercase; letter-spacing:.18em; }
        .np-alert-state { color:var(--np-muted); font-size:.58rem; padding:.2rem .45rem; border:1px solid var(--np-line); border-radius:999px; }
        .np-alert-card h3 { color:#f7fbf9; margin:.45rem 0 .32rem; font-size:1.03rem; }
        .np-alert-card p { margin:0 0 .55rem; font-size:.79rem; line-height:1.55; color:#a8bbb5; }
        .np-alert-card small { color:#647b74; font-size:.62rem; }
        .np-alert-action { display:flex; flex-direction:column; gap:.14rem; margin:.7rem 0; padding:.65rem .75rem; border-radius:11px; background:rgba(255,255,255,.025); color:#b9cac4; font-size:.72rem; }
        .np-alert-action b { color:var(--alert-color); text-transform:uppercase; letter-spacing:.1em; font-size:.56rem; }
        .np-all-clear { display:flex; align-items:center; gap:.75rem; margin:.85rem 0 1.1rem; padding:.85rem 1rem; border-radius:16px;
          border:1px solid rgba(191,245,109,.16); background:linear-gradient(90deg,rgba(191,245,109,.055),rgba(85,228,210,.025)); }
        .np-all-clear>span { width:32px; height:32px; display:grid; place-items:center; border-radius:10px; background:rgba(191,245,109,.12); color:var(--np-lime); font-weight:900; }
        .np-all-clear strong { display:block; color:#edf8f3; font-size:.8rem; }
        .np-all-clear small { color:var(--np-muted); font-size:.65rem; display:block; }
        .np-command-note { min-height:2.65rem; display:flex; align-items:center; padding:.55rem .8rem; border:1px solid var(--np-line); border-radius:12px; color:var(--np-muted); font-size:.67rem; }
        .np-command-note b { color:var(--np-gold); margin-right:.25rem; }
        .np-status-pill { display:inline-block; padding:.3rem .55rem; border:1px solid var(--np-line-gold); border-radius:999px; color:var(--np-gold); font-size:.62rem; }
        .np-login-shell { max-width:1050px; margin:2.5rem auto 1.25rem; padding:2rem 2.2rem; display:grid;
          grid-template-columns:90px 1fr; gap:1.4rem; align-items:center; border:1px solid var(--np-line-gold); border-radius:30px;
          background:linear-gradient(135deg,rgba(18,38,31,.94),rgba(5,14,11,.96)); box-shadow:0 42px 130px rgba(0,0,0,.38),inset 0 1px 0 rgba(255,255,255,.05); }
        .np-login-mark { width:78px; height:78px; display:grid; place-items:center; border-radius:24px; color:#07100f; font-size:1.35rem; font-weight:950;
          background:linear-gradient(135deg,var(--np-lime),var(--np-champagne),var(--np-gold)); box-shadow:0 0 58px rgba(216,179,91,.18); }
        .np-login-shell span { color:var(--np-gold); font-size:.62rem; font-weight:900; letter-spacing:.2em; }
        .np-login-shell h1 { margin:.35rem 0 .55rem; font-size:clamp(2rem,4vw,3.5rem)!important; }
        .np-login-shell p { margin:0; max-width:760px; line-height:1.7; }
        .np-user-chip { display:flex; flex-direction:column; padding:.75rem .8rem; border:1px solid var(--np-line-gold); border-radius:15px;
          background:linear-gradient(120deg,rgba(216,179,91,.08),rgba(85,228,210,.035)); margin:.2rem 0 .65rem; }
        .np-user-chip span { color:var(--np-gold); font-size:.55rem; font-weight:900; letter-spacing:.16em; text-transform:uppercase; }
        .np-user-chip strong { color:#f7fbf9; font-size:.82rem; margin:.2rem 0 .05rem; }
        .np-user-chip small { color:var(--np-muted)!important; font-size:.62rem; }
        .np-message { margin:.7rem 0; padding:1rem 1.1rem; border:1px solid var(--np-line); border-radius:17px;
          background:linear-gradient(135deg,rgba(17,35,29,.9),rgba(7,18,15,.94)); box-shadow:0 18px 55px rgba(0,0,0,.13); }
        .np-message span { color:var(--np-cyan); font-size:.57rem; font-weight:850; letter-spacing:.1em; text-transform:uppercase; }
        .np-message h4 { color:#f4faf7; margin:.35rem 0 .3rem; }
        .np-message p { color:#afc1bb; margin:.2rem 0 .55rem; line-height:1.6; }
        .np-message small { color:#61776f; font-size:.58rem; }
        .np-meal-completed { opacity:.72; border-left:3px solid var(--np-lime); padding-left:.65rem; }
        .np-meal-completed strong { text-decoration:line-through; text-decoration-color:rgba(191,245,109,.42); }
        .np-meal-skipped { opacity:.58; border-left:3px solid var(--np-orange); padding-left:.65rem; }
        @keyframes np-pulse { 0%,100%{opacity:.55;transform:scale(.88)} 50%{opacity:1;transform:scale(1.15)} }
        hr { border-color:var(--np-line); }
        @media(max-width:900px) { .np-command-status span:nth-child(n+2){display:none}.np-command-bar{align-items:flex-start}.np-hero{padding:1.4rem 1.1rem} }
        @media(max-width:720px) { .block-container{padding:.8rem .75rem 3rem}.np-meal{grid-template-columns:55px 1fr}.np-meal>span{display:none}.np-command-bar small{display:none} }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="np-brand">
          <div class="np-logo">NP</div>
          <div><strong>NutriPulse AI</strong><small>Clinical Nutrition Studio</small></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero(
    eyebrow: str,
    title: str,
    description: str,
    badge: str | None = None,
    image_path: str | Path | None = None,
) -> None:
    badge_html = f'<span class="np-badge"><i class="np-dot"></i>{badge}</span>' if badge else ""
    hero_class = "np-hero"
    hero_style = ""
    if image_path:
        try:
            encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
            hero_class += " visual"
            hero_style = (
                ' style="background-image:linear-gradient(90deg,rgba(2,8,6,.98) 0%,'
                'rgba(2,8,6,.90) 34%,rgba(2,8,6,.28) 68%,rgba(2,8,6,.12) 100%),'
                f'url(data:image/jpeg;base64,{encoded})"'
            )
        except OSError:
            pass
    st.markdown(
        f"""
        <section class="{hero_class}"{hero_style}>
          <div class="np-eyebrow">{eyebrow}</div>
          <h1>{title}</h1>
          <p>{description}</p>
          {badge_html}
        </section>
        """,
        unsafe_allow_html=True,
    )


def footer() -> None:
    st.markdown(
        '<div class="np-footer">Clinical decision support only — not a diagnosis, medicine prescription or emergency service.</div>',
        unsafe_allow_html=True,
    )
