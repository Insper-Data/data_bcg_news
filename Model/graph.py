import json
import os
from urllib.request import urlopen

import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import plotly.express as px
import sys
from plotly.tools import mpl_to_plotly
from configs import *
from model_v2 import *

import pandas as pd
from wordcloud import WordCloud
from io import BytesIO
import base64
import matplotlib.pyplot as plt


class Graficos:
    def __init__(self, load = False):
        self.Brazil = ''
        self.state_id_map = {}
        self.dicionario_filtro = {'Acre': 'AC',
                                  'Alagoas': 'AL',
                                  'Amapá': 'AP',
                                  'Amazonas': 'AM',
                                  'Bahia': 'BA',
                                  'Ceará': 'CE',
                                  'Distrito Federal': 'DF',
                                  'Espírito Santo': 'ES',
                                  'Goiás': 'GO',
                                  'Maranhão': 'MA',
                                  'Mato Grosso': 'MT',
                                  'Mato Grosso do Sul': 'MS',
                                  'Minas Gerais': 'MG',
                                  'Pará': 'PA',
                                  'Paraíba': 'PB',
                                  'Paraná': 'PR',
                                  'Pernambuco': 'PE',
                                  'Piauí': 'PI',
                                  'Rio de Janeiro': 'RJ',
                                  'Rio Grande do Norte': 'RN',
                                  'Rio Grande do Sul': 'RS',
                                  'Rondônia': 'RO',
                                  'Roraima': 'RR',
                                  'Santa Catarina': 'SC',
                                  'São Paulo': 'SP',
                                  'Sergipe': 'SE',
                                  'Tocantins': 'TO'}
        self.df_aux = ''
        self.df = ''
        self.df2 = ''
        self.colors = ['Tealgrn', 'dense', 'algae', 'Aggrnyl', 'Teal', 'Agsunset', 'Tealgrn', 'dense', 'algae',
                       'Aggrnyl',
                       'Teal', 'Agsunset']
        self.rgb_first_continuos_color = {'Tealgrn': 'rgb(176, 242, 188)',
                                          'dense': 'rgb(230, 240, 240)',
                                          'algae': 'rgb(214, 249, 207)',
                                          'Aggrnyl': 'rgb(36, 86, 104)',
                                          'Teal': 'rgb(209, 238, 234)',
                                          'Agsunset': 'rgb(75, 41, 145)'}

        self.rgb_last_continuos_color = {'Tealgrn': 'rgb(37, 125, 152)',
                                         'dense': 'rgb(54, 14, 36)',
                                         'algae': 'rgb(17, 36, 20)',
                                         'Aggrnyl': 'rgb(237, 239, 93)',
                                         'Teal': 'rgb(42, 86, 116)',
                                         'Agsunset': 'rgb(237, 217, 163)'}
        self.zeus = ''
        self.load = load
        self.df_final = ''
        self.agregado = ''
        self.df_agregado = ''
        self.is_load = False
        self.df_loaded = False
        self.df_loadedv2 = False
        self.discreate_colors = ''

    def pega_conteudo_auxilar(self):
        with urlopen(
                'https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson') as response:
            self.Brazil = json.load(response)  # Javascrip object notation
        self.df_aux = pd.read_csv('https://raw.githubusercontent.com/nayanemaia/Dataset_Soja/main/soja%20sidra.csv')

    def executa_zeus(self, termo, usuario):

        termo = termo
        user = USERS[f'{usuario.capitalize()}']
        path_files = constroi_id(termo)
        treino_id = path_files[0]
        teste_id = path_files[1]

        print(treino_id, teste_id)

        self.zeus = Zeus(
            termo=termo,
            user=user,
            treino_id=treino_id,
            test_id=teste_id
        )

    def roda_modelo(self, local, data_start, data_end):

        if local == 'TUDO':
            local = False

        self.zeus.filtrar_treino(local=local,
                                 data_start=data_start,
                                 data_end=data_end)

        self.zeus.criar_base_sintetica(numero_de_amostras=NUMERO_DE_AMOSTRAS,
                                       porcentagem_para_criacao=PORCENTAGEM_PARA_CRIACAO)
        self.zeus.treina_lightGBM()

        self.zeus.rodando_louvain(porcentagem_do_sample=PORCENTAGEM_PARA_SAMPLE)

        self.zeus.pega_variaveis(teste=True)

        self.zeus.filtrar_teste(local=local,
                                data_start=data_start,
                                data_end=data_end)

        self.zeus.classifica_agrupamento()

        self.df = self.zeus.faz_agregacao()

    def faz_agregacao(self, df, is_load):
        # Agrega os resultados
        self.is_load = is_load
        self.df_loaded = df.copy()
        self.df_loadedv2 = df.copy()
        self.df_loaded.drop(columns=['unique_identifier', 'sigla'], inplace=True)
        self.agregado = df[['unique_identifier', 'sigla', 'data', 'label']]
        self.df_agregado = pd.crosstab(self.agregado.sigla, self.agregado.label, normalize='index')

        self.df = self.df_agregado

    def coleta_dados_do_json(self):
        for feature in self.Brazil['features']:
            feature['id'] = feature['properties']['name']
            self.state_id_map[feature['properties']['sigla']] = feature['id']

    def prepara_df_aux(self):
        self.df_aux.Estado = self.df_aux.Estado.map(self.dicionario_filtro)
        self.df_aux.drop_duplicates(subset=['Estado'], inplace=True)
        self.df_aux.drop(['Unnamed: 5', 'Produção', 'ano'], axis=1, inplace=True)
        self.df_aux.set_index('Estado', inplace=True)

    def cria_df_pronto(self):
        self.df2 = pd.concat([self.df_aux, self.df], axis=1)
        self.df2.fillna(value=0, inplace=True)
        self.df2['Estado'] = self.df2.index
        self.df2['Estado'] = self.df2.Estado.map(self.state_id_map)
        colunas = self.df2.columns.tolist()
        numero_de_clusters = []
        map_clusters = {}
        for index, coluna in enumerate(colunas):
            if isinstance(coluna, int):
                map_clusters[coluna] = f'cluster {coluna}'
                numero_de_clusters.append(index)

        self.df2.rename(columns=map_clusters, inplace=True)

        return numero_de_clusters

    def constroi_grafico_1(self, n_cluster):

        lista_fig = []
        #print(self.df2)
        for numero in range(n_cluster):
            try:
                fig = px.choropleth(
                    data_frame=self.df2,
                    locations='Estado',
                    geojson=self.Brazil,
                    color=f'cluster {numero}',
                    hover_name='Estado',
                    hover_data=[f'cluster {numero}', "Longitude", "Latitude"],
                    color_continuous_scale=self.colors[numero]
                )
                fig.update(layout_coloraxis_showscale=False)
                fig.update_geos(fitbounds="locations", visible=False)
                fig.update_layout(title_text=f"<b>Estados com mais noticias no cluster {numero}<b>", title_x=0.5,
                                  )

                lista_fig.append(fig)
            except:
                lista_fig.append('')
        return lista_fig

    def constroi_grafico_2(self, numero2, n_cluster):
        lista_fig = []

        for numero in range(n_cluster):
            if self.is_load:
                try:
                    #print(self.df_loaded.head())
                    df_data = pd.DataFrame({'word': self.df_loaded[self.df_loaded.label == numero].drop(
                        columns=['label', 'sentimento']).sum(axis=0).nlargest(numero2).index.tolist(),
                                            'value': self.df_loaded[self.df_loaded.label == numero].drop(
                                                columns=['label']).sum(axis=0).nlargest(numero2).values.tolist()})
                    scale = [(self.rgb_last_continuos_color[self.colors[numero]]),
                             (self.rgb_last_continuos_color[self.colors[numero]])]

                    fig = px.bar(df_data, x='word', y='value', color_continuous_scale=scale,
                                 color='value',
                                 )
                    fig.update(layout_coloraxis_showscale=False)
                    fig.update_layout(title_text=f"<b>As palavras que mais aparecem no cluster {numero}<b>",
                                      title_x=0.5,
                                      template='simple_white')

                    fig.update_xaxes(showgrid=False)
                    fig.update_yaxes(showgrid=False)
                    lista_fig.append(fig)

                except:
                    lista_fig.append('')

            else:
                try:
                    df_data = pd.DataFrame({'word': self.zeus.var_teste[self.zeus.var_teste.label == numero].drop(
                        columns=['label']).sum(axis=0).nlargest(numero2).index.tolist(),
                                            'value': self.zeus.var_teste[self.zeus.var_teste.label == numero].drop(
                                                columns=['label']).sum(axis=0).nlargest(numero2).values.tolist()})
                    scale = [(self.rgb_last_continuos_color[self.colors[numero]]),
                             (self.rgb_last_continuos_color[self.colors[numero]])]

                    fig = px.bar(df_data, x='word', y='value', color_continuous_scale=scale,
                                 color='value',
                                 )
                    fig.update(layout_coloraxis_showscale=False)
                    fig.update_layout(title_text=f"<b>As palavras que mais aparecem no cluster {numero}<b>", title_x=0.5,
                                      template='simple_white')

                    fig.update_xaxes(showgrid=False)
                    fig.update_yaxes(showgrid=False)
                    lista_fig.append(fig)

                except:
                    lista_fig.append('')

        return lista_fig

    def plot_wordcloud(self, data):

        d = {a: x for a, x in data.values}
        wc = WordCloud(background_color='white', width=700, height=450)
        wc.fit_words(d)
        return wc.to_image()

    def constroi_grafico_3(self, numero2, n_cluster):
        lista_fig = []

        for numero in range(n_cluster):
            # try:
            if self.is_load:
                df_data = pd.DataFrame({'word': self.df_loaded[self.df_loaded.label == numero].drop(
                    columns=['label', 'sentimento']).sum(axis=0).nlargest(numero2).index.tolist(),
                                        'value': self.df_loaded[self.df_loaded.label == numero].drop(
                                            columns=['label']).sum(axis=0).nlargest(numero2).values.tolist()})
                #print(df_data)

                df_data.value = df_data.value.astype(float)
                df_data.value += +0.001
                img = BytesIO()
                #print(df_data.head())
                imagem_wc = self.plot_wordcloud(df_data)
                imagem_wc.save(img, format='PNG')

                lista_fig.append('data:image/png;base64,{}'.format(base64.b64encode(img.getvalue()).decode()))
                print('WC FOI FEITO')

            else:
                df_data = pd.DataFrame({'word': self.zeus.var_teste[self.zeus.var_teste.label == numero].drop(
                    columns=['label', 'sentimento']).sum(axis=0).nlargest(numero2).index.tolist(),
                                        'value': self.zeus.var_teste[self.zeus.var_teste.label == numero].drop(
                                            columns=['label']).sum(axis=0).nlargest(numero2).values.tolist()})
                #print(df_data)

                df_data.value = df_data.value.astype(float)
                df_data.value += +0.001
                img = BytesIO()
                print(df_data.head())
                imagem_wc = self.plot_wordcloud(df_data)
                imagem_wc.save(img, format='PNG')

                lista_fig.append('data:image/png;base64,{}'.format(base64.b64encode(img.getvalue()).decode()))
                print('WC FOI FEITO')
        return lista_fig

    def constroi_grafico_4(self, n_cluster):
        lista_fig = []
        if not self.is_load:

            df_work = self.zeus.var_teste.copy()
            df_work['sentimento'] = self.zeus.sentimento
            df_work['data'] = self.zeus.data_df
            self.df_final = df_work.copy()
            self.df_final['unique_identifier'] = self.zeus.var_teste_original['unique_identifier']
            self.df_final['sigla'] = self.zeus.var_teste_original['sigla']
            #print(self.df_final.head())
            for numero in range(n_cluster):
                df_data = df_work[df_work.label == numero]
                df_data.data = pd.to_datetime(df_data.data)
                df_data.sort_values(by='data', inplace=True)
                date_buttons = [
                    {'count': 1, 'step': 'month', 'stepmode': 'todate', 'label': '1MTD'},
                    {'count': 3, 'step': 'month', 'stepmode': 'todate', 'label': '3MTD'},
                    {'count': 6, 'step': 'month', 'stepmode': 'todate', 'label': '6MTD'},
                    {'count': 1, 'step': 'year', 'stepmode': 'todate', 'label': '1YTD'},
                ]
                fig = px.line(df_data, x='data', y='sentimento')
                fig.update_layout(title_text=f"<b>Sentimento no tempo do cluster {numero}<b>", title_x=0.5,
                                  template='simple_white')
                fig.update_layout({'xaxis': {'rangeselector': {'buttons': date_buttons}},
                                   'yaxis': {'range': [-1, 1]}})
                fig.update_traces(line_color=self.rgb_last_continuos_color[self.colors[numero]])

                lista_fig.append(fig)
        else:
            df_work = self.df_loaded.copy()

            for numero in range(n_cluster):
                df_data = df_work[df_work.label == numero]
                df_data.data = pd.to_datetime(df_data.data)
                df_data.sort_values(by='data', inplace=True)
                date_buttons = [
                    {'count': 1, 'step': 'month', 'stepmode': 'todate', 'label': '1MTD'},
                    {'count': 3, 'step': 'month', 'stepmode': 'todate', 'label': '3MTD'},
                    {'count': 6, 'step': 'month', 'stepmode': 'todate', 'label': '6MTD'},
                    {'count': 1, 'step': 'year', 'stepmode': 'todate', 'label': '1YTD'},
                ]
                fig = px.line(df_data, x='data', y='sentimento')
                fig.update_layout(title_text=f"<b>Sentimento no tempo do cluster {numero}<b>", title_x=0.5,
                                  template='simple_white')
                fig.update_layout({'xaxis': {'rangeselector': {'buttons': date_buttons}},
                                   'yaxis': {'range': [-1, 1]}})
                fig.update_traces(line_color=self.rgb_last_continuos_color[self.colors[numero]])

                lista_fig.append(fig)

        return lista_fig

    def constroi_grafico_5(self):

        if self.is_load:
            siglas = self.df_loadedv2.sigla.unique().tolist()
            df = self.df_loadedv2

        else:
            siglas = self.df_final.sigla.unique().tolist()
            df = self.df_final

        df_result = pd.DataFrame(index=siglas)
        for i in df.label.unique().tolist():
            x = df[df.label == i]
            dfx = pd.DataFrame(x.sigla.value_counts(normalize='columns').values, columns=[f'Cluster {i}'],
                               index=x.sigla.unique().tolist())
            df_result = pd.concat([df_result, dfx], axis=1)

        df_result.fillna(0, inplace=True)
        df_result['dominante'] = df_result.idxmax(axis=1)
        #print(df_result)

        df_dominante = pd.concat([self.df2, df_result['dominante']], axis=1)
        df_dominante.fillna('Sem grupo', inplace=True)
        #print(df_dominante)

        colunas = df_result.columns.tolist()
        del colunas[-1]
        print(df_dominante.head())
        color_discreate_map = dict(zip(colunas, self.rgb_last_continuos_color.values()))
        color_discreate_map['Sem grupo'] = 'rgb(255, 210, 255)'
        self.discreate_colors = dict(zip(colunas, self.rgb_last_continuos_color.values()))
        #print(color_discreate_map)
        fig = px.choropleth(
            data_frame=df_dominante,
            locations='Estado',
            geojson=self.Brazil,
            color='dominante',
            hover_name='Estado',
            hover_data=['dominante', "Longitude", "Latitude"],
            color_discrete_map=self.discreate_colors
        )
        fig.update(layout_coloraxis_showscale=False)
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(title_text=f"<b>Clusters mais dominantes em cada estado<b>", title_x=0.5,
                          )

        return fig

    def constroi_grafico_6(self):
        if self.is_load:
            df = self.df_loadedv2

        else:
            df = self.df_final

        df2 = df.copy()
        df2.drop(columns=['data', 'unique_identifier', 'sigla'], inplace=True)
        lista_cluster = []
        lista_variedade_lexical = []
        lista_sentimento_medio = []
        lista_numero_de_artigos = []
        for cluster in df2.label.unique().tolist():
            dfx = df2[df2.label == cluster].copy()
            lista_sentimento_medio.append(dfx.sentimento.mean())
            dfx.drop(columns=['label', 'sentimento'], inplace=True)

            filtro = dfx.sum(axis=0) != 0
            dfz = dfx[dfx.columns[filtro]]
            print(dfz.shape)
            lista_cluster.append(f'Cluster {cluster}')
            lista_variedade_lexical.append(dfz.shape[1])
            lista_numero_de_artigos.append(dfz.shape[0])



        dff = pd.DataFrame({'clusters': lista_cluster,
                            'variedade_lexical': lista_variedade_lexical,
                            'sentimento_medio': np.array(lista_sentimento_medio) * 100,
                            'numero_de_artigos': lista_numero_de_artigos})

        fig = px.scatter(data_frame=dff,
                         x='sentimento_medio',
                         y='variedade_lexical',
                         size='numero_de_artigos',
                         color='clusters',
                         color_discrete_map=self.discreate_colors)
        fig.update_layout(title_text=f"<b>Sentimento pela variedade lexical<b>", title_x=0.5,
                          template='simple_white')

        return fig
