#=================
#Spatial Multi-Criteria Analysis for Flood Disaster Preparedness in Educational Facilities: A WebGIS-Ready Study Case of Jakarta
#=================

import requests
import folium
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
from branca.colormap import LinearColormap

import requests
import geopandas as gpd

urls = {
    "risiko_banjir": 'https://geoserver.mapid.io/layers_new/get_layer?api_key=70b6758f25e94e6a849a32d935bce369&layer_id=6984ac9dbbaa47f3ce68dc4d&project_id=697e526a949d92a51f0b4816',
    "kepadatan_penduduk": 'https://geoserver.mapid.io/layers_new/get_layer?api_key=70b6758f25e94e6a849a32d935bce369&layer_id=6984acd196de9425652f4015&project_id=697e526a949d92a51f0b4816',
    "fasilitas_pendidikan": 'https://geoserver.mapid.io/layers_new/get_layer?api_key=70b6758f25e94e6a849a32d935bce369&layer_id=6984ac32bbaa47f3ce68c2f2&project_id=697e526a949d92a51f0b4816',
}


import geopandas as gpd

def get_gdf_from_api(url):
    response = requests.get(url)
    if response.status_code == 200:
        geojson = response.json()
        gdf = gpd.GeoDataFrame.from_features(geojson['features'])
        print(f"Berhasil mengambil data dari {url.split('&layer_id=')[1][:10]}...")
        return gdf
    else:
        print(f"Gagal mengambil data dari {url}")
        return gpd.GeoDataFrame()

# Membaca semua data ke dalam dictionary GeoDataFrame
gdfs = {}
for key, url in urls.items():
    gdfs[key] = get_gdf_from_api(url)

from pyproj import CRS

for key, gdf in gdfs.items():
    # Isi null dengan default (0 atau 'TIDAK DIKETAHUI')
    for col in gdf.columns:
        if gdf[col].dtype == 'O':
            gdf[col] = gdf[col].fillna('TIDAK DIKETAHUI')
        else:
            gdf[col] = gdf[col].fillna(0)
    # Set CRS ke EPSG:4326 jika belum
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf.set_crs(epsg=4326, inplace=True)
    gdfs[key] = gdf
print("Semua data sudah dicek dan disesuaikan.")

import folium

for key, gdf in gdfs.items():
    m = folium.Map(location=[-6.23, 106.83], zoom_start=13)
    folium.GeoJson(gdf).add_to(m)
    folium.LayerControl().add_to(m)
    display(m)  
    print(f"Peta untuk variabel: {key}")

import geopandas as gpd

for key in gdfs.keys():
    if 'ID' in gdfs[key].columns:
        gdfs[key] = gdfs[key].drop(columns=['ID'])

gdf_list = [
    gdfs['kepadatan_penduduk'],
    gdfs['risiko_banjir'],
    gdfs['fasilitas_pendidikan'],
]

def overlay_multiple(gdf_list):
    result = gdf_list[0]
    for gdf in gdf_list[1:]:
        if not gdf.empty:
            result = gpd.overlay(result, gdf, how='intersection')
            result = result[result.is_valid]
    return result

gdf_intersect = overlay_multiple(gdf_list)
print(f"Jumlah area hasil intersect: {len(gdf_intersect)}")


print("Kolom hasil intersect:", gdf_intersect.columns)

# 1. Overlay banjir + kepadatan
gdf_temp = gpd.overlay(
    gdfs['risiko_banjir'], 
    gdfs['kepadatan_penduduk'], 
    how='intersection'
)
print(f"   ✓ Layer 1+2: {len(gdf_temp)} area")

# 2. Overlay + pendidikan
gdf_intersect = gpd.overlay(
    gdf_temp, 
    gdfs['fasilitas_pendidikan'], 
    how='intersection'
)
print(f"   ✓ FINAL (3 layer): {len(gdf_intersect)} area")

def skoring_prioritas_evakuasi(row):
    """
    SKORING UNTUK PRIORITAS EVAKUASI FASILITAS PENDIDIKAN SAAT BANJIR
    
    Bobot:
    - Risiko Banjir (50%): Semakin tinggi risiko, semakin prioritas
    - Kepadatan (30%): Semakin padat, semakin besar populasi terdampak
    - Fasilitas Pendidikan (20%): Ada sekolah = prioritas evakuasi
    """
    
    # 1. RISIKO BANJIR (50%)
    banjir = str(row.get('RISIKO_BANJIR', '')).upper()
    if 'TINGGI' in banjir:
        skor_banjir = 10
    elif 'SEDANG' in banjir:
        skor_banjir = 6
    else:  # RENDAH
        skor_banjir = 2
    
    # 2. KEPADATAN PENDUDUK (30%)
    padat = str(row.get('KEPADATAN', '')).upper()
    if 'TINGGI' in padat:
        skor_padat = 10
    elif 'SEDANG' in padat:
        skor_padat = 6
    else:  # RENDAH
        skor_padat = 3
    
    # 3. FASILITAS PENDIDIKAN (20%)
    pendidikan = str(row.get('DEKAT_PENDIDIKAN', '')).upper()
    skor_pendidikan = 10 if 'YA' in pendidikan else 0
    
    # HITUNG SKOR TOTAL (WEIGHTED SUM)
    skor_total = (
        skor_banjir * 0.5 +
        skor_padat * 0.3 +
        skor_pendidikan * 0.2
    )
    
    return pd.Series({
        'SKOR_BANJIR': skor_banjir,
        'SKOR_PADAT': skor_padat,
        'SKOR_PENDIDIKAN': skor_pendidikan,
        'SKOR_TOTAL': round(skor_total, 1)  # 1 desimal saja biar rapi
    })

kolom_skoring = ['SKOR_BANJIR', 'SKOR_PADAT', 'SKOR_PENDIDIKAN', 'SKOR_TOTAL']
for col in kolom_skoring:
    if col in gdf_intersect.columns:
        gdf_intersect = gdf_intersect.drop(columns=[col])
        print(f"✅ Kolom {col} lama dihapus")

print("\n📊 Menerapkan skoring multi-kriteria...")
gdf_intersect = pd.concat([
    gdf_intersect, 
    gdf_intersect.apply(skoring_prioritas_evakuasi, axis=1)
], axis=1)

print("\n✅ HASIL SKORING (5 baris pertama):")
print("="*60)
print(gdf_intersect[['RISIKO_BANJIR', 'KEPADATAN', 'DEKAT_PENDIDIKAN', 
                     'SKOR_BANJIR', 'SKOR_PADAT', 'SKOR_PENDIDIKAN', 'SKOR_TOTAL']].head(5))

def klasifikasi_prioritas(skor):
    if skor >= 8:
        return 'PRIORITAS 1 - KRITIS'
    elif skor >= 6:
        return 'PRIORITAS 2 - TINGGI'
    elif skor >= 4:
        return 'PRIORITAS 3 - SEDANG'
    else:
        return 'PRIORITAS 4 - RENDAH'

gdf_intersect['PRIORITAS'] = gdf_intersect['SKOR_TOTAL'].apply(klasifikasi_prioritas)

print("\n📈 STATISTIK DESKRIPTIF:")
print("-" * 40)
print(f"Total area dianalisis: {len(gdf_intersect)}")
print("\nDistribusi Prioritas Evakuasi:")
print(gdf_intersect['PRIORITAS'].value_counts())

print("\n📊 RATA-RATA SKOR PER KATEGORI:")
print(f"Rata-rata Skor Banjir: {gdf_intersect['SKOR_BANJIR'].mean():.1f}")
print(f"Rata-rata Skor Kepadatan: {gdf_intersect['SKOR_PADAT'].mean():.1f}")
print(f"Rata-rata Skor Pendidikan: {gdf_intersect['SKOR_PENDIDIKAN'].mean():.1f}")
print(f"Rata-rata Skor Total: {gdf_intersect['SKOR_TOTAL'].mean():.1f}")

import folium
import branca.colormap as cm

warna_prioritas = {
    'PRIORITAS 1 - KRITIS': '#dc3545',  
    'PRIORITAS 2 - TINGGI': '#ffc107',  
    'PRIORITAS 3 - SEDANG': '#28a745',  
    'PRIORITAS 4 - RENDAH': '#17a2b8'   
}

def style_evakuasi(feature):
    prioritas = feature['properties'].get('PRIORITAS', 'PRIORITAS 4 - RENDAH')
    prioritas = prioritas.strip()
    
    return {
        'fillColor': warna_prioritas.get(prioritas, '#6c757d'),
        'color': 'white',
        'weight': 0.8,
        'fillOpacity': 0.7,
        'dashArray': '3'
    }

m = folium.Map(
    location=[-6.23, 106.83], 
    zoom_start=11,
    tiles='cartodbpositron',
    control_scale=True
)

folium.GeoJson(
    gdf_intersect,
    style_function=style_evakuasi,
    tooltip=folium.GeoJsonTooltip(
        fields=['PRIORITAS', 'SKOR_TOTAL', 'RISIKO_BANJIR', 'KEPADATAN', 'DEKAT_PENDIDIKAN'],
        aliases=['🏷️ Prioritas', '📊 Skor', '🌊 Banjir', '👥 Kepadatan', '🏫 Ada Sekolah?']
    )
).add_to(m)

colormap = cm.StepColormap(
    colors=['#dc3545', '#ffc107', '#28a745', '#17a2b8'],
    vmin=0, vmax=3,
    index=[0, 1, 2, 3, 4],
    caption='Prioritas Evakuasi'
)

legend_html = '''
<div style="
    position: fixed; 
    bottom: 30px; 
    left: 30px; 
    width: 260px; 
    background: white; 
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    z-index: 9999; 
    padding: 15px;
    border-left: 5px solid #007bff;
    font-family: 'Arial';
">
    <h4 style="margin-top: 0; margin-bottom: 15px; color: #333;">
        🚨 PRIORITAS EVAKUASI
    </h4>
    <p style="margin: 5px 0;">
        <span style="background: #dc3545; width: 20px; height: 20px; display: inline-block; border-radius: 3px;"></span> 
        PRIORITAS 1 - KRITIS
    </p>
    <p style="margin: 5px 0;">
        <span style="background: #ffc107; width: 20px; height: 20px; display: inline-block; border-radius: 3px;"></span> 
        PRIORITAS 2 - TINGGI
    </p>
    <p style="margin: 5px 0;">
        <span style="background: #28a745; width: 20px; height: 20px; display: inline-block; border-radius: 3px;"></span> 
        PRIORITAS 3 - SEDANG
    </p>
    <p style="margin: 5px 0;">
        <span style="background: #17a2b8; width: 20px; height: 20px; display: inline-block; border-radius: 3px;"></span> 
        PRIORITAS 4 - RENDAH
    </p>
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))
colormap.add_to(m) 
m

print("="*70)
print("📊 ANALISIS STATISTIK - PRIORITAS EVAKUASI FASILITAS PENDIDIKAN")
print("="*70)

# 1. DISTRIBUSI PRIORITAS 
print("\n1. DISTRIBUSI PRIORITAS EVAKUASI:")
print("-"*50)
prioritas_counts = gdf_intersect['PRIORITAS'].value_counts()
for prioritas, jumlah in prioritas_counts.items():
    persen = (jumlah / len(gdf_intersect)) * 100
    print(f"   {prioritas}: {jumlah} zona ({persen:.1f}%)")

# 2. STATISTIK SKOR TOTAL
print("\n2. STATISTIK SKOR TOTAL:")
print("-"*50)
print(f"   Minimum    : {gdf_intersect['SKOR_TOTAL'].min():.1f}")
print(f"   Maksimum   : {gdf_intersect['SKOR_TOTAL'].max():.1f}")
print(f"   Rata-rata  : {gdf_intersect['SKOR_TOTAL'].mean():.1f}")
print(f"   Median     : {gdf_intersect['SKOR_TOTAL'].median():.1f}")

# 3. DISTRIBUSI RISIKO BANJIR
print("\n3. DISTRIBUSI RISIKO BANJIR:")
print("-"*50)
if 'RISIKO_BANJIR' in gdf_intersect.columns:
    banjir_counts = gdf_intersect['RISIKO_BANJIR'].value_counts()
    for risiko, jumlah in banjir_counts.items():
        persen = (jumlah / len(gdf_intersect)) * 100
        print(f"   {risiko}: {jumlah} zona ({persen:.1f}%)")

# 4. DISTRIBUSI KEPADATAN PENDUDUK
print("\n4. DISTRIBUSI KEPADATAN PENDUDUK:")
print("-"*50)
if 'KEPADATAN' in gdf_intersect.columns:
    padat_counts = gdf_intersect['KEPADATAN'].value_counts()
    for padat, jumlah in padat_counts.items():
        persen = (jumlah / len(gdf_intersect)) * 100
        print(f"   {padat}: {jumlah} zona ({persen:.1f}%)")

# 5. DISTRIBUSI FASILITAS PENDIDIKAN
print("\n5. DISTRIBUSI FASILITAS PENDIDIKAN:")
print("-"*50)
if 'DEKAT_PENDIDIKAN' in gdf_intersect.columns:
    pendidikan_counts = gdf_intersect['DEKAT_PENDIDIKAN'].value_counts()
    for status, jumlah in pendidikan_counts.items():
        persen = (jumlah / len(gdf_intersect)) * 100
        print(f"   {status}: {jumlah} zona ({persen:.1f}%)")

# 6. REKOMENDASI
print("\n6. INSIGHT & REKOMENDASI:")
print("-"*50)

zona_tinggi = len(gdf_intersect[gdf_intersect['PRIORITAS'].str.contains('TINGGI', na=False)])
zona_sedang = len(gdf_intersect[gdf_intersect['PRIORITAS'].str.contains('SEDANG', na=False)])

print(f"   • {zona_tinggi} zona PRIORITAS 2 - TINGGI: Perlu kesiapsiagaan tinggi")
print(f"   • {zona_sedang} zona PRIORITAS 3 - SEDANG: Monitoring rutin")
print(f"   • Total zona prioritas: {len(gdf_intersect)} zona")

if 'DEKAT_PENDIDIKAN' in gdf_intersect.columns:
    sekolah_ada = len(gdf_intersect[gdf_intersect['DEKAT_PENDIDIKAN'] == 'YA'])
    sekolah_tidak = len(gdf_intersect[gdf_intersect['DEKAT_PENDIDIKAN'] == 'TIDAK'])
    print(f"\n   • {sekolah_ada} zona dengan fasilitas pendidikan (perlu proteksi)")
    print(f"   • {sekolah_tidak} zona tanpa fasilitas pendidikan (potensi pembangunan)")

print("\n" + "="*70)

import os

output_dir = r"C:\UPSKILLING\WebGIS Development\Python for Spatial Data\WebGIS_Development\labs\sesi6_python_spatial\data_geojson"
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "hasil_analisis_prioritas_evakuasi")
gdf_intersect.to_file(output_path, driver='GeoJSON')
print(f"Hasil analisis berhasil disimpan di: {output_path}")




