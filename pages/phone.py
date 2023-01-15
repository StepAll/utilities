import datetime
from typing import List

import streamlit as st
import pandas as pd
import plotly.express as px

from google_api import get_google_service, get_gs_table
from google_api import GSPage

from utilities import fig_line_area, fig_bar
from utilities import st_multiselect_empty, date_eom, color_cur_prev
from utilities import auth

@st.cache
def get_phones(phone_bills_gs:GSPage, match_gs:GSPage) -> pd.DataFrame:
    service = get_google_service(phone_bills_gs.service_account_json, api='sheets')
    df_bills = get_gs_table(service, phone_bills_gs.gs_id, phone_bills_gs.page_name)

    service = get_google_service(match_gs.service_account_json, api='sheets')
    df_matches = get_gs_table(service, match_gs.gs_id, match_gs.page_name)

    df_bills['Дата'] = pd.to_datetime(df_bills['Дата'], format='%d.%m.%Y')
    df_bills['date_eom'] = df_bills['Дата'].map(date_eom)
    df_bills['Сумма'].replace(' ','', regex=True, inplace=True)
    df_bills['Сумма'].replace(',','', regex=True, inplace=True)
    df_bills['Сумма'] = df_bills['Сумма'].map(pd.to_numeric)
    df = df_bills.set_index('Номер').join(df_matches.set_index('Номер')).reset_index()
    df.columns = ['number', 'date', 'summ', 'date_eom', 'owner', 'group', 'is_active']
    
    df = df.groupby(['number','date_eom', 'owner', 'group'])['summ'].sum().reset_index().sort_values('date_eom')
    df['prev_summ'] = df.groupby('number')['summ'].transform(lambda x: x.shift(1))

    df['year'] = df['date_eom'].map(lambda x: x.year)
    df['month_num'] = df['date_eom'].map(lambda x: x.month)

    df_matches.columns = ['number', 'owner', 'group', 'is_active']
    df_matches['is_active'] = df_matches['is_active'].map(pd.to_numeric).fillna(0).map(int)
    return df, df_matches




PHONE_GOOGLESHEET_ID = st.secrets['PHONE_GOOGLESHEET_ID']
PHONE_BILLS_PAGE_ID = st.secrets['PHONE_BILLS_PAGE_ID']
PHONE_BILLS_PAGE_NAME = st.secrets['PHONE_BILLS_PAGE_NAME']
PHONE_MATCH_PAGE_ID = st.secrets['PHONE_MATCH_PAGE_ID']
PHONE_MATCH_NAME = st.secrets['PHONE_MATCH_NAME']
SERVICE_ACCOUNT_JSON = st.secrets['SERVICE_ACCOUNT_JSON']


phone_bills_gs = GSPage(
                service_account_json=SERVICE_ACCOUNT_JSON,
                gs_id=PHONE_GOOGLESHEET_ID,
                page_id=PHONE_BILLS_PAGE_ID,
                page_name=PHONE_BILLS_PAGE_NAME
            )
match_gs = GSPage(
                service_account_json=SERVICE_ACCOUNT_JSON,
                gs_id=PHONE_GOOGLESHEET_ID,
                page_id=PHONE_MATCH_PAGE_ID,
                page_name=PHONE_MATCH_NAME
            )

df, phones = get_phones(phone_bills_gs, match_gs)
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
log_info = 'войдите в систему, чтобы увидеть персонализированную информацию'

with st.sidebar:
    st.markdown("***")
    st.write(f'[__Расходы за телефон__](https://docs.google.com/spreadsheets/d/{phone_bills_gs.gs_id}/edit#gid={phone_bills_gs.page_id})')
    flt_year = st.slider("Период", min(years),  max(years), (max(years)-5,  max(years)))
    flt_year_df = df[df['year'].between(flt_year[0], flt_year[1])]
    
    flt_group = st_multiselect_empty(flt_year_df['group'],'Группы', ['Семья', 'Родители', 'Морозовы'])
    flt_df = flt_year_df[flt_year_df['group'].isin(flt_group)]

st.title('Телефон')
################################################################################
# add phone bills

if "disabled_phone_bill_add_but" not in st.session_state:
    st.session_state["disabled_phone_bill_add_but"] = False

if st.session_state.get("phone_bill_add_but", False):
    st.session_state["disabled_phone_bill_add_but"] = True
else:
    st.session_state["disabled_phone_bill_add_but"] = False

phones = phones[phones['is_active'] == 1].sort_values('number')
df_tmp = flt_df[flt_df['date_eom']==max(flt_df['date_eom'])]

form = st.empty()
if st.button('Внести данные', key='phone_bill_add_but', disabled=not st.session_state["authentication_status"] or st.session_state["disabled_phone_bill_add_but"]):
    form = st.form(key="add_phone_bills")
    form.subheader('Внесите данные')
    new_month_sel = form.date_input('выберете любую дату в рамках нужного месяца', date_eom(max(flt_year_df['date_eom'])+datetime.timedelta(days=1)), min_value=min(flt_year_df['date_eom']), max_value=date_eom(max(flt_year_df['date_eom'])+datetime.timedelta(days=1)))

    bill = []
    for number in phones['number']:
        cur_row = df_tmp[df_tmp['number'] == number].head(1)
        name_str = f"{cur_row['owner'].iloc[0]}"
        date_str = f"{cur_row['date_eom'].iloc[0].strftime('%d.%m.%Y')}"
        sum_str = f"{cur_row['summ'].iloc[0]:,.2f}"
        bill.append((number, form.text_input(f"**{name_str}**({number}) {date_str}: **{sum_str}** руб.", key=number)))

    if form.form_submit_button("Сохранить"):
        form.empty()
        st.session_state["phone_bill_add_but"]=False
    if form.form_submit_button("Отменить"):
        form.empty()
        st.session_state["phone_bill_add_but"]=False
################################################################################

st.subheader(f"За месяц")

month_sel = st.date_input('выберете любую дату в рамках нужного месяца', max(flt_year_df['date_eom']), min_value=min(flt_year_df['date_eom']), max_value=max(flt_year_df['date_eom']) )
month_sel = date_eom(month_sel)
month_sel = datetime.datetime.combine(month_sel, datetime.datetime.min.time())
st.info(f"на дату: __{month_sel.strftime('%d.%m.%Y')}__")

df_tmp = flt_df[['group','summ', 'prev_summ']][flt_df['date_eom']==month_sel].groupby('group').sum().sort_values('summ', ascending=False)
col = st.columns(len(df_tmp))
for i in range(len(df_tmp)):
    with col[i]:
        st.metric(f'__{df_tmp.index[i]}__',
            int(df_tmp['summ'][i]),
            int(df_tmp['summ'][i] - df_tmp['prev_summ'][i]),
            delta_color="inverse")



st.write('подробно')
if st.session_state["authentication_status"]:
    df_tmp = flt_df[['group','owner','number','summ', 'prev_summ']][flt_df['date_eom']==month_sel].sort_values(['group','owner','number']).set_index(['group','owner','number'])
    df_tmp['diff'] = df_tmp['summ'] - df_tmp['prev_summ']
    df_tmp['icon_diff'] = df_tmp['diff'].map(lambda x: f"↑{x:.2f}" if x>0 else f"↓{x:.2f}" if x<0 else '-')
    df_tmp_font_color = df_tmp.apply(lambda x: color_cur_prev(x['summ'], x['prev_summ']), axis=1)
    st.dataframe(df_tmp[['summ', 'icon_diff']].rename(columns={'summ':'сумма', 'icon_diff':'изм.'})
        .style
        .format({'сумма':'{:8,.2f}'})
        .apply(lambda _: df_tmp_font_color, subset=['изм.']))
else:
    st.warning(log_info)



st.subheader(f"Динамика расходов")
yaxis_title = 'руб.'
st.plotly_chart(fig_line_area(flt_df.groupby(['group', 'date_eom']).sum().reset_index(),
                        x='date_eom', y='summ', type='line', color='group',
                        title='расходы по группам', xaxis_title='год-месяц', yaxis_title=yaxis_title))

st.write('подробно')
if st.session_state["authentication_status"]:
    group_sel = st_multiselect_empty(flt_df['group'],'по группе', ['Семья'])
    flt_year_group_df = flt_df[flt_df['group'].isin(group_sel)]

    st.plotly_chart(fig_line_area(flt_year_group_df,
                        x='date_eom', y='summ', type='line', color='owner', hover_name='number',
                        title='расходы по телефонам', xaxis_title='год-месяц', yaxis_title=yaxis_title))
else:
    st.warning(log_info)
