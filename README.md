
# 사진 GPS로 지도 만들기 (photo_gps_mapper)

사진(EXIF)의 GPS 정보를 읽어서, 촬영 위치가 표시된 **인터랙티브 HTML 지도**를 생성합니다.  
팝업에 **썸네일**이 보이며, 썸네일을 클릭하면 브라우저에서 **큰 사진(사본)**이 새 탭으로 열립니다.

## 설치
```bash
pip install exifread folium pillow
```

## 사용법
```bash
python photo_gps_mapper.py "C:\사진폴더" -o my_trip_map.html
```
- `--thumb-size 480` : 팝업 썸네일 최대 크기(px), 기본 480
- `--no-cluster` : 마커 클러스터링 끄기

> 출력: `my_trip_map.html` 과 같은 폴더에 `map_photos/` 폴더가 생성되어, 사진 사본과 썸네일이 저장됩니다.  
> **HTML 파일과 `map_photos` 폴더를 함께 보관/이동**해야 썸네일/큰 사진이 정상적으로 열립니다.

## 참고
- 원본을 그대로 링크하지 않고 브라우저 호환성을 위해 **사본(JPEG)**을 생성합니다.
- HEIC/PNG 등은 JPEG로 변환되며, 투명 배경은 흰색으로 채워집니다.
- 사진이 많다면 출력 폴더 용량이 커질 수 있습니다.
