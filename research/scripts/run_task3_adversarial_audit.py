import os
import time
import json
import pickle
import duckdb
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.metrics import precision_score, recall_score, roc_auc_score, f1_score

start_time = time.time()

print("=" * 60)
print("ЗАДАЧА 3: ПЕССИМИСТИЧЕСКИЙ АУДИТ, СТРЕСС-ТЕСТИРОВАНИЕ И АНАЛИЗ УТЕЧЕК")
print("=" * 60)

reports_dir = "g:/lct2/ml_research/reports"
models_dir = "g:/lct2/ml_research/models"
data_dir = "g:/lct2/ml_research/data"

con = duckdb.connect()

# 1. Загрузка обученной модели и датасета
model_pkl_path = os.path.join(models_dir, "sensor_failure_lgbm.pkl")
features_path = os.path.join(data_dir, "ml_feature_matrix.parquet")

print(f"Загрузка модели из {model_pkl_path}...")
with open(model_pkl_path, "rb") as f:
    saved_bundle = pickle.load(f)

model = saved_bundle["model"]
encoder = saved_bundle["encoder"]
feature_cols = saved_bundle["features"]
threshold = saved_bundle["threshold"]

print(f"Загрузка обучающей матрицы из {features_path}...")
df_ml = con.execute(f"SELECT * FROM read_parquet('{features_path}')").df()

# -------------------------------------------------------------
# ТЕСТ 1: АНАЛИЗ ВАЖНОСТИ ПРИЗНАКОВ (FEATURE IMPORTANCE / GAIN)
# -------------------------------------------------------------
print("\n" + "-" * 50)
print("ТЕСТ 1: АНАЛИЗ ВАЖНОСТИ ПРИЗНАКОВ И КОРРЕЛЯЦИЙ С ТАРГЕТОМ")
print("-" * 50)

gains = model.booster_.feature_importance(importance_type='gain')
total_gain = sum(gains) if sum(gains) > 0 else 1.0
gain_pct = {col: round(float(g) / total_gain * 100.0, 2) for col, g in zip(feature_cols, gains)}
gain_sorted = sorted(gain_pct.items(), key=lambda x: x[1], reverse=True)

print("Топ признаков по Gain:")
for feat, pct in gain_sorted:
    print(f"  {feat:20s}: {pct:6.2f}%")

# Корреляция с таргетом
corrs = {}
for col in feature_cols:
    if col in df_ml.columns and np.issubdtype(df_ml[col].dtype, np.number):
        corrs[col] = round(float(df_ml[col].corr(df_ml['target_failure_24_72h'])), 4)
corrs_sorted = sorted(corrs.items(), key=lambda x: abs(x[1]), reverse=True)

print("\nТоп корреляций с целевой переменной target_failure_24_72h:")
for feat, c in corrs_sorted[:7]:
    print(f"  {feat:20s}: corr = {c:+.4f}")

# Проверка подозрительных признаков утечки
suspect_features = ['failure_events', 'failure_rate_pct', 'mtbf_hours']
suspect_gain_sum = sum(gain_pct.get(f, 0) for f in suspect_features)
print(f"\nСуммарная доля подозрительных признаков в модели: {suspect_gain_sum:.1f}%")

# -------------------------------------------------------------
# ТЕСТ 2: ABLATION STUDY (ТЕСТИРОВАНИЕ БЕЗ ПОДОЗРИТЕЛЬНЫХ ПРИЗНАКОВ)
# -------------------------------------------------------------
print("\n" + "-" * 50)
print("ТЕСТ 2: ABLATION STUDY (УДАЛЕНИЕ ПОЖИЗНЕННЫХ СТАТИСТИК ОТКАЗОВ)")
print("-" * 50)

clean_features = [f for f in feature_cols if f not in suspect_features]
print(f"Очищенный набор признаков ({len(clean_features)}): {clean_features}")

# Обучаем модель строго БЕЗ пожизненных статистик
cat_clean = [f for f in ['subsystem_type', 'sensor_type', 'tag_root'] if f in clean_features]
X_clean = df_ml[clean_features].copy()
X_clean[cat_clean] = encoder.transform(df_ml[cat_clean].astype(str))
y = df_ml['target_failure_24_72h'].to_numpy()

X_tr, X_te, y_tr, y_te = train_test_split(X_clean, y, test_size=0.25, random_state=42, stratify=y)

clean_lgb = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, max_depth=6, random_state=42, n_jobs=-1)
clean_lgb.fit(X_tr, y_tr)

clean_probs = clean_lgb.predict_proba(X_te)[:, 1]
clean_auc = roc_auc_score(y_te, clean_probs)
clean_p = precision_score(y_te, (clean_probs >= 0.5).astype(int), zero_division=0)
clean_r = recall_score(y_te, (clean_probs >= 0.5).astype(int), zero_division=0)

print(f"Качество модели БЕЗ пожизненных агрегатов (Честный бейзлайн):")
print(f"  ROC-AUC:   {clean_auc:.4f} (было 0.9990, падение: {0.9990 - clean_auc:.4f})")
print(f"  Precision: {clean_p:.4f} (при пороге 0.50)")
print(f"  Recall:    {clean_r:.4f}")

# -------------------------------------------------------------
# ТЕСТ 3: ТЕСТИРОВАНИЕ НА ПРИНЦИПИАЛЬНО НЕИЗВЕСТНЫХ ДАТЧИКАХ (OUT-OF-SENSOR)
# -------------------------------------------------------------
print("\n" + "-" * 50)
print("ТЕСТ 3: OUT-OF-SENSOR GENERALIZATION (GROUP K-FOLD ПО КАНАЛАМ)")
print("-" * 50)

gkf = GroupKFold(n_splits=5)
group_aucs = []
group_precisions = []
group_recalls = []

groups = df_ml['channel_id'].values

for fold, (train_idx, test_idx) in enumerate(gkf.split(X_clean, y, groups=groups)):
    X_tr_g, y_tr_g = X_clean.iloc[train_idx], y[train_idx]
    X_te_g, y_te_g = X_clean.iloc[test_idx], y[test_idx]
    
    m_g = lgb.LGBMClassifier(n_estimators=150, learning_rate=0.05, max_depth=5, random_state=42, n_jobs=-1)
    m_g.fit(X_tr_g, y_tr_g)
    
    probs_g = m_g.predict_proba(X_te_g)[:, 1]
    auc_g = roc_auc_score(y_te_g, probs_g)
    group_aucs.append(auc_g)
    group_precisions.append(precision_score(y_te_g, (probs_g >= 0.5).astype(int), zero_division=0))
    group_recalls.append(recall_score(y_te_g, (probs_g >= 0.5).astype(int), zero_division=0))

mean_g_auc = np.mean(group_aucs)
mean_g_p = np.mean(group_precisions)
mean_g_r = np.mean(group_recalls)

print(f"Результаты на абсолютно НОВЫХ каналах (5-fold GroupKFold):")
print(f"  Средний ROC-AUC:   {mean_g_auc:.4f} (разброс: [{min(group_aucs):.4f}, {max(group_aucs):.4f}])")
print(f"  Средний Precision: {mean_g_p:.4f}")
print(f"  Средний Recall:    {mean_g_r:.4f}")

# -------------------------------------------------------------
# ТЕСТ 4: СТРЕСС-ТЕСТИРОВАНИЕ МОДЕЛЕЙ 2, 3, 4 НА СЕНСОРНЫЙ ШУМ
# -------------------------------------------------------------
print("\n" + "-" * 50)
print("ТЕСТ 4: УСТОЙЧИВОСТЬ МОДЕЛЕЙ 2-4 К СЕНСОРНОМУ ШУМУ")
print("-" * 50)

noise_levels = [0.0, 0.10, 0.25, 0.50]
noise_results = {}

# Загружаем модель пожарного риска
with open(os.path.join(models_dir, "fire_thermal_risk.pkl"), "rb") as f:
    fire_bundle = pickle.load(f)
fire_model = fire_bundle["model"]
fire_feats = fire_bundle["features"]

# Генерируем тестовый срез
np.random.seed(42)
n_test = 2000
test_fire_df = pd.DataFrame({
    'local_temp': np.random.normal(9.0, 3.5, size=n_test),
    'temp_gradient_picket': np.random.exponential(1.8, size=n_test),
    'picket_km': np.random.uniform(0, 90, size=n_test),
    'smoke_sensor_rate': np.random.beta(0.5, 5, size=n_test),
    'ventilation_active': np.random.choice([0, 1], size=n_test, p=[0.15, 0.85]),
    'is_heating_season': np.random.choice([0, 1], size=n_test, p=[0.4, 0.6]),
    'hour_of_day': np.random.randint(0, 24, size=n_test)
})
y_fire_true = ((test_fire_df['local_temp'] > 19.0).astype(int) * 3 +
               (test_fire_df['temp_gradient_picket'] > 4.0).astype(int) * 2 +
               (test_fire_df['smoke_sensor_rate'] > 0.25).astype(int) * 3 >= 3).astype(int)

fire_noise_scores = {}
for nl in noise_levels:
    noisy_df = test_fire_df.copy()
    if nl > 0:
        noisy_df['local_temp'] += np.random.normal(0, 5.0 * nl, size=n_test)
        noisy_df['temp_gradient_picket'] += np.random.normal(0, 2.0 * nl, size=n_test)
    
    probs = fire_model.predict_proba(noisy_df[fire_feats])[:, 1]
    auc_val = roc_auc_score(y_fire_true, probs)
    p_val = precision_score(y_fire_true, (probs >= 0.35).astype(int), zero_division=0)
    fire_noise_scores[f"noise_{int(nl*100)}pct"] = {"roc_auc": round(auc_val, 4), "precision": round(p_val, 4)}
    print(f"  Уровень шума {int(nl*100)}%: ROC-AUC = {auc_val:.4f}, Precision = {p_val:.4f}")

# -------------------------------------------------------------
# СОХРАНЕНИЕ РЕЗУЛЬТАТОВ АУДИТА
# -------------------------------------------------------------
audit_report = {
    "audit_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "target_leakage_detected": True,
    "leakage_root_cause": (
        "Таблица sensor_reliability_8yr содержала пожизненные агрегаты отказов (failure_events, failure_rate_pct, mtbf_hours), "
        "рассчитанные на всем 8-летнем периоде (2019-2026). Модель использовала знание будущих отказов датчиков "
        "для предсказания в любой точке прошлого, что дало искусственно завышенные метрики (ROC-AUC 0.9990)."
    ),
    "feature_gain_breakdown": gain_sorted,
    "suspect_features_gain_pct": round(suspect_gain_sum, 2),
    "honest_baseline_without_leaks": {
        "roc_auc": round(clean_auc, 4),
        "precision": round(clean_p, 4),
        "recall": round(clean_r, 4)
    },
    "out_of_sensor_generalization": {
        "mean_roc_auc": round(mean_g_auc, 4),
        "mean_precision": round(mean_g_p, 4),
        "mean_recall": round(mean_g_r, 4)
    },
    "noise_stress_test_fire_model": fire_noise_scores,
    "next_task_action": (
        "Задача 4 (Очевидное следствие): Сформировать честный Point-in-Time Feature Store, "
        "где скользящие признаки (тревоги за 1ч/6ч/24ч, частота дребезга delta_t < 30с, смены статусов) "
        "рассчитываются строго ДО точки наблюдения t_obs. Исключить глобальные пожизненные агрегаты из будущего. "
        "Переобучить и откалибровать модели для честного выполнения норматива ТЗ (Precision > 0.70, Recall > 0.50)."
    )
}

audit_json_path = os.path.join(reports_dir, "task3_leakage_audit_report.json")
with open(audit_json_path, "w", encoding="utf-8") as f:
    json.dump(audit_report, f, ensure_ascii=False, indent=2)

summary_md_path = os.path.join(reports_dir, "task3_leakage_audit_summary.md")
with open(summary_md_path, "w", encoding="utf-8") as f:
    f.write(f"""# Результаты жесткого пессимистического аудита моделей (Задача 3)

Дата: {time.strftime('%Y-%m-%d %H:%M:%S')}  
Команда: Dolos | Аудитор: Слава (ML Lead)

## 1. Главный вывод: обнаружена критическая утечка данных (Data Leakage)
Метрика ROC-AUC 0,9990 в Задаче 2 оказалась следствием **Target Leakage через пожизненные статистики надежности**:
- Признаки `failure_events`, `failure_rate_pct` и `mtbf_hours` в таблице `sensor_reliability_8yr` были рассчитаны на полном интервале 2019–2026 годов.
- На эти три признака приходилось **{suspect_gain_sum:.1f}%** всей предсказательной силы модели!
- Модель фактически определяла: «Ломался ли данный канал когда-либо за 8 лет? Если да – прогнозируем отказ».

## 2. Честные метрики модели без протекших признаков (Ablation Study)
При удалении пожизненных статистик и сохранении только метаданных датчика и временных признаков:
- Честный ROC-AUC: **{clean_auc:.4f}** (падение на {0.9990 - clean_auc:.4f})
- Честный Precision: **{clean_p:.4f}**
- Честный Recall: **{clean_r:.4f}**

## 3. Проверка на принципиально новых датчиках (Out-of-Sensor GroupKFold)
При кросс-валидации по 5 непересекающимся группам каналов:
- Средний ROC-AUC на новых датчиках: **{mean_g_auc:.4f}**
- Средний Precision: **{mean_g_p:.4f}**
- Модель сохраняет базовое пространственное разделение, но без динамических скользящих признаков телеметрии (flapping, rolling alarms) качество недостаточно стабильно.

## 4. Очевидная следующая задача (Задача 4)
Нам необходимо:
1. Построить Point-in-Time Feature Store: считать скользящие признаки (число тревог за 1ч/6ч/24ч, частота дребезга delta_t < 30с, скачки градиентов) строго на отрезке [t_obs - 24ч, t_obs] без малейшего заглядывания в будущее.
2. Исключить любые глобальные признаки, выходящие за пределы обучающего окна.
3. Обучить чистую, устойчивую к жюри модель и откалибровать порог для честного преодоления планки ТЗ (Precision >= 0.70, Recall >= 0.50).
""")

print("\n" + "=" * 60)
print("ЗАДАЧА 3 ВЫПОЛНЕНА! РЕЗУЛЬТАТЫ АУДИТА ЗАФИКСИРОВАНЫ.")
print(f"Отчет записан в: {summary_md_path}")
print(f"Время работы аудита: {round(time.time() - start_time, 1)} секунд")
print("=" * 60)
