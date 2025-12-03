import streamlit as st
from openai import OpenAI
from datetime import datetime, timedelta
import json
from typing import Dict, List
import base64
from io import BytesIO
from PIL import Image

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

class GPTClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def parse_inventory_from_text(self, text: str) -> List[Dict]:
        prompt = f"""다음 텍스트에서 식재료 정보를 추출해주세요.
        
텍스트: {text}

다음 JSON 형식으로만 응답해주세요 (다른 설명 없이):
[
    {{"name": "식재료명", "quantity": 숫자, "unit": "단위"}},
    ...
]

단위는 "개", "g", "kg", "ml", "L" 중 하나를 사용하세요."""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    
    def parse_inventory_from_image(self, image_data: str) -> List[Dict]:
        prompt = """이 영수증 이미지에서 식재료와 수량 정보를 추출해주세요.

**중요한 이름 규칙**: 
상품명(name)에서 '맛있는', '신선한', '몸에 좋은', '유기농', '국산', '프리미엄' 같은 **수식어, 형용사, 브랜드명은 모두 제거**하고 **핵심 식재료 명칭**만 적어주세요.

다음 JSON 형식으로만 응답해주세요 (다른 설명 없이):
[
    {"name": "식재료명", "quantity": 숫자, "unit": "단위", "price": 가격},
    ...
]

단위는 "개", "g", "kg", "ml", "L" 중 하나를 사용하세요."""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}"
                        }
                    }
                ]
            }],
            temperature=0.3
        )
        
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)

def main():
    st.set_page_config(
        page_title="tAIste",
        page_icon="🍳",
        layout="wide"
    )
    
    StateManager.initialize()
    
    if 'api_key' not in st.session_state:
        st.session_state.api_key = None

    with st.sidebar:
        st.title("tAIste")
        st.caption("똑똑한 냉장고 관리 & 맞춤 메뉴 추천")
        
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.session_state.api_key or "",
            help="sk-proj- 또는 sk-로 시작하는 API 키를 입력하세요"
        )
        
        if api_key and api_key != st.session_state.api_key:
            if api_key.startswith("sk-"):
                try:
                    test_client = OpenAI(api_key=api_key)
                    test_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": "Hi"}],
                        max_tokens=5
                    )
                    st.session_state.api_key = api_key
                    st.success("✅ API 키가 확인되었습니다!")
                except Exception as e:
                    st.error(f"❌ API 키가 올바르지 않습니다: {str(e)}")
                    st.session_state.api_key = None
            else:
                st.error("❌ API 키는 'sk-'로 시작해야 합니다")
                st.session_state.api_key = None
    
    if not st.session_state.api_key:
        st.warning("👈 사이드바에서 OpenAI API 키를 입력해주세요.")
        return

    st.header("🍳 GPT 파싱 기능 테스트")
    
    gpt_client = GPTClient(st.session_state.api_key)
    
    tab1, tab2 = st.tabs(["텍스트 파싱", "이미지 파싱"])
    
    with tab1:
        text_input = st.text_area(
            "식재료 입력",
            placeholder="예: 달걀 10개, 우유 1L, 양파 3개"
        )
        if st.button("파싱 테스트", type="primary"):
            if text_input:
                with st.spinner("분석 중..."):
                    try:
                        result = gpt_client.parse_inventory_from_text(text_input)
                        st.success("파싱 완료!")
                        st.json(result)
                    except Exception as e:
                        st.error(f"오류: {str(e)}")
    
    with tab2:
        uploaded_file = st.file_uploader("영수증 이미지 업로드", type=['png', 'jpg', 'jpeg'])
        if uploaded_file and st.button("이미지 파싱 테스트", type="primary"):
            with st.spinner("분석 중..."):
                try:
                    image = Image.open(uploaded_file)
                    buffered = BytesIO()
                    image.save(buffered, format="PNG")
                    image_data = base64.b64encode(buffered.getvalue()).decode()
                    
                    result = gpt_client.parse_inventory_from_image(image_data)
                    st.success("파싱 완료!")
                    st.json(result)
                except Exception as e:
                    st.error(f"오류: {str(e)}")

if __name__ == "__main__":
    main()