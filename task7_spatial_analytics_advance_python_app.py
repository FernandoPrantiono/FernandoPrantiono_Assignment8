import streamlit as st
import folium
from streamlit_folium import folium_static
import requests
import pandas as pd
import json

# Konfigurasi halaman
st.set_page_config(
    page_title="Dashboard Prioritas Evakuasi Banjir",
    page_icon="🌊",
    layout="wide"
)

st.title("🌊 Dashboard Prioritas Evakuasi Banjir Jakarta")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("🔍 Kontrol")
    
    # Tombol ambil data
    if st.button("🔄 Ambil Data dari Flask", type="primary"):
        with st.spinner("Mengambil data..."):
            try:
                response = requests.get('http://127.0.0.1:5000/api/hasil_analisis')
                if response.status_code == 200:
                    st.session_state['data'] = response.json()
                    st.success("✅ Data berhasil diambil!")
                    st.balloons()
                else:
                    st.error(f"❌ Error: {response.status_code}")
            except Exception as e:
                st.error(f"❌ Gagal connect ke Flask: {e}")
                st.info("Jalankan Flask dulu: python day04_spatial_analytics_advance_python_api.py")
    
    # Tampilkan info jika data ada
    if 'data' in st.session_state:
        st.markdown("---")
        st.subheader("📊 Ringkasan")
        features = st.session_state['data']['features']
        st.metric("Jumlah Zona", len(features))

# Main content - hanya tampil jika data ada
if 'data' in st.session_state:
    data = st.session_state['data']
    
    # Buat 2 kolom
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("🗺️ Peta Prioritas Evakuasi")
        
        # Buat peta
        m = folium.Map(location=[-6.23, 106.83], zoom_start=11, tiles='cartodbpositron')
        
        # Warna berdasarkan prioritas
        warna = {
            'PRIORITAS 1 - KRITIS': '#dc3545',  # Merah
            'PRIORITAS 2 - TINGGI': '#ffc107',  # Kuning
            'PRIORITAS 3 - SEDANG': '#28a745',  # Hijau
            'PRIORITAS 4 - RENDAH': '#17a2b8'   # Biru
        }
        
        # Style function
        def style_function(feature):
            prioritas = feature['properties'].get('PRIORITAS', '')
            return {
                'fillColor': warna.get(prioritas, '#6c757d'),
                'color': 'white',
                'weight': 1,
                'fillOpacity': 0.7
            }
        
        # Tooltip
        tooltip = folium.GeoJsonTooltip(
            fields=['PRIORITAS', 'SKOR_TOTAL', 'RISIKO_BANJIR', 'KEPADATAN', 'DEKAT_PENDIDIKAN'],
            aliases=['Prioritas:', 'Skor:', 'Risiko Banjir:', 'Kepadatan:', 'Ada Sekolah:'],
            localize=True,
            sticky=False,
            labels=True,
            style="""
                background-color: #F0EFEF;
                border: 2px solid black;
                border-radius: 3px;
                box-shadow: 3px;
            """,
            max_width=800,
        )
        
        # Tambahkan ke peta
        folium.GeoJson(
            data,
            style_function=style_function,
            tooltip=tooltip
        ).add_to(m)
        
        # Tampilkan peta
        folium_static(m, width=800, height=500)
    
    with col2:
        st.subheader("📋 Legenda")
        st.markdown("🔴 **Prioritas 1** - KRITIS")
        st.markdown("🟡 **Prioritas 2** - TINGGI")
        st.markdown("🟢 **Prioritas 3** - SEDANG")
        st.markdown("🔵 **Prioritas 4** - RENDAH")
        
        # Statistik cepat
        st.markdown("---")
        st.subheader("📈 Statistik Cepat")
        
        # Hitung distribusi prioritas
        priorities = [f['properties']['PRIORITAS'] for f in data['features']]
        priority_counts = pd.Series(priorities).value_counts()
        
        for priority, count in priority_counts.items():
            st.write(f"{priority}: {count} zona")
    
    # Tampilkan data dalam tabel
    st.markdown("---")
    st.subheader("📋 Data Detail")
    
    # Buat dataframe dari properties
    df_data = []
    for feature in data['features']:
        props = feature['properties']
        df_data.append({
            'Prioritas': props.get('PRIORITAS', ''),
            'Skor Total': props.get('SKOR_TOTAL', 0),
            'Risiko Banjir': props.get('RISIKO_BANJIR', ''),
            'Kepadatan': props.get('KEPADATAN', ''),
            'Ada Sekolah': props.get('DEKAT_PENDIDIKAN', '')
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True)
    
else:
    # Tampilkan pesan jika belum ambil data
    st.info("👈 Klik tombol 'Ambil Data dari Flask' di sidebar untuk memulai")
    st.image("https://via.placeholder.com/800x400?text=Klik+tombol+di+sidebar+untuk+melihat+peta", use_container_width=True)

# Footer
st.markdown("---")
st.caption("WebGIS Flood Evacuation Priority - Education Sector | Data dari Flask API")