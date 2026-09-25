"""Контрольные статичные графики поверх ML-витрин пункта 6."""

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import duckdb


COLORS = {
    "ink":"#18324a", "blue":"#2274a5", "teal":"#1e9d89",
    "amber":"#d59629", "red":"#c65050", "muted":"#788797",
    "pale":"#e8eef2",
}


def save(fig, folder, name):
    fig.savefig(folder / f"{name}.png",dpi=170,bbox_inches="tight")
    fig.savefig(folder / f"{name}.svg",bbox_inches="tight")
    plt.close(fig)


def style():
    plt.rcParams.update({
        "font.family":"DejaVu Sans", "font.size":10,
        "axes.titlesize":14, "axes.labelcolor":COLORS["ink"],
        "text.color":COLORS["ink"], "axes.edgecolor":"#b8c4cc",
        "xtick.color":COLORS["ink"],"ytick.color":COLORS["ink"],
        "figure.facecolor":"white","axes.facecolor":"white",
        "grid.color":"#dce4e9","grid.alpha":0.7,
    })


def finish_axis(ax):
    ax.spines[["top","right"]].set_visible(False)
    ax.grid(axis="y")
    ax.set_axisbelow(True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = args.root
    folder = args.output or root / "visualization_v1" / "figures"
    folder.mkdir(parents=True,exist_ok=True)
    style()
    con = duckdb.connect()
    view = root / "visualization_v1"

    daily = con.execute(f"SELECT * FROM read_parquet('{(view / 'object_day.parquet').as_posix()}')").df()
    daily["activity_date"] = pd.to_datetime(daily["activity_date"])
    by_day = daily.groupby("activity_date",as_index=True)[[
        "review_groups","draft_count","smoke_situations","gas_situations",
        "observed_situations"]].sum()
    monthly = by_day.resample("MS").sum()
    fig,axes=plt.subplots(2,1,figsize=(13,7),layout="constrained")
    queue_monthly=monthly.loc[monthly.index>=pd.Timestamp("2024-07-01")]
    axes[0].plot(queue_monthly.index,queue_monthly["review_groups"],color=COLORS["blue"],lw=2.3,
                 label="Группы черновиков")
    axes[0].plot(queue_monthly.index,queue_monthly["draft_count"],color=COLORS["amber"],lw=1.6,
                 label="Отдельные черновики")
    axes[0].set_title("Очередь черновиков – июль 2024 – июнь 2026",loc="left")
    axes[0].set_ylabel("За месяц")
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[0].xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    axes[0].legend(frameon=False,ncol=2)
    finish_axis(axes[0])
    axes[1].plot(monthly.index,monthly["observed_situations"],color=COLORS["ink"],lw=2,
                 label="Все наблюдаемые ситуации")
    axes[1].plot(monthly.index,monthly["smoke_situations"],color=COLORS["red"],lw=1.4,
                 label="Сигналы дыма")
    axes[1].plot(monthly.index,monthly["gas_situations"],color=COLORS["teal"],lw=1.4,
                 label="Газовые карточки")
    axes[1].set_title("Наблюдаемые ситуации – вся доступная история",loc="left")
    axes[1].set_ylabel("За месяц")
    axes[1].legend(frameon=False,ncol=3)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[1].xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    finish_axis(axes[1])
    fig.text(.02,-.01,"Пожары здесь не подсчитаны. Наблюдаемые сигналы не равны физическим авариям.",
             fontsize=9,color=COLORS["muted"])
    save(fig,folder,"01_overview")

    coverage = con.execute(f"SELECT snapshot_date,observation_state,count(*) n FROM read_parquet("
                           f"'{(root / 'its_evidence_v1' / 'channel_history.parquet').as_posix()}') "
                           "GROUP BY 1,2 ORDER BY 1,2").df()
    coverage["snapshot_date"] = pd.to_datetime(coverage["snapshot_date"])
    pivot = coverage.pivot(index="snapshot_date",columns="observation_state",values="n").fillna(0)
    order = ["recent_observation","ambiguous_simultaneous_statuses",
             "conflicting_recent_status_flag","no_recent_observation",
             "new_or_never_observed","metadata_missing"]
    labels = ["Есть записи","Одновременные статусы","Конфликт одного статуса",
              "Нет записи за 72 ч","Новый без истории","Нет метаданных"]
    palette = [COLORS["teal"],COLORS["amber"],COLORS["red"],
               COLORS["muted"],"#b6c2cc",COLORS["ink"]]
    fig,ax=plt.subplots(figsize=(13,5),layout="constrained")
    values=[pivot.get(key,pd.Series(0,index=pivot.index)) for key in order]
    ax.stackplot(pivot.index,*values,labels=labels,colors=palette,alpha=.9)
    ax.set_title("Наблюдение каналов по месяцам",loc="left")
    ax.set_ylabel("Каналы")
    ax.legend(loc="upper center",bbox_to_anchor=(.5,-.12),ncol=3,frameon=False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    finish_axis(ax)
    fig.text(.02,-.06,"Свежесть и неоднозначность телеметрии не являются оценкой исправности оборудования.",
             fontsize=9,color=COLORS["muted"])
    save(fig,folder,"02_coverage")

    shift = con.execute(f"SELECT shift_start,sum(review_groups) n FROM read_parquet("
                        f"'{(view / 'shift_workload.parquet').as_posix()}') "
                        "GROUP BY 1 ORDER BY 1").df()
    full_slots = pd.date_range("2024-07-01", "2026-06-30 12:00:00",freq="12h")
    shift["shift_start"] = pd.to_datetime(shift["shift_start"])
    counts = shift.set_index("shift_start")["n"].reindex(full_slots,fill_value=0)
    frequency = counts.value_counts().sort_index()
    fig,ax=plt.subplots(figsize=(11,5),layout="constrained")
    ax.bar(frequency.index,frequency.values,width=.8,color=COLORS["blue"])
    ax.set_title("Нагрузка очереди – группы за 12-часовую смену",loc="left")
    ax.set_xlabel("Групп в смену")
    ax.set_ylabel("Смен")
    ax.set_xticks(frequency.index)
    finish_axis(ax)
    fig.text(.02,-.01,"Включены смены без черновиков. Группа может содержать несколько отдельных решений.",
             fontsize=9,color=COLORS["muted"])
    save(fig,folder,"03_shift_workload")

    selected = daily[(daily.object_id==5113)&(daily.activity_date.dt.year==2025)]
    weekly=selected.set_index("activity_date")[["review_groups","smoke_situations",
                                                   "gas_situations"]].resample("W-MON").sum()
    fig,ax=plt.subplots(figsize=(13,5),layout="constrained")
    ax.plot(weekly.index,weekly.smoke_situations,color=COLORS["red"],lw=1.8,
            label="Дымовые ситуации")
    ax.plot(weekly.index,weekly.gas_situations,color=COLORS["teal"],lw=1.8,
            label="Газовые ситуации")
    ax.plot(weekly.index,weekly.review_groups,color=COLORS["blue"],lw=1.8,
            label="Группы черновиков")
    ax.set_title("Объект 5113 – недельная картина 2025 года",loc="left")
    ax.set_ylabel("Ситуации или группы")
    ax.legend(frameon=False,ncol=3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    finish_axis(ax)
    fig.text(.02,-.01,"Дымовая ситуация не обозначает подтверждённый пожар; группы не являются оценкой срочности.",
             fontsize=9,color=COLORS["muted"])
    save(fig,folder,"04_object_5113")

    smoke_folder = view / "cases" / "smoke_5113_20251029"
    smoke = con.execute(f"SELECT * FROM read_parquet('{(smoke_folder / 'points.parquet').as_posix()}') "
                        "ORDER BY event_time").df()
    smoke["event_time"] = pd.to_datetime(smoke["event_time"])
    smoke_meta=json.loads((smoke_folder / "case_meta.json").read_text(encoding="utf-8"))
    signal=pd.Timestamp(smoke_meta["signal_time"])
    fig,axes=plt.subplots(2,1,figsize=(12,6),sharex=True,layout="constrained",
                          gridspec_kw={"height_ratios":[1,2]})
    statuses=smoke[smoke.value_kind=="status"]
    channel_ids=sorted(smoke.channel_id.unique())
    ymap={channel:i for i,channel in enumerate(channel_ids)}
    for _,row in statuses.iterrows():
        axes[0].scatter(row.event_time,ymap[row.channel_id],
                        color=COLORS["red"] if row.is_alarm else COLORS["muted"],s=55)
    axes[0].set_yticks(list(ymap.values()),[str(channel) for channel in channel_ids])
    axes[0].set_ylabel("Канал")
    axes[0].set_title("Дым и температура – объект 5113, ПК108, 29.10.2025",loc="left")
    numeric=smoke[(smoke.value_kind=="numeric") &
                  (smoke.sensor_type=="Датчик температуры")]
    axes[1].scatter(numeric.event_time,numeric.numeric_value,color=COLORS["amber"],s=54)
    for _,row in numeric.iterrows():
        if row.numeric_value>=90:
            axes[1].annotate(f"{row.numeric_value:g}",(row.event_time,row.numeric_value),
                             xytext=(4,5),textcoords="offset points",fontsize=8)
    axes[1].set_ylabel("Числовое значение температуры\nединица не подтверждена")
    for ax in axes:
        ax.axvline(signal,color=COLORS["red"],ls="--",lw=1)
        finish_axis(ax)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.text(.02,-.02,"Сигнал дыма показан пунктиром. Значения 999/928 требуют проверки; физический пожар не подтверждён.",
             fontsize=9,color=COLORS["muted"])
    save(fig,folder,"05_smoke_temperature_case")

    gas_folder=view / "cases" / "gas_5578_20250407"
    gas=con.execute(f"SELECT * FROM read_parquet('{(gas_folder / 'points.parquet').as_posix()}') "
                    "ORDER BY event_time").df()
    gas["event_time"] = pd.to_datetime(gas["event_time"])
    gas_meta=json.loads((gas_folder / "case_meta.json").read_text(encoding="utf-8"))
    fig,axes=plt.subplots(2,1,figsize=(12,6),sharex=True,layout="constrained",
                          gridspec_kw={"height_ratios":[3,1]})
    numeric=gas[(gas.sensor_type=="Газовый датчик")&(gas.value_kind=="numeric")]
    for channel,part in numeric.groupby("channel_id"):
        axes[0].scatter(part.event_time,part.numeric_value,s=13,alpha=.65,label=str(channel))
    axes[0].axhline(1.0,color=COLORS["red"],ls="--",lw=1.6,
                    label="Заявленный порог прибора 1 об.%")
    axes[0].set_ylabel("Метан, об.%")
    axes[0].set_title("Газовая ситуация – объект 5578, 07.04.2025",loc="left")
    axes[0].legend(frameon=False,ncol=4,fontsize=8)
    status=gas[(gas.sensor_type=="Газовый датчик")&(gas.value_kind=="status")]
    for i,(channel,part) in enumerate(status.groupby("channel_id")):
        axes[1].scatter(part.event_time,[i]*len(part),s=45,
                        c=[COLORS["red"] if value else COLORS["muted"]
                           for value in part.is_alarm])
    axes[1].set_ylabel("Статусы")
    axes[1].set_yticks([])
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    for ax in axes:
        ax.axvline(pd.Timestamp(gas_meta["signal_time"]),color=COLORS["ink"],ls=":")
        finish_axis(ax)
    fig.text(.02,-.02,"Число выше 1 об.% не доказывает утечку. Плановая проверка возможна, график ППР не получен.",
             fontsize=9,color=COLORS["muted"])
    save(fig,folder,"06_gas_case")

    fire=json.loads((view / "fire_history_view.json").read_text(encoding="utf-8"))
    years=[row["yr"] for row in fire["smoke_signal_statistics"]]
    signals=[row["signal_records"] for row in fire["smoke_signal_statistics"]]
    fig,axes=plt.subplots(1,2,figsize=(13,4.8),layout="constrained",
                          gridspec_kw={"width_ratios":[1,2]})
    axes[0].axis("off")
    axes[0].text(0,.8,"История пожаров",fontsize=16,weight="bold",color=COLORS["ink"])
    axes[0].text(0,.55,"Реестр подтверждённых\nпожаров не предоставлен",fontsize=13,
                 color=COLORS["red"])
    axes[0].text(0,.25,"Число реальных пожаров неизвестно.\n"
                 "1 совпадение дыма и температуры\nоставлено для ручной проверки.",fontsize=10,
                 color=COLORS["ink"])
    axes[1].bar(years,signals,color=COLORS["blue"])
    axes[1].set_title("Отдельно – сообщения «Обнаружен дым»",loc="left")
    axes[1].set_ylabel("Исходные сообщения")
    finish_axis(axes[1])
    fig.text(.51,-.02,"2026 год показан только по 30 июня. Число сообщений зависит от охвата телеметрии.",
             fontsize=9,color=COLORS["muted"])
    save(fig,folder,"07_fire_history_smoke")

    quality=con.execute(f"SELECT * FROM read_parquet("
                        f"'{(view / 'forecast_quality_daily.parquet').as_posix()}')").df()
    quality["activity_date"] = pd.to_datetime(quality["activity_date"])
    quality["month"] = quality.activity_date.dt.to_period("M").dt.to_timestamp()
    quality=quality.groupby(["month","model_version"],as_index=False)[[
        "evaluable_drafts","matched_scada_drafts"]].sum()
    fig,axes=plt.subplots(2,1,figsize=(13,6),sharex=True,layout="constrained")
    for ax,(model,part) in zip(axes,quality.groupby("model_version")):
        ax.bar(part.month,part.evaluable_drafts,width=20,color=COLORS["pale"],
               label="Доступны для оценки")
        ax.bar(part.month,part.matched_scada_drafts,width=20,color=COLORS["blue"],
               label="Совпали с будущей записью SCADA")
        ax.set_title(model,loc="left",fontsize=11)
        ax.set_ylabel("Черновики")
        finish_axis(ax)
    axes[0].legend(frameon=False,ncol=2)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[1].xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    fig.text(.02,-.02,"Совпадение с SCADA не подтверждает физическую аварию. Периоды уже изучались и не являются независимым тестом.",
             fontsize=9,color=COLORS["muted"])
    save(fig,folder,"08_forecast_quality")

    print(json.dumps({"figures":8,"output":str(folder)},ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
