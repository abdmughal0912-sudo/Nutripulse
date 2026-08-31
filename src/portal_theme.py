from __future__ import annotations

import streamlit as st


def apply_portal_theme() -> None:
    """Apply readable pastel portal accents, compact authentication, and star-wave motion."""
    st.markdown(
        """
        <style>
        .np-portal-marker{display:none}
        .stApp:has(.np-portal-marker){
          background:
            radial-gradient(circle at 8% 12%,rgba(165,243,252,.16),transparent 25%),
            radial-gradient(circle at 88% 18%,rgba(216,180,254,.14),transparent 27%),
            radial-gradient(circle at 72% 82%,rgba(253,230,138,.11),transparent 27%),
            radial-gradient(circle at 22% 78%,rgba(187,247,208,.12),transparent 25%),
            linear-gradient(145deg,#06100d 0%,#091712 48%,#07110f 100%)!important;
        }
        .stApp:has(.np-portal-marker):after{
          content:"";position:fixed;z-index:0;inset:0;pointer-events:none;opacity:.44;
          background-image:
            radial-gradient(circle,#cffafe 0 1px,transparent 1.8px),
            radial-gradient(circle,#e9d5ff 0 1.2px,transparent 2px),
            radial-gradient(circle,#fef3c7 0 1px,transparent 1.8px),
            radial-gradient(circle,#d9f99d 0 .9px,transparent 1.7px);
          background-size:92px 92px,137px 137px,173px 173px,211px 211px;
          background-position:0 0,31px 48px,72px 19px,14px 96px;
          animation:np-portal-stars 18s ease-in-out infinite alternate;
          filter:drop-shadow(0 0 5px rgba(207,250,254,.42));
        }
        .stApp:has(.np-portal-marker) [data-testid="stMainBlockContainer"]{position:relative;z-index:1}
        .stApp:has(.np-portal-marker) [data-testid="stSidebar"]{
          background:linear-gradient(180deg,rgba(13,32,27,.98),rgba(8,20,17,.99));
          border-right:1px solid rgba(207,250,254,.18);
        }
        .stApp:has(.np-portal-marker) div[data-testid="stMetric"],
        .stApp:has(.np-portal-marker) .np-card,
        .stApp:has(.np-portal-marker) .np-panel{
          background:linear-gradient(145deg,rgba(225,250,244,.105),rgba(216,180,254,.055));
          border-color:rgba(207,250,254,.20);
          box-shadow:0 22px 70px rgba(0,0,0,.19),inset 0 1px 0 rgba(255,255,255,.085);
        }
        .stApp:has(.np-portal-marker) .np-hero{
          background:
            radial-gradient(circle at 86% 20%,rgba(216,180,254,.12),transparent 26%),
            linear-gradient(125deg,rgba(30,58,49,.90),rgba(11,27,22,.91));
          border-color:rgba(253,230,138,.21);
        }
        .stApp:has(.np-portal-marker) .np-alert-card,
        .stApp:has(.np-portal-marker) .np-message,
        .stApp:has(.np-portal-marker) .np-food-card,
        .stApp:has(.np-portal-marker) .np-vision-result{
          background:linear-gradient(135deg,rgba(229,255,248,.095),rgba(196,181,253,.05));
          border-color:rgba(224,231,255,.17);
        }
        .stApp:has(.np-portal-marker) p,
        .stApp:has(.np-portal-marker) label,
        .stApp:has(.np-portal-marker) li,
        .stApp:has(.np-portal-marker) [data-testid="stMarkdownContainer"] p{
          font-size:.96rem!important;line-height:1.62!important;
        }
        .stApp:has(.np-portal-marker) .stCaption,
        .stApp:has(.np-portal-marker) [data-testid="stCaptionContainer"],
        .stApp:has(.np-portal-marker) small{font-size:.78rem!important;line-height:1.5!important}
        .stApp:has(.np-portal-marker) .np-panel p,
        .stApp:has(.np-portal-marker) .np-alert-card p,
        .stApp:has(.np-portal-marker) .np-message p,
        .stApp:has(.np-portal-marker) .np-food-card .macros{font-size:.9rem!important}
        .stApp:has(.np-portal-marker) [data-testid="stSidebar"] label p{font-size:.9rem!important}
        .stApp:has(.np-portal-marker) .np-eyebrow,
        .stApp:has(.np-portal-marker) .np-section-kicker,
        .stApp:has(.np-portal-marker) .np-severity{font-size:.71rem!important}

        .np-auth-starfield{position:fixed;z-index:0;inset:0;pointer-events:none;overflow:hidden;
          background:
            radial-gradient(circle at 15% 22%,rgba(191,245,109,.11),transparent 24%),
            radial-gradient(circle at 84% 32%,rgba(165,243,252,.12),transparent 24%),
            radial-gradient(circle at 60% 88%,rgba(216,180,254,.10),transparent 26%)}
        .np-auth-starfield:before,.np-auth-starfield:after{content:"";position:absolute;inset:-10%;opacity:.62;
          background-image:radial-gradient(circle,#cffafe 0 1.2px,transparent 2px),radial-gradient(circle,#fef3c7 0 1px,transparent 1.8px),radial-gradient(circle,#e9d5ff 0 1.1px,transparent 1.9px);
          background-size:84px 84px,133px 133px,189px 189px;animation:np-auth-stars 15s ease-in-out infinite alternate}
        .np-auth-starfield:after{opacity:.35;transform:scale(1.16);animation-duration:22s;animation-direction:alternate-reverse}
        div[data-testid="stHorizontalBlock"]:has(.np-auth-card-marker){position:relative;z-index:1;align-items:flex-start;min-height:0!important;margin:2.3rem 0 4rem;gap:1rem!important}
        div[data-testid="column"]:has(.np-auth-card-marker){max-width:720px!important;padding:1.65rem 1.8rem 1.8rem!important;overflow:visible!important;border:1px solid rgba(207,250,254,.21);border-radius:24px;background:linear-gradient(145deg,rgba(18,43,36,.96),rgba(20,27,39,.95));box-shadow:0 36px 120px rgba(0,0,0,.42),inset 0 1px 0 rgba(255,255,255,.10);backdrop-filter:blur(24px)}
        .np-auth-card-marker{text-align:center;margin:.2rem auto 1.1rem;max-width:540px}
        .np-auth-card-marker>span,.np-reset-heading>span{color:#a5f3fc;font-size:.68rem;font-weight:900;letter-spacing:.18em}
        .np-auth-card-marker h1{margin:.35rem 0 .4rem!important;color:#fff;font-size:2.25rem!important;line-height:1.05!important}
        .np-auth-card-marker p{margin:0;color:#b9cbc5;font-size:.92rem!important;line-height:1.55!important}
        .np-reset-heading{padding:.8rem 0 .5rem}.np-reset-heading h3{margin:.35rem 0;color:#fff}.np-reset-heading p{margin:0;color:#a9bbb5;font-size:.88rem!important}
        div[data-testid="column"]:has(.np-auth-card-marker) .stTabs [data-baseweb="tab-list"]{justify-content:center;overflow-x:auto;scrollbar-width:none}
        div[data-testid="column"]:has(.np-auth-card-marker) .stTabs [data-baseweb="tab"]{font-size:.84rem;padding:.45rem .65rem;white-space:nowrap}
        div[data-testid="column"]:has(.np-auth-card-marker) .stTextInput input{min-height:2.7rem;font-size:1rem!important}
        div[data-testid="column"]:has(.np-auth-card-marker) .stButton>button{min-height:2.65rem}
        @keyframes np-portal-stars{0%{background-position:0 0,31px 48px,72px 19px,14px 96px;transform:translate3d(0,-8px,0)}50%{background-position:90px 34px,-25px 126px,145px -30px,-70px 162px;transform:translate3d(0,8px,0)}100%{background-position:180px 4px,-82px 72px,218px 34px,-154px 106px;transform:translate3d(0,-4px,0)}}
        @keyframes np-auth-stars{0%{background-position:0 0,18px 42px,65px 17px;transform:translate3d(-1.5%,0,0) rotate(-.4deg)}50%{background-position:78px 34px,-45px 115px,148px -29px;transform:translate3d(1.5%,-12px,0) rotate(.4deg)}100%{background-position:156px 6px,-108px 64px,231px 25px;transform:translate3d(-.5%,8px,0) rotate(-.2deg)}}
        @media(max-width:720px){div[data-testid="stHorizontalBlock"]:has(.np-auth-card-marker){margin:1rem 0 2rem;display:block!important}div[data-testid="stHorizontalBlock"]:has(.np-auth-card-marker)>div[data-testid="column"]{display:none!important}div[data-testid="stHorizontalBlock"]:has(.np-auth-card-marker)>div[data-testid="column"]:has(.np-auth-card-marker){display:block!important;width:100%!important;max-width:none!important;padding:1.15rem!important;border-radius:20px}.np-auth-card-marker h1{font-size:1.9rem!important}}
        @media(prefers-reduced-motion:reduce){.stApp:has(.np-portal-marker):after,.np-auth-starfield:before,.np-auth-starfield:after{animation:none!important}}
        </style>
        """,
        unsafe_allow_html=True,
    )
