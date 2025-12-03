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
    
    def calculate_nutrition_target(self, profile: Dict) -> Dict:
        prompt = f"""다음 사용자 정보를 바탕으로 일일 권장 영양 섭취량을 계산해주세요.

사용자 정보:
- 나이: {profile['age']}세
- 성별: {profile['gender']}
- 키: {profile['height']}cm
- 몸무게: {profile['weight']}kg
- 활동량: {profile['activity_level']}

다음 JSON 형식으로만 응답해주세요 (다른 설명 없이):
{{
    "calories": 숫자,
    "protein": 숫자,
    "carbs": 숫자,
    "fat": 숫자
}}"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    
    def recommend_recipes(self, inventory: List[Dict], nutrition_deficiency: Dict, meal_history: List[Dict]) -> List[Dict]:
        inventory_str = ", ".join([f"{item['name']} {item['quantity']}{item['unit']}" for item in inventory])
        deficiency_str = ", ".join([f"{k}: {v:.1f}" for k, v in nutrition_deficiency.items() if v > 0])
        
        recent_meals = [meal['recipe_name'] for meal in meal_history[-7:]] if meal_history else []
        recent_meals_str = ", ".join(recent_meals) if recent_meals else "없음"
        
        prompt = f"""다음 조건에 맞는 요리 레시피 3개를 추천해주세요.

보유 식재료: {inventory_str}
부족한 영양소: {deficiency_str}
최근 7일 식사 기록: {recent_meals_str}

다음 JSON 형식으로만 응답해주세요 (다른 설명 없이):
[
    {{
        "name": "레시피명",
        "nutrition": {{"protein": 숫자, "carbs": 숫자, "fat": 숫자, "calories": 숫자}},
        "ingredients": ["재료명 수량g", "재료명 수량ml", ...],
        "steps": ["조리과정1", "조리과정2", ...],
        "youtube_query": "유튜브 검색어"
    }},
    ...
]

보유한 식재료를 최대한 활용하고, 부족한 영양소를 보충할 수 있는 레시피를 추천해주세요."""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    
    def recommend_nutrient_rich_recipes(self, deficiency: Dict, inventory: List[Dict]) -> List[Dict]:
        deficiency_str = ", ".join([f"{k} {v:.1f} 부족" for k, v in deficiency.items()])
        inventory_str = json.dumps(inventory, ensure_ascii=False)
        
        prompt = f"""다음 부족한 영양소를 효과적으로 보충할 수 있는 요리 메뉴 2가지를 추천해주세요.

부족한 상태: {deficiency_str}
현재 보유 재고: {inventory_str}

다음 JSON 형식으로만 응답해주세요 (다른 설명 없이):
[
    {{
        "name": "메뉴명",
        "reason": "이 메뉴가 추천된 이유",
        "ingredients": ["재료명 수량g", "재료명 수량ml", ...],
        "missing_ingredients": ["부족한재료1", "부족한재료2", ...],
        "steps": ["조리과정1", "조리과정2", ...],
        "nutrition": {{"calories": 숫자, "protein": 숫자, "carbs": 숫자, "fat": 숫자}},
        "youtube_query": "유튜브 검색어"
    }},
    ...
]"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
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

    st.header("🍳 영양 계산 및 레시피 추천 테스트")
    
    gpt_client = GPTClient(st.session_state.api_key)
    
    tab1, tab2 = st.tabs(["영양 목표 계산", "레시피 추천"])
    
    with tab1:
        st.subheader("프로필 설정")
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("나이", min_value=1, value=25)
            height = st.number_input("키 (cm)", min_value=100, value=175)
        with col2:
            gender = st.selectbox("성별", ["male", "female"])
            weight = st.number_input("몸무게 (kg)", min_value=30, value=70)
        
        if st.button("영양 목표 계산", type="primary"):
            with st.spinner("계산 중..."):
                try:
                    profile = {"age": age, "gender": gender, "height": height, "weight": weight, "activity_level": "moderate"}
                    result = gpt_client.calculate_nutrition_target(profile)
                    st.success("계산 완료!")
                    st.json(result)
                except Exception as e:
                    st.error(f"오류: {str(e)}")
    
    with tab2:
        st.subheader("레시피 추천 테스트")
        
        # 테스트용 재고 추가
        if st.button("테스트 재고 추가"):
            st.session_state.inventory = [
                {"name": "쌀", "quantity": 5, "unit": "kg"},
                {"name": "달걀", "quantity": 10, "unit": "개"},
                {"name": "양파", "quantity": 3, "unit": "개"}
            ]
            st.success("테스트 재고가 추가되었습니다!")
        
        if st.button("레시피 추천받기", type="primary"):
            if not st.session_state.inventory:
                st.warning("재고를 먼저 추가해주세요.")
            else:
                with st.spinner("추천 중..."):
                    try:
                        recipes = gpt_client.recommend_recipes(
                            st.session_state.inventory,
                            {"protein": 20, "calories": 500},
                            []
                        )
                        st.success("추천 완료!")
                        for recipe in recipes:
                            st.subheader(recipe['name'])
                            st.json(recipe)
                    except Exception as e:
                        st.error(f"오류: {str(e)}")

if __name__ == "__main__":
    main()