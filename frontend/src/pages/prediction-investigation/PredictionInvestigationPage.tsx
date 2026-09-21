import { useParams } from 'react-router-dom';
import { PageShell } from '../../components/feedback/PageShell';
export default function PredictionInvestigationPage() {
  const { predictionId } = useParams();
  return (
    <PageShell
      title={`Прогноз ${predictionId ?? ''}`}
      description="Исследование прогноза"
      section="Детали прогноза"
      message="Материалы для исследования появятся здесь."
    />
  );
}
