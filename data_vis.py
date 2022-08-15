from jupyter_dash import JupyterDash
import plotly.graph_objects as go
import dash
from dash import Dash, dcc, html, Input, Output, State, ctx
import pandas as pd
import plotly.express as px
import json
import requests
import numpy as np
from io import StringIO
from os.path import exists

# Load site locations from the internet
# This will allow us, using the site's code, to plot all our stations on a map
# Note: it has some incoherencies that we fix here (i.e. misnamed columns)
site_locations_url = 'https://www.lcsqa.org/system/files/media/documents/Liste%20points%20de%20mesures%202020%20pour%20site%20LCSQA_221292021.xlsx'
site_locations = pd.read_excel(site_locations_url, sheet_name='Points de mesure', header=2)
site_locations = site_locations.rename(columns={'Code station': 'code site', 'Latitude': 'unused', 'Longitude': 'Latitude', 'NO2': 'Longitude'})
site_locations = site_locations[['code site', 'Nom station', 'Latitude', 'Longitude']]
site_locations = site_locations[(site_locations.Latitude > 0) & (site_locations.Longitude > -6)]

# Load pollution data
# We only load some of the available dates for speed
def get_data():
    feather_file = 'pollution_data.feather'
    if exists(feather_file):
        return pd.read_feather(feather_file)
    else:
        url_tpl = 'https://files.data.gouv.fr/lcsqa/concentrations-de-polluants-atmospheriques-reglementes/temps-reel/2021/FR_E2_2021-{:02}-{:02}.csv'
        wanted_columns = ['Date de début', 'Date de fin', 'code site', 'nom site', 'Polluant', 'valeur', 'valeur brute', 'unité de mesure', 'validité']

        all_dfs = []
        for month in range(1):
            for day in range(7):
                url = url_tpl.format(month+1, day+1)
                response = requests.get(url)
                print('Loading {}'.format(url))
                if not response.ok:
                    continue
                csv_str = response.content.decode('utf-8')
                csv_str_io = StringIO(csv_str)
                df = pd.read_csv(csv_str_io, sep=';')
                df = df[wanted_columns]
                # convert the 'Date' column to datetime format
                df['Date de début']= pd.to_datetime(df['Date de début'])
                df['Date de fin']= pd.to_datetime(df['Date de fin'])
                all_dfs.append(df)
        df = pd.concat(all_dfs).reset_index()
        df.fillna(0)
        df.to_feather(feather_file)
        return df

df = get_data()
# Gather a list of all available polluants
polluants = df['Polluant'].unique()
site_names = df['nom site'].unique()

# only keep locations that have pollution data
site_locations = site_locations[site_locations['Nom station'].isin(site_names)]

# Combined all these informations into on DataFrame for plotting
df_mean_pollution = df[['code site', 'valeur']].groupby(by=['code site']).mean()

fig = go.Figure()
# This Scatter plot acts as an outline for our points
fig.add_trace(go.Scattermapbox(
        lat=site_locations['Latitude'], lon=site_locations['Longitude'],
        mode='markers',
        marker=go.scattermapbox.Marker(
            size=13,
            color='black'
        )
    ))

# This plots ou actual data, colored by average pollution levels
fig.add_trace(
    go.Scattermapbox(
        lat=site_locations['Latitude'],
        lon=site_locations['Longitude'],
        hovertemplate =
        '<b>%{text}</b><br>'+
        '%{lat}°<b>N</b> %{lon}°<b>E</b>',
        text = site_locations["Nom station"],
        marker=go.scattermapbox.Marker(
            size=11,
            color=df_mean_pollution['valeur'],
            opacity=0.9,
            colorscale=['yellow', 'orange', 'red']
        )
))

fig.update_layout(
    autosize=True,
    margin={"r":10,"t":30,"l":10,"b":10},
    hovermode='closest',
    clickmode='event+select',
    showlegend=False,
    mapbox=dict(
        bearing=0,
        style="open-street-map",
        zoom=5,
        center=go.layout.mapbox.Center(
            lat=46.5,
            lon=3
        )
    ),
)
fig.data[0].update(unselected={'marker': {'opacity':1}})
fig.data[1].update(selected={'marker': {'size':14, 'color':'#33ee44', 'opacity':1}}, unselected={'marker': {'opacity':0.8}})

DEFAULT_PLOTLY_COLORS=['rgb(31, 119, 180)', 'rgb(255, 127, 14)',
                       'rgb(44, 160, 44)', 'rgb(214, 39, 40)',
                       'rgb(148, 103, 189)', 'rgb(140, 86, 75)',
                       'rgb(227, 119, 194)', 'rgb(127, 127, 127)',
                       'rgb(188, 189, 34)', 'rgb(23, 190, 207)']

# Build small example app.
app = JupyterDash(__name__)

pollution_for_selected_site = df[(df['nom site'] == 'Lyon Périphérique') & (df['Polluant'] == 'PM10')]

def create_empty_figure(polluant):
    fig = go.Figure()
    fig.update_layout(title=f'<b>{polluant}</b>', title_y=0.8, title_x=0.03, margin={'l':0, 'r':0, 't':30, 'b':0}, yaxis_title=None, xaxis_title=None)
    return fig

checklist = dcc.Checklist(
    polluants,
    polluants,
    inline=True,
    id='pollution_checklist'
)

app.layout =   html.Div([
    dcc.Graph(className='child', id='map_sensors', figure=fig),
    html.Div(children=[checklist, html.Div([html.H1('Select location on map to'), html.H1('display pollution data')])],
             className='child',
             id='line_graphs')
], className='parent')

color_palettes = [px.colors.qualitative.Plotly,
                  px.colors.qualitative.D3,
                  px.colors.qualitative.Antique,
                  px.colors.qualitative.Bold,
                  px.colors.qualitative.Safe,
                  px.colors.qualitative.Vivid,
                  px.colors.qualitative.Set3,
                  px.colors.qualitative.Dark2]

# Builds all the line graphs from the selected point
@app.callback(
    Output('line_graphs', 'children'),
    Input('map_sensors', 'selectedData'),
    Input('pollution_checklist', 'value'))
def display_selected_data(selectedData, value):
    checklist.value = value
    if selectedData is not None and len(selectedData) > 0:
        site_names = [selected_point['text'] for selected_point in selectedData['points']]
        pollution_for_selected_sites = [df[df['nom site'] == site_name] for site_name in site_names]
        children = [checklist]
        for i, polluant in enumerate(polluants):
            if polluant not in value:
                continue
            all_dfs = []
            for pollution_for_selected_site in pollution_for_selected_sites:
                all_dfs.append(pollution_for_selected_site[pollution_for_selected_site['Polluant'] == polluant])
            pollution_for_selected_site_for_polluant = pd.concat(all_dfs)
            if pollution_for_selected_site_for_polluant.empty:
                continue
            fig = px.line(pollution_for_selected_site_for_polluant,
                          x='Date de début', y='valeur', color='nom site',
                          color_discrete_sequence=color_palettes[i])
            fig.update_traces(line_width=1) #, line_color=DEFAULT_PLOTLY_COLORS[i])
            fig.update_layout(title=f'<b>{polluant}</b>',
                              title_y=0.8, title_x=0.03,
                              margin={'l':0, 'r':0, 't':30, 'b':0},
                              yaxis_title=None, xaxis_title=None)
            graph = dcc.Graph(id=polluant.replace('.', '_'), figure=fig, className='line-graph')
            children.append(graph)

        if len(children) == 1:
            return [checklist, html.H1('No data for locations: {}.'.format(site_names))]
        graph_height = '{}%'.format(100/(len(children)-1))
        for graph in children[1:]:
            graph.style = {'height': graph_height}
        return children
    else:
        return [checklist, html.Div([html.H1('Select location on map to'), html.H1('display pollution data')])]


if __name__ == '__main__':
    app.run_server(mode='external', debug=True)