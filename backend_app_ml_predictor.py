import os
import json
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# =========================================================================
# 1. PYDANTIC СХЕМЫ ДЛЯ API (КОНТРАКТ ДАННЫХ)
# =========================================================================

class SensorRiskOutput(BaseModel):
    channel_id: int
    sensor_type: str
    failure_probability: float = Field(..., description="Вероятность отказа (0.0 - 1.0)")
    risk_level: str = Field(..., description="Уровень риска: low, medium, high, critical")
    maintenance_urgency: str = Field(..., description="Срочность: FLASH_1_6H, URGENT_6_24H, PLANNED_24_48H, NORMAL")
    lead_time_hours: float = Field(..., description="Расчетный горизонт упреждения (часы)")
    health_index_its: int = Field(..., description="Индекс технического состояния ИТС (0 - 100 баллов)")
    top_risk_factors: List[str] = Field(default_factory=list, description="Топ-3 физические причины риска")
    recommendation: str = Field(..., description="Текстовая рекомендация для наряда на ремонт")


# =========================================================================
# 2. ПРОИЗВОДСТВЕННЫЙ КЛАСС ИНФЕРЕНСА
# =========================================================================

class SensorFailurePredictor:
    """
    Высокопроизводительный предиктивный движок v7.2 (5 доменных голов).
    Время инференса: < 2 мс на канал.
    """
    
    def __init__(self, models_dir: Optional[str] = None):
        if models_dir is None:
            # Дефолтный путь относительно backend
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            models_dir = os.path.join(base_dir, "production_ml", "models")
            
        self.models_dir = models_dir
        self.manifest_path = os.path.join(models_dir, "models_meta.json")
        self.models: Dict[str, Any] = {}
        self.meta: Dict[str, Any] = {}
        self.sensor_to_domain: Dict[str, str] = {}
        
        self._load_models()

    def _load_models(self):
        if not os.path.exists(self.manifest_path):
            raise FileNotFoundError(f"Манифест метаданных не найден: {self.manifest_path}")
            
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.meta = json.load(f)
            
        heads = self.meta.get("heads", {})
        for domain_name, head_info in heads.items():
            model_file = os.path.join(self.models_dir, head_info["model_file"])
            if os.path.exists(model_file):
                with open(model_file, "rb") as mf:
                    self.models[domain_name] = pickle.load(mf)
                    
            for s_type in head_info.get("sensors", []):
                self.sensor_to_domain[s_type] = domain_name
                
        print(f"[SensorFailurePredictor] Успешно загружено {len(self.models)} доменных голов из {self.models_dir}")

    def _compute_interactions(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Генерация интерактивных физических признаков на лету."""
        f = features.copy()
        
        # 1. Фазы: Асимметрия x Искрение sub2s
        asym = float(f.get("state_transition_asymmetry_24h", 0.0))
        sub2s = float(f.get("micro_burst_sub2s_ratio", 0.0))
        f["inter_phase_arc_asym"] = asym * sub2s
        
        # 2. Насосы: Скважность x Ночной перегруз
        duty = float(f.get("duty_cycle_24h", 0.0))
        night_ex = float(f.get("night_excess", 0.0))
        f["inter_pump_night_duty"] = duty * np.log1p(max(0.0, night_ex))
        
        # 3. Температура: Шум x Зависание АЦП
        t_std = float(f.get("analog_std_24h", 0.0))
        freeze = float(f.get("adc_bit_freezing_hours", 0.0))
        f["inter_temp_std_freeze"] = t_std * np.log1p(freeze)
        
        # 4. Газ: Сползание нуля x Ступенчатость
        creep = abs(float(f.get("baseline_creep_7d", 0.0)))
        quant = float(f.get("quantization_step_anomaly", 0.0))
        f["inter_gas_creep_quant"] = creep * quant
        
        # 5. Пожарка: Тревоги x Триграммы отскока
        alarm_r = float(f.get("alarm_ratio_24h", 0.0))
        bounce = float(f.get("rapid_bounce_triplet_count", 0.0))
        f["inter_fire_alarm_bounce"] = alarm_r * np.log1p(bounce)
        
        # 6. Спектральная турбулентность: Jitter x Энтропия
        jitter = float(f.get("period_jitter_cv", 0.0))
        spec_ent = float(f.get("spectral_entropy_ls", 0.0))
        f["inter_jitter_spec_entropy"] = jitter * spec_ent
        
        return f

    def predict_channel(self, channel_id: int, sensor_type: str, raw_features: Dict[str, Any]) -> SensorRiskOutput:
        """Инференс по одному каналу телемеханики."""
        domain = self.sensor_to_domain.get(sensor_type)
        
        # Если тип датчика неизвестен — дефолтный безопасный ответ
        if domain is None or domain not in self.models:
            return SensorRiskOutput(
                channel_id=channel_id,
                sensor_type=sensor_type,
                failure_probability=0.01,
                risk_level="low",
                maintenance_urgency="NORMAL",
                lead_time_hours=72.0,
                health_index_its=99,
                top_risk_factors=["Датчик вне зоны активного предиктивного мониторинга"],
                recommendation="Штатный мониторинг."
            )
            
        head_info = self.meta["heads"][domain]
        req_features = head_info["features"]
        thresholds = head_info.get("operational_thresholds", {"flash_1_6h": 0.70, "urgent_6_24h": 0.50, "planned_24_48h": 0.30})
        
        # Обогащаем фичи интеракциями
        enriched_feats = self._compute_interactions(raw_features)
        
        # Формируем вектор в строгом порядке модели
        x_vec = np.array([[float(enriched_feats.get(k, 0.0)) for k in req_features]], dtype=np.float32)
        
        # Расчет вероятности
        prob = float(self.models[domain].predict_proba(x_vec)[0, 1])
        
        # Расчет ИТС (0 - 100 баллов)
        its_score = max(0, min(100, int(round(100.0 * (1.0 - prob)))))
        
        # Определение горизонта и срочности
        th_flash = thresholds.get("flash_1_6h", 0.70)
        th_urg   = thresholds.get("urgent_6_24h", 0.50)
        th_plan  = thresholds.get("planned_24_48h", 0.30)
        
        if prob >= th_flash:
            risk_lvl = "critical"
            urgency = "FLASH_1_6H"
            lead_time = 4.0
        elif prob >= th_urg:
            risk_lvl = "high"
            urgency = "URGENT_6_24H"
            lead_time = 12.0
        elif prob >= th_plan:
            risk_lvl = "medium"
            urgency = "PLANNED_24_48H"
            lead_time = 24.0
        else:
            risk_lvl = "low"
            urgency = "NORMAL"
            lead_time = 72.0
            
        # Формирование объяснения дефекта (Root Cause Analysis)
        factors = []
        rec = "Штатный режим работы оборудования."
        
        if domain == "POWER_PHASE":
            if enriched_feats.get("undefined_ratio_24h", 0) > 0.05:
                factors.append(f"Выход сопротивления шлейфа за допуски (Неопределен: {enriched_feats['undefined_ratio_24h']*100:.1f}%)")
            if enriched_feats.get("state_transition_asymmetry_24h", 0) > 0.20:
                factors.append("Нарушение симметрии питания (односторонние потери пакетов)")
            if enriched_feats.get("micro_burst_sub2s_ratio", 0) > 0.25:
                factors.append("Электрическое искрение контактов (Delta_t <= 2c)")
            rec = "Внеплановая ревизия контактора и протяжка клеммных соединений питания." if prob >= th_plan else rec

        elif domain == "ANALOG_TEMP":
            if enriched_feats.get("adc_bit_freezing_hours", 0) >= 12:
                factors.append(f"Зависание младшего бита АЦП ({enriched_feats['adc_bit_freezing_hours']}ч константы)")
            if enriched_feats.get("analog_std_24h", 0) > 2.0:
                factors.append(f"Высокий шум термопары (СКО = {enriched_feats['analog_std_24h']:.2f}°C)")
            rec = "Калибровка измерительного тракта или замена термопары." if prob >= th_plan else rec

        elif domain == "HYDRO_MECHANICS":
            if enriched_feats.get("night_excess", 0) > 15:
                factors.append("Аномальный ночной цикл откачки при отсутствии водопритока")
            if enriched_feats.get("duty_cycle_24h", 0) > 0.40:
                factors.append(f"Высокая скважность работы (насос включен {enriched_feats['duty_cycle_24h']*100:.1f}% суток)")
            rec = "Проверка поплавкового датчика уровня и очистка зумпфа насоса." if prob >= th_plan else rec

        if not factors and prob >= th_plan:
            factors.append("Комплексное накопление спектрального шума и джиттера")

        return SensorRiskOutput(
            channel_id=channel_id,
            sensor_type=sensor_type,
            failure_probability=round(prob, 4),
            risk_level=risk_lvl,
            maintenance_urgency=urgency,
            lead_time_hours=lead_time,
            health_index_its=its_score,
            top_risk_factors=factors[:3],
            recommendation=rec
        )