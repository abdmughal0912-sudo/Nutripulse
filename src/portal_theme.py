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
        .np-live-banner{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:.25rem 1rem;
          margin:.35rem 0 1rem;padding:.9rem 1.05rem;border:1px solid rgba(190,242,100,.38);border-radius:18px;
          background:linear-gradient(110deg,rgba(20,83,45,.88),rgba(8,47,43,.84),rgba(67,56,202,.20));
          box-shadow:0 16px 46px rgba(16,185,129,.12),inset 0 1px 0 rgba(255,255,255,.10)}
        .np-live-banner span{grid-row:1/3;display:flex;align-items:center;gap:.55rem;color:#d9f99d;font-size:.74rem;font-weight:900;letter-spacing:.13em}
        .np-live-banner i,.np-live-practitioner i{width:.7rem;height:.7rem;border-radius:999px;background:#bef264;box-shadow:0 0 0 .28rem rgba(190,242,100,.12),0 0 18px #bef264;animation:np-live-pulse 1.8s ease-in-out infinite}
        .np-live-banner strong{color:#fff;font-size:1rem}.np-live-banner small{color:#b8ccc5!important;font-size:.78rem!important}
        .np-live-practitioner{display:flex;align-items:center;gap:.75rem;margin:.55rem 0 .9rem;padding:.75rem .8rem;border:1px solid rgba(190,242,100,.24);border-radius:15px;background:rgba(22,101,52,.18)}
        .np-live-practitioner div{display:grid}.np-live-practitioner strong{color:#d9f99d;font-size:.72rem;letter-spacing:.09em}.np-live-practitioner small{color:#9fb7ae!important;font-size:.7rem!important}
        .np-care-presence{display:grid;gap:.22rem;justify-items:end;text-align:right;margin:-.2rem 0 .7rem;padding:.7rem .8rem;border:1px solid rgba(190,242,100,.30);border-radius:15px;background:rgba(22,101,52,.18)}
        .np-care-presence span{display:flex;align-items:center;gap:.48rem;color:#d9f99d;font-size:.72rem;font-weight:900;letter-spacing:.08em}.np-care-presence i{width:.62rem;height:.62rem;border-radius:50%;background:#bef264;box-shadow:0 0 15px #bef264;animation:np-live-pulse 1.8s ease-in-out infinite}.np-care-presence small{color:#adc2ba!important;font-size:.7rem!important}.np-care-presence.offline{border-color:rgba(148,163,184,.22);background:rgba(51,65,85,.16)}.np-care-presence.offline span{color:#cbd5e1}.np-care-presence.offline i{background:#64748b;box-shadow:none;animation:none}
        .np-assistant-meta{margin:.2rem 0 .55rem;padding:.55rem .7rem;border-radius:12px;border:1px solid rgba(165,243,252,.15);background:rgba(165,243,252,.055);color:#a9c7bd;font-size:.75rem}
        .np-assistant-meta b{color:#cffafe}.np-assistant-safety{color:#fde68a!important}

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
        div:is([data-testid="column"],[data-testid="stColumn"]):has(.np-auth-card-marker){max-width:720px!important;padding:1.65rem 1.8rem 1.8rem!important;overflow:visible!important;border:1px solid rgba(207,250,254,.21);border-radius:24px;background:linear-gradient(145deg,rgba(18,43,36,.96),rgba(20,27,39,.95));box-shadow:0 36px 120px rgba(0,0,0,.42),inset 0 1px 0 rgba(255,255,255,.10);backdrop-filter:blur(24px)}
        .np-auth-card-marker{text-align:center;margin:.2rem auto 1.1rem;max-width:540px}
        .np-auth-card-marker>span,.np-reset-heading>span{color:#a5f3fc;font-size:.68rem;font-weight:900;letter-spacing:.18em}
        .np-auth-card-marker h1{margin:.35rem 0 .4rem!important;color:#fff;font-size:2.25rem!important;line-height:1.05!important}
        .np-auth-card-marker p{margin:0;color:#b9cbc5;font-size:.92rem!important;line-height:1.55!important}
        .np-reset-heading{padding:.8rem 0 .5rem}.np-reset-heading h3{margin:.35rem 0;color:#fff}.np-reset-heading p{margin:0;color:#a9bbb5;font-size:.88rem!important}
        div:is([data-testid="column"],[data-testid="stColumn"]):has(.np-auth-card-marker) .stTabs [data-baseweb="tab-list"]{justify-content:center;overflow-x:auto;scrollbar-width:none}
        div:is([data-testid="column"],[data-testid="stColumn"]):has(.np-auth-card-marker) .stTabs [data-baseweb="tab"]{font-size:.84rem;padding:.45rem .65rem;white-space:nowrap}
        div:is([data-testid="column"],[data-testid="stColumn"]):has(.np-auth-card-marker) .stTextInput input{min-height:2.7rem;font-size:1rem!important}
        div:is([data-testid="column"],[data-testid="stColumn"]):has(.np-auth-card-marker) .stButton>button{min-height:2.65rem}
        @keyframes np-portal-stars{0%{background-position:0 0,31px 48px,72px 19px,14px 96px;transform:translate3d(0,-8px,0)}50%{background-position:90px 34px,-25px 126px,145px -30px,-70px 162px;transform:translate3d(0,8px,0)}100%{background-position:180px 4px,-82px 72px,218px 34px,-154px 106px;transform:translate3d(0,-4px,0)}}
        @keyframes np-auth-stars{0%{background-position:0 0,18px 42px,65px 17px;transform:translate3d(-1.5%,0,0) rotate(-.4deg)}50%{background-position:78px 34px,-45px 115px,148px -29px;transform:translate3d(1.5%,-12px,0) rotate(.4deg)}100%{background-position:156px 6px,-108px 64px,231px 25px;transform:translate3d(-.5%,8px,0) rotate(-.2deg)}}
        @keyframes np-live-pulse{0%,100%{opacity:.72;transform:scale(.88)}50%{opacity:1;transform:scale(1.12)}}
        @media(max-width:720px){div[data-testid="stHorizontalBlock"]:has(.np-auth-card-marker){margin:1rem 0 2rem;display:block!important}div[data-testid="stHorizontalBlock"]:has(.np-auth-card-marker)>div:is([data-testid="column"],[data-testid="stColumn"]){display:none!important}div[data-testid="stHorizontalBlock"]:has(.np-auth-card-marker)>div:is([data-testid="column"],[data-testid="stColumn"]):has(.np-auth-card-marker){display:block!important;width:100%!important;max-width:none!important;padding:1.15rem!important;border-radius:20px}.np-auth-card-marker h1{font-size:1.9rem!important}.np-live-banner{grid-template-columns:1fr}.np-live-banner span{grid-row:auto}.np-live-banner strong,.np-live-banner small{padding-left:1.25rem}}
        @media(prefers-reduced-motion:reduce){.stApp:has(.np-portal-marker):after,.np-auth-starfield:before,.np-auth-starfield:after,.np-live-banner i,.np-live-practitioner i,.np-care-presence i{animation:none!important}}
        </style>
        """,
        unsafe_allow_html=True,
    )
