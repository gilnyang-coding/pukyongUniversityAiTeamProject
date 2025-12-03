import streamlit as st
from openai import OpenAI
from PIL import Image
from datetime import datetime

class StateManager:
    @staticmethod
    def initialize():
        if 'user_profile' not in st.session_state:
            st.session_state.user_profile = {
                "user_id": "user_001",
                "name": "",
                "age": 25,
                "gender": "male",
                "height": 175,
                "weight": 70,
                "activity_level": "moderate",
                "daily_calories": 2000
            }
        
        if 'inventory' not in st.session_state:
            st.session_state.inventory = []
        
        if 'nutrition_status' not in st.session_state:
            st.session_state.nutrition_status = {
                "period_days": 7,
                "daily_average": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0},
                "daily_target": {"calories": 2000, "protein": 75, "carbs": 275, "fat": 66.7},
                "deficiency": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0},
                "last_updated": datetime.now().isoformat()
            }
        
        if 'expenses' not in st.session_state:
            st.session_state.expenses = []
        
        if 'meal_history' not in st.session_state:
            st.session_state.meal_history = []
            
        if 'selected_recipe_index' not in st.session_state:
            st.session_state.selected_recipe_index = None

def main():
    st.set_page_config(
        page_title="tAIste",
        page_icon="🍳",
        layout="wide"
    )
    
    StateManager.initialize()
    
    with st.sidebar:
        st.title("tAIste")
        st.caption("똑똑한 냉장고 관리 & 맞춤 메뉴 추천")
    
    st.header("🍳 tAIste 애플리케이션")
    st.write("상태 관리 시스템이 초기화되었습니다.")
    
    # 디버그용 상태 표시
    st.subheader("현재 세션 상태")
    st.json({
        "user_profile": st.session_state.user_profile,
        "inventory_count": len(st.session_state.inventory),
        "meal_history_count": len(st.session_state.meal_history)
    })

if __name__ == "__main__":
    main()