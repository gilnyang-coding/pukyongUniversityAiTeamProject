import streamlit as st
from openai import OpenAI
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional
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
- 예시: '맛있는 부산 어묵' -> '어묵'
- 예시: '신선한 무항생제 달걀' -> '달걀'
- 예시: '유기농 흙당근' -> '당근'
- 예시: '몸에 좋은 제철 시금치' -> '시금치'

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

**중요**: 
- 레시피 재료의 단위는 가급적 '보유 식재료'의 단위와 맞춰주세요.
- 고체 재료는 그램(g) 단위로 표시: "쌀 200g", "양파 150g", "달걀 50g" (1개 = 약 50g)
- 액체 재료는 밀리리터(ml) 단위로 표시: "물 500ml", "우유 200ml", "간장 15ml"

보유한 식재료를 최대한 활용하고, 부족한 영양소를 보충할 수 있는 레시피를 추천해주세요.
최근에 먹은 음식과 중복되지 않도록 해주세요."""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    
    def update_inventory_after_cooking(self, inventory: List[Dict], used_ingredients: List[str]) -> List[Dict]:
        prompt = f"""현재 재고에서 사용한 재료만큼 차감하여 남은 재고를 계산해주세요.

현재 재고: {json.dumps(inventory, ensure_ascii=False)}
사용한 재료: {json.dumps(used_ingredients, ensure_ascii=False)}

**계산 규칙**:
1. 단위가 서로 다를 경우(개 vs g), **평균 무게**를 기준으로 환산하여 차감하세요.
    - 예: '양파 150g' 사용, 재고가 '양파 3개'라면 -> 양파 1개(약 200g)를 사용한 것으로 간주하여 '양파 2개' 남음으로 처리.
    - 예: '달걀 100g' 사용, 재고가 '달걀 10개'라면 -> 달걀 2개(50g*2) 차감.

2. '개' 단위의 재료는 소수점으로 남기지 말고, 가급적 정수 단위 혹은 0.5단위로 처리하세요. (예: 2.2개 -> 2개)
3. 액체류는 ml 단위로 정확히 계산하세요.

다음 JSON 형식으로만 응답해주세요 (다른 설명 없이):
[
    {{"name": "식재료명", "quantity": 남은_수량, "unit": "원래_단위"}},
    ...
]

수량이 0 이하가 된 재료는 목록에서 제외해주세요.
원래 단위(kg, L, 개)를 유지하되, 계산은 환산해서 해주세요."""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        updated_items = json.loads(content)
        
        inventory_dict = {item['name']: item for item in inventory}
        
        for item in updated_items:
            if item['name'] in inventory_dict:
                item['added_date'] = inventory_dict[item['name']].get('added_date', datetime.now().isoformat())
                item['expiry_date'] = inventory_dict[item['name']].get('expiry_date', (datetime.now() + timedelta(days=7)).isoformat())
            else:
                item['added_date'] = datetime.now().isoformat()
                item['expiry_date'] = (datetime.now() + timedelta(days=7)).isoformat()
        
        return updated_items

    def recommend_nutrient_rich_recipes(self, deficiency: Dict, inventory: List[Dict]) -> List[Dict]:
        deficiency_str = ", ".join([f"{k} {v:.1f} 부족" for k, v in deficiency.items()])
        inventory_str = json.dumps(inventory, ensure_ascii=False)
        
        prompt = f"""다음 부족한 영양소를 효과적으로 보충할 수 있는 요리 메뉴 2가지를 추천해주세요.

부족한 상태: {deficiency_str}
현재 보유 재고: {inventory_str}

조건:
1. 부족한 영양소가 풍부한 식재료를 주재료로 사용해야 합니다.
2. 각 메뉴가 왜 이 영양소 보충에 좋은지 'reason'에 한 문장으로 설명해주세요.
3. 재료는 반드시 구체적인 수량(g, ml, 개)을 포함해주세요.
4. **현재 보유 재고와 비교하여 부족한 재료가 있다면 'missing_ingredients' 리스트에 담아주세요.** (재고가 충분하면 빈 리스트)

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

# -------------------------------------------------------------------------
# UI 렌더링 함수
# -------------------------------------------------------------------------
def render_recipe_ui(gpt_client, recipe, index, key_suffix, origin_list_key=None, show_use_btn=True, show_delete_btn=False):
    with st.expander(f"🍽️ {recipe['name']}", expanded=True):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if 'reason' in recipe:
                st.caption(f"💡 {recipe['reason']}")
            
            st.subheader("재료")
            for ingredient in recipe['ingredients']:
                st.write(f"- {ingredient}")
            
            if 'missing_ingredients' in recipe and recipe['missing_ingredients']:
                st.warning(f"⚠️ 부족한 재료: {', '.join(recipe['missing_ingredients'])}")
            
            if 'steps' in recipe:
                st.subheader("조리 방법")
                for idx, step in enumerate(recipe['steps'], 1):
                    st.write(f"{idx}. {step}")
        
        with col2:
            st.subheader("영양 정보")
            nutrition = recipe['nutrition']
            nutri_map = {"calories": "칼로리", "protein": "단백질", "carbs": "탄수화물", "fat": "지방"}
            unit_map = {"calories": "kcal", "protein": "g", "carbs": "g", "fat": "g"}
            
            for k, v in nutrition.items():
                kor_key = nutri_map.get(k, k)
                unit = unit_map.get(k, "")
                st.metric(kor_key, f"{v} {unit}")
        
        # 버튼 영역
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if 'youtube_query' in recipe:
                youtube_url = f"https://www.youtube.com/results?search_query={recipe['youtube_query']}"
                st.link_button("유튜브에서 보기", youtube_url)
        
        with col_btn2:
            if show_use_btn:
                if st.button("이 레시피 사용", key=f"use_{index}_{key_suffix}"):
                    with st.spinner("재고를 확인중입니다..."):
                        try:
                            check_prompt = f"""현재 재고로 이 레시피를 만들 수 있는지 엄격하게 확인하지 말고, 통상적인 식재료 무게를 고려하여 유연하게 판단해주세요.

현재 재고: {json.dumps(st.session_state.inventory, ensure_ascii=False)}
레시피 재료: {json.dumps(recipe['ingredients'], ensure_ascii=False)}

**핵심 판단 기준 (단위 변환)**:
1. 재고는 '개' 단위이고 레시피는 'g/ml' 단위일 경우, 아래 평균 무게를 기준으로 변환하여 판단하세요.
    - 양파 1개 ≈ 200g, 감자 1개 ≈ 150g, 당근 1개 ≈ 150g, 달걀 1개 ≈ 50g, 대파 1대 ≈ 80g, 마늘 1쪽 ≈ 5g

2. 예시: 
    - 재고 '양파 1개' vs 레시피 '양파 150g' -> **충분함 (true)**
    - 재고 '양파 1개' vs 레시피 '양파 300g' -> 부족함 (false)

다음 JSON 형식으로만 응답해주세요:
{{
    "sufficient": true or false,
    "missing_items": ["부족한 재료1 (필요: X, 보유: Y)", ...]
}}"""
                            
                            check_response = gpt_client.client.chat.completions.create(
                                model="gpt-4o",
                                messages=[{"role": "user", "content": check_prompt}],
                                temperature=0.3
                            )
                            
                            check_content = check_response.choices[0].message.content.strip()
                            check_content = check_content.replace("```json", "").replace("```", "").strip()
                            check_result = json.loads(check_content)
                            
                            if not check_result['sufficient']:
                                st.error(f"❌ 재고가 부족합니다! 부족한 재료: {', '.join(check_result['missing_items'])}")
                            else:
                                with st.spinner("재고를 업데이트중입니다..."):
                                    updated_inventory = gpt_client.update_inventory_after_cooking(
                                        st.session_state.inventory,
                                        recipe['ingredients']
                                    )
                                    st.session_state.inventory = updated_inventory
                                    
                                    st.session_state.meal_history.append({
                                        'date': datetime.now().isoformat(),
                                        'recipe_name': recipe['name'],
                                        'nutrition': recipe['nutrition']
                                    })
                                    
                                    daily_intake = {}
                                    for meal in st.session_state.meal_history:
                                        date_key = meal['date'][:10]
                                        if date_key not in daily_intake:
                                            daily_intake[date_key] = {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0}
                                        
                                        daily_intake[date_key]['calories'] += meal['nutrition']['calories']
                                        daily_intake[date_key]['protein'] += meal['nutrition']['protein']
                                        daily_intake[date_key]['carbs'] += meal['nutrition']['carbs']
                                        daily_intake[date_key]['fat'] += meal['nutrition']['fat']
                                    
                                    days_count = len(daily_intake)
                                    if days_count > 0:
                                        avg_nutrition = {
                                            'calories': sum(d['calories'] for d in daily_intake.values()) / days_count,
                                            'protein': sum(d['protein'] for d in daily_intake.values()) / days_count,
                                            'carbs': sum(d['carbs'] for d in daily_intake.values()) / days_count,
                                            'fat': sum(d['fat'] for d in daily_intake.values()) / days_count
                                        }
                                        st.session_state.nutrition_status['daily_average'] = avg_nutrition
                                        
                                        target = st.session_state.nutrition_status['daily_target']
                                        st.session_state.nutrition_status['deficiency'] = {
                                            k: max(0, target[k] - avg_nutrition[k]) for k in target.keys()
                                        }
                                    
                                    st.success("✅ 재고가 업데이트되었습니다!")
                                    
                                    if origin_list_key == 'recommended_recipes':
                                        st.session_state.selected_recipe_index = index
                                        
                                    st.rerun()
                        except Exception as e:
                            st.error(f"오류 발생: {str(e)}")
            
            if show_delete_btn:
                if st.button("삭제", key=f"del_rec_{index}_{key_suffix}"):
                    if origin_list_key and origin_list_key in st.session_state:
                        st.session_state[origin_list_key] = []
                        st.session_state.selected_recipe_index = None
                        st.rerun()

def render_inventory_page(gpt_client: GPTClient):
    st.header("🥗 냉장고 재고 관리")
    
    st.subheader("재고 추가")
    
    tab1, tab2 = st.tabs(["텍스트 입력", "영수증 사진"])
    
    with tab1:
        text_input = st.text_area(
            "식재료 입력",
            placeholder="예: 달걀 10개, 우유 1L, 양파 3개",
            height=100
        )
        if st.button("텍스트로 재고 추가", type="primary"):
            if text_input:
                with st.spinner("식재료 정보를 분석중입니다..."):
                    try:
                        parsed_items = gpt_client.parse_inventory_from_text(text_input)
                        for item in parsed_items:
                            item['added_date'] = datetime.now().isoformat()
                            item['expiry_date'] = (datetime.now() + timedelta(days=7)).isoformat()
                            st.session_state.inventory.append(item)
                        st.success(f"{len(parsed_items)}개 항목이 추가되었습니다!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류 발생: {str(e)}")
    
    with tab2:
        uploaded_file = st.file_uploader("영수증 사진 업로드", type=['png', 'jpg', 'jpeg'])
        if uploaded_file and st.button("영수증에서 재고 추가", type="primary"):
            with st.spinner("영수증을 분석중입니다..."):
                try:
                    image = Image.open(uploaded_file)
                    buffered = BytesIO()
                    image.save(buffered, format="PNG")
                    image_data = base64.b64encode(buffered.getvalue()).decode()
                    
                    parsed_items = gpt_client.parse_inventory_from_image(image_data)
                    
                    total_expense = sum(item.get('price', 0) for item in parsed_items)
                    if total_expense > 0:
                        st.session_state.expenses.append({
                            'date': datetime.now().isoformat(),
                            'amount': total_expense,
                            'items': ', '.join([item['name'] for item in parsed_items])
                        })
                    
                    for item in parsed_items:
                        item['added_date'] = datetime.now().isoformat()
                        item['expiry_date'] = (datetime.now() + timedelta(days=7)).isoformat()
                        st.session_state.inventory.append(item)
                    
                    st.success(f"{len(parsed_items)}개 항목이 추가되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"오류 발생: {str(e)}")
    
    st.subheader("현재 재고")
    if st.session_state.inventory:
        for idx, item in enumerate(st.session_state.inventory):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{item['name']}** - {item['quantity']}{item['unit']}")
            with col2:
                st.write(f"추가: {item['added_date'][:10]}")
            with col3:
                if st.button("삭제", key=f"del_{idx}"):
                    st.session_state.inventory.pop(idx)
                    st.rerun()
    else:
        st.info("재고가 비어있습니다. 위에서 재고를 추가해주세요.")
    
    st.subheader("💰 지출 내역")
    if st.session_state.expenses:
        total = sum(exp['amount'] for exp in st.session_state.expenses)
        st.metric("총 지출", f"{total:,}원")
        
        for exp in st.session_state.expenses[-5:]:
            st.write(f"**{exp['date'][:10]}** - {exp['amount']:,}원 ({exp['items']})")
    else:
        st.info("지출 내역이 없습니다.")

def render_nutrition_page(gpt_client: GPTClient):
    st.header("📊 영양 분석")
    
    with st.expander("프로필 설정", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("나이", min_value=1, max_value=120, value=st.session_state.user_profile['age'])
            height = st.number_input("키 (cm)", min_value=100, max_value=250, value=st.session_state.user_profile['height'])
        with col2:
            gender = st.selectbox("성별", ["남성", "여성"], index=0 if st.session_state.user_profile['gender'] == "male" else 1)
            weight = st.number_input("몸무게 (kg)", min_value=30, max_value=200, value=st.session_state.user_profile['weight'])
        
        activity_level = st.selectbox(
            "활동량",
            ["매우 적음", "적음", "보통", "활동적", "매우 활동적"],
            index=2
        )
        
        if st.button("프로필 저장 및 영양 목표 계산"):
            st.session_state.user_profile.update({
                'age': age,
                'gender': gender,
                'height': height,
                'weight': weight,
                'activity_level': activity_level
            })
            
            with st.spinner("영양 목표를 계산중입니다..."):
                try:
                    target = gpt_client.calculate_nutrition_target(st.session_state.user_profile)
                    st.session_state.nutrition_status['daily_target'] = target
                    st.success("영양 목표가 업데이트되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"오류 발생: {str(e)}")
    
    st.subheader("일일 권장 섭취량")
    target = st.session_state.nutrition_status['daily_target']
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("칼로리", f"{target['calories']:.0f} kcal")
    with col2:
        st.metric("단백질", f"{target['protein']:.1f} g")
    with col3:
        st.metric("탄수화물", f"{target['carbs']:.1f} g")
    with col4:
        st.metric("지방", f"{target['fat']:.1f} g")
    
    deficiency = st.session_state.nutrition_status['deficiency']
    
    if any(v > 0 for v in deficiency.values()):
        st.divider()
        st.subheader("⚠️ 부족한 영양소 채우기")
        
        deficient_items = {k: v for k, v in deficiency.items() if v > 0}
        
        cols = st.columns(2)
        for idx, (nutrient, value) in enumerate(deficient_items.items()):
            name_map = {"calories": "칼로리", "protein": "단백질", "carbs": "탄수화물", "fat": "지방"}
            unit_map = {"calories": "kcal", "protein": "g", "carbs": "g", "fat": "g"}
            
            korean_name = name_map.get(nutrient, nutrient)
            unit = unit_map.get(nutrient, "")
            
            with cols[idx % 2]:
                st.info(f"**{korean_name}** 부족! (목표 대비 -{value:.1f}{unit})")
                
                target_val = st.session_state.nutrition_status['daily_target'][nutrient]
                if target_val > 0:
                    current_val = max(0, target_val - value)
                    ratio = min(1.0, current_val / target_val)
                    st.progress(ratio, text=f"현재 섭취: {ratio*100:.0f}%")

        st.write("") 
        if st.button("✨ 부족한 영양소를 채워줄 메뉴 추천받기", type="primary", use_container_width=True):
            with st.spinner("영양 밸런스를 위한 최적의 메뉴를 찾고 있습니다..."):
                try:
                    recipes = gpt_client.recommend_nutrient_rich_recipes(deficient_items, st.session_state.inventory)
                    st.session_state.nutrient_recipes = recipes
                except Exception as e:
                    st.error(f"추천 중 오류 발생: {str(e)}")

        if 'nutrient_recipes' in st.session_state and st.session_state.nutrient_recipes:
            st.write("---")
            st.write("### 🥗 추천 보양 메뉴")
            
            for idx, recipe in enumerate(st.session_state.nutrient_recipes):
                render_recipe_ui(gpt_client, recipe, idx, "nutrient", origin_list_key='nutrient_recipes', show_use_btn=True, show_delete_btn=False)

    st.divider()
    st.subheader("📅 최근 식사 기록")
    
    if st.session_state.meal_history:
        for meal in reversed(st.session_state.meal_history):
            try:
                dt = datetime.fromisoformat(meal['date'])
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = meal['date']
            
            with st.container():
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"**{meal['recipe_name']}**")
                    st.caption(f"{date_str}")
                with c2:
                    n = meal['nutrition']
                    st.write(f"{n['calories']} kcal")
                    st.caption(f"탄수화물:{n['carbs']} 단백질:{n['protein']} 지방:{n['fat']}")
            st.divider()
    else:
        st.info("아직 식사 기록이 없습니다. 메뉴 추천에서 요리를 완료해보세요!")

def render_recommendation_page(gpt_client: GPTClient):
    st.header("🍳 메뉴 추천")
    
    if not st.session_state.inventory:
        st.warning("재고가 없습니다. 먼저 재고를 추가해주세요.")
        return
    
    if st.button("레시피 추천받기", type="primary"):
        with st.spinner("맞춤 레시피를 생성중입니다..."):
            try:
                recipes = gpt_client.recommend_recipes(
                    st.session_state.inventory,
                    st.session_state.nutrition_status['deficiency'],
                    st.session_state.meal_history
                )
                st.session_state.recommended_recipes = recipes
                st.session_state.selected_recipe_index = None
            except Exception as e:
                st.error(f"오류 발생: {str(e)}")
    
    if 'recommended_recipes' in st.session_state and st.session_state.recommended_recipes:
        selected_idx = st.session_state.selected_recipe_index
        
        if selected_idx is None:
            for idx, recipe in enumerate(st.session_state.recommended_recipes):
                render_recipe_ui(
                    gpt_client, 
                    recipe, 
                    idx, 
                    "recommend", 
                    origin_list_key='recommended_recipes',
                    show_use_btn=True,
                    show_delete_btn=False
                )
        else:
            if 0 <= selected_idx < len(st.session_state.recommended_recipes):
                target_recipe = st.session_state.recommended_recipes[selected_idx]
                render_recipe_ui(
                    gpt_client, 
                    target_recipe, 
                    selected_idx, 
                    "recommend", 
                    origin_list_key='recommended_recipes',
                    show_use_btn=False, 
                    show_delete_btn=True 
                )
            else:
                st.session_state.selected_recipe_index = None
                st.rerun()

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
        
        # [수정됨] 사이드바에서 API 키 입력 (기본값 제거)
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
                    # 간단한 테스트 호출로 유효성 검사
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
        
        st.divider()
        
        page = st.radio(
            "메뉴",
            ["재고 관리", "메뉴 추천", "영양 분석"], 
            index=0
        )
    
    if not st.session_state.api_key:
        st.warning("👈 사이드바에서 OpenAI API 키를 입력해주세요.")
        return

    try:
        gpt_client = GPTClient(st.session_state.api_key)
        
        if page == "재고 관리":
            render_inventory_page(gpt_client)
        elif page == "영양 분석":
            render_nutrition_page(gpt_client)
        elif page == "메뉴 추천":
            render_recommendation_page(gpt_client)
            
    except Exception as e:
        st.error(f"API 연결 오류: {str(e)}")

if __name__ == "__main__":
    main()