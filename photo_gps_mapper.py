#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
photo_gps_mapper.py
사진의 EXIF GPS 정보를 읽어 촬영 위치가 표시된 인터랙티브 지도를 생성합니다.
- 입력: 사진 폴더 (JPG/HEIC/PNG 일부 포함)
- 출력: HTML 지도 파일 (기본: photo_map.html)
- 팝업: 썸네일이 표시되고, 클릭하면 원본(사본) 사진을 새 탭에서 열람할 수 있습니다.

필요 패키지:
    pip install exifread folium pillow
"""
import argparse
import sys
import os
import shutil
from typing import Optional, Dict, Any, List

# 외부 패키지
try:
    import exifread
except Exception as e:
    print("[오류] exifread 패키지가 필요합니다. 아래 명령으로 설치하세요:\\n  pip install exifread", file=sys.stderr)
    raise

try:
    from PIL import Image, ImageOps
except Exception as e:
    print("[오류] Pillow 패키지가 필요합니다. 아래 명령으로 설치하세요:\\n  pip install pillow", file=sys.stderr)
    raise

try:
    import folium
    from folium.plugins import MarkerCluster
except Exception as e:
    print("[오류] folium 패키지가 필요합니다. 아래 명령으로 설치하세요:\\n  pip install folium", file=sys.stderr)
    raise


SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.JPG', '.JPEG', '.PNG', '.HEIC', '.HEIF'}


def dms_to_deg(dms, ref) -> float:
    """EXIF의 DMS(Degrees, Minutes, Seconds) 값을 십진수로 변환."""
    def _to_float(x):
        try:
            return float(x.num) / float(x.den)
        except Exception:
            return float(x)
    deg = _to_float(dms[0])
    minutes = _to_float(dms[1])
    seconds = _to_float(dms[2])
    result = deg + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ['S', 'W']:
        result = -result
    return result


def extract_exif_gps(image_path: str) -> Optional[Dict[str, Any]]:
    """이미지 파일에서 EXIF GPS와 촬영 시각을 추출."""
    gps = None
    dt = None

    # exifread 우선
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
        lat = tags.get('GPS GPSLatitude')
        lat_ref = tags.get('GPS GPSLatitudeRef')
        lon = tags.get('GPS GPSLongitude')
        lon_ref = tags.get('GPS GPSLongitudeRef')
        dt_tag = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')

        if lat and lat_ref and lon and lon_ref:
            gps = (dms_to_deg(lat.values, str(lat_ref)), dms_to_deg(lon.values, str(lon_ref)))
        if dt_tag:
            dt = str(dt_tag)
    except Exception:
        pass

    # Pillow fallback
    if gps is None:
        try:
            img = Image.open(image_path)
            exif = getattr(img, "_getexif", lambda: None)()
            if exif:
                gps_info = exif.get(34853)  # GPSInfo
                if gps_info:
                    lat = gps_info.get(2); lat_ref = gps_info.get(1)
                    lon = gps_info.get(4); lon_ref = gps_info.get(3)
                    if lat and lat_ref and lon and lon_ref:
                        gps = (dms_to_deg(lat, lat_ref), dms_to_deg(lon, lon_ref))
                dt = exif.get(36867) or exif.get(306)  # DateTimeOriginal or Image DateTime
        except Exception:
            pass

    if gps and gps[0] is not None and gps[1] is not None:
        return {"lat": gps[0], "lon": gps[1], "datetime": dt}
    return None


def scan_images(folder: str) -> List[str]:
    files = []
    for root, _, fnames in os.walk(folder):
        for fn in fnames:
            ext = os.path.splitext(fn)[1]
            if ext in SUPPORTED_EXT:
                files.append(os.path.join(root, fn))
    return files


def make_thumbnail(src_path: str, dst_path: str, max_size: int = 512) -> None:
    """썸네일/큰보기용 JPEG 생성. EXIF 회전 보정 포함."""
    with Image.open(src_path) as im:
        try:
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        im.thumbnail((max_size, max_size))
        if im.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        im.save(dst_path, format="JPEG", quality=85, optimize=True)


def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, '_')
    return name


def main():
    parser = argparse.ArgumentParser(description="사진 EXIF GPS로 지도 만들기 (+사진 열람 팝업)")
    parser.add_argument("input_folder", help="사진들이 들어있는 폴더 경로")
    parser.add_argument("-o", "--output", default="photo_map.html", help="출력 HTML 파일명 (기본: photo_map.html)")
    parser.add_argument("--thumb-size", type=int, default=480, help="팝업 썸네일 최대 크기(px), 기본 480")
    parser.add_argument("--no-cluster", action="store_true", help="마커 클러스터링 끄기")
    args = parser.parse_args()

    images = scan_images(args.input_folder)
    if not images:
        print("[안내] 지원되는 사진 파일이 없습니다. (JPG/PNG/HEIC 등)", file=sys.stderr)
        sys.exit(1)

    # 추출
    items = []
    for p in images:
        info = extract_exif_gps(p)
        if info:
            items.append({"path": p, **info})

    if not items:
        print("[안내] 사진에서 GPS 정보를 찾지 못했습니다. (스마트폰 촬영 시 위치 정보 설정이 꺼져 있을 수 있음)", file=sys.stderr)
        sys.exit(2)

    # 출력 폴더와 이미지 사본/썸네일 저장 폴더
    out_html = os.path.abspath(args.output)
    out_dir = os.path.dirname(out_html) if os.path.dirname(out_html) else os.getcwd()
    img_dir = os.path.join(out_dir, "map_photos")
    os.makedirs(img_dir, exist_ok=True)

    # 지도 중심
    avg_lat = sum(x["lat"] for x in items) / len(items)
    avg_lon = sum(x["lon"] for x in items) / len(items)

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12, control_scale=True, tiles='OpenStreetMap')
    cluster = None if args.no_cluster else MarkerCluster()

    # 마커 생성
    for idx, it in enumerate(items, start=1):
        src = it["path"]
        base = sanitize_filename(os.path.basename(src))
        stem = f"{idx:04d}_{os.path.splitext(base)[0]}"
        large_rel = f"{stem}.jpg"
        thumb_rel = f"{stem}_thumb.jpg"
        large_path = os.path.join(img_dir, large_rel)
        thumb_path = os.path.join(img_dir, thumb_rel)

        # 큰 사본(최대 2048), 썸네일(args.thumb_size)
        make_thumbnail(src, large_path, max_size=2048)
        make_thumbnail(src, thumb_path, max_size=args.thumb_size)

        name = os.path.basename(src)
        dt = it.get("datetime") or ""
        lat = it["lat"]; lon = it["lon"]

        html = f"""
        <div style='width:{args.thumb_size+40}px'>
          <a href="map_photos/{large_rel}" target="_blank" rel="noopener">
            <img src="map_photos/{thumb_rel}" style="max-width:100%; height:auto; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.3);" />
          </a>
          <div style="margin-top:6px; font-size:12px; line-height:1.3">
            <b>{name}</b><br/>
            {dt}<br/>
            {lat:.6f}, {lon:.6f}
          </div>
        </div>
        """
        popup = folium.Popup(html=html, max_width=args.thumb_size+80)
        marker = folium.Marker(location=[lat, lon], popup=popup, tooltip=name)
        if cluster:
            cluster.add_child(marker)
        else:
            marker.add_to(m)

    if cluster:
        cluster.add_to(m)

    m.save(out_html)
    print(f"[완료] 지도 파일 생성: {out_html}")
    print(f"[안내] 'map_photos' 폴더에 사진 사본과 썸네일이 저장되어 브라우저에서 안전하게 열람됩니다.")
    print("       HTML과 'map_photos' 폴더를 함께 보관/이동하세요.")

if __name__ == "__main__":
    main()
