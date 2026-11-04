import { researchApi } from '@/adapters/research-api-adapter';
import type { OptimizationRequest, OptimizationResultPayload } from '@/adapters/research-api-adapter';
import { useResearchRuns } from '@/hooks/use-research-runs';

export function useOptimizationResearch() {
  const { runs, ...rest } = useResearchRuns<OptimizationRequest, OptimizationResultPayload>(
    'optimization', '優化', researchApi.submitOptimization);
  return { ...rest, optRuns: runs };
}
