import datetime
import yaml
import base64

from dataclasses import dataclass
from typing import List

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit_authenticator as stauth

from google_api import get_google_service, get_gs_table
from google_api import GSPage





def date_eom(x:datetime):
    return (x.replace(day=1) + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)

def st_multiselect_empty(ser:pd.Series, title:str='', default:List[str]=None) -> List[str]:
    group_sel = st.multiselect(title, list(set(ser)), default)
    return set(ser) if not group_sel else group_sel

def color_cur_prev(cur, prev):
    color = 'green' if cur < prev else 'red' if cur > prev else 'grey'
    return f'color: {color}'

def fig_line_area(df:pd.DataFrame, 
            x:str, 
            y:str, 
            type:str = 'line', # line / area
            color:str=None, 
            title:str='', 
            line_color:str=None, 
            line_colors:List[str]=[],
            xaxis_title:str='', 
            yaxis_title:str='',
            hover_name:str=None,
            markers=True
            ):
    
    px_fig = px.line
    if type == 'area':
        px_fig = px.area

    fig = px_fig(df, x=x, y=y, color=color, hover_name=hover_name, markers=markers)
    if color and line_colors:
        for i in  range(len(line_colors)):
            fig['data'][i]['line']['color']=line_colors[i]
    elif line_color: 
        fig.update_traces(line_color=line_color)


    fig.update_traces(marker=dict(size=4))

    fig.update_layout(title=title, xaxis_title=xaxis_title, yaxis_title=yaxis_title)
    fig.update_yaxes(rangemode="tozero")

    fig.update_layout({'plot_bgcolor': 'rgba(255, 255, 255, 0.3)',
                        'paper_bgcolor': 'rgba(255, 255, 255, 0.2)',
                     })

    return fig

def fig_bar(df:pd.DataFrame, 
            x:str, 
            y:str, 
            color:str=None, 
            title:str='', 
            marker_color:str=None, 
            color_discrete_map:dict=None,
            xaxis_title:str='', 
            yaxis_title:str='',
            barmode:str='relative',
            hover_name:str=None
            ):

    px_fig = px.bar
    fig = px_fig(df, x=x, y=y, barmode=barmode, hover_name=hover_name)
    if color:
        fig = px_fig(df, x=x, y=y, color=color, barmode=barmode, hover_name=hover_name)
        if color_discrete_map:
            fig = px_fig(df, x=x, y=y, color=color, color_discrete_map=color_discrete_map, barmode=barmode, hover_name=hover_name)
    elif marker_color: 
           fig.update_traces(marker_color=marker_color)

    fig.update_layout(title=title, xaxis_title=xaxis_title, yaxis_title=yaxis_title)
    fig.update_yaxes(rangemode="tozero")
    fig.update_layout({'plot_bgcolor': 'rgba(255, 255, 255, 0.3)',
                    'paper_bgcolor': 'rgba(255, 255, 255, 0.2)',
                    })
    return fig



def set_bg_hack(main_bg):
    '''
    A function to unpack an image from root folder and set as bg.

    Returns
    -------
    The background.
    '''
    # set bg name
    main_bg_ext = "png"
        
    st.markdown(
         f"""
         <style>
         .stApp {{
             background: url(data:image/{main_bg_ext};base64,{base64.b64encode(open(main_bg, "rb").read()).decode()});
             background-size: cover
         }}
         </style>
         """,
         unsafe_allow_html=True
     )


@st.cache
def get_meters(meters_gs:GSPage) -> pd.DataFrame:
    service = get_google_service(meters_gs.service_account_json, api='sheets')
    df_meters = get_gs_table(service, meters_gs.gs_id, meters_gs.page_name)
    df_meters = df_meters[['Дата', 'счетчик', 'место', 'показания', 'потребление']]
    df_meters['Дата'] = pd.to_datetime(df_meters['Дата'], format='%d.%m.%Y')
    df_meters['date_eom'] = df_meters['Дата'].map(date_eom)
    df_meters['показания'].replace(' ','', regex=True, inplace=True)
    df_meters['показания'].replace(',','', regex=True, inplace=True)
    df_meters['показания'] = df_meters['показания'].map(pd.to_numeric)
    df_meters['потребление'] = df_meters['потребление'].map(pd.to_numeric)
    
    df_meters_by_month = pd.DataFrame(df_meters.groupby(['счетчик', 'date_eom']).agg({'показания':'max','потребление':'sum' })).reset_index().sort_values('date_eom')
    df_meters_by_month.columns = ['meter', 'date_eom', 'value', 'consumption']
    df_meters_by_month['prev_consumption'] = df_meters_by_month.groupby('meter')['consumption'].transform(lambda x: x.shift(1))
    df_meters_by_month['year'] = df_meters_by_month['date_eom'].map(lambda x: x.year)
    df_meters_by_month['month_num'] = df_meters_by_month['date_eom'].map(lambda x: x.month)
    return df_meters_by_month

def auth():
    # auth
    # https://blog.streamlit.io/streamlit-authenticator-part-1-adding-an-authentication-component-to-your-app/
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=stauth.SafeLoader)

        authenticator  = stauth.Authenticate(
            config['credentials'],
            config['cookie']['name'],
            config['cookie']['key'],
            config['cookie']['expiry_days'],
            config['preauthorized']
        )

    st.session_state["name"], st.session_state["authentication_status"], st.session_state["username"] = authenticator.login('Войти', 'sidebar')
    return authenticator

st.set_page_config(page_title='Household', page_icon='🟡')
set_bg_hack('bg_utilities.png')

if "add_phone_bills_show_form" not in st.session_state:
   st.session_state["add_phone_bills_show_form"]=False
else:
    st.session_state["add_phone_bills_show_form"]=False


# st.session_state initiation
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None
if 'name' not in st.session_state:
    st.session_state['name'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'authenticator' not in st.session_state:
    st.session_state['authenticator'] = None

# set constants
GOOGLESHEET_ID = st.secrets['GOOGLESHEET_ID']
METERS_PAGE_ID = st.secrets['METERS_PAGE_ID']
METERS_PAGE_NAME = st.secrets['METERS_PAGE_NAME']
SERVICE_ACCOUNT_JSON = st.secrets['SERVICE_ACCOUNT_JSON']


meters_gs = GSPage(
            service_account_json=SERVICE_ACCOUNT_JSON,
            gs_id=GOOGLESHEET_ID,
            page_id=METERS_PAGE_ID,
            page_name=METERS_PAGE_NAME
            )


# main

df_meters_by_month = get_meters(meters_gs) 

meters_water = ['ХВС', 'ГВС']
meters_electricity = ['ЭЛ.ЭНЕРГИЯ']
meters_gas = ['ГАЗ']

years = list(set(df_meters_by_month['year']))

st.title('Потребление ресурсов')

################################################################################
# auth
authenticator = auth()
if st.session_state["authentication_status"]:
    authenticator.logout('Выйти', 'sidebar')
    with st.sidebar:
        st.write(f'Вы вошли как *{st.session_state["name"]}*')
elif st.session_state["authentication_status"] == False:
    with st.sidebar:
        st.error('Пользователь/пароль неверные')
################################################################################





with st.sidebar:
    st.markdown("***")
    st.write(f'[__Показания счетчиков__](https://docs.google.com/spreadsheets/d/{meters_gs.gs_id}/edit#gid={meters_gs.page_id})')
    flt_year = st.slider("Период", min(years),  max(years), (max(years)-5,  max(years)))



flt_year_meters_by_month = df_meters_by_month[df_meters_by_month['year'].between(flt_year[0], flt_year[1])]
flt_year_meters_by_year = flt_year_meters_by_month.groupby(['meter', 'year'])['consumption'].sum().reset_index()
flt_year_meters_by_month_num = flt_year_meters_by_month.groupby(['meter', 'month_num'])['consumption'].mean().reset_index()

st.subheader('За месяц')
month_sel = st.date_input('выберете любую дату в рамках нужного месяца', 
                            max(flt_year_meters_by_month['date_eom']), 
                            min_value=min(flt_year_meters_by_month['date_eom']), 
                            max_value=max(flt_year_meters_by_month['date_eom']) )
month_sel = date_eom(month_sel)
month_sel = datetime.datetime.combine(month_sel, datetime.datetime.min.time())
st.info(f"на дату: __{month_sel.strftime('%d.%m.%Y')}__")

df_last_month = flt_year_meters_by_month[flt_year_meters_by_month['date_eom'] == month_sel]
meters_list = list(set(df_last_month['meter']))
col = st.columns(len(meters_list))

for i in range(len(meters_list)):
    with col[i]:
        st.metric(f'__{meters_list[i]}__' + ('  кВт' if meters_list[i]=='ЭЛ.ЭНЕРГИЯ' else '  куб.м'), 
            int(max(df_last_month[df_last_month['meter']==meters_list[i]]['consumption'])), 
            int(max(df_last_month[df_last_month['meter']==meters_list[i]]['consumption']) - max(df_last_month[df_last_month['meter']==meters_list[i]]['prev_consumption'])),
            delta_color="inverse")

st.subheader('Динамика')
tab1, tab2, tab3 = st.tabs(['Вода', 'Эл. энергия', 'Газ'])

with tab1:
    st.subheader('__Вода__')
    yaxis_title = 'куб.м'

    tab11, tab12 = st.tabs(['Общее потребление', 'Потребление по видам'])
    
    with tab11:
        line_color = marker_color ='blue'

        # df
        flt_year_by_month = flt_year_meters_by_month[flt_year_meters_by_month['meter'].isin(meters_water)].groupby(['date_eom', 'year','month_num'])['consumption'].sum().reset_index()
        flt_year_by_year = flt_year_by_month.groupby('year')['consumption'].sum().reset_index()
        flt_year_by_month_num = flt_year_by_month.groupby('month_num')['consumption'].mean().reset_index()
        # charts
        st.plotly_chart(fig_line_area(flt_year_by_year, x='year', y='consumption', type='line', line_color=line_color,
            title='общее потребление, по годам', xaxis_title='год', yaxis_title=yaxis_title))
        st.plotly_chart(fig_line_area(flt_year_by_month, x='date_eom', y='consumption', type='line', line_color=line_color,
            title='общее потребление, по месяцам', xaxis_title='год-месяц', yaxis_title=yaxis_title))
        st.plotly_chart(fig_bar(flt_year_by_month_num, x='month_num', y='consumption', marker_color=marker_color, 
            title='среднее потребление, по месяцам', xaxis_title='месяц', yaxis_title=yaxis_title))        
        st.plotly_chart(fig_line_area(flt_year_meters_by_month[flt_year_meters_by_month['meter'].isin(meters_water)].groupby(['year', 'month_num']).sum().reset_index(), 
            x='month_num', y='consumption', color='year', type='line', 
            title='общее потребление, по месяцам', xaxis_title='месяц', yaxis_title=yaxis_title))

    with tab12:
        line_colors=['red', 'blue']
        color_discrete_map={
                meters_water[1]: 'red',
                meters_water[0]: 'blue'}
        radio_opt = ['Сумма','Сравнение']
        
        st.subheader('потребление по видам')
        col1, col2 = st.columns([1,5])
        with col1:
            fig_type = st.radio('Вид', radio_opt)
            if fig_type == radio_opt[0]:
                fig_type_by_year = fig_line_area(flt_year_meters_by_year[flt_year_meters_by_year['meter'].isin(meters_water)], x='year', y='consumption', type='area', color='meter',
                    title='суммарное потребление по видам, по годам', xaxis_title='год', yaxis_title=yaxis_title, line_colors=line_colors)
            else:
                fig_type_by_year = fig_line_area(flt_year_meters_by_year[flt_year_meters_by_year['meter'].isin(meters_water)], x='year', y='consumption', type='line', color='meter',
                    title='суммарное потребление по видам, по годам', xaxis_title='год', yaxis_title=yaxis_title, line_colors=line_colors)
        with col2:
            st.plotly_chart(fig_type_by_year)


        col1, col2 = st.columns([1,5])
        with col1:
            fig_type = st.radio('Вид ', radio_opt)
            if fig_type == radio_opt[0]:
                fig_type_by_month = fig_line_area(flt_year_meters_by_month[flt_year_meters_by_month['meter'].isin(meters_water)], x='date_eom', y='consumption', type='area', color='meter',
                title='суммарное потребление по видам, по месяцам', xaxis_title='год-месяц', yaxis_title=yaxis_title, line_colors=line_colors)
            else:
                fig_type_by_month = fig_line_area(flt_year_meters_by_month[flt_year_meters_by_month['meter'].isin(meters_water)], x='date_eom', y='consumption', type='line', color='meter',
                title='суммарное потребление по видам, по месяцам', xaxis_title='год-месяц', yaxis_title=yaxis_title, line_colors=line_colors)
        with col2:
            st.plotly_chart(fig_type_by_month)


        col1, col2 = st.columns([1,5])
        with col1:
            fig_type = st.radio('Вид  ', radio_opt)
            if fig_type == radio_opt[0]:
                fig_type_by_month_num = fig_bar(flt_year_meters_by_month_num[flt_year_meters_by_month_num['meter'].isin(meters_water)], x='month_num', y='consumption', color='meter',
                    title='среднее потребление воды по видам, по месяцам', xaxis_title='месяц', yaxis_title=yaxis_title,
                    color_discrete_map=color_discrete_map)
            else:
                fig_type_by_month_num = fig_bar(flt_year_meters_by_month_num[flt_year_meters_by_month_num['meter'].isin(meters_water)], x='month_num', y='consumption', color='meter',  barmode='group',
                    title='среднее потребление воды по видам, по месяцам', xaxis_title='месяц', yaxis_title=yaxis_title,
                    color_discrete_map=color_discrete_map)   
        with col2:
            st.plotly_chart(fig_type_by_month_num)



with tab2:
    line_color = marker_color ='orange'
    yaxis_title = 'кВт'

    st.subheader('Эл. энергия')

    flt_year_by_month = flt_year_meters_by_month[flt_year_meters_by_month['meter'].isin(meters_electricity)].groupby([ 'date_eom', 'year','month_num'])['consumption'].sum().reset_index()
    flt_year_by_year = flt_year_by_month.groupby('year')['consumption'].sum().reset_index()
    flt_year_by_month_num = flt_year_by_month.groupby('month_num')['consumption'].mean().reset_index()

    # charts
    st.plotly_chart(fig_line_area(flt_year_by_year, x='year', y='consumption', type='line', line_color=line_color, 
        title='общее потребление, по годам', xaxis_title='год', yaxis_title=yaxis_title))
    st.plotly_chart(fig_line_area(flt_year_by_month, x='date_eom', y='consumption', type='line', line_color=line_color, 
        title='общее потребление, по месяцам', xaxis_title='год-месяц', yaxis_title=yaxis_title))
    st.plotly_chart(fig_bar(flt_year_by_month_num, x='month_num', y='consumption', marker_color=marker_color,
        title='среднее потребление, по месяцам', xaxis_title='месяц', yaxis_title=yaxis_title))
    st.plotly_chart(fig_line_area(flt_year_meters_by_month[flt_year_meters_by_month['meter'].isin(meters_electricity)].groupby(['year', 'month_num']).sum().reset_index(), 
        x='month_num', y='consumption', color='year', type='line', 
        title='общее потребление, по месяцам', xaxis_title='месяц', yaxis_title=yaxis_title))



with tab3:
    line_color = marker_color ='violet'
    yaxis_title = 'куб.м'
    
    st.subheader('Газ')

    flt_year_by_month = flt_year_meters_by_month[flt_year_meters_by_month['meter'].isin(meters_gas)].groupby(['date_eom', 'year','month_num'])['consumption'].sum().reset_index()
    flt_year_by_year = flt_year_by_month.groupby('year')['consumption'].sum().reset_index()
    flt_year_by_month_num = flt_year_by_month.groupby('month_num')['consumption'].mean().reset_index()

    # charts
    st.plotly_chart(fig_line_area(flt_year_by_year, x='year', y='consumption', type='line', line_color=line_color, 
        title='общее потребление, по годам', xaxis_title='год', yaxis_title=yaxis_title))
    st.plotly_chart(fig_line_area(flt_year_by_month, x='date_eom', y='consumption', type='line', line_color=line_color, 
        title='общее потребление, по месяцам', xaxis_title='год-месяц', yaxis_title=yaxis_title))
    st.plotly_chart(fig_bar(flt_year_by_month_num, x='month_num', y='consumption', marker_color=marker_color,
        title='среднее потребление, по месяцам', xaxis_title='месяц', yaxis_title=yaxis_title))
    st.plotly_chart(fig_line_area(flt_year_meters_by_month[flt_year_meters_by_month['meter'].isin(meters_gas)].groupby(['year', 'month_num']).sum().reset_index(), 
        x='month_num', y='consumption', color='year', type='line', 
        title='общее потребление, по месяцам', xaxis_title='месяц', yaxis_title=yaxis_title))



