import streamlit as st

def load_css():
    """Load custom CSS for the application"""
    st.markdown("""
        <style>
        /* Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* Global Font Settings */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: #1E2A3A;
        }
        
        /* Main Container Background */
        .stApp {
            background-color: #F8F9FA;
        }
        
        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #1E2A3A;
            border-right: 1px solid #334155;
        }
        
        /* Sidebar Text Colors */
        section[data-testid="stSidebar"] .stMarkdown, 
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span {
            color: #E2E8F0 !important;
        }
        
        section[data-testid="stSidebar"] h1, 
        section[data-testid="stSidebar"] h2, 
        section[data-testid="stSidebar"] h3 {
             color: #FFFFFF !important;
        }
        
        /* Sidebar Logo/Header */
        section[data-testid="stSidebar"] .stMarkdown h1 {
            color: #FFFFFF !important;
            font-size: 1.8rem;
            font-weight: 800;
            text-align: center;
            margin-bottom: 2rem;
            text-shadow: 0 4px 8px rgba(0,0,0,0.3);
            background: linear-gradient(180deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 100%);
            padding: 15px 0;
            border-bottom: 1px solid #334155;
            letter-spacing: 1px;
        }
        
        /* Sidebar Navigation (Radio Buttons) */
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label {
            padding: 10px 15px;
            border-radius: 8px;
            transition: all 0.3s ease;
            margin-bottom: 4px;
            border: 1px solid transparent;
            color: #94A3B8 !important; /* Dimmed text for inactive */
        }
        
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
            background-color: rgba(255, 255, 255, 0.05);
            color: #FFFFFF !important;
            cursor: pointer;
        }
        
        /* Active Item Styling */
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-checked="true"] {
            background: linear-gradient(90deg, rgba(11, 79, 108, 0.9), rgba(11, 79, 108, 0.6));
            color: #FFFFFF !important;
            font-weight: 600;
            border: 1px solid rgba(56, 189, 248, 0.3);
            box-shadow: 0 0 15px rgba(56, 189, 248, 0.15); /* Soft Blue Glow */
            transform: translateX(4px);
        }

        /* Sidebar Buttons (Logout etc.) */
        section[data-testid="stSidebar"] button {
            background-color: rgba(255, 255, 255, 0.1) !important;
            color: #FFFFFF !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            transition: all 0.3s ease !important;
        }

        section[data-testid="stSidebar"] button:hover {
            background-color: #EF4444 !important; /* Red color for logout action */
            border-color: #EF4444 !important;
            color: #FFFFFF !important;
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3) !important;
        }
        
        /* Card Styling (Containers) */
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
            background-color: white;
            padding: 1rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border: 1px solid #F0F2F6;
        }
        
        /* Metrics Styling */
        [data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            color: #0B4F6C !important;
        }
        
        [data-testid="stMetricLabel"] {
            font-size: 0.9rem !important;
            color: #64748B !important;
            font-weight: 500 !important;
        }
        
        /* Header Styling */
        h1, h2, h3 {
            color: #0B4F6C !important;
            font-weight: 700 !important;
        }
        
        h4, h5, h6 {
            color: #1E2A3A !important;
            font-weight: 600 !important;
        }
        
        /* Button Styling - Primary */
        button[kind="primary"] {
            background-color: #0B4F6C !important;
            border: none !important;
            border-radius: 6px !important;
            color: white !important;
            font-weight: 600 !important;
            transition: all 0.2s;
        }
        
        button[kind="primary"]:hover {
            background-color: #093E55 !important;
            box-shadow: 0 4px 12px rgba(11, 79, 108, 0.2);
        }
        
        /* Button Styling - Secondary */
        button[kind="secondary"] {
            border: 1px solid #D1D5DB !important;
            background-color: white !important;
            color: #374151 !important;
            border-radius: 6px !important;
        }
        
        button[kind="secondary"]:hover {
            border-color: #0B4F6C !important;
            color: #0B4F6C !important;
            background-color: #F8FAFC !important;
        }
        
        /* Tab Styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
            background-color: transparent;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: white;
            border-radius: 4px 4px 0px 0px;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
            color: #64748B;
            font-weight: 500;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #fff;
            color: #0B4F6C;
            border-bottom: 2px solid #0B4F6C;
            font-weight: 700;
        }
        
        /* DataFrame Styling */
        [data-testid="stDataFrame"] {
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            overflow: hidden;
        }
        
        /* Alerts & Info Boxes */
        .stAlert {
            border-radius: 8px;
            border: none;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        /* Custom Classes */
        .card-header {
            font-size: 1.1rem;
            font-weight: 600;
            color: #0B4F6C;
            margin-bottom: 0.5rem;
            border-bottom: 1px solid #F0F2F6;
            padding-bottom: 0.5rem;
        }
        
        .stat-card {
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            text-align: center;
            transition: transform 0.2s;
        }
        
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.1);
        }
        
        /* Login Form Styling */
        [data-testid="stForm"] {
            border: 1px solid #E0E0E0;
            padding: 2rem;
            border-radius: 16px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
            background-color: white;
        }
        
        </style>
    """, unsafe_allow_html=True)

def card_metric(label, value, delta=None, color="#0B4F6C"):
    """Render a custom HTML metric card"""
    delta_html = ""
    if delta:
        color_delta = "#10B981" if "+" in str(delta) or float(str(delta).replace("%","").replace("+","")) >= 0 else "#EF4444"
        delta_html = f'<div style="font-size: 0.9rem; color: {color_delta}; margin-top: 4px;">{delta}</div>'
    
    st.markdown(f"""
        <div class="stat-card">
            <div style="font-size: 0.9rem; color: #64748B; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">{label}</div>
            <div style="font-size: 2rem; font-weight: 700; color: {color}; margin: 8px 0;">{value}</div>
            {delta_html}
        </div>
    """, unsafe_allow_html=True)
