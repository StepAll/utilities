import datetime

import streamlit as st
import pandas as pd
import plotly.express as px

from google_api import get_google_service, get_gs_table
from google_api import GSPage

from utilities import fig_line_area, fig_bar
from utilities import st_multiselect_empty, date_eom, color_cur_prev
from utilities import auth




@st.cache
def get_payments(payments_gs:GSPage) -> pd.DataFrame:
    service = get_google_service(payments_gs.service_account_json, api='sheets')
    df_payments = get_gs_table(service, payments_gs.gs_id, payments_gs.page_name)
    df_payments['Дата'] = pd.to_datetime(df_payments['Дата'], format='%d.%m.%Y')
    df_payments['date_eom'] = df_payments['Дата'].map(date_eom)
    df_payments[['сумма', 'комиссия']] = df_payments[['сумма', 'комиссия']].replace(' ','', regex=True)
    df_payments[['сумма', 'комиссия']] = df_payments[['сумма', 'комиссия']].replace(',','', regex=True)
    df_payments[['сумма', 'комиссия']] = df_payments[['сумма', 'комиссия']].applymap(pd.to_numeric)
    df_payments.columns = ['date', 'service', 'supplier', 'summ', 'commision',  'date_eom']
    df_payments['summ_w_comm'] = df_payments[['summ', 'commision']].sum(skipna=True, axis=1)

    df_payments.sort_values('date_eom', inplace=True)
    df_payments['prev_summ'] = df_payments.groupby(['service', 'supplier'])['summ'].transform(lambda x: x.shift(1))
    df_payments['prev_comm'] = df_payments.groupby(['service', 'supplier'])['commision'].transform(lambda x: x.shift(1))
    df_payments['summ_w_comm']= df_payments.groupby(['service', 'supplier'])['summ_w_comm'].transform(lambda x: x.shift(1))
    
    df_payments['year'] = df_payments['date_eom'].map(lambda x: x.year)
    df_payments['month_num'] = df_payments['date_eom'].map(lambda x: x.month)
    df_payments['supplier_service'] = df_payments.apply(lambda x: f"{x['supplier']}_{x['service']}", axis=1)
    df_payments['supplier_service_formated'] = df_payments.apply(lambda x: f"__:blue[{x['supplier']}]__  \n(_{x['service']}_)", axis=1)
    return df_payments

def graphics_set(flt_df:pd.DataFrame, metric_title:str, items:list=None) -> None:
    # metrics
    if items:
        flt_df = flt_df[flt_df['supplier_service'].isin(items)]
    
    df_metric = flt_df[['date_eom','summ', 'prev_summ']][flt_df['date_eom']==month_sel].groupby('date_eom').sum().sort_values('summ', ascending=False)
    col1, col2 = st.columns([1,4])
    with col1:
        if len(df_metric)==0:
            st.markdown(f'**{metric_title}**  \nНет начислений в этом месяце')
        else:
            st.metric(metric_title, 
                int(df_metric['summ']),
                int(df_metric['summ'] - df_metric['prev_summ']),
                delta_color="inverse")
    with col2:
        tab1, tab2, tab3, tab4 = st.tabs(['мес-год', 'год', 'ср.мес', 'сравнить годы'])
        with tab1:
            df_fig =  flt_df[['date_eom','summ']].groupby('date_eom').sum()
            fig = fig_line_area(df_fig.reset_index(), 
                        x='date_eom', 
                        y='summ', 
                        type='line', # line / area
                        title='динамика общих расходов', 
                        xaxis_title='год-месяц', 
                        yaxis_title='руб.'
                        )
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            df_fig =  flt_df[['year','summ']].groupby('year').sum()
            fig = fig_line_area(df_fig.reset_index(), 
                        x='year', 
                        y='summ', 
                        type='line', # line / area
                        title='динамика общих расходов', 
                        xaxis_title='год', 
                        yaxis_title='руб.',
                        line_color=None
                        )
            st.plotly_chart(fig, use_container_width=True)
        with tab3:
            df_fig =  flt_df[['month_num', 'year', 'summ']].groupby('month_num').agg({'summ':'sum', 'year':'nunique'})
            df_fig['summ_mean'] = df_fig['summ'].div(df_fig['year'])
            fig = fig_bar(df_fig.reset_index(), 
                        x='month_num', 
                        y='summ_mean', 
                        barmode='relative',
                        title='ср. мес. расходы', 
                        xaxis_title='мес', 
                        yaxis_title='руб.',
                        marker_color=None
                        )
            st.plotly_chart(fig, use_container_width=True)
        with tab4:
            df_fig =  flt_df[['year','month_num', 'summ']].groupby(['year', 'month_num']).sum().reset_index()
            fig = fig_line_area(df_fig.reset_index(), 
                        x='month_num', 
                        y='summ',
                        color='year', 
                        type='line', # line / area
                        title='динамика расходов по месяцам', 
                        xaxis_title='год', 
                        yaxis_title='руб.',
                        line_color=None
                        )
            st.plotly_chart(fig, use_container_width=True)
    return None

# set constants
GOOGLESHEET_ID = st.secrets['GOOGLESHEET_ID']
PAYMENTS_PAGE_ID = st.secrets['PAYMENTS_PAGE_ID']
PAYMENTS_PAGE_NAME = st.secrets['PAYMENTS_PAGE_NAME']
SERVICE_ACCOUNT_JSON = st.secrets['SERVICE_ACCOUNT_JSON']

payments_gs = GSPage(
            service_account_json=SERVICE_ACCOUNT_JSON,
            gs_id=GOOGLESHEET_ID,
            page_id=PAYMENTS_PAGE_ID,
            page_name=PAYMENTS_PAGE_NAME
            )

df = get_payments(payments_gs)
years = list(set(df['year']))

################################################################################
authenticator = auth()
if st.session_state["authentication_status"]:
    authenticator.logout('Выйти', 'sidebar')
    with st.sidebar:
        st.write(f'Вы вошли как *{st.session_state["name"]}*')
elif st.session_state["authentication_status"] == False:
    with st.sidebar:
        st.error('Пользователь/пароль неверные')
################################################################################

st.title('Коммунальные платежи')
with st.sidebar:
    st.markdown("***")
    st.write(f'[__Коммунальные платежи__](https://docs.google.com/spreadsheets/d/{payments_gs.gs_id}/edit#gid={payments_gs.page_id})')
    flt_year = st.slider("Период", min(years),  max(years), (max(years)-5,  max(years)))
    flt_year_df = df[df['year'].between(flt_year[0], flt_year[1])]
    flt_supp = st_multiselect_empty(list(set(flt_year_df['supplier'])), title='Поставщики', default=None)
    flt_df = flt_year_df[flt_year_df['supplier'].isin(flt_supp)]

st.subheader('Всего')
month_sel = st.date_input(' выберете любую дату в рамках нужного месяца', max(flt_df['date_eom']), min_value=min(flt_df['date_eom']), max_value=max(flt_df['date_eom']))
month_sel = date_eom(month_sel)
month_sel = datetime.datetime.combine(month_sel, datetime.datetime.min.time())
st.info(f"на дату: __{month_sel.strftime('%d.%m.%Y')}__")


graphics_set(flt_df, "**Всего**", items=None)

df_month = flt_df[['supplier', 'service', 'summ', 'summ_w_comm', 'prev_summ']][flt_df['date_eom']==month_sel].groupby(['supplier', 'service']).sum().sort_values('summ', ascending=False)
df_month['diff'] = df_month['summ'] - df_month['prev_summ']
df_month['icon_diff'] = df_month['diff'].map(lambda x: f"↑{x:.2f}" if x>0 else f"↓{x:.2f}" if x<0 else '-')
df_month['color_diff'] = df_month.apply(lambda x: color_cur_prev(x['summ'], x['prev_summ']), axis=1)

col1, col2 = st.columns([1,4])
with col2:
    st.dataframe(df_month[['summ', 'icon_diff', 'summ_w_comm']].rename(columns={'summ':'сумма', 'icon_diff':'изм.', 'summ_w_comm':'сумма с комиссией'}) 
                            .style
                            .format({'сумма':'{:8,.2f}', 'сумма с комиссией':'{:8,.2f}'})
                            .apply(lambda _: df_month['color_diff'], subset=['изм.'])
                            )


st.subheader('По поставщикам / услугам')
supplier_service_list = (flt_df[['supplier_service', 'supplier_service_formated', 'date_eom','summ']]
                .groupby(['supplier_service', 'supplier_service_formated'])
                .sum()
                .sort_values('summ', ascending=False)
                .reset_index()[['supplier_service', 'supplier_service_formated']])
for _,i,f in supplier_service_list.itertuples():
    graphics_set(flt_df, f, items=[i])
