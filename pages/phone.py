import datetime
import time
from typing import List

import streamlit as st
import pandas as pd
import plotly.express as px

from google_api import get_google_service, get_gs_table, write_to_gs
from google_api import GSPage

from utilities import fig_line_area, fig_bar
from utilities import st_multiselect_empty, date_eom, color_cur_prev
from utilities import auth
from utilities import set_bg_hack


# @st.cache
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

set_bg_hack('bg_phones.png')


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
                page_name=PHONE_BILLS_PAGE_NAME,
                header_row_reserve=1,
                first_col_letter='A',
                last_col_letter='C'
            )
match_gs = GSPage(
                service_account_json=SERVICE_ACCOUNT_JSON,
                gs_id=PHONE_GOOGLESHEET_ID,
                page_id=PHONE_MATCH_PAGE_ID,
                page_name=PHONE_MATCH_NAME,
                header_row_reserve=1
            )

df, phones = get_phones(phone_bills_gs, match_gs)

if 'first_empty_row_df' not in st.session_state:
    st.session_state['first_empty_row_df'] = len(df) + 1 + phone_bills_gs.header_row_reserve
first_col_letter = phone_bills_gs.first_col_letter
last_col_letter = phone_bills_gs.last_col_letter

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
    st.session_state["add_phone_bills_show_form"] = False
elif st.session_state["authentication_status"] == None:
    st.session_state["add_phone_bills_show_form"] = False
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
################################################################################
def clear_form_text():
    for number in phones['number']:
        st.session_state[number] = "0"
    get_prev_month()
    hide_form()

def write_form_text():
    phone_bills_to_write = []
    for number in phones['number']:
        v = st.session_state[number]
        try:
            v_float = float(v)
        except ValueError:
            v_float = 0.0
        phone_bills_to_write.append([st.session_state["form_month_sel"].strftime('%d.%m.%Y'), number, v_float])

    range = f"{first_col_letter}{st.session_state['first_empty_row_df']}:{last_col_letter}{st.session_state['first_empty_row_df'] +len(phone_bills_to_write)-1}"
    write_to_gs(phone_bills_gs, phone_bills_to_write, range)
    st.session_state['first_empty_row_df'] += len(phone_bills_to_write)

    st.success('Данные внесены')

    clear_form_text()
    get_prev_month()
    hide_form()

def get_prev_month():
    st.session_state["new_month_sel"] = date_eom(st.session_state["form_month_sel"])
    st.session_state["prev_month"]= date_eom(date_eom(st.session_state["new_month_sel"])-datetime.timedelta(days=32))
    add_phone_bills_show_form()

def add_phone_bills_show_form():
    st.session_state["add_phone_bills_show_form"]=True
def hide_form():
    st.session_state["add_phone_bills_show_form"]=False


if "disabled_phone_bill_add_but" not in st.session_state:
    st.session_state["disabled_phone_bill_add_but"] = False

if st.session_state.get("phone_bill_add_but", False):
    st.session_state["disabled_phone_bill_add_but"] = True
else:
    st.session_state["disabled_phone_bill_add_but"] = False

if "new_month_sel" not in st.session_state:
    st.session_state["new_month_sel"]= max(flt_year_df['date_eom'])
    st.session_state["prev_month"]= date_eom(date_eom(st.session_state["new_month_sel"])-datetime.timedelta(days=32))

if "add_phone_bills_show_form" not in st.session_state:
    add_phone_bills_show_form()

phones = phones[phones['is_active'] == 1].sort_values('number')
df_tmp = flt_df[flt_df['date_eom']==datetime.datetime.combine(st.session_state["new_month_sel"], datetime.datetime.min.time())]
df_tmp_prev = flt_df[flt_df['date_eom']==datetime.datetime.combine(st.session_state["prev_month"], datetime.datetime.min.time())]

st.button('Внести данные', key='phone_bill_add_but', 
                disabled=not st.session_state["authentication_status"] 
                or st.session_state["add_phone_bills_show_form"]
                or st.session_state["disabled_phone_bill_add_but"],
                on_click=add_phone_bills_show_form)

if st.session_state["add_phone_bills_show_form"]:
    st.date_input('выберете любую дату в рамках нужного месяца', 
                                    value=st.session_state["new_month_sel"], 
                                    min_value=min(flt_year_df['date_eom']), 
                                    max_value=date_eom(max(flt_year_df['date_eom'])+datetime.timedelta(days=1)),
                                    key='form_month_sel'
                                    , on_change=get_prev_month
                                    )

    form = st.form(key="add_phone_bills")
    form.subheader('Внесите данные') 
                                
    for number in phones['number']:
        month_row = df_tmp[df_tmp['number'] == number].head(1)
        sum_str = f"{month_row['summ'].iloc[0]:,.2f}" if len(month_row)==1 else "0"
            
        
        prev_month_row = df_tmp_prev[df_tmp_prev['number'] == number].head(1)
        prev_name_str = f"{prev_month_row['owner'].iloc[0]}" if len(prev_month_row)==1 else "0"
        prev_date_str = f"{prev_month_row['date_eom'].iloc[0].strftime('%m.%Y')}" if len(prev_month_row)==1 else "0"
        prev_sum_str = f"{prev_month_row['summ'].iloc[0]:,.2f}" if len(prev_month_row)==1 else "0"

        form.text_input(f"**{prev_name_str}**({number}) пред. мес *{prev_date_str}*: **{prev_sum_str}** руб.", placeholder=sum_str, key=number)
    
    form.form_submit_button("Сохранить", on_click=write_form_text)
    form.form_submit_button("Отменить", on_click=clear_form_text)

################################################################################
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
    st.table(df_tmp[['summ', 'icon_diff']].rename(columns={'summ':'сумма', 'icon_diff':'изм.'})
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