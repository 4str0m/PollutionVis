from jupyter_dash import JupyterDash
import plotly.graph_objects as go
import dash
from dash import Dash, dcc, html, Input, Output, State
import pandas as pd
import plotly.express as px
import json

df = pd.read_csv('/home/benoit/Downloads/FR_E2_2021-01-03.csv', sep=';')
df = df[['Date de début', 'Date de fin', 'code site', 'nom site', 'Polluant', 'valeur', 'valeur brute', 'unité de mesure', 'validité']]

polluants = df['Polluant'].unique()

average_pollution_per_polluant_per_site = {}
for polluant in polluants:
    average_pollution_per_polluant_per_site[polluant] = pd.DataFrame
    df_of_polluant = df[df['Polluant'] == polluant]
    df_of_polluant_grouped_by_site = df_of_polluant.groupby(by=['code site'])
    average_pollution_per_polluant_per_site[polluant] = df_of_polluant_grouped_by_site.mean()

site_locations = pd.read_excel('/home/benoit/Downloads/Liste points de mesures 2020 pour site LCSQA_221292021.xlsx',
                     sheet_name='Points de mesure',
                     header=2)
site_locations = site_locations.rename(columns={'Code station': 'code site', 'Latitude': 'unused', 'Longitude': 'Latitude', 'NO2': 'Longitude'})
site_locations = site_locations[['code site', 'Nom station', 'Latitude', 'Longitude']]
site_locations = site_locations[(site_locations.Latitude > 0) & (site_locations.Longitude > -6)]

site_location_and_PM10_pollution = pd.merge(site_locations, average_pollution_per_polluant_per_site['PM10'], on=['code site'])

fig = go.Figure()

fig.add_trace(go.Scattermapbox(
        lat=site_location_and_PM10_pollution['Latitude'], lon=site_location_and_PM10_pollution['Longitude'],
        mode='markers',
        marker=go.scattermapbox.Marker(
            size=13,
            color='black'
        )
    ))

fig.add_trace(
    go.Scattermapbox(
        lat=site_location_and_PM10_pollution['Latitude'],
        lon=site_location_and_PM10_pollution['Longitude'],
        hovertemplate =
        '<b>%{text}</b><br>'+
        'N%{lat}° E%{lon}°',
        text = site_location_and_PM10_pollution["Nom station"],
        marker=go.scattermapbox.Marker(
            size=11,
            color=site_location_and_PM10_pollution['valeur'],
            colorscale=['yellow', 'orange', 'red']
        )
))


fig.update_layout(
    title='Pollution',
    autosize=True,
    margin={"r":0,"t":30,"l":0,"b":0},
    hovermode='closest',
    clickmode='event+select',
    showlegend=False,
    mapbox=dict(
        bearing=0,
        # labels={'valeur': 'µg/m3'},
        style="open-street-map",
        zoom=5,
        center=go.layout.mapbox.Center(
            lat=46.5,
            lon=3
        )
    ),
)

# Build small example app.
app = JupyterDash(__name__)

pollution_for_selected_site = df[(df['nom site'] == 'Lyon Périphérique') & (df['Polluant'] == 'PM10')]

app.layout =   html.Div([
    dcc.Graph(className='child', id='map_sensors', figure=fig),
    dcc.Graph(className='child', id='time_series1', figure={})
], className='parent')

@app.callback(
    Output('time_series1', 'figure'),
    Input('map_sensors', 'selectedData'))
def display_selected_data(selectedData):
    if selectedData is not None and len(selectedData) > 0:
        nom_site = selectedData['points'][0]['text']
        pollution_for_selected_site = df[(df['nom site'] == nom_site) & (df['Polluant'] == 'PM10')]
        fig = go.Figure(go.Scatter(x=pollution_for_selected_site['Date de début'], y=pollution_for_selected_site['valeur']))
        fig.update_traces(mode='lines+markers')
        return fig
    else:
        return {}

if __name__ == '__main__':
    app.run_server(mode='external', debug=True)