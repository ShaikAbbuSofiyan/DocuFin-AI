import { useQuery } from '@tanstack/react-query';
import { apiClient } from './api';
import { LivenessData, ReadinessData } from '../types/health';

export const HEALTH_KEYS = {
  live: ['health', 'live'] as const,
  ready: ['health', 'ready'] as const,
};

export function useLiveHealth(refetchInterval: number | false = 10000) {
  return useQuery<LivenessData, Error>({
    queryKey: HEALTH_KEYS.live,
    queryFn: apiClient.getLiveHealth,
    refetchInterval,
    retry: 1,
  });
}

export function useReadyHealth(refetchInterval: number | false = 10000) {
  return useQuery<ReadinessData, Error>({
    queryKey: HEALTH_KEYS.ready,
    queryFn: apiClient.getReadyHealth,
    refetchInterval,
    retry: 1,
  });
}
