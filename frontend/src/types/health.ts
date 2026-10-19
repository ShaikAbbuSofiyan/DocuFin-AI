export interface ComponentHealth {
  status: 'connected' | 'degraded' | 'error' | string;
  latency_ms?: number;
  details?: string | null;
}

export interface LivenessData {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
}

export interface ReadinessData {
  status: 'ready' | 'not_ready' | string;
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
  components: {
    database?: ComponentHealth;
    redis?: ComponentHealth;
    [key: string]: ComponentHealth | undefined;
  };
}
