#  Real-Time Air Pollution Dashboard

A comprehensive web application built with Streamlit that provides real-time air quality data visualization using the AQICN API.

##  Features

- **Interactive World Map**: Global AQI data visualization with OpenStreetMap
- **Detailed Analytics**: City-specific pollutant analysis with charts and tables
- **Real-time Data**: Live air quality information from AQICN API
- **Health Recommendations**: Actionable advice based on air quality levels
- **Responsive Design**: Works on desktop and mobile devices

## Demo
<img width="1348" height="659" alt="image" src="https://github.com/user-attachments/assets/d6232e4f-ddf2-490f-abed-094a83685563" />
<img width="1270" height="612" alt="image" src="https://github.com/user-attachments/assets/56996db1-0adc-499c-a5fa-d28b3ed6cfae" />



## 🛠️ Installation

1. **Install dependencies**
    streamlit>=1.28.0
    requests>=2.31.0
    pandas>=2.0.0
    plotly>=5.15.0
    pydeck>=0.8.0


3. **Get AQICN API Token**
   - Visit [AQICN Token Request](https://aqicn.org/data-platform/token/)
   - Replace the token in `AP.py` with your token

4. **Run the application**
   ```bash
   streamlit run AP.py
   ```

## 📋 Usage

1. **Map View Tab**: 
   - View global AQI data on an interactive map
   - Hover over markers to see city and AQI information
   - Search for specific cities to zoom to that location

2. **Graph & Table Tab**:
   - Enter a city name in the sidebar
   - Click "Fetch Data" to get detailed pollutant information
   - View bar charts, pie charts, and detailed data tables
   - Get health recommendations based on air quality

## 🔧 Technologies Used

- **Streamlit**: Web application framework
- **Plotly**: Interactive data visualization
- **PyDeck**: Map visualization with OpenStreetMap
- **Pandas**: Data manipulation and analysis
- **AQICN API**: Real-time air quality data source

## 📊 Supported Pollutants

- PM2.5 (Fine Particulate Matter)
- PM10 (Coarse Particulate Matter)
- O₃ (Ozone)
- NO₂ (Nitrogen Dioxide)
- SO₂ (Sulfur Dioxide)
- CO (Carbon Monoxide)



## Acknowledgments

- [AQICN](https://aqicn.org/) for providing the air quality API
- [Streamlit](https://streamlit.io/) for the amazing web framework
- [OpenStreetMap](https://www.openstreetmap.org/) for map data

## 📞 Contact

Your Name Gul Nawaz
Email: gulnawaz001@outlook.com

