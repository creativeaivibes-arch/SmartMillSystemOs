import streamlit as st
from app.core.help_content import get_help_text

# Global Language Config (In a real app, this might come from session_state or user profile)
DEFAULT_LANG = 'tr'

def render_help_button(module_key):
    """
    Renders a standard Help expander/button for the given module.
    
    Args:
        module_key (str): Key matching an entry in HELP_CONTENT
    """
    # Get content based on current language (todo: implement language switching)
    lang = st.session_state.get('language', DEFAULT_LANG)
    
    help_data = get_help_text(module_key, lang)
    
    # Render styles
    st.markdown("""
    <style>
    .help-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #0B4F6C;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    with st.expander(f"❓ {help_data['title']}", expanded=False):
        st.markdown(f"""
        <div class="help-box">
            {help_data['content']}
        </div>
        """, unsafe_allow_html=True)
