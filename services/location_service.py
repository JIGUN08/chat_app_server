#location_service.py
import os
import requests
from . import context_service # context_service 임포트

SEARCH_TRIGGERS = {
    'FD6': (['맛집', '음식점', '배고파', '뭐 먹지', '국밥'], '맛집', '음식점'),
    'CE7': (['카페', '커피'], '카페', '카페'),
    'MT1': (['마트', '대형마트', '장보기'], '대형마트', '마트'),
    'CS2': (['편의점'], '편의점', '편의점'),
    'CT1': (['영화관', '영화'], '문화시설', '영화관'),
    'AT4': (['공원', '산책'], '공원', '공원'),
    'HP8': (['병원', '아파'], '병원', '병원'),
    'PM9': (['약국', '약'], '약국', '약국'),
    'SW8': (['지하철역', '지하철'], '지하철역', '지하철역'),
}

def get_location_context(latitude, longitude):

    api_key = os.environ.get("KAKAO_API_KEY")

    if not api_key:
        return ""
    headers = {"Authorization": f"KakaoAK {api_key}"}

    try:
        coord_params = {"x": longitude, "y": latitude}
        response = requests.get("https://dapi.kakao.com/v2/local/geo/coord2address.json", headers=headers, params=coord_params)
        response.raise_for_status()
        address_data = response.json()

        if not address_data['documents']:
            return ""
        
        address_doc = address_data['documents'][0]
        road_address = address_doc.get('road_address')
        address_name = address_doc['address']['address_name']
        if road_address and road_address.get('building_name'):

            return f"[현재 위치]: {road_address['building_name']}"
        
        keyword_params = {
            'query': address_name, 'x': longitude, 'y': latitude,
            'radius': 20, 'sort': 'distance'
        }
        response = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=headers, params=keyword_params)
        response.raise_for_status()
        places_data = response.json()

        if places_data['documents']:
            return f"[현재 위치]: {places_data['documents'][0]['place_name']}"
        
        if address_name:
            return f"[현재 위치]: {address_name} 부근"
        
    except (requests.exceptions.RequestException, KeyError, IndexError) as e:
        print(f"Kakao API 호출 오류: {e}")
    return ""



def get_location_based_recommendation(user, message, latitude, longitude):
    """
    사용자 메시지, 위치, 선호도를 종합하여 장소를 추천합니다.
    """
    if not latitude or not longitude:
        print("--- [Location Debug] 위치 정보 (위도/경도)가 없어 검색을 건너뜁니다. ---")
        return ""

    for category_code, (keywords, category_name, preference_keyword) in SEARCH_TRIGGERS.items():

        message_lower = message.lower()
        if any(keyword in message_lower for keyword in keywords):
            print(f"--- [Location Debug] 트리거 감지: {category_name} ({category_code}) ---")

            # 1. 사용자 선호 장소 목록 가져오기
            preferred_places = context_service.get_user_place_preferences(user, preference_keyword)

            # 2. 선호 장소가 주변에 있는지 검색
            if preferred_places:
                print(f"--- [Location Debug] 선호 장소 검색 시작: {preferred_places} ---")
                # 🚨 search_specific_places_nearby 함수 사용
                found_preferred_places = search_specific_places_nearby(latitude, longitude, preferred_places)
                if found_preferred_places:
                    places_str = ", ".join([f"'{p}'" for p in found_preferred_places])
                    print(f"--- [Location Debug] 선호 장소 발견: {places_str} ---")
                    return f"[선호 장소 추천]: 주변에 자주 가시던 {places_str}이(가) 있어요! 가보시는 건 어때요?"
                else:
                    print(f"--- [Location Debug] 주변에서 선호 장소 찾지 못함. 일반 검색으로 전환. ---")
            else:
                 print(f"--- [Location Debug] 선호 장소 데이터 없음. 일반 검색으로 전환. ---")
            
            # 3. (선호 장소가 없거나 주변에 없는 경우) 주변의 다른 장소 추천
            return find_nearby_places(latitude, longitude, category_code, category_name)
    print("--- [Location Debug] 위치 검색 키워드가 감지되지 않았습니다. ---")
    return ""

def find_nearby_places(latitude, longitude, category_code, category_name):
    print(f"--- [API Debug] find_nearby_places 호출됨: {category_name} (Code: {category_code}) ---")
  
    api_key = os.environ.get("KAKAO_API_KEY")
    if not api_key:
        print("--- [API Debug] 카카오 API 키 없음. 빈 문자열 반환. ---")
        return ""
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {
        "category_group_code": category_code, "x": longitude, "y": latitude,
        "radius": 1000, "sort": "accuracy",
    }
    try:
        response = requests.get("https://dapi.kakao.com/v2/local/search/category.json", headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if not data['documents']:
            print(f"--- [API Debug] 카카오 API 검색 결과: 문서(documents)가 비어있음. 반환: \"\". ---")
            return ""
        
        place_list = [place['place_name'] for place in data['documents'][:5]]
        print(f"--- [API Debug] 카카오 API 검색 성공: {len(place_list)}개 장소 발견. ---")

        return f"[주변 {category_name} 정보]: " + ", ".join(place_list)
    
    except requests.exceptions.HTTPError as e:
        print(f"--- [API Debug] 카카오 API HTTP 오류 ({e.response.status_code}): {e} ---")
        return "" # 👈 두 번째 실패 경로

    except (requests.exceptions.RequestException, KeyError) as e:
        print(f"Kakao API 주변 {category_name} 검색 오류: {e}")
        return ""

def search_specific_places_nearby(latitude, longitude, place_names):
  
    api_key = os.environ.get("KAKAO_API_KEY")
    if not api_key:
        return []
    headers = {"Authorization": f"KakaoAK {api_key}"}
    found_places = []
    for place_name in place_names:
        params = {
            'query': place_name, 'y': latitude, 'x': longitude,
            'radius': 1000, 'sort': 'distance'
        }
        try:
            response = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            if data['documents']:
                found_places.append(place_name)
        except (requests.exceptions.RequestException, KeyError) as e:
            print(f"Kakao API 키워드 검색 오류 ({place_name}): {e}")
            continue
    return found_places
