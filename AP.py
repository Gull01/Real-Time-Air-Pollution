import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import pydeck as pdk
import datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API token from environment variables
AQICN_TOKEN = os.getenv("AQICN_API_TOKEN")

# Check if API token is available
if not AQICN_TOKEN:
    st.error("❌ API token not found! Please set AQICN_API_TOKEN in your environment variables or .env file.")
    st.info("💡 Create a .env file in your project directory with: AQICN_API_TOKEN=your_token_here")
    st.stop()

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
                
                # Define actual air pollutants vs environmental parameters
                air_pollutants = {
                    "pm25": {"name": "PM2.5", "desc": "Fine Particulate Matter", "unit": "µg/m³"},
                    "pm10": {"name": "PM10", "desc": "Coarse Particulate Matter", "unit": "µg/m³"},
                    "o3": {"name": "O₃", "desc": "Ozone", "unit": "µg/m³"},
                    "no2": {"name": "NO₂", "desc": "Nitrogen Dioxide", "unit": "µg/m³"},
                    "so2": {"name": "SO₂", "desc": "Sulfur Dioxide", "unit": "µg/m³"},
                    "co": {"name": "CO", "desc": "Carbon Monoxide", "unit": "mg/m³"}
                }
                
                environmental_params = {
                    "h": {"name": "Humidity", "desc": "Relative Humidity", "unit": "%"},
                    "p": {"name": "Pressure", "desc": "Atmospheric Pressure", "unit": "hPa"},
                    "t": {"name": "Temperature", "desc": "Air Temperature", "unit": "°C"},
                    "w": {"name": "Wind Speed", "desc": "Wind Speed", "unit": "m/s"},
                    "wg": {"name": "Wind Gust", "desc": "Wind Gust Speed", "unit": "m/s"},
                    "wd": {"name": "Wind Direction", "desc": "Wind Direction", "unit": "°"},
                    "r": {"name": "Rain", "desc": "Rainfall", "unit": "mm"},
                    "d": {"name": "Dew Point", "desc": "Dew Point Temperature", "unit": "°C"}
                }
                
                # Combine all parameters for display
                all_params = {**air_pollutants, **environmental_params}
                
                # Separate pollutants from environmental data
                df_pollutants = df_city[df_city["parameter"].str.lower().isin(air_pollutants.keys())].copy()
                df_environmental = df_city[df_city["parameter"].str.lower().isin(environmental_params.keys())].copy()
                
                # Update visualizations to show only air pollutants
                if not df_pollutants.empty:
                    st.subheader("🌬️ Air Pollutant Analysis")
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        # Bar chart with only pollutants
                        fig = px.bar(
                            df_pollutants, 
                            x="parameter", 
                            y="value",
                            title=f"🏭 Air Pollutant Levels in {city.title()}",
                            color="value",
                            color_continuous_scale="RdYlGn_r",
                            labels={"parameter": "Pollutant", "value": "Concentration"}
                        )
                        fig.update_layout(
                            xaxis_title="Air Pollutant Type",
                            yaxis_title="Concentration Level",
                            showlegend=False
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Pie chart for pollutant distribution
                        fig_pie = px.pie(
                            df_pollutants, 
                            values="value", 
                            names="parameter",
                            title="🥧 Pollutant Distribution"
                        )
                        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig_pie, use_container_width=True)
                
                # Environmental parameters chart
                if not df_environmental.empty:
                    st.subheader("🌤️ Environmental Conditions")
                    fig_env = px.bar(
                        df_environmental, 
                        x="parameter", 
                        y="value",
                        title=f"🌡️ Environmental Parameters in {city.title()}",
                        color="parameter",
                        labels={"parameter": "Parameter", "value": "Value"}
                    )
                    fig_env.update_layout(
                        xaxis_title="Environmental Parameter",
                        yaxis_title="Value",
                        showlegend=False
                    )
                    st.plotly_chart(fig_env, use_container_width=True)
                
                # Enhanced dataframe with proper categorization
                df_enhanced = df_city.copy()
                df_enhanced["Parameter Name"] = df_enhanced["parameter"].map(
                    lambda x: all_params.get(x.lower(), {}).get("name", x.upper())
                )
                df_enhanced["Description"] = df_enhanced["parameter"].map(
                    lambda x: all_params.get(x.lower(), {}).get("desc", "Environmental Parameter")
                )
                df_enhanced["Unit"] = df_enhanced["parameter"].map(
                    lambda x: all_params.get(x.lower(), {}).get("unit", "units")
                )
                df_enhanced["Category"] = df_enhanced["parameter"].map(
                    lambda x: "Air Pollutant" if x.lower() in air_pollutants else "Environmental"
                )
                
                # Display tables by category
                if not df_pollutants.empty:
                    st.subheader("🏭 Air Pollutants")
                    df_poll_display = df_enhanced[df_enhanced["Category"] == "Air Pollutant"][
                        ["Parameter Name", "Description", "value", "Unit", "time"]
                    ].rename(columns={"value": "Concentration", "time": "Timestamp"})
                    st.dataframe(df_poll_display, use_container_width=True, hide_index=True)
                
                if not df_environmental.empty:
                    st.subheader("🌤️ Environmental Parameters")
                    df_env_display = df_enhanced[df_enhanced["Category"] == "Environmental"][
                        ["Parameter Name", "Description", "value", "Unit", "time"]
                    ].rename(columns={"value": "Value", "time": "Timestamp"})
                    st.dataframe(df_env_display, use_container_width=True, hide_index=True)
                
                # Health recommendations based only on pollutants
                st.subheader("💡 Health Recommendations")
                if not df_pollutants.empty:
                    max_pollutant_value = df_pollutants["value"].max()
                    if max_pollutant_value <= 50:
                        st.success("✅ Air quality is good. Enjoy outdoor activities!")
                    elif max_pollutant_value <= 100:
                        st.warning("⚠️ Moderate air quality. Sensitive individuals should limit outdoor exposure.")
                    elif max_pollutant_value <= 150:
                        st.error("🚨 Unhealthy for sensitive groups. Consider reducing outdoor activities.")
                    else:
                        st.error("☠️ Unhealthy air quality. Avoid outdoor activities and consider wearing masks.")
                else:
                    st.info("No air pollutant data available for health assessment.")
                    
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
