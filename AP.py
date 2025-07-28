import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import pydeck as pdk
import datetime

AQICN_TOKEN = "774abaf823c71f1fea9228a928c51651040157de"  # AQICN API token

def extract_time_from_api(time_data):
    """Helper function to extract time consistently from API response"""
    if isinstance(time_data, dict):
        return time_data.get("s", "")
    elif isinstance(time_data, str):
        return time_data
    else:
        return ""

def fetch_data(city):
    # AQICN API expects city/station name in the URL
    url = f"https://api.waqi.info/feed/{city}/"
    params = {"token": AQICN_TOKEN}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "ok":
            iaqi = data["data"].get("iaqi", {})
            time = extract_time_from_api(data["data"].get("time", {}))
            city_geo = data["data"].get("city", {}).get("geo", None)
            rows = []
            for pollutant, value in iaqi.items():
                rows.append({
                    "parameter": pollutant,
                    "value": value.get("v"),
                    "time": time
                })
            return pd.DataFrame(rows), city_geo
        else:
            st.error(f"No data returned by API for city: {city}. ({data.get('data')})")
            return pd.DataFrame(), None
    else:
        st.error(f"Error fetching data. Status: {response.status_code}, Details: {response.text}")
        return pd.DataFrame(), None

def fetch_global_aqi():
    # Fetch AQI data for a wide bounding box (worldwide)
    url = "https://api.waqi.info/map/bounds/"
    params = {
        "token": AQICN_TOKEN,
        "latlng": "-85,-180,85,180"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "ok":
            stations = data.get("data", [])
            rows = []
            for s in stations:
                # Extract proper station/city name
                station_name = ""
                
                # Try station field first
                station_field = s.get("station", None)
                if isinstance(station_field, dict):
                    station_name = station_field.get("name", "")
                elif isinstance(station_field, str):
                    station_name = station_field
                
                # If no station name, try city field
                if not station_name:
                    city_field = s.get("city", None)
                    if isinstance(city_field, dict):
                        station_name = city_field.get("name", "")
                    elif isinstance(city_field, str):
                        station_name = city_field
                
                # Final fallback to UID
                if not station_name:
                    station_name = f"Station {s.get('uid', 'Unknown')}"
                
                # Since map bounds API doesn't provide time, use a consistent format
                # that matches what we show in the table
                time_str = "Real-time data"  # Simple consistent message
                
                rows.append({
                    "city": station_name,
                    "lat": s.get("lat"),
                    "lon": s.get("lon"),
                    "aqi": s.get("aqi"),
                    "uid": s.get("uid"),
                    "time": time_str
                })
            return pd.DataFrame(rows)
        else:
            st.warning("No global AQI data found.")
            return pd.DataFrame()
    else:
        st.warning("Failed to fetch global AQI data.")
        return pd.DataFrame()

def main():
    st.title("Real-Time Air Pollution Dashboard (AQICN)")

    tab1, tab2 = st.tabs(["🌍 Map View", "📊 Graph & Table"])

    with st.sidebar:
        st.header("Search Options")
        city = st.text_input("Enter City (e.g., delhi, beijing, los angeles)", value="delhi")
        search = st.button("Fetch Data")

    # Fetch global AQI data for map
    df_map = fetch_global_aqi()
    # Default map view
    map_center = [20, 0]
    map_zoom = 1

    # If user searches for a city, fetch its data and geo
    df_city = pd.DataFrame()
    city_geo = None
    if search:
        df_city, city_geo = fetch_data(city)
        if city_geo and len(city_geo) == 2:
            map_center = city_geo
            map_zoom = 8

    # --- Tab 1: Map View ---
    with tab1:
        st.subheader("Global AQI Map (OpenStreetMap)")
        if not df_map.empty:
            df_map["aqi"] = pd.to_numeric(df_map["aqi"], errors="coerce")
            df_map = df_map.dropna(subset=["lat", "lon", "aqi"])
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=df_map,
                get_position='[lon, lat]',
                get_color='[255, 255-(aqi*2), 0, 160]',
                get_radius=12000,
                pickable=True,
                radius_min_pixels=4,
                radius_max_pixels=20,
                auto_highlight=True,
            )
            view_state = pdk.ViewState(
                longitude=map_center[1],
                latitude=map_center[0],
                zoom=map_zoom,
                min_zoom=1,
                max_zoom=15,
                pitch=0,
                bearing=0
            )
            tooltip = {
                "html": "<b>City:</b> {city} <br/> <b>AQI:</b> {aqi}",
                "style": {"backgroundColor": "steelblue", "color": "white"}
            }
            st.pydeck_chart(pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",  # OSM style
                initial_view_state=view_state,
                layers=[layer],
                tooltip=tooltip
            ), use_container_width=True)
            st.info("Click or hover on a marker to see AQI and city info. If you searched for a city, the map is centered on it.")
        else:
            st.warning("No global AQI data to display.")

    # --- Tab 2: Graph & Table ---
    with tab2:
        st.subheader("City Pollutant Details")
        if search:
            if df_city.empty:
                st.error(f"No data found for the specified city: {city}.")
            else:
                # Display city name and timestamp
                st.markdown(f"### 📍 **{city.title()}** Air Quality Data")
                if not df_city["time"].iloc[0]:
                    st.caption("⏰ Real-time data")
                else:
                    st.caption(f"⏰ Last updated: {df_city['time'].iloc[0]}")
                
                # Key metrics in columns
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Total Pollutants", len(df_city))
                with col2:
                    avg_value = df_city["value"].mean()
                    st.metric("📈 Average Level", f"{avg_value:.1f}")
                with col3:
                    max_pollutant = df_city.loc[df_city["value"].idxmax()]
                    st.metric("⚠️ Highest", f"{max_pollutant['parameter'].upper()}: {max_pollutant['value']}")
                
                st.divider()
                
                # Enhanced visualizations
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Bar chart with color coding
                    fig = px.bar(
                        df_city, 
                        x="parameter", 
                        y="value",
                        title=f"🌬️ Pollutant Levels in {city.title()}",
                        color="value",
                        color_continuous_scale="RdYlGn_r",
                        labels={"parameter": "Pollutant", "value": "Concentration"}
                    )
                    fig.update_layout(
                        xaxis_title="Pollutant Type",
                        yaxis_title="Concentration Level",
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Pie chart for pollutant distribution
                    fig_pie = px.pie(
                        df_city, 
                        values="value", 
                        names="parameter",
                        title="🥧 Pollutant Distribution"
                    )
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                # Enhanced data table
                st.subheader("📋 Detailed Data Table")
                # Add pollutant descriptions
                pollutant_info = {
                    "pm25": {"name": "PM2.5", "desc": "Fine Particulate Matter", "unit": "µg/m³"},
                    "pm10": {"name": "PM10", "desc": "Coarse Particulate Matter", "unit": "µg/m³"},
                    "o3": {"name": "O₃", "desc": "Ozone", "unit": "µg/m³"},
                    "no2": {"name": "NO₂", "desc": "Nitrogen Dioxide", "unit": "µg/m³"},
                    "so2": {"name": "SO₂", "desc": "Sulfur Dioxide", "unit": "µg/m³"},
                    "co": {"name": "CO", "desc": "Carbon Monoxide", "unit": "mg/m³"}
                }
                
                # Enhance dataframe with descriptions
                df_enhanced = df_city.copy()
                df_enhanced["Pollutant Name"] = df_enhanced["parameter"].map(
                    lambda x: pollutant_info.get(x, {}).get("name", x.upper())
                )
                df_enhanced["Description"] = df_enhanced["parameter"].map(
                    lambda x: pollutant_info.get(x, {}).get("desc", "Unknown")
                )
                df_enhanced["Unit"] = df_enhanced["parameter"].map(
                    lambda x: pollutant_info.get(x, {}).get("unit", "Unknown")
                )
                
                # Reorder columns
                df_display = df_enhanced[["Pollutant Name", "Description", "value", "Unit", "time"]].rename(
                    columns={"value": "Concentration", "time": "Timestamp"}
                )
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Health recommendations
                st.subheader("💡 Health Recommendations")
                max_value = df_city["value"].max()
                if max_value <= 50:
                    st.success("✅ Air quality is good. Enjoy outdoor activities!")
                elif max_value <= 100:
                    st.warning("⚠️ Moderate air quality. Sensitive individuals should limit outdoor exposure.")
                elif max_value <= 150:
                    st.error("🚨 Unhealthy for sensitive groups. Consider reducing outdoor activities.")
                else:
                    st.error("☠️ Unhealthy air quality. Avoid outdoor activities and consider wearing masks.")
                    
        else:
            # Welcome message with instructions
            st.markdown("""
            ### 🎯 Welcome to Air Quality Analysis
            
            **How to use:**
            1. 🔍 Enter a city name in the sidebar (e.g., delhi, beijing, paris)
            2. 📊 Click "Fetch Data" to get real-time air quality information
            3. 🗺️ View global data on the Map tab
            4. 📈 Analyze detailed pollutant data here
            
            **Available Cities:** Try major cities like Delhi, Beijing, London, New York, Tokyo, etc.
            """)
            
            # Sample chart for demonstration
            sample_data = pd.DataFrame({
                "parameter": ["PM2.5", "PM10", "O₃", "NO₂"],
                "value": [35, 45, 80, 25]
            })
            fig_sample = px.bar(
                sample_data, 
                x="parameter", 
                y="value",
                title="📊 Sample Air Quality Data",
                color="value",
                color_continuous_scale="RdYlGn_r"
            )
            st.plotly_chart(fig_sample, use_container_width=True)

if __name__ == '__main__':
    main()